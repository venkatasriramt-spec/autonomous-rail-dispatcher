"""
baseline_dispatchers.py
Benchmark baseline dispatchers for comparative verification:
1. StaticDispatcher (Default fixed schedule, no interventions)
2. FIFODispatcher (First-come-first-served, greedy first available platform)
3. PriorityGreedyDispatcher (Rule-based priority hierarchy: HighSpeed > Regional > Freight)
"""

import numpy as np
from typing import Dict, Any, Optional


class BaseDispatcher:
    def __init__(self, name: str = "BaseDispatcher"):
        self.name = name

    def predict(self, observation: np.ndarray, info: Optional[Dict[str, Any]] = None) -> np.ndarray:
        raise NotImplementedError


class StaticDispatcher(BaseDispatcher):
    """
    Static Baseline: Executes no dynamic interventions.
    Trains follow static duarouter routes and fixed timetable dwells.
    """
    def __init__(self):
        super().__init__(name="Static_Baseline")

    def predict(self, observation: np.ndarray, info: Optional[Dict[str, Any]] = None) -> np.ndarray:
        # [route_act=0 (main), plat_act=0 (default platform), hold_act=0 (no hold)]
        return np.array([0, 0, 0], dtype=np.int64)


class FIFODispatcher(BaseDispatcher):
    """
    First-In First-Out (FIFO) Heuristic:
    Reassigns platforms greedily to the first open track if scheduled platform is occupied.
    Does not account for train priority classes.
    """
    def __init__(self):
        super().__init__(name="FIFO_Heuristic")

    def predict(self, observation: np.ndarray, info: Optional[Dict[str, Any]] = None) -> np.ndarray:
        # Obs layout:
        # [16..27]: Platform occupancy pairs [is_occupied, dwell] for 6 platforms
        route_act = 0
        plat_act = 0
        hold_act = 0

        # Check if approaching station (obs[15] == 1.0)
        approaching_station = observation[15] > 0.5
        if approaching_station:
            sched_idx = 0
            if info and isinstance(info, dict) and "scheduled_platform_idx" in info:
                sched_idx = int(info["scheduled_platform_idx"])
            sched_feat = 16 + sched_idx * 2 if (0 <= sched_idx < 6) else 16

            sched_edge = info.get("scheduled_platform_edge", "") if (info and isinstance(info, dict)) else ""
            max_plats = 6
            if "City_3" in str(sched_edge):
                max_plats = 4
            elif any(c in str(sched_edge) for c in ("City_1", "City_4")):
                max_plats = 5

            sched_plat_occupied = (observation[sched_feat] > 0.5) if sched_feat < 28 else False
            if info and isinstance(info, dict) and info.get("scheduled_platform_occupied"):
                sched_plat_occupied = True

            if sched_plat_occupied:
                for p_idx in range(max_plats):
                    if p_idx != sched_idx:
                        feat_idx = 16 + (p_idx * 2)
                        if feat_idx < 28 and observation[feat_idx] < 0.5:
                            plat_act = p_idx + 1
                            break

        return np.array([route_act, plat_act, hold_act], dtype=np.int64)


class PriorityGreedyDispatcher(BaseDispatcher):
    """
    Rule-Based Priority Heuristic:
    1. High-Speed passenger trains receive top right-of-way.
    2. Slower freight trains are diverted into passing loops when express trains are near.
    3. Occupied platforms are dynamically reallocated.
    4. Lower-priority trains hold at stations if a higher-priority service is delayed downstream.
    """
    def __init__(self):
        super().__init__(name="Priority_Greedy_Heuristic")

    def predict(self, observation: np.ndarray, info: Optional[Dict[str, Any]] = None) -> np.ndarray:
        route_act = 0
        plat_act = 0
        hold_act = 0

        priority = observation[5]            # Ego train priority
        is_overtake_cand = observation[14]   # Faster train caught behind slower train
        approaching_st = observation[15]     # Approaching station
        leader_prio = observation[13]        # Lead train priority

        # 1. Reroute / Passing Loop Divert
        if is_overtake_cand > 0.5:
            # Slower train ahead: if ego is High-Speed, attempt bypass or loop
            if priority >= 0.8:
                route_act = 2  # Attempt High-Speed Bypass
            else:
                route_act = 1  # Divert to Passing Loop siding

        # 2. Platform allocation: if upcoming scheduled platform is busy
        if approaching_st > 0.5:
            sched_idx = 0
            if info and isinstance(info, dict) and "scheduled_platform_idx" in info:
                sched_idx = int(info["scheduled_platform_idx"])
            sched_feat = 16 + sched_idx * 2 if (0 <= sched_idx < 6) else 16

            sched_edge = info.get("scheduled_platform_edge", "") if (info and isinstance(info, dict)) else ""
            max_plats = 6
            if "City_3" in str(sched_edge):
                max_plats = 4
            elif any(c in str(sched_edge) for c in ("City_1", "City_4")):
                max_plats = 5

            sched_plat_occupied = (observation[sched_feat] > 0.5) if sched_feat < 28 else False
            if info and isinstance(info, dict) and info.get("scheduled_platform_occupied"):
                sched_plat_occupied = True

            if sched_plat_occupied:
                for p_idx in range(max_plats):
                    if p_idx != sched_idx:
                        feat_idx = 16 + (p_idx * 2)
                        if feat_idx < 28 and observation[feat_idx] < 0.5:
                            plat_act = p_idx + 1
                            break

        # 3. Departure Hold: If low-priority freight train is stopped and high-priority train is close ahead/behind
        is_stopped = observation[9] > 0.5
        if is_stopped and priority < 0.4 and leader_prio > 0.7:
            hold_act = 2  # Hold 60s to let express clear block

        return np.array([route_act, plat_act, hold_act], dtype=np.int64)
