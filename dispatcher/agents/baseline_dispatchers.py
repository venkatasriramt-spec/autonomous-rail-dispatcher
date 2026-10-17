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


def parse_scheduled_platform_edge(sched_edge: Optional[str]) -> Optional[int]:
    """Parses 0-indexed platform number from platform edge string (e.g. City_1_plat_2_fw -> 1)."""
    if sched_edge and "_plat_" in str(sched_edge):
        try:
            return int(str(sched_edge).split("_plat_")[1].split("_")[0]) - 1
        except Exception:
            pass
    return None


def parse_scheduled_platform_idx(
    info: Optional[Dict[str, Any]],
    max_plats: int = 6,
    default: int = 0
) -> int:
    """Safely extracts and parses scheduled_platform_idx from step info, guarding against None and out-of-range values."""
    if info and isinstance(info, dict):
        val = info.get("scheduled_platform_idx")
        if val is not None:
            try:
                idx = int(val)
                if 0 <= idx < max_plats:
                    return idx
            except (ValueError, TypeError):
                pass
        sched_edge = info.get("scheduled_platform_edge")
        edge_idx = parse_scheduled_platform_edge(sched_edge)
        if edge_idx is not None and 0 <= edge_idx < max_plats:
            return edge_idx
    return default


def get_station_capacity_from_edge(sched_edge: Optional[str], default: int = 6) -> int:
    """Returns the physical platform capacity based on edge name."""
    if not sched_edge:
        return default
    edge_str = str(sched_edge)
    if "City_3" in edge_str:
        return 4
    elif any(c in edge_str for c in ("City_1", "City_4")):
        return 5
    return default


def find_free_alternative_platform(
    obs: np.ndarray,
    sched_idx: int,
    max_plats: int,
    obs_offset: int = 16,
    stride: int = 2
) -> int:
    """
    Finds the first free alternate platform (1-indexed action) excluding the scheduled platform.
    Returns 0 if no alternative is available.
    """
    for p_idx in range(max_plats):
        if p_idx != sched_idx:
            feat_idx = obs_offset + (p_idx * stride)
            if feat_idx < len(obs) and obs[feat_idx] < 0.5:
                return p_idx + 1
    return 0


def resolve_heuristic_platform(
    observation: np.ndarray,
    info: Optional[Dict[str, Any]] = None
) -> int:
    """
    Shared resolution logic for baseline dispatchers:
    Checks if scheduled platform is occupied and returns first free alternate (or 0).
    """
    if observation[15] <= 0.5:
        return 0

    sched_edge = info.get("scheduled_platform_edge") if (info and isinstance(info, dict)) else None
    max_plats = get_station_capacity_from_edge(sched_edge)

    # Accept scheduled_platform_idx only when within platform-feature range [0, max_plats);
    # otherwise parse scheduled_platform_edge as fallback before checking platform availability.
    sched_idx = parse_scheduled_platform_idx(info, max_plats=max_plats)
    sched_feat = 16 + sched_idx * 2

    sched_plat_occupied = (observation[sched_feat] > 0.5) if sched_feat < len(observation) else False
    if info and isinstance(info, dict) and info.get("scheduled_platform_occupied"):
        sched_plat_occupied = True

    if sched_plat_occupied:
        return find_free_alternative_platform(observation, sched_idx, max_plats, obs_offset=16, stride=2)
    return 0


class FIFODispatcher(BaseDispatcher):
    """
    First-In First-Out (FIFO) Heuristic:
    Reassigns platforms greedily to the first open track if scheduled platform is occupied.
    Does not account for train priority classes.
    """
    def __init__(self):
        super().__init__(name="FIFO_Heuristic")

    def predict(self, observation: np.ndarray, info: Optional[Dict[str, Any]] = None) -> np.ndarray:
        route_act = 0
        plat_act = resolve_heuristic_platform(observation, info)
        hold_act = 0
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
        leader_prio = observation[13]        # Lead train priority

        # 1. Reroute / Passing Loop Divert
        if is_overtake_cand > 0.5:
            # Slower train ahead: if ego is High-Speed, attempt bypass or loop
            if priority >= 0.8:
                route_act = 2  # Attempt High-Speed Bypass
            else:
                route_act = 1  # Divert to Passing Loop siding

        # 2. Platform allocation: if upcoming scheduled platform is busy
        plat_act = resolve_heuristic_platform(observation, info)

        # 3. Departure Hold: If low-priority freight train is stopped and high-priority train is close ahead/behind
        is_stopped = observation[9] > 0.5
        if is_stopped and priority < 0.4 and leader_prio > 0.7:
            hold_act = 2  # Hold 60s to let express clear block

        return np.array([route_act, plat_act, hold_act], dtype=np.int64)
