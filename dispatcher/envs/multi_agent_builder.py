"""
multi_agent_builder.py
Extracts localized, decentralized observation vectors for each MARL agent:
1. Station Agents: 24 features focused on station throat headway, platform availability, and dwell clearing.
2. Corridor Agent: 14 features focused on trunk line block occupancy, overtaking candidates, and bypass availability.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from .marl_zones import (
    MARL_AGENT_IDS,
    STATION_CITY_MAP,
    STATION_OBS_DIM,
    CORRIDOR_OBS_DIM,
    get_agent_for_vehicle
)
from .observation_builder import STATION_PLATFORMS, PLATFORM_LENGTHS, ROLLING_STOCK_SPECS


class MultiAgentObservationBuilder:
    def __init__(self, reward_engine: Any):
        self.reward_engine = reward_engine

    def build_multi_agent_observations(
        self,
        train_states: Dict[str, Dict[str, Any]],
        sim_time: float,
        active_trains: int,
        traci_module: Any
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, Optional[str]]]:
        """
        Builds observation vectors for all 7 MARL agents.
        Returns:
            obs_dict: Mapping of agent_id -> normalized numpy array
            focus_train_dict: Mapping of agent_id -> vehicle_id being prioritized by that agent
        """
        # Group trains by their controlling agent
        agent_trains: Dict[str, List[str]] = {aid: [] for aid in MARL_AGENT_IDS}

        for veh_id, state in train_states.items():
            road_id = state.get("road_id", "")
            upcoming_station = state.get("upcoming_station")
            dist_to_station = state.get("dist_to_next_stop", 9999.0)
            is_at_stop = state.get("is_at_stop", False)

            assigned_agent = get_agent_for_vehicle(
                veh_id=veh_id,
                road_id=road_id,
                upcoming_station=upcoming_station,
                dist_to_station=dist_to_station,
                is_at_stop=is_at_stop
            )
            agent_trains[assigned_agent].append(veh_id)

        # Select focus train for each agent based on operational priority (highest delay / approaching conflict)
        focus_train_dict: Dict[str, Optional[str]] = {}
        for aid in MARL_AGENT_IDS:
            vehs = agent_trains[aid]
            if not vehs:
                focus_train_dict[aid] = None
                continue

            # Prioritize trains with delay or trains in the critical decision threshold (approaching platform or ready to depart)
            def sort_key(v_id: str) -> float:
                st = train_states[v_id]
                score = st.get("delay_sec", 0.0) * st.get("priority", 0.5)
                # Boost priority if in critical approach zone
                if 200.0 <= st.get("dist_to_next_stop", 9999.0) <= 1500.0:
                    score += 500.0
                if st.get("is_at_stop", False):
                    score += 200.0
                return score

            best_veh = max(vehs, key=sort_key)
            focus_train_dict[aid] = best_veh

        # Build individual observation vectors
        obs_dict: Dict[str, np.ndarray] = {}

        # 1. Station Agents (station_city_1 .. station_city_6)
        time_norm = (sim_time % 86400.0) / 86400.0
        city_reverse_map = {
            "station_city_1": "City_1",
            "station_city_2": "City_2",
            "station_city_3": "City_3_EW",  # Central hub primary deck
            "station_city_4": "City_4",
            "station_city_5": "City_5",
            "station_city_6": "City_6"
        }

        for aid in MARL_AGENT_IDS:
            if aid.startswith("station_"):
                city_name = city_reverse_map.get(aid, "City_1")
                obs = self._build_station_obs(
                    city_name=city_name,
                    focus_veh_id=focus_train_dict[aid],
                    train_states=train_states,
                    time_norm=time_norm,
                    zone_trains_count=len(agent_trains[aid]),
                    total_trains_count=max(active_trains, 1),
                    traci_module=traci_module
                )
                obs_dict[aid] = obs
            else:
                # 2. Corridor Agent (corridor_trunk)
                obs = self._build_corridor_obs(
                    focus_veh_id=focus_train_dict[aid],
                    train_states=train_states,
                    time_norm=time_norm,
                    line_trains_count=len(agent_trains[aid]),
                    total_trains_count=max(active_trains, 1),
                    traci_module=traci_module
                )
                obs_dict[aid] = obs

        return obs_dict, focus_train_dict

    def _build_station_obs(
        self,
        city_name: str,
        focus_veh_id: Optional[str],
        train_states: Dict[str, Dict[str, Any]],
        time_norm: float,
        zone_trains_count: int,
        total_trains_count: int,
        traci_module: Any
    ) -> np.ndarray:
        """Constructs 24-dimensional observation vector for a Station-Master Agent."""
        obs = np.zeros(STATION_OBS_DIM, dtype=np.float32)

        # Context features (0..2)
        obs[0] = float(time_norm)
        obs[1] = float(zone_trains_count / 10.0)  # Local station queue density
        obs[2] = float(zone_trains_count / total_trains_count)

        # Ego train features (3..8)
        if focus_veh_id and focus_veh_id in train_states:
            st = train_states[focus_veh_id]
            obs[3] = float(st.get("priority", 0.5))
            obs[4] = float(min(st.get("delay_sec", 0.0) / 600.0, 1.0))
            obs[5] = float(st.get("speed_ratio", 0.0))
            obs[6] = float(min(st.get("dist_to_next_stop", 9999.0) / 2500.0, 1.0))
            obs[7] = 1.0 if st.get("is_at_stop", False) else 0.0
            obs[8] = float(min(st.get("dwell_time", 0.0) / 180.0, 1.0))

            # Leader features (9..11)
            obs[9] = float(st.get("leader_priority", 0.0))
            obs[10] = float(min(st.get("leader_dist", 3000.0) / 3000.0, 1.0))
            obs[11] = float(st.get("leader_speed", 0.0) / 33.33)

        # Platform status matrix (12..23: 6 binary occupancies + 6 dwell ratios)
        plats_fw = STATION_PLATFORMS.get(city_name, {}).get("fw", [])
        for p_idx in range(min(6, len(plats_fw))):
            plat_edge = plats_fw[p_idx]
            is_occ = 0.0
            dwell_ratio = 0.0
            try:
                edge_vehs = traci_module.edge.getLastStepVehicleIDs(plat_edge)
                if edge_vehs:
                    is_occ = 1.0
                    v_on_plat = edge_vehs[0]
                    v_speed = traci_module.vehicle.getSpeed(v_on_plat)
                    if v_speed < 0.1:
                        stops = traci_module.vehicle.getStops(v_on_plat)
                        if stops:
                            dwell_ratio = min(stops[0].duration / 180.0, 1.0)
            except Exception:
                pass
            obs[12 + p_idx] = float(is_occ)
            obs[18 + p_idx] = float(dwell_ratio)

        return np.clip(obs, -1.0, 1.0)

    def _build_corridor_obs(
        self,
        focus_veh_id: Optional[str],
        train_states: Dict[str, Dict[str, Any]],
        time_norm: float,
        line_trains_count: int,
        total_trains_count: int,
        traci_module: Any
    ) -> np.ndarray:
        """Constructs 14-dimensional observation vector for the Corridor Block Agent."""
        obs = np.zeros(CORRIDOR_OBS_DIM, dtype=np.float32)

        # Context features (0..2)
        obs[0] = float(time_norm)
        obs[1] = float(line_trains_count / 20.0)  # Corridor density
        obs[2] = float(line_trains_count / total_trains_count)

        # Ego train features (3..6)
        if focus_veh_id and focus_veh_id in train_states:
            st = train_states[focus_veh_id]
            obs[3] = float(st.get("priority", 0.5))
            obs[4] = float(min(st.get("delay_sec", 0.0) / 600.0, 1.0))
            obs[5] = float(st.get("speed_ratio", 0.0))
            road_id = st.get("road_id", "")
            obs[6] = 1.0 if "c3_" in road_id or "bypass" in road_id else 0.0

            # Traffic ahead & overtake candidates (7..10)
            obs[7] = float(min(st.get("leader_dist", 3000.0) / 3000.0, 1.0))
            obs[8] = float(st.get("leader_speed", 0.0) / 33.33)
            obs[9] = float(st.get("leader_priority", 0.0))
            obs[10] = 1.0 if (st.get("leader_dist", 3000.0) < 1500.0 and st.get("leader_speed", 50.0) < st.get("speed_m_s", 0.0)) else 0.0

        # Siding and bypass availability (11..13)
        loop_occ = 0.0
        try:
            loop_vehs = traci_module.edge.getLastStepVehicleIDs("c3_Town_8_Town_9_loop_siding_fw")
            if loop_vehs:
                loop_occ = 1.0
        except Exception:
            pass
        obs[11] = float(loop_occ)

        bypass_occ = 0.0
        try:
            bypass_vehs = traci_module.edge.getLastStepVehicleIDs("bypass_City_2_City_5_fw_b0")
            if bypass_vehs:
                bypass_occ = 1.0
        except Exception:
            pass
        obs[12] = float(bypass_occ)

        # Tight headway alert
        obs[13] = 1.0 if obs[7] < 0.30 else 0.0

        return np.clip(obs, -1.0, 1.0)
