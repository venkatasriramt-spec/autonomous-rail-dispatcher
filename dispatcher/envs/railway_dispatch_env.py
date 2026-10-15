"""
railway_dispatch_env.py
Gymnasium Environment for Autonomous Railway Traffic Management and Train Dispatching.
Wraps Eclipse SUMO via TraCI into an event-driven, multi-class decision environment.
"""

import os
import sys
import uuid
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import Dict, Any, Optional, Tuple, List

# Ensure SUMO tools are on path
if "SUMO_HOME" in os.environ:
    sumo_tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    if sumo_tools not in sys.path:
        sys.path.append(sumo_tools)
elif os.path.exists("/usr/share/sumo/tools"):
    if "/usr/share/sumo/tools" not in sys.path:
        sys.path.append("/usr/share/sumo/tools")

import traci
try:
    from sumolib.miscutils import getFreeSocketPort
except ImportError:
    getFreeSocketPort = None

from .observation_builder import ObservationBuilder
from .action_handler import ActionHandler
from .reward_engine import RewardEngine
from ..scenarios.perturbations import DisruptionManager, PerturbationConfig


class RailwayDispatchEnv(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"]}

    def __init__(
        self,
        sumocfg_path: Optional[str] = None,
        start_time_sec: float = 21600.0,    # 06:00 AM morning operational surge
        sim_horizon_sec: float = 7200.0,    # 2 hours active dispatch window per episode
        macro_step_sec: float = 15.0,       # 15s macroscopic decision interval
        perturbation_config: Optional[PerturbationConfig] = None,
        gui: bool = False,
        seed: Optional[int] = None
    ):
        super().__init__()

        # Paths
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.sumocfg_path = sumocfg_path or os.path.join(
            base_dir, "trains", "sumo_config", "train_simulation.sumocfg"
        )
        if not os.path.exists(self.sumocfg_path):
            raise FileNotFoundError(f"SUMO config not found at {self.sumocfg_path}")

        self.start_time_sec = start_time_sec
        self.sim_horizon_sec = sim_horizon_sec
        self.end_time_sec = start_time_sec + sim_horizon_sec
        self.macro_step_sec = macro_step_sec
        self.gui = gui
        self.instance_id = f"rail_env_{uuid.uuid4().hex[:8]}"
        self.is_connected = False

        # Core Engines
        self.reward_engine = RewardEngine()
        self.obs_builder = ObservationBuilder(self.reward_engine)
        self.action_handler = ActionHandler()
        self.disruption_manager = DisruptionManager(perturbation_config)

        # Action Space: MultiDiscrete([Route, Platform, DepartureHold])
        # 1. Route: 0=Default Main, 1=Passing Loop Siding, 2=High-Speed Bypass
        # 2. Platform: 0=Scheduled Default, 1..6=Alternate Platform 1..6
        # 3. DepartureHold: 0=Proceed/Clear, 1=Hold 30s, 2=Hold 60s, 3=Hold 120s
        self.action_space = spaces.MultiDiscrete([3, 7, 4])

        # Observation Space: 28 continuous normalized features
        self.observation_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(self.obs_builder.obs_dim,),
            dtype=np.float32
        )

        # Runtime Trackers
        self.sim_time = 0.0
        self.focus_veh_id: Optional[str] = None
        self.train_states: Dict[str, Dict[str, Any]] = {}
        self.departed_ontime: List[str] = []
        self.completed_trains: List[str] = []
        self.total_knock_on_events = 0
        self.episode_step_count = 0

        if seed is not None:
            self.reset(seed=seed)

    def _select_focus_vehicle(self) -> Optional[str]:
        """
        Prioritizes which active train requires immediate dispatcher intervention.
        """
        if not self.train_states:
            return None

        # 1. Train approaching a station platform throat (< 1500m)
        approach_candidates = [
            v for v, s in self.train_states.items()
            if s.get("upcoming_station") and 200.0 < s.get("dist_to_next_stop", 9999.0) < 1800.0
        ]
        if approach_candidates:
            # Pick the candidate with the highest priority or delay
            approach_candidates.sort(
                key=lambda v: (self.train_states[v]["priority"], self.train_states[v]["delay_sec"]),
                reverse=True
            )
            return approach_candidates[0]

        # 2. Train approaching passing loop or bypass
        divergence_candidates = [
            v for v, s in self.train_states.items()
            if "Town_8" in s.get("road_id", "") or "Throat2" in s.get("road_id", "")
        ]
        if divergence_candidates:
            return divergence_candidates[0]

        # 3. Train stopped whose dwell has finished (ready for departure authorization)
        stopped_candidates = [
            v for v, s in self.train_states.items()
            if s.get("is_at_stop", False) and s.get("delay_sec", 0) > 0
        ]
        if stopped_candidates:
            stopped_candidates.sort(
                key=lambda v: self.train_states[v]["priority"],
                reverse=True
            )
            return stopped_candidates[0]

        # 4. Fallback: Train with highest delay
        sorted_by_delay = sorted(
            self.train_states.keys(),
            key=lambda v: (self.train_states[v]["priority"] * self.train_states[v]["delay_sec"]),
            reverse=True
        )
        return sorted_by_delay[0]

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)

        self._close_traci()
        self.instance_id = f"rail_env_{uuid.uuid4().hex[:8]}"

        binary = "sumo-gui" if self.gui else "sumo"
        cmd = [
            binary,
            "-c", self.sumocfg_path,
            "--no-step-log", "true",
            "--time-to-teleport", "180",
            "--collision.action", "teleport",
            "--no-warnings", "true",
            "--duration-log.disable", "true",
            "--random", "true"
        ]
        if self.start_time_sec > 0:
            cmd.extend(["--begin", str(int(self.start_time_sec))])

        port = None
        if getFreeSocketPort is not None:
            try:
                port = getFreeSocketPort()
            except Exception:
                port = None

        try:
            if port is not None:
                traci.start(cmd, port=port, label=self.instance_id)
            else:
                traci.start(cmd, label=self.instance_id)
            self.is_connected = True
        except Exception:
            traci.start(cmd)
            self.is_connected = True

        self.sim_time = self.start_time_sec
        self.episode_step_count = 0
        self.total_knock_on_events = 0
        self.departed_ontime.clear()
        self.completed_trains.clear()
        self.reward_engine.reset()
        self.action_handler.reset()
        self.disruption_manager.reset()

        # Initial step to synchronize simulation time with begin
        try:
            traci.simulationStep()
            self.sim_time = traci.simulation.getTime()
        except Exception:
            pass

        # Update initial fleet state
        self._refresh_train_states()
        self.focus_veh_id = self._select_focus_vehicle()
        obs = self.obs_builder.build_observation(
            self.focus_veh_id,
            self.train_states,
            self.sim_time,
            traci
        )

        info = self._get_info()
        return obs, info

    def _refresh_train_states(self):
        active_ids = traci.vehicle.getIDList()
        current_active = {}
        for vid in active_ids:
            try:
                state = self.obs_builder.extract_train_features(vid, self.sim_time, traci)
                current_active[vid] = state
            except Exception:
                pass

        # Detect arrived / completed trains
        for vid in list(self.train_states.keys()):
            if vid not in current_active:
                self.completed_trains.append(vid)

        self.train_states = current_active

    def step(
        self,
        action: Any
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        self.episode_step_count += 1
        self.departed_ontime.clear()
        self.completed_trains.clear()
        step_knock_ons = 0

        applied_veh_id = self.focus_veh_id

        # 1. Apply Dispatcher Decision to Focus Train
        self.action_handler.apply_action(
            applied_veh_id,
            action,
            self.train_states,
            self.sim_time,
            traci
        )

        # 2. Advance Microscopic Simulation by macro_step_sec (e.g. 15s)
        target_time = self.sim_time + self.macro_step_sec
        sim_alive = True
        while self.sim_time < target_time and self.sim_time < self.end_time_sec:
            # Check for disruption triggers
            self.disruption_manager.step(self.sim_time, traci)
            try:
                traci.simulationStep()
                self.sim_time = traci.simulation.getTime()
            except Exception:
                sim_alive = False
                break

            # Detect secondary knock-on decelerations
            try:
                active_vehs = traci.vehicle.getIDList()
                for vid in active_vehs:
                    try:
                        leader_info = traci.vehicle.getLeader(vid, 1000.0)
                        if leader_info:
                            lead_id, dist = leader_info
                            if dist < 250.0 and traci.vehicle.getSpeed(vid) < 5.0:
                                # Train caught behind stopped/slow lead train
                                step_knock_ons += 1
                    except Exception:
                        pass
            except Exception:
                pass

        self.total_knock_on_events += step_knock_ons

        # 3. Refresh Fleet State & Next Focus Vehicle
        if sim_alive:
            self._refresh_train_states()
            self.focus_veh_id = self._select_focus_vehicle()
        else:
            self.train_states.clear()
            self.focus_veh_id = None

        # 4. Compute Reward (including intervention penalty on applied_veh_id)
        reward = self.reward_engine.compute_reward(
            self.train_states,
            self.departed_ontime,
            self.completed_trains,
            step_knock_ons,
            focus_veh_id=applied_veh_id,
            action=action
        )

        # 5. Check Termination Conditions
        terminated = (self.sim_time >= self.end_time_sec) or (not sim_alive)
        truncated = False

        obs = self.obs_builder.build_observation(
            self.focus_veh_id,
            self.train_states,
            self.sim_time,
            traci
        )
        info = self._get_info()

        if terminated:
            self._close_traci()

        return obs, float(reward), terminated, truncated, info

    def _get_info(self) -> Dict[str, Any]:
        all_delays = [s["delay_sec"] for s in self.train_states.values()] if self.train_states else [0.0]
        mean_delay = float(np.mean(all_delays)) if all_delays else 0.0
        max_delay = float(np.max(all_delays)) if all_delays else 0.0
        ontime_count = sum(1 for d in all_delays if d <= 180.0)
        punctuality = (ontime_count / max(1, len(all_delays))) * 100.0

        return {
            "sim_time": self.sim_time,
            "active_trains": len(self.train_states),
            "mean_delay_sec": mean_delay,
            "max_delay_sec": max_delay,
            "punctuality_pct": punctuality,
            "knock_on_events": self.total_knock_on_events,
            "focus_vehicle": self.focus_veh_id,
            "applied_actions_count": len(self.action_handler.action_history)
        }

    def _close_traci(self):
        try:
            if hasattr(traci, "_connections"):
                traci._connections.pop(self.instance_id, None)
                traci._connections.pop("default", None)
            traci.close()
        except Exception:
            pass
        self.is_connected = False

    def close(self):
        self._close_traci()
