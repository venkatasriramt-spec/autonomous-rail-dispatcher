"""
mappo_agent.py
Multi-Agent Proximal Policy Optimization (MAPPO) Architecture for Railway Dispatching.

Implements Centralized Training with Decentralized Execution (CTDE):
1. Decentralized Actors:
   - 6 Station Actors: Localized policy mapping 24-dim observation -> MultiDiscrete([7, 4])
   - 1 Corridor Actor: Localized policy mapping 14-dim observation -> Discrete(3)
2. Centralized Critic:
   - Value network evaluating the joint state S_joint (158-dim) across all 7 interlocking zones
3. Decentralized Exception & Interlocking Guardrails:
   - Embeds Frontier 1 & Frontier 2 safeguards locally within each agent's execution loop
"""

import os
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Any, Optional, Tuple, List

from ..envs.marl_zones import (
    MARL_AGENT_IDS,
    STATION_AGENT_NAMES,
    STATION_OBS_DIM,
    CORRIDOR_OBS_DIM
)


class StationActor(nn.Module):
    """Decentralized actor policy for a Station-Master Interlocking Agent."""
    def __init__(self, obs_dim: int = STATION_OBS_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh()
        )
        self.plat_head = nn.Linear(64, 7)  # Platform choices 0..6
        self.hold_head = nn.Linear(64, 4)  # Hold choices 0..3

    def forward(self, obs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        feat = self.net(obs)
        return self.plat_head(feat), self.hold_head(feat)

    def select_action(self, obs: np.ndarray, deterministic: bool = True) -> np.ndarray:
        with torch.no_grad():
            t_obs = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
            p_logits, h_logits = self.forward(t_obs)
            if deterministic:
                p_act = torch.argmax(p_logits, dim=-1).item()
                h_act = torch.argmax(h_logits, dim=-1).item()
            else:
                p_act = torch.distributions.Categorical(logits=p_logits).sample().item()
                h_act = torch.distributions.Categorical(logits=h_logits).sample().item()
        return np.array([p_act, h_act], dtype=np.int64)

    def get_action_and_log_prob(self, obs: torch.Tensor, deterministic: bool = False) -> Tuple[torch.Tensor, torch.Tensor]:
        """Samples action and computes log probability for training rollouts."""
        p_logits, h_logits = self.forward(obs)
        p_dist = torch.distributions.Categorical(logits=p_logits)
        h_dist = torch.distributions.Categorical(logits=h_logits)
        if deterministic:
            p_act = torch.argmax(p_logits, dim=-1)
            h_act = torch.argmax(h_logits, dim=-1)
        else:
            p_act = p_dist.sample()
            h_act = h_dist.sample()
        actions = torch.stack([p_act, h_act], dim=-1)
        log_prob = p_dist.log_prob(p_act) + h_dist.log_prob(h_act)
        return actions, log_prob

    def evaluate_actions(self, obs: torch.Tensor, actions: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Evaluates log probabilities and entropy of given actions for PPO updates."""
        p_logits, h_logits = self.forward(obs)
        p_dist = torch.distributions.Categorical(logits=p_logits)
        h_dist = torch.distributions.Categorical(logits=h_logits)
        p_log_prob = p_dist.log_prob(actions[:, 0])
        h_log_prob = h_dist.log_prob(actions[:, 1])
        log_prob = p_log_prob + h_log_prob
        entropy = p_dist.entropy() + h_dist.entropy()
        return log_prob, entropy


class CorridorActor(nn.Module):
    """Decentralized actor policy for the Corridor Block Agent."""
    def __init__(self, obs_dim: int = CORRIDOR_OBS_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, 3)  # Route choices 0..2 (Mainline, Siding, Bypass)
        )

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.net(obs)

    def select_action(self, obs: np.ndarray, deterministic: bool = True) -> int:
        with torch.no_grad():
            t_obs = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
            logits = self.forward(t_obs)
            if deterministic:
                route_act = torch.argmax(logits, dim=-1).item()
            else:
                route_act = torch.distributions.Categorical(logits=logits).sample().item()
        return int(route_act)

    def get_action_and_log_prob(self, obs: torch.Tensor, deterministic: bool = False) -> Tuple[torch.Tensor, torch.Tensor]:
        """Samples route action and computes log probability for training rollouts."""
        logits = self.forward(obs)
        dist = torch.distributions.Categorical(logits=logits)
        if deterministic:
            route_act = torch.argmax(logits, dim=-1)
        else:
            route_act = dist.sample()
        log_prob = dist.log_prob(route_act)
        return route_act, log_prob

    def evaluate_actions(self, obs: torch.Tensor, actions: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Evaluates log probabilities and entropy of given route actions for PPO updates."""
        logits = self.forward(obs)
        dist = torch.distributions.Categorical(logits=logits)
        log_prob = dist.log_prob(actions)
        entropy = dist.entropy()
        return log_prob, entropy


class CentralizedCritic(nn.Module):
    """Centralized Critic evaluating joint state value V(S_joint) during CTDE training."""
    def __init__(self, joint_dim: int = 6 * STATION_OBS_DIM + CORRIDOR_OBS_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(joint_dim, 128),
            nn.Tanh(),
            nn.Linear(128, 64),
            nn.Tanh(),
            nn.Linear(64, 1)
        )

    def forward(self, joint_obs: torch.Tensor) -> torch.Tensor:
        return self.net(joint_obs)

    def evaluate_state(self, joint_obs: torch.Tensor) -> torch.Tensor:
        """Evaluates scalar value V(S_joint) across batch."""
        return self.forward(joint_obs).squeeze(-1)



class MAPPODispatcher:
    """
    Cooperative Multi-Agent PPO Dispatcher coordinating all 7 decentralized interlocking agents.
    Equipped with local Dispatch-by-Exception and Smart Interlocking guardrails.
    """
    def __init__(
        self,
        checkpoint_path: Optional[str] = None,
        exception_gating: bool = True,
        smart_interlocking: bool = True
    ):
        self.exception_gating = exception_gating
        self.smart_interlocking = smart_interlocking

        # Instantiate decentralized actors
        self.actors: Dict[str, nn.Module] = {}
        for aid in MARL_AGENT_IDS:
            if aid.startswith("station_"):
                self.actors[aid] = StationActor()
            else:
                self.actors[aid] = CorridorActor()

        # Instantiate centralized critic
        self.critic = CentralizedCritic()

        # Load weights if checkpoint exists
        if checkpoint_path is not None:
            if not os.path.exists(checkpoint_path):
                raise FileNotFoundError(f"Checkpoint not found at: {checkpoint_path}")
            self.load(checkpoint_path)


    def predict(
        self,
        obs_dict: Dict[str, np.ndarray],
        info: Optional[Dict[str, Any]] = None,
        deterministic: bool = True
    ) -> Dict[str, Any]:
        """
        Generates decentralized actions across all agents.
        Applies local Frontier 1 & 2 exception gating at each interlocking zone.
        """
        actions = {}
        day = info.get("day") if (info and isinstance(info, dict)) else None

        for aid in MARL_AGENT_IDS:
            obs = obs_dict.get(aid, np.zeros(STATION_OBS_DIM if aid.startswith("station_") else CORRIDOR_OBS_DIM))

            if aid.startswith("station_"):
                # Station Agent Decision
                plat_act, hold_act = self._decide_station_action(aid, obs, day, deterministic)
                actions[aid] = np.array([plat_act, hold_act], dtype=np.int64)
            else:
                # Corridor Agent Decision
                route_act = self._decide_corridor_action(obs, deterministic)
                actions[aid] = route_act

        return actions

    def _decide_station_action(
        self,
        aid: str,
        obs: np.ndarray,
        day: Optional[str],
        deterministic: bool
    ) -> Tuple[int, int]:
        DELAY_THRESHOLD = 0.05
        is_critical_approach = (0.05 < obs[6] < 0.60)

        # Frontier 1: Dispatch-by-Exception Gating
        # In real-world rail operations, trains run on scheduled nominal routes by default.
        # The AI dispatcher intervenes only when an active physical exception is detected.
        if self.exception_gating:
            has_train = obs[3] > 0.0          # priority > 0 indicates active train
            has_delay = obs[4] > DELAY_THRESHOLD  # delay > 30s
            is_at_stop = obs[7] > 0.5
            is_leader_tight = (obs[10] < 0.25 and obs[10] > 0.0)

            # Check if station throat has tight leader or active platform conflict
            has_throat_conflict = is_leader_tight or (is_critical_approach and obs[12] > 0.5)

            # If the consist is on-time with clear track ahead and no conflict, leave on nominal schedule
            if not has_train or (not has_delay and not is_at_stop and not has_throat_conflict):
                return 0, 0

        # Query local neural actor
        action = self.actors[aid].select_action(obs, deterministic=deterministic)
        plat_act, hold_act = int(action[0]), int(action[1])

        # Frontier 2: Smart Interlocking Guardrails
        if self.smart_interlocking:
            # Rule 1: Platform reallocation is only physically valid when approaching a station
            if plat_act > 0 and not (0.05 < obs[6] < 0.65):
                plat_act = 0

            # Rule 2: Bar holds on trains that are already delayed or without tight leader
            # Never hold a train that is already running late!
            is_ontime = obs[4] <= DELAY_THRESHOLD
            is_leader_tight = (obs[10] < 0.25 and obs[10] > 0.0)
            if hold_act > 0 and (not is_ontime or not is_leader_tight):
                hold_act = 0

            # Rule 3: Dynamic open platform resolution when Platform 1 is blocked/staging
            assigned_is_blocked = (plat_act <= 1) or (plat_act > 1 and obs[12 + plat_act - 1] > 0.5)
            if is_critical_approach and (day == "Sun" or assigned_is_blocked) and obs[12] > 0.5:
                # Platform 1 is blocked or turnaround staged; route to first open platform
                found_open = False
                for p_idx in range(1, 6):
                    if obs[12 + p_idx] < 0.5:
                        plat_act = p_idx + 1
                        found_open = True
                        break
                if not found_open:
                    plat_act = 0
            elif not (day == "Sun") and obs[12] <= 0.5:
                # Default platform is free and unblocked; maintain nominal timetable routing
                plat_act = 0
            elif plat_act > 0:
                # Don't route to an already-occupied platform
                target_plat_idx = plat_act - 1
                if target_plat_idx < 6 and obs[12 + target_plat_idx] > 0.5:
                    plat_act = 0

        return plat_act, hold_act

    def _decide_corridor_action(self, obs: np.ndarray, deterministic: bool) -> int:
        """Corridor Agent decision logic with local Frontier 1 & 2 guardrails."""
        # Frontier 1: Dispatch-by-Exception Gating
        # If mainline track is clear ahead and consist is on time, default to mainline (0)
        if self.exception_gating:
            leader_dist_norm = obs[7]
            is_overtake_candidate = obs[10] > 0.5
            if leader_dist_norm > 0.50 and not is_overtake_candidate:
                return 0

        # Query local neural actor
        route_act = self.actors["corridor_trunk"].select_action(obs, deterministic=deterministic)

        # Frontier 2: Loop siding protection on clear track
        if self.smart_interlocking:
            if route_act == 1 and obs[10] < 0.5:  # not an overtake candidate
                route_act = 0

        return int(route_act)

    def save(self, path: str):
        """Serializes all decentralized actor weights and the centralized critic."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state_dict = {
            f"actor_{aid}": self.actors[aid].state_dict() for aid in MARL_AGENT_IDS
        }
        state_dict["critic"] = self.critic.state_dict()
        torch.save(state_dict, path)

    def load(self, path: str):
        """Loads weights into decentralized actors and centralized critic."""
        state_dict = torch.load(path, map_location="cpu")
        for aid in MARL_AGENT_IDS:
            k = f"actor_{aid}"
            if k in state_dict:
                self.actors[aid].load_state_dict(state_dict[k])
        if "critic" in state_dict:
            self.critic.load_state_dict(state_dict["critic"])
