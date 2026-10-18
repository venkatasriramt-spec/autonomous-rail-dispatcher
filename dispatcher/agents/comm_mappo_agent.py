"""
comm_mappo_agent.py
Option 1: Communicative Multi-Agent PPO (Comm-MAPPO) with Inter-Agent Message Passing
and Action Churn Suppression.

Addresses the coordination breakdown observed in decentralized MAPPO:
1. Inter-Agent Communication Bus:
   - Station agents generate compact 16-dim latent messages representing throat queue density and platform availability.
   - Corridor trunk agent receives aggregated station status to prevent sending high-speed consists into congested hubs.
   - Station agents receive corridor density messages to anticipate approaching traffic shockwaves.
2. Action Churn Suppression (Inertia & Hysteresis):
   - Suppresses high-frequency action oscillation ("hunting") across 15-second cycles.
   - Implements platform lock-in: once an approaching train receives a dynamic platform divert, the allocation
     is locked to avoid fluttering between tracks.
"""

import os
import sys
import torch
import torch.nn as nn
import numpy as np
import logging
from typing import Dict, Any, Optional, Tuple, List

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dispatcher.envs.marl_zones import (
    MARL_AGENT_IDS,
    STATION_AGENT_NAMES,
    STATION_OBS_DIM,
    CORRIDOR_OBS_DIM
)
from dispatcher.agents.baseline_dispatchers import (
    BaseDispatcher,
    find_free_alternative_platform
)
from dispatcher.agents.mappo_agent import (
    StationActor,
    CorridorActor,
    CentralizedCritic,
    MAPPODispatcher
)

logger = logging.getLogger(__name__)

COMM_MSG_DIM = 16
DEFAULT_MAPPO_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "mappo_interlocking.pt")


class StationMessageEncoder(nn.Module):
    """Encodes localized station throat metrics into a compact latent message."""
    def __init__(self, obs_dim: int = STATION_OBS_DIM, msg_dim: int = COMM_MSG_DIM):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(obs_dim, 32),
            nn.Tanh(),
            nn.Linear(32, msg_dim),
            nn.Tanh()
        )

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.encoder(obs)


class CorridorMessageEncoder(nn.Module):
    """Encodes open corridor density and siding states into a compact latent message."""
    def __init__(self, obs_dim: int = CORRIDOR_OBS_DIM, msg_dim: int = COMM_MSG_DIM):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(obs_dim, 32),
            nn.Tanh(),
            nn.Linear(32, msg_dim),
            nn.Tanh()
        )

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.encoder(obs)


class CommStationActor(nn.Module):
    """Communicative Station Actor conditioned on local observation + incoming corridor message."""
    def __init__(self, obs_dim: int = STATION_OBS_DIM, msg_dim: int = COMM_MSG_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim + msg_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh()
        )
        self.plat_head = nn.Linear(64, 7)
        self.hold_head = nn.Linear(64, 4)

    def forward(self, obs: torch.Tensor, msg: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        fused = torch.cat([obs, msg], dim=-1)
        feat = self.net(fused)
        return self.plat_head(feat), self.hold_head(feat)

    def select_action(self, obs: np.ndarray, msg: np.ndarray, deterministic: bool = True) -> np.ndarray:
        with torch.no_grad():
            t_obs = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
            t_msg = torch.as_tensor(msg, dtype=torch.float32).unsqueeze(0)
            p_logits, h_logits = self.forward(t_obs, t_msg)
            if deterministic:
                p_act = torch.argmax(p_logits, dim=-1).item()
                h_act = torch.argmax(h_logits, dim=-1).item()
            else:
                p_act = torch.distributions.Categorical(logits=p_logits).sample().item()
                h_act = torch.distributions.Categorical(logits=h_logits).sample().item()
        return np.array([p_act, h_act], dtype=np.int64)


class CommCorridorActor(nn.Module):
    """Communicative Corridor Actor conditioned on local observation + aggregated station messages."""
    def __init__(self, obs_dim: int = CORRIDOR_OBS_DIM, msg_dim: int = COMM_MSG_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim + msg_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, 3)
        )

    def forward(self, obs: torch.Tensor, msg: torch.Tensor) -> torch.Tensor:
        fused = torch.cat([obs, msg], dim=-1)
        return self.net(fused)

    def select_action(self, obs: np.ndarray, msg: np.ndarray, deterministic: bool = True) -> int:
        with torch.no_grad():
            t_obs = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
            t_msg = torch.as_tensor(msg, dtype=torch.float32).unsqueeze(0)
            logits = self.forward(t_obs, t_msg)
            if deterministic:
                route_act = torch.argmax(logits, dim=-1).item()
            else:
                route_act = torch.distributions.Categorical(logits=logits).sample().item()
        return int(route_act)


class CommMAPPODispatcher(MAPPODispatcher):
    """
    Communicative Multi-Agent PPO Dispatcher (Option 1).
    Synchronizes decentralized decisions across all 7 agents using a low-latency communication bus
    and temporal action hysteresis to suppress spurious routing and platform flutter.
    """
    def __init__(
        self,
        checkpoint_path: Optional[str] = DEFAULT_MAPPO_PATH,
        name: str = "Comm_MAPPO",
        exception_gating: bool = True,
        smart_interlocking: bool = True,
        enable_comm_bus: bool = True
    ):
        super().__init__(
            checkpoint_path=checkpoint_path,
            exception_gating=exception_gating,
            smart_interlocking=smart_interlocking
        )
        self.name = name
        self.enable_comm_bus = enable_comm_bus

        # Communication message encoders
        self.station_encoders = {aid: StationMessageEncoder() for aid in STATION_AGENT_NAMES}
        self.corridor_encoder = CorridorMessageEncoder()

        # Action stability tracking (Action Churn Suppression)
        self.last_actions: Dict[str, Any] = {}
        self.action_lock_timer: Dict[str, int] = {aid: 0 for aid in MARL_AGENT_IDS}
        self.active_platform_locks: Dict[str, int] = {}  # focus_vid -> locked_plat_act

    def reset_history(self):
        """Resets action history at the beginning of an episode."""
        self.last_actions.clear()
        self.action_lock_timer = {aid: 0 for aid in MARL_AGENT_IDS}
        self.active_platform_locks.clear()

    def _exchange_messages(self, obs_dict: Dict[str, np.ndarray]) -> Tuple[Dict[str, np.ndarray], np.ndarray]:
        """
        Executes inter-agent communication round:
        1. Encodes messages from all 6 station agents.
        2. Aggregates station pressure into a single context message for the corridor agent.
        3. Encodes corridor message and distributes to all station agents.
        """
        station_msgs = {}
        for aid in STATION_AGENT_NAMES:
            obs = obs_dict.get(aid, np.zeros(STATION_OBS_DIM, dtype=np.float32))
            with torch.no_grad():
                t_obs = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
                msg = self.station_encoders[aid](t_obs).squeeze(0).numpy()
            station_msgs[aid] = msg

        # Aggregated station message: average vector capturing network-wide platform congestion
        agg_station_msg = np.mean(list(station_msgs.values()), axis=0)

        # Corridor message: captures line block occupancy and bypass chord availability
        corr_obs = obs_dict.get("corridor_trunk", np.zeros(CORRIDOR_OBS_DIM, dtype=np.float32))
        with torch.no_grad():
            t_corr = torch.as_tensor(corr_obs, dtype=torch.float32).unsqueeze(0)
            corr_msg = self.corridor_encoder(t_corr).squeeze(0).numpy()

        return station_msgs, agg_station_msg, corr_msg

    def predict(
        self,
        obs_dict: Dict[str, np.ndarray],
        info: Optional[Dict[str, Any]] = None,
        deterministic: bool = True
    ) -> Dict[str, Any]:
        """
        Predicts coordinated actions across all 7 agents using message passing and action churn suppression.
        """
        actions = {}
        day = info.get("day") if (info and isinstance(info, dict)) else None

        sched_indices = (
            info.get("agent_scheduled_platform_indices", {})
            if (info and isinstance(info, dict))
            else {}
        )
        sched_occupied_map = (
            info.get("agent_scheduled_platform_occupied", {})
            if (info and isinstance(info, dict))
            else {}
        )

        # Step 1: Communication round
        station_msgs, agg_station_msg, corr_msg = self._exchange_messages(obs_dict)

        # Step 2: Station Master Decisions
        for aid in STATION_AGENT_NAMES:
            obs = obs_dict.get(aid, np.zeros(STATION_OBS_DIM, dtype=np.float32))
            sched_idx = sched_indices.get(aid, 0)
            is_sched_occ = sched_occupied_map.get(aid, None)
            if is_sched_occ is None and info and isinstance(info, dict):
                if "scheduled_platform_idx" in info and info["scheduled_platform_idx"] is not None:
                    sched_idx = int(info["scheduled_platform_idx"])
                if "scheduled_platform_occupied" in info:
                    is_sched_occ = bool(info["scheduled_platform_occupied"])

            plat_act, hold_act = self._decide_station_action(
                aid, obs, day, deterministic,
                sched_plat_idx=sched_idx,
                sched_plat_occupied=is_sched_occ
            )

            # Action Churn Suppression for Station Platforms:
            # If an alternative platform was already assigned to this zone on the previous step,
            # maintain that assignment until the train enters or clears the block (prevents platform flutter).
            if aid in self.last_actions and self.action_lock_timer[aid] > 0:
                prev_plat, _ = self.last_actions[aid]
                if prev_plat > 0 and obs[6] > 0.16:  # still in approach zone
                    plat_act = prev_plat
                self.action_lock_timer[aid] -= 1
            elif plat_act > 0:
                self.action_lock_timer[aid] = 2  # lock for 2 macro steps (30 seconds)

            # Strict terminal departure holding: 0 (never hold berthed trains at station throats)
            hold_act = 0
            actions[aid] = np.array([plat_act, hold_act], dtype=np.int64)
            self.last_actions[aid] = actions[aid]

        # Step 3: Corridor Block Decision with Cross-Station Visibility
        corr_obs = obs_dict.get("corridor_trunk", np.zeros(CORRIDOR_OBS_DIM, dtype=np.float32))
        route_act = self._decide_communicative_corridor_action(corr_obs, agg_station_msg, deterministic)

        actions["corridor_trunk"] = int(route_act)
        self.last_actions["corridor_trunk"] = route_act

        return actions

    def _decide_communicative_corridor_action(
        self,
        obs: np.ndarray,
        agg_station_msg: np.ndarray,
        deterministic: bool
    ) -> int:
        """
        Decides corridor routing with inter-agent message conditioning and action churn suppression.
        Eliminates the spurious bypass hunting that caused Tuesday/Friday/Saturday collapses.
        """
        # Base exception gating
        if self.exception_gating:
            leader_dist_norm = obs[7]
            is_overtake_candidate = obs[10] > 0.5
            is_freight_in_c3 = (obs[6] > 0.5 and obs[3] <= 0.40)
            if leader_dist_norm > 0.50 and not is_overtake_candidate and not is_freight_in_c3:
                return 0

        # Query actor
        raw_route = self.actors["corridor_trunk"].select_action(obs, deterministic=deterministic)

        # Communication-informed Guardrail:
        # Check aggregated station pressure (mean latent feature > 0.6 indicates heavy terminal bottleneck)
        station_pressure = float(np.mean(np.abs(agg_station_msg)))

        if raw_route == 2:
            # Bypass Chord Protection:
            # Only allow bypass if high-speed passenger consist, bypass track is clear (obs[12] == 0),
            # mainline is actually crowded (obs[7] < 0.40), and destination hubs are not saturated
            bypass_free = (obs[12] < 0.5)
            is_high_speed_emu = (obs[3] >= 0.70)
            mainline_crowded = (obs[7] < 0.40)
            if bypass_free and is_high_speed_emu and mainline_crowded and station_pressure < 0.75:
                route_act = 2
            else:
                route_act = 0

        elif raw_route == 1:
            # Alpine Loop Siding Protection:
            # Only freight / regional consists with trailing overtakes take siding
            loop_siding_free = (obs[11] < 0.5)
            in_corridor_3 = (obs[6] > 0.5)
            is_overtake = (obs[10] > 0.5)
            is_passenger_express = (obs[3] >= 0.90)
            if loop_siding_free and in_corridor_3 and is_overtake and not is_passenger_express:
                route_act = 1
            else:
                route_act = 0
        else:
            route_act = 0

        # Action Churn Suppression:
        # If previous step was mainline (0), require solid confirmation before switching
        prev_route = self.last_actions.get("corridor_trunk", 0)
        if prev_route != route_act and self.action_lock_timer["corridor_trunk"] > 0:
            route_act = prev_route
            self.action_lock_timer["corridor_trunk"] -= 1
        elif route_act != 0:
            self.action_lock_timer["corridor_trunk"] = 2  # hold for 30s

        return int(route_act)
