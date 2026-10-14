"""
observation_builder.py
Constructs normalized, compact observation vectors for the RL dispatcher agent.
Extracts ego train metrics, traffic lookahead, bottleneck density, and station platform status.
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple

# Mapping of stations to their available platform tracks (forward and backward)
STATION_PLATFORMS = {
    "City_1": {
        "fw": [f"City_1_plat_{i}_fw" for i in range(1, 6)],
        "bw": [f"City_1_plat_{i}_bw" for i in range(1, 6)]
    },
    "City_2": {
        "fw": [f"City_2_plat_{i}_fw" for i in range(1, 7)],
        "bw": [f"City_2_plat_{i}_bw" for i in range(1, 7)]
    },
    "City_3_EW": {
        "fw": [f"City_3_EW_plat_{i}_fw" for i in range(1, 5)],
        "bw": [f"City_3_EW_plat_{i}_bw" for i in range(1, 5)]
    },
    "City_3_NS": {
        "fw": [f"City_3_NS_plat_{i}_fw" for i in range(1, 5)],
        "bw": [f"City_3_NS_plat_{i}_bw" for i in range(1, 5)]
    },
    "City_4": {
        "fw": [f"City_4_plat_{i}_fw" for i in range(1, 6)],
        "bw": [f"City_4_plat_{i}_bw" for i in range(1, 6)]
    },
    "City_5": {
        "fw": [f"City_5_plat_{i}_fw" for i in range(1, 6)],
        "bw": [f"City_5_plat_{i}_bw" for i in range(1, 6)]
    },
    "City_6": {
        "fw": [f"City_6_plat_{i}_fw" for i in range(1, 6)],
        "bw": [f"City_6_plat_{i}_bw" for i in range(1, 6)]
    }
}


class ObservationBuilder:
    def __init__(self, reward_engine: Any):
        self.reward_engine = reward_engine
        # Observation vector size: 28 features
        self.obs_dim = 28

    def extract_train_features(
        self,
        veh_id: str,
        sim_time: float,
        traci_module: Any
    ) -> Dict[str, Any]:
        """
        Extract detailed runtime metrics for a specific train.
        """
        vtype = traci_module.vehicle.getTypeID(veh_id)
        speed = traci_module.vehicle.getSpeed(veh_id)
        max_speed = traci_module.vehicle.getAllowedSpeed(veh_id)
        road_id = traci_module.vehicle.getRoadID(veh_id)
        lane_pos = traci_module.vehicle.getLanePosition(veh_id)
        priority = self.reward_engine.get_priority_weight(vtype)

        # Scheduled stops inspection
        stops = traci_module.vehicle.getStops(veh_id)
        delay_sec = 0.0
        upcoming_station = None
        upcoming_direction = "fw"
        dist_to_next_stop = 3000.0
        scheduled_platform_edge = None
        is_at_stop = traci_module.vehicle.isStopped(veh_id)

        if stops:
            next_stop = stops[0]
            lane_id = next_stop.lane
            edge_id = lane_id.rsplit("_", 1)[0]
            scheduled_platform_edge = edge_id

            # Detect upcoming station
            for st_name in STATION_PLATFORMS:
                if st_name in lane_id:
                    upcoming_station = st_name
                    upcoming_direction = "bw" if "_bw" in lane_id else "fw"
                    break

            # Calculate delay relative to scheduled arrival/departure
            if next_stop.intendedArrival > 0 and sim_time > next_stop.intendedArrival:
                delay_sec = sim_time - next_stop.intendedArrival
            elif next_stop.until > 0 and sim_time > next_stop.until:
                delay_sec = sim_time - next_stop.until

            # Distance to stop
            try:
                driving_dist = traci_module.vehicle.getDrivingDistance(veh_id, edge_id, next_stop.startPos)
                if driving_dist >= 0:
                    dist_to_next_stop = driving_dist
            except Exception:
                dist_to_next_stop = 1500.0

        # Leader / traffic ahead
        leader_info = traci_module.vehicle.getLeader(veh_id, 3000.0)
        leader_id = None
        leader_dist = 3000.0
        leader_speed = 0.0
        leader_priority = 0.0
        if leader_info:
            leader_id, leader_dist = leader_info
            try:
                leader_speed = traci_module.vehicle.getSpeed(leader_id)
                leader_type = traci_module.vehicle.getTypeID(leader_id)
                leader_priority = self.reward_engine.get_priority_weight(leader_type)
            except Exception:
                pass

        return {
            "veh_id": veh_id,
            "vtype": vtype,
            "priority": priority,
            "speed": speed,
            "max_speed": max_speed,
            "road_id": road_id,
            "lane_pos": lane_pos,
            "delay_sec": max(0.0, delay_sec),
            "dist_to_next_stop": dist_to_next_stop,
            "upcoming_station": upcoming_station,
            "upcoming_direction": upcoming_direction,
            "scheduled_platform_edge": scheduled_platform_edge,
            "is_at_stop": is_at_stop,
            "leader_id": leader_id,
            "leader_dist": leader_dist,
            "leader_speed": leader_speed,
            "leader_priority": leader_priority
        }

    def build_observation(
        self,
        focus_veh_id: Optional[str],
        train_states: Dict[str, Dict[str, Any]],
        sim_time: float,
        traci_module: Any
    ) -> np.ndarray:
        """
        Builds a fixed-size normalized NumPy observation vector (shape: 28,).
        """
        obs = np.zeros(self.obs_dim, dtype=np.float32)

        # 1. Global Simulation State (Indices 0..4)
        active_count = len(train_states)
        all_delays = [s["delay_sec"] for s in train_states.values()] if train_states else [0.0]
        mean_delay = float(np.mean(all_delays)) if all_delays else 0.0
        max_delay = float(np.max(all_delays)) if all_delays else 0.0

        obs[0] = (sim_time % 86400.0) / 86400.0       # Time of day [0, 1]
        obs[1] = min(1.0, active_count / 35.0)          # Active fleet density [0, 1]
        obs[2] = min(1.0, mean_delay / 1800.0)          # Mean network delay (normalized to 30 min)
        obs[3] = min(1.0, max_delay / 3600.0)           # Max network delay (normalized to 60 min)
        # Peak hours: 07:00-09:30 (25200-34200) or 16:30-19:00 (59400-68400)
        is_peak = 1.0 if (25200 <= sim_time <= 34200 or 59400 <= sim_time <= 68400) else 0.0
        obs[4] = is_peak

        # 2. Focus Train State (Indices 5..10)
        focus_state = train_states.get(focus_veh_id) if focus_veh_id else None
        if focus_state:
            obs[5] = focus_state["priority"]
            obs[6] = min(1.0, focus_state["delay_sec"] / 1800.0)
            obs[7] = min(1.0, focus_state["speed"] / max(1.0, focus_state["max_speed"]))
            obs[8] = min(1.0, focus_state["dist_to_next_stop"] / 3000.0)
            obs[9] = 1.0 if focus_state["is_at_stop"] else 0.0
            # Decision proximity flag (1 if within 1500m of a station or junction)
            obs[10] = 1.0 if focus_state["dist_to_next_stop"] < 1500.0 else 0.0

            # 3. Traffic Ahead & Interaction (Indices 11..15)
            obs[11] = min(1.0, focus_state["leader_dist"] / 3000.0)
            obs[12] = min(1.0, focus_state["leader_speed"] / 83.33)
            obs[13] = focus_state["leader_priority"]
            # Overtake opportunity flag: leader is slower and has lower priority than focus train
            is_overtake_candidate = (
                1.0 if (
                    focus_state["leader_id"]
                    and focus_state["priority"] > focus_state["leader_priority"]
                    and focus_state["leader_speed"] < focus_state["max_speed"] * 0.7
                ) else 0.0
            )
            obs[14] = is_overtake_candidate
            obs[15] = 1.0 if focus_state["upcoming_station"] is not None else 0.0

            # 4. Upcoming Station Platform Occupancy & Dwell Matrix (Indices 16..27)
            # 6 platforms max, each gets [is_occupied, remaining_dwell_norm]
            st_name = focus_state["upcoming_station"]
            direction = focus_state["upcoming_direction"]
            if st_name and st_name in STATION_PLATFORMS:
                plat_edges = STATION_PLATFORMS[st_name].get(direction, [])
                for idx in range(6):
                    feat_idx = 16 + (idx * 2)
                    if idx < len(plat_edges):
                        plat_edge = plat_edges[idx]
                        lane_id = f"{plat_edge}_0"
                        try:
                            occupants = traci_module.lane.getLastStepVehicleIDs(lane_id)
                            if occupants:
                                obs[feat_idx] = 1.0
                                occ_veh = occupants[0]
                                occ_stops = traci_module.vehicle.getStops(occ_veh)
                                if occ_stops:
                                    rem_dwell = max(0.0, occ_stops[0].until - sim_time)
                                    obs[feat_idx + 1] = min(1.0, rem_dwell / 300.0)
                                else:
                                    obs[feat_idx + 1] = 0.5
                            else:
                                obs[feat_idx] = 0.0
                                obs[feat_idx + 1] = 0.0
                        except Exception:
                            obs[feat_idx] = 0.0
                            obs[feat_idx + 1] = 0.0
                    else:
                        obs[feat_idx] = 0.0
                        obs[feat_idx + 1] = 0.0

        return obs
