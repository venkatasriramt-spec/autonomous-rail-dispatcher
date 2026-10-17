"""
marl_zones.py
Spatial decomposition and zone authority definitions for Multi-Agent Reinforcement Learning (MARL).

Decouples the centralized corridor into localized Interlocking Control Areas (Stellbereiche):
1. 6 Station-Master Agents (Hub Interlocking):
   - station_city_1: Terminal Hub 1 (5 platform tracks, pocket turnaround)
   - station_city_2: Major Hub 2 (6 platform tracks, bypass junction)
   - station_city_3: Central Bi-Level Interchange Hub (4 EW + 4 NS platform tracks)
   - station_city_4: Hub 4 (5 platform tracks, reversing pockets)
   - station_city_5: Hub 5 (6 platform tracks, bypass chord junction)
   - station_city_6: Terminal Hub 6 (6 platform tracks, coastal junction)
2. 1 Corridor Block Agent:
   - corridor_trunk: Inter-city line blocks, Alpine Passing Loop on Corridor 3, High-Speed Bypass.
"""

from typing import Dict, Any, List, Optional, Tuple
from gymnasium.spaces import MultiDiscrete, Discrete, Box
import numpy as np

# List of all active MARL agent identifiers
MARL_AGENT_IDS = [
    "station_city_1",
    "station_city_2",
    "station_city_3",
    "station_city_4",
    "station_city_5",
    "station_city_6",
    "corridor_trunk"
]

STATION_AGENT_NAMES = [
    "station_city_1",
    "station_city_2",
    "station_city_3",
    "station_city_4",
    "station_city_5",
    "station_city_6"
]

STATION_CITY_MAP = {
    "City_1": "station_city_1",
    "City_2": "station_city_2",
    "City_3_EW": "station_city_3",
    "City_3_NS": "station_city_3",
    "City_3": "station_city_3",
    "City_4": "station_city_4",
    "City_5": "station_city_5",
    "City_6": "station_city_6"
}

# Local action spaces
# Station Agent: Platform Selection (0..6) + Departure Hold (0..3: proceed, 30s, 60s, 120s)
STATION_ACTION_SPACE = MultiDiscrete([7, 4])

# Corridor Agent: Route Selection (0 = Mainline, 1 = Passing Loop, 2 = High-Speed Bypass)
CORRIDOR_ACTION_SPACE = Discrete(3)

# Observation dimensions:
# Station Agent: 24 features (local time, density, ego priority, delay, speed, leader metrics, platform occupancy & dwell matrix)
STATION_OBS_DIM = 24

# Corridor Agent: 14 features (line density, time of day, train priority, delay, speed, leader dist, overtake candidate, loop/bypass status)
CORRIDOR_OBS_DIM = 14

# Total centralized observation dimension for CTDE Critic
TOTAL_JOINT_OBS_DIM = 6 * STATION_OBS_DIM + CORRIDOR_OBS_DIM



def get_agent_for_vehicle(
    veh_id: str,
    road_id: str,
    upcoming_station: Optional[str] = None,
    dist_to_station: float = 9999.0,
    is_at_stop: bool = False
) -> str:
    """
    Determines which decentralized agent has jurisdictional dispatch authority
    over the given vehicle at the current simulation timestamp.
    """
    # 1. If currently stopped or dwelling at a station platform, the station master has authority
    if is_at_stop:
        for city_prefix, agent_id in STATION_CITY_MAP.items():
            if city_prefix in road_id:
                return agent_id

    # 2. If approaching a multi-platform city station within the interlocking approach window (<= 2500m)
    if upcoming_station and 200.0 <= dist_to_station <= 2500.0:
        if upcoming_station in STATION_CITY_MAP:
            return STATION_CITY_MAP[upcoming_station]

    # 3. If currently traveling on an edge belonging to a station yard/throat
    for city_prefix, agent_id in STATION_CITY_MAP.items():
        if road_id.startswith(f"{city_prefix}_") or f"_{city_prefix}_" in road_id:
            return agent_id

    # 4. Otherwise, the vehicle is traveling on open line blocks under Corridor Trunk jurisdiction
    return "corridor_trunk"


def get_agent_action_spaces() -> Dict[str, Any]:
    """Returns the mapping of agent IDs to their respective Gymnasium action spaces."""
    spaces = {}
    for agent_id in MARL_AGENT_IDS:
        if agent_id.startswith("station_"):
            spaces[agent_id] = STATION_ACTION_SPACE
        else:
            spaces[agent_id] = CORRIDOR_ACTION_SPACE
    return spaces


def get_agent_observation_spaces() -> Dict[str, Box]:
    """Returns the mapping of agent IDs to their respective Gymnasium observation spaces."""
    spaces = {}
    for agent_id in MARL_AGENT_IDS:
        dim = STATION_OBS_DIM if agent_id.startswith("station_") else CORRIDOR_OBS_DIM
        spaces[agent_id] = Box(
            low=-1.0,
            high=1.0,
            shape=(dim,),
            dtype=np.float32
        )
    return spaces
