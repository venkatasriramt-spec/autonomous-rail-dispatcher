"""
multi_agent_railway_env.py
Decentralized Multi-Agent Gymnasium Environment for Autonomous Railway Dispatching (MARL).

Decomposes network control into:
- 6 Station-Master Interlocking Agents: station_city_1 through station_city_6
  (Platform selection 0..6 + Departure holding 0..3)
- 1 Corridor Block Agent: corridor_trunk
  (Mainline routing, Alpine loop overtakes, and High-Speed Bypass 0..2)
"""

import os
import sys
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import Dict, Any, Optional, Tuple, List

from .railway_dispatch_env import RailwayDispatchEnv
from .marl_zones import (
    MARL_AGENT_IDS,
    STATION_AGENT_NAMES,
    STATION_CITY_MAP,
    get_agent_action_spaces,
    get_agent_observation_spaces
)
from .multi_agent_builder import MultiAgentObservationBuilder
from ..scenarios.perturbations import PerturbationConfig
import traci


class MultiAgentRailwayEnv(RailwayDispatchEnv):
    """
    Decentralized Multi-Agent Railway Dispatching Environment conforming to
    Centralized Training with Decentralized Execution (CTDE) principles.
    """

    def __init__(
        self,
        sumocfg_path: Optional[str] = None,
        start_time_sec: float = 21600.0,
        sim_horizon_sec: float = 7200.0,
        macro_step_sec: float = 15.0,
        perturbation_config: Optional[PerturbationConfig] = None,
        gui: bool = False,
        seed: Optional[int] = None,
        cooperation_factor: float = 0.5,  # Weight of shared global reward vs local zone reward
        port: Optional[int] = None
    ):
        super().__init__(
            sumocfg_path=sumocfg_path,
            start_time_sec=start_time_sec,
            sim_horizon_sec=sim_horizon_sec,
            macro_step_sec=macro_step_sec,
            perturbation_config=perturbation_config,
            gui=gui,
            seed=None,
            port=port
        )

        self.agents = list(MARL_AGENT_IDS)
        self.cooperation_factor = cooperation_factor

        # Multi-Agent Observation Builder
        self.marl_obs_builder = MultiAgentObservationBuilder(self.reward_engine)

        # Action and Observation Spaces
        self.action_spaces = get_agent_action_spaces()
        self.observation_spaces = get_agent_observation_spaces()

        # Track focus trains per agent for decision attribution
        self.agent_focus_trains: Dict[str, Optional[str]] = {aid: None for aid in self.agents}

        if seed is not None:
            self.reset(seed=seed)

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        """
        Resets the multi-agent environment and returns observations for all 7 agents.
        """
        _, global_info = super().reset(seed=seed, options=options)

        if not hasattr(self, "marl_obs_builder"):
            return {}, global_info

        # Build initial multi-agent observations
        obs_dict, focus_dict = self.marl_obs_builder.build_multi_agent_observations(
            train_states=self.train_states,
            sim_time=self.sim_time,
            active_trains=len(self.train_states),
            traci_module=traci
        )
        self.agent_focus_trains = focus_dict

        day = global_info.get("day", getattr(self, "day", "all"))
        sched_indices, sched_occ = self._get_agent_platform_info()
        info = {
            "day": day,
            "global_info": global_info,
            "focus_trains": dict(self.agent_focus_trains),
            "agent_scheduled_platform_indices": sched_indices,
            "agent_scheduled_platform_occupied": sched_occ
        }
        return obs_dict, info


    def step(
        self,
        action_dict: Dict[str, Any]
    ) -> Tuple[
        Dict[str, np.ndarray],
        Dict[str, float],
        Dict[str, bool],
        Dict[str, bool],
        Dict[str, Any]
    ]:
        """
        Executes decentralized actions across all agents, advances the microscopic simulation,
        and returns decentralized observations and rewards.

        action_dict:
            "station_city_k": [plat_act (0..6), hold_act (0..3)]
            "corridor_trunk": route_act (0..2)
        """
        self.episode_step_count += 1
        self.departed_ontime.clear()
        self.completed_trains.clear()

        # 1. Apply decentralized actions to each agent's active focus consist
        agent_actions_summary = {}
        applied_agents = set()

        for aid, action in action_dict.items():
            focus_vid = self.agent_focus_trains.get(aid)
            if not focus_vid or focus_vid not in self.train_states:
                continue

            if aid.startswith("station_"):
                # Station Master action: [plat_act, hold_act]
                plat_act = int(action[0]) if hasattr(action, "__len__") and len(action) > 0 else 0
                hold_act = int(action[1]) if hasattr(action, "__len__") and len(action) > 1 else 0
                full_act = [0, plat_act, hold_act]
                is_active = (plat_act > 0 or hold_act > 0)
            else:
                # Corridor Controller action: route_act
                route_act = int(action) if not hasattr(action, "__len__") else int(action[0])
                full_act = [route_act, 0, 0]
                is_active = (route_act > 0)

            res = self.action_handler.apply_action(
                focus_vid,
                full_act,
                self.train_states,
                self.sim_time,
                traci
            )
            agent_actions_summary[aid] = res

            if is_active and any(c.get("type") in ("platform_reassigned", "diverted_to_passing_loop", "high_speed_bypass_reroute", "departure_held") for c in res.get("changes", [])):
                applied_agents.add(aid)

        # 2. Advance Microscopic SUMO Simulation by macro_step_sec (15s)
        target_time = self.sim_time + self.macro_step_sec
        sim_alive = True
        step_knock_ons = 0
        knock_on_vehs_this_step = set()

        while self.sim_time < target_time and self.sim_time < self.end_time_sec:
            self.disruption_manager.step(self.sim_time, traci)
            try:
                traci.simulationStep()
                self.sim_time = traci.simulation.getTime()
            except Exception:
                sim_alive = False
                break

            try:
                self.total_collisions += traci.simulation.getCollidingVehiclesNumber()
                self.total_teleports += traci.simulation.getStartingTeleportNumber()
            except Exception:
                pass

            try:
                active_vehs = traci.vehicle.getIDList()
                for vid in active_vehs:
                    if vid in knock_on_vehs_this_step:
                        continue
                    speed = traci.vehicle.getSpeed(vid)
                    allowed = traci.vehicle.getAllowedSpeed(vid)
                    leader_info = traci.vehicle.getLeader(vid, 150.0)
                    is_stopped = traci.vehicle.isStopped(vid)
                    if (not is_stopped) and speed < 3.0 and leader_info is not None and leader_info[1] < 150.0:
                        lead_id = leader_info[0]
                        lead_stopped = False
                        try:
                            lead_stopped = traci.vehicle.isStopped(lead_id)
                        except Exception:
                            lead_stopped = False
                        if not lead_stopped:
                            step_knock_ons += 1
                            knock_on_vehs_this_step.add(vid)
            except Exception:
                pass

        self.total_knock_on_events += step_knock_ons

        # 3. Synchronize train states
        if sim_alive:
            self._refresh_train_states()

        # Check termination & truncation
        terminated_flag = not sim_alive
        truncated_flag = self.sim_time >= self.end_time_sec

        # 4. Build new observations and update focus trains
        obs_dict, focus_dict = self.marl_obs_builder.build_multi_agent_observations(
            train_states=self.train_states,
            sim_time=self.sim_time,
            active_trains=len(self.train_states),
            traci_module=traci
        )
        self.agent_focus_trains = focus_dict

        # 5. Compute Decentralized & Cooperative CTDE Rewards
        # Global network metrics
        delays = [s["delay_sec"] for s in self.train_states.values()]
        mean_delay = float(np.mean(delays)) if delays else 0.0
        max_delay = float(np.max(delays)) if delays else 0.0
        ontime_count = sum(1 for d in delays if d <= 180.0)
        punctuality = float(ontime_count / len(delays) * 100.0) if delays else 100.0

        # Global system reward
        global_reward = - (mean_delay / 60.0) - (0.1 * step_knock_ons)
        if punctuality >= 98.0:
            global_reward += 0.5

        # Local agent rewards
        reward_dict: Dict[str, float] = {}
        city_reverse_map = {
            "station_city_1": "City_1",
            "station_city_2": "City_2",
            "station_city_3": "City_3",
            "station_city_4": "City_4",
            "station_city_5": "City_5",
            "station_city_6": "City_6"
        }

        for aid in self.agents:
            if aid.startswith("station_"):
                city_key = city_reverse_map.get(aid, "City_1")
                # Zone trains
                zone_delays = [
                    s["delay_sec"] for s in self.train_states.values()
                    if city_key in s.get("road_id", "") or city_key in str(s.get("upcoming_station", ""))
                ]
                zone_mean_delay = float(np.mean(zone_delays)) if zone_delays else 0.0
                local_reward = - (zone_mean_delay / 60.0)
            else:
                # Corridor agent
                corridor_delays = [
                    s["delay_sec"] for s in self.train_states.values()
                    if not any(c in s.get("road_id", "") for c in ["City_1", "City_2", "City_3", "City_4", "City_5", "City_6"])
                ]
                corridor_mean_delay = float(np.mean(corridor_delays)) if corridor_delays else 0.0
                local_reward = - (corridor_mean_delay / 60.0)

            # Blended CTDE Reward: (1 - α) * Local + α * Global
            blended_reward = (1.0 - self.cooperation_factor) * local_reward + self.cooperation_factor * global_reward

            # Action Workload Penalty (Pareto Regularization): applied only to agents whose actions were actually applied
            if aid in applied_agents:
                blended_reward -= 0.10  # Baseline intervention cost

            reward_dict[aid] = float(np.clip(blended_reward, -10.0, 5.0))

        # PettingZoo / Multi-Agent termination flags
        terminated_dict = {aid: terminated_flag for aid in self.agents}
        truncated_dict = {aid: truncated_flag for aid in self.agents}
        terminated_dict["__all__"] = terminated_flag
        truncated_dict["__all__"] = truncated_flag

        sched_indices, sched_occ = self._get_agent_platform_info()
        info_dict = {
            "day": getattr(self, "day", "all"),
            "mean_delay_sec": mean_delay,
            "max_delay_sec": max_delay,
            "punctuality_pct": punctuality,
            "knock_on_events": self.total_knock_on_events,
            "active_trains": len(self.train_states),
            "step_knock_ons": step_knock_ons,
            "agent_actions": agent_actions_summary,
            "focus_trains": dict(self.agent_focus_trains),
            "agent_scheduled_platform_indices": sched_indices,
            "agent_scheduled_platform_occupied": sched_occ
        }

        return obs_dict, reward_dict, terminated_dict, truncated_dict, info_dict

    def _get_agent_platform_info(self) -> Tuple[Dict[str, int], Dict[str, bool]]:
        sched_plat_indices = {}
        sched_plat_occupied = {}
        for aid, vid in getattr(self, "agent_focus_trains", {}).items():
            if vid and vid in self.train_states:
                st = self.train_states[vid]
                edge = st.get("scheduled_platform_edge")
                idx = 0
                if edge and "_plat_" in str(edge):
                    try:
                        idx = int(str(edge).split("_plat_")[1].split("_")[0]) - 1
                    except Exception:
                        idx = 0
                sched_plat_indices[aid] = idx
                sched_plat_occupied[aid] = bool(st.get("scheduled_platform_occupied", False))
        return sched_plat_indices, sched_plat_occupied
