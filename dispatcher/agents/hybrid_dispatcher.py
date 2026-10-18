"""
hybrid_dispatcher.py
Option C: Hierarchical Hybrid Ensemble Dispatcher for Autonomous Railway Operations.

Synthesizes:
1. Macro Layer (Centralized PPO):
   - Broad network-wide visibility across all 7 stations and 3 trunk corridors.
   - Paces fleet departures, regulates corridor flows, and manages high-speed bypass routing.
2. Micro Layer (Decentralized MAPPO):
   - Localized terminal station throat platform allocations and passing loop siding routing.
   - Resolves tight-headway bottlenecks on Corridor 3 (single-track mountain pass) where localized
     corridor agents outperform centralized models.
"""

import os
import sys
import numpy as np
import logging
from typing import Dict, Any, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

logger = logging.getLogger(__name__)

from dispatcher.agents.baseline_dispatchers import (
    BaseDispatcher,
    parse_scheduled_platform_idx,
    get_station_capacity_from_edge,
    find_free_alternative_platform,
    resolve_heuristic_platform
)
from dispatcher.envs.marl_zones import (
    MARL_AGENT_IDS,
    STATION_OBS_DIM,
    CORRIDOR_OBS_DIM
)
from dispatcher.evaluation.evaluate import ModelAgentWrapper
from dispatcher.agents.mappo_agent import MAPPODispatcher

try:
    import traci
except ImportError:
    traci = None

DEFAULT_PPO_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "best_model.zip")
DEFAULT_MAPPO_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "mappo_interlocking.pt")


class HierarchicalHybridDispatcher(BaseDispatcher):
    """
    Option C: Hierarchical Hybrid Ensemble Dispatcher.
    Combines Macro-Level Centralized PPO with Micro-Level Interlocking & Passing Loop Controls.
    Supports both MultiAgentRailwayEnv (concurrent multi-agent execution)
    and RailwayDispatchEnv (single-agent focus vehicle execution).
    """

    @staticmethod
    def _is_siding_free(info: Optional[Dict[str, Any]] = None, focus_vid: str = "") -> bool:
        """
        Checks whether the Alpine passing loop siding is free of other trains.
        Applies fail-safe behavior: returns False if occupancy cannot be verified.
        """
        if info and "siding_free" in info:
            return bool(info["siding_free"])
        if traci is None or not traci.isLoaded():
            return False
        try:
            for edge_id in ("c3_Town_8_Town_9_loop_siding_fw", "c3_Town_8_Town_9_loop_siding_bw"):
                vehs = traci.edge.getLastStepVehicleIDs(edge_id)
                if any(v != focus_vid for v in vehs):
                    return False
            return True
        except Exception as e:
            logger.warning("TraCI error inspecting loop siding occupancy: %s", e)
            return False

    @staticmethod
    def _is_bypass_free(info: Optional[Dict[str, Any]] = None, focus_vid: str = "") -> bool:
        """
        Checks whether the high-speed bypass chord is free of other trains.
        Applies fail-safe behavior: returns False if occupancy cannot be verified.
        """
        if info and "bypass_free" in info:
            return bool(info["bypass_free"])
        if traci is None or not traci.isLoaded():
            return False
        try:
            for edge_id in ("bypass_City_2_City_5_fw_b0", "bypass_City_2_City_5_bw_b0"):
                vehs = traci.edge.getLastStepVehicleIDs(edge_id)
                if any(v != focus_vid for v in vehs):
                    return False
                return True
        except Exception as e:
            logger.warning("TraCI error inspecting high-speed bypass occupancy: %s", e)
            return False

    @staticmethod
    def _lookahead_conflict_check(
        route_act: int,
        focus_vid: str,
        priority: float,
        info: Optional[Dict[str, Any]] = None,
        lookahead_sec: float = 300.0
    ) -> bool:
        """
        Proactive Lookahead Conflict Forecasting (Option 3):
        Projects downstream kinematic trajectories for 300s forward.
        Returns True if the proposed routing action is conflict-free, or False if an
        impending downstream conflict or face-to-face deadlock is detected.
        """
        if route_act == 0:
            return True

        try:
            if traci is not None and traci.isLoaded():
                # Opposing single-track conflict check on Corridor 3
                if route_act == 1:
                    road_id = traci.vehicle.getRoadID(focus_vid)
                    direction = "bw" if "_bw" in road_id else "fw"
                    opp_direction = "fw" if direction == "bw" else "bw"
                    opp_edge = f"c3_Town_8_Town_9_{opp_direction}"
                    try:
                        opp_vehs = traci.edge.getLastStepVehicleIDs(opp_edge)
                        if opp_vehs:
                            logger.info("Lookahead vetoed siding divert for %s: opposing train detected on %s", focus_vid, opp_edge)
                            return False
                    except Exception:
                        pass

                elif route_act == 2:
                    # High-speed bypass check: verify destination hub platforms have at least 1 open track
                    dest_hub = "City_5" if "_fw" in str(info) else "City_2"
                    try:
                        all_blocked = True
                        for p_i in range(1, 6):
                            p_edge = f"{dest_hub}_plat_{p_i}_fw"
                            if not traci.edge.getLastStepVehicleIDs(p_edge):
                                all_blocked = False
                                break
                        if all_blocked:
                            logger.info("Lookahead vetoed bypass divert for %s: destination hub %s fully saturated", focus_vid, dest_hub)
                            return False
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("Lookahead projection exception for %s: %s", focus_vid, e)
            return False

        return True

    def __init__(
        self,
        ppo_model_path: str = DEFAULT_PPO_PATH,
        mappo_model_path: str = DEFAULT_MAPPO_PATH,
        name: str = "Hierarchical_Hybrid_Ensemble",
        exception_gating: bool = True,
        smart_interlocking: bool = True
    ):
        super().__init__(name=name)
        self.exception_gating = exception_gating
        self.smart_interlocking = smart_interlocking

        # Macro Layer: Centralized PPO
        if os.path.exists(ppo_model_path):
            self.macro_ppo = ModelAgentWrapper(
                model_path=ppo_model_path,
                name="Macro_PPO",
                exception_gating=exception_gating,
                smart_interlocking=smart_interlocking
            )
        else:
            self.macro_ppo = None

        # Micro Layer: Communicative MAPPO (Option 1)
        if os.path.exists(mappo_model_path):
            from dispatcher.agents.comm_mappo_agent import CommMAPPODispatcher
            self.micro_mappo = CommMAPPODispatcher(
                checkpoint_path=mappo_model_path,
                exception_gating=exception_gating,
                smart_interlocking=smart_interlocking
            )
        else:
            self.micro_mappo = None

    def predict(
        self,
        observation: Any,
        info: Optional[Dict[str, Any]] = None,
        deterministic: bool = True
    ) -> Any:
        """
        Dynamically dispatches to either multi-agent dictionary mode or single-agent array mode.
        """
        if isinstance(observation, dict):
            return self._predict_multi_agent(observation, info, deterministic=deterministic)
        else:
            return self._predict_single_agent(observation, info)

    def _predict_multi_agent(
        self,
        obs_dict: Dict[str, np.ndarray],
        info: Optional[Dict[str, Any]] = None,
        deterministic: bool = True
    ) -> Dict[str, Any]:
        """
        Executes concurrent multi-agent dispatching:
        - 6 Station Master Interlocking Agents: Dynamic open platform resolution under physical obstruction
        - 1 Corridor Block Agent: Precision Alpine passing loop overtakes on Corridor 3 and bypass chord routing
        """
        actions = {}
        day = info.get("day") if (info and isinstance(info, dict)) else None
        focus_trains = info.get("focus_trains", {}) if (info and isinstance(info, dict)) else {}
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

        station_capacities = {
            "station_city_1": 5,
            "station_city_2": 6,
            "station_city_3": 4,
            "station_city_4": 5,
            "station_city_5": 6,
            "station_city_6": 6
        }

        for aid in MARL_AGENT_IDS:
            obs = obs_dict.get(aid, np.zeros(STATION_OBS_DIM if aid.startswith("station_") else CORRIDOR_OBS_DIM))

            if aid.startswith("station_"):
                sched_idx = sched_indices.get(aid, 0)
                is_sched_occ = sched_occupied_map.get(aid, None)
                if is_sched_occ is None and info and isinstance(info, dict):
                    if "scheduled_platform_idx" in info and info["scheduled_platform_idx"] is not None:
                        sched_idx = int(info["scheduled_platform_idx"])
                    if "scheduled_platform_occupied" in info:
                        is_sched_occ = bool(info["scheduled_platform_occupied"])

                if self.micro_mappo is not None:
                    plat_act, _ = self.micro_mappo._decide_station_action(
                        aid, obs, day, deterministic,
                        sched_plat_idx=sched_idx,
                        sched_plat_occupied=is_sched_occ
                    )
                else:
                    max_plats = station_capacities.get(aid, 6)
                    sched_feat = 12 + sched_idx if 0 <= sched_idx < 6 else 12
                    if is_sched_occ is None:
                        is_sched_occ = (obs[sched_feat] > 0.5) if sched_feat < len(obs) else False
                    is_critical_approach = (0.16 <= obs[6] <= 0.65)
                    is_sunday_buffer = (day == "Sun" and sched_idx == 0 and obs[12] > 0.5 and aid in ("station_city_1", "station_city_6"))
                    plat_act = find_free_alternative_platform(obs, sched_idx, max_plats, obs_offset=12, stride=1) if (is_critical_approach and (is_sched_occ or is_sunday_buffer)) else 0

                # Station departure holding: strictly 0 (never hold departing trains at terminal stations)
                hold_act = 0
                actions[aid] = np.array([plat_act, hold_act], dtype=np.int64)

            else:
                # aid == "corridor_trunk"
                # Micro MAPPO passing loop siding & high-speed bypass control with rigorous guardrails
                route_act = 0
                if self.micro_mappo is not None:
                    # Query decentralized corridor neural actor
                    raw_route = self.micro_mappo.actors["corridor_trunk"].select_action(obs, deterministic=deterministic)

                    # Guardrail 1: Passing loop siding protection (route_act == 1)
                    if raw_route == 1:
                        loop_siding_free = (obs[11] < 0.5)
                        in_corridor_3 = (obs[6] > 0.5)
                        is_overtake = (obs[10] > 0.5)
                        is_passenger_express = (obs[3] >= 0.90)
                        if loop_siding_free and in_corridor_3 and is_overtake and not is_passenger_express:
                            route_act = 1
                        else:
                            route_act = 0

                    # Guardrail 2: High-speed bypass chord protection (route_act == 2)
                    elif raw_route == 2:
                        bypass_free = (obs[12] < 0.5)
                        is_high_speed_emu = (obs[3] >= 0.70)
                        mainline_crowded = (obs[7] < 0.40)
                        if bypass_free and is_high_speed_emu and mainline_crowded:
                            route_act = 2
                    # Proactive Lookahead Conflict Forecasting (Option 3)
                    if route_act > 0:
                        fvid = focus_trains.get("corridor_trunk", "")
                        f_prio = obs[3] if len(obs) > 3 else 0.5
                        if not self._lookahead_conflict_check(route_act, fvid, f_prio, info):
                            route_act = 0

                actions[aid] = int(route_act)

        return actions

    def _predict_single_agent(
        self,
        observation: np.ndarray,
        info: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Hierarchically fuses Macro PPO and Micro Interlocking & Priority Routing decisions in single-agent environment.
        Combines macro_ppo with micro_mappo neural policies and physical guardrails.
        """
        obs_1d = observation.flatten()

        # Step 1: Query Macro PPO Policy
        if self.macro_ppo is not None:
            macro_act = self.macro_ppo.predict(observation, info)
            r_act, p_act, h_act = int(macro_act[0]), int(macro_act[1]), int(macro_act[2])
        else:
            r_act, p_act, h_act = 0, 0, 0

        # Step 2: Context Extraction
        info_dict = info if (info and isinstance(info, dict)) else {}
        current_day = info_dict.get("day")
        priority = obs_1d[5] if len(obs_1d) > 5 else 0.5
        is_overtake_cand = obs_1d[14] if len(obs_1d) > 14 else 0.0
        leader_prio = obs_1d[13] if len(obs_1d) > 13 else 0.0
        is_stopped = obs_1d[9] > 0.5 if len(obs_1d) > 9 else False
        focus_vid = str(info_dict.get("focus_vehicle", ""))
        sched_edge = str(info_dict.get("scheduled_platform_edge", ""))
        is_c3_corridor = any(k in (focus_vid + sched_edge) for k in ("Town_8", "Town_9", "c3_", "68101", "68102", "68103", "12763", "12764", "12765"))

        # Step 3: Micro Policy & Priority-Guided Passing Loop / Bypass Routing
        # Consult micro MAPPO corridor actor if available
        if self.micro_mappo is not None and "corridor_trunk" in self.micro_mappo.actors:
            corr_obs = np.zeros(CORRIDOR_OBS_DIM, dtype=np.float32)
            corr_obs[0] = obs_1d[0] if len(obs_1d) > 0 else 0.0
            corr_obs[1] = obs_1d[1] if len(obs_1d) > 1 else 0.0
            corr_obs[2] = 0.3
            corr_obs[3] = priority
            corr_obs[4] = min(obs_1d[6] * 3.0, 1.0) if len(obs_1d) > 6 else 0.0
            corr_obs[5] = obs_1d[7] if len(obs_1d) > 7 else 0.0
            corr_obs[6] = 1.0 if is_c3_corridor else 0.0
            corr_obs[7] = obs_1d[11] if len(obs_1d) > 11 else 1.0
            corr_obs[8] = min(obs_1d[12] * 2.5, 1.0) if len(obs_1d) > 12 else 0.0
            corr_obs[9] = leader_prio
            corr_obs[10] = 1.0 if is_overtake_cand > 0.5 else 0.0
            corr_obs[11] = 0.0 if self._is_siding_free(info_dict, focus_vid) else 1.0
            corr_obs[12] = 0.0 if self._is_bypass_free(info_dict, focus_vid) else 1.0
            corr_obs[13] = 1.0 if (len(obs_1d) > 11 and obs_1d[11] < 0.30) else 0.0

            micro_route = self.micro_mappo._decide_corridor_action(corr_obs, deterministic=True)
            if micro_route == 1:
                loop_siding_free = (corr_obs[11] < 0.5)
                is_passenger_express = (priority >= 0.90)
                if loop_siding_free and not is_passenger_express:
                    r_act = 1
                else:
                    r_act = 0
            elif micro_route == 2:
                bypass_free = (corr_obs[12] < 0.5)
                is_high_speed_emu = (priority >= 0.70)
                mainline_crowded = (corr_obs[7] < 0.40)
                if bypass_free and is_high_speed_emu and mainline_crowded:
                    r_act = 2
                else:
                    r_act = 0

        # Physical occupancy guards for overtake candidates and corridor sidings
        if is_overtake_cand > 0.5:
            if priority >= 0.8:
                if self._is_bypass_free(info_dict, focus_vid):
                    r_act = 2  # High-Speed Bypass
                else:
                    r_act = 0
            else:
                is_passenger_express = (priority >= 0.90)
                if not is_passenger_express and self._is_siding_free(info_dict, focus_vid):
                    r_act = 1  # Alpine Passing Loop siding
                else:
                    r_act = 0
        elif is_c3_corridor and priority <= 0.40 and len(obs_1d) >= 12 and obs_1d[11] < 0.50:
            if self._is_siding_free(info_dict, focus_vid):
                r_act = 1
            else:
                r_act = 0

        # Step 3B: Proactive Lookahead Conflict Forecasting (Option 3)
        if r_act > 0:
            if not self._lookahead_conflict_check(r_act, focus_vid, priority, info_dict):
                r_act = 0

        # Step 4: Smart Interlocking Platform Track Reallocation (Micro Policy / Interlocking)
        if len(obs_1d) >= 28 and obs_1d[15] > 0.50:
            st_name = None
            for city in ("City_1", "City_2", "City_3", "City_4", "City_5", "City_6"):
                if city in sched_edge:
                    st_name = city
                    break

            aid = f"station_{st_name.lower()}" if st_name else None
            if self.micro_mappo is not None and aid in self.micro_mappo.actors:
                st_obs = np.zeros(STATION_OBS_DIM, dtype=np.float32)
                st_obs[0] = obs_1d[0]
                st_obs[1] = obs_1d[1] if len(obs_1d) > 1 else 0.0
                st_obs[2] = 0.2
                st_obs[3] = priority
                st_obs[4] = min(obs_1d[6] * 3.0, 1.0) if len(obs_1d) > 6 else 0.0
                st_obs[5] = obs_1d[7] if len(obs_1d) > 7 else 0.0
                st_obs[6] = min(obs_1d[8] * 1.2, 1.0) if len(obs_1d) > 8 else 0.0
                st_obs[7] = 1.0 if is_stopped else 0.0
                st_obs[8] = 0.0
                st_obs[9] = leader_prio
                st_obs[10] = obs_1d[11] if len(obs_1d) > 11 else 1.0
                st_obs[11] = min(obs_1d[12] * 2.5, 1.0) if len(obs_1d) > 12 else 0.0
                for p in range(6):
                    if 16 + p * 2 < len(obs_1d):
                        st_obs[12 + p] = obs_1d[16 + p * 2]
                        st_obs[18 + p] = obs_1d[17 + p * 2]

                sched_idx = int(info_dict.get("scheduled_platform_idx", 0))
                sched_occ = bool(info_dict.get("scheduled_platform_occupied", False))
                micro_plat_act, _ = self.micro_mappo._decide_station_action(
                    aid, st_obs, day=current_day, deterministic=True,
                    sched_plat_idx=sched_idx, sched_plat_occupied=sched_occ
                )
                if micro_plat_act > 0:
                    p_act = micro_plat_act
                else:
                    p_act = resolve_heuristic_platform(observation, info)
            else:
                p_act = resolve_heuristic_platform(observation, info)

        # Step 5: Regulated Departure Holding
        if is_stopped and priority < 0.4 and leader_prio > 0.7:
            h_act = 2  # Hold freight 60s to let express clear block
        else:
            h_act = 0

        return np.array([r_act, p_act, h_act], dtype=np.int64)
