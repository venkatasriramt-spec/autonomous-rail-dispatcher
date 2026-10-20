"""
backend/core/network_geometry.py
Extracts, formats, and caches 2D railway network geometry for frontend rendering.
"""

import os
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple
from pathlib import Path

from backend.config import ROOT_DIR, NET_FILE, ADD_FILE, GEOMETRY_CACHE_FILE

# Machine-independent relative paths for source files
NET_FILE_REL = str(Path(NET_FILE).relative_to(ROOT_DIR))
ADD_FILE_REL = str(Path(ADD_FILE).relative_to(ROOT_DIR))

# Station friendly display names
STATION_DISPLAY_NAMES = {
    "City_1": "City 1 Metropolis",
    "City_2": "City 2 North Junction",
    "City_3": "City 3 Bi-Level Interchange Hub",
    "City_4": "City 4 South Terminal",
    "City_5": "City 5 East Port Hub",
    "City_6": "City 6 Mountain Gateway",
    "Town_1": "Town 1 Valley",
    "Town_2": "Town 2 Foothills",
    "Town_3": "Town 3 Alpine Pass",
    "Town_4": "Town 4 Summit",
    "Town_5": "Town 5 Meadow",
    "Town_6": "Town 6 Riverside",
    "Town_7": "Town 7 Pine Ridge",
    "Town_8": "Town 8 Highland",
    "Town_9": "Town 9 Lakeview",
    "Town_10": "Town 10 Crossway",
    "Town_11": "Town 11 Forest Edge",
    "Town_12": "Town 12 Basin"
}

_CACHED_GEOMETRY: Dict[str, Any] = {}
_CACHED_MTIME: float = 0.0


def categorize_edge(edge_id: str) -> str:
    """Categorizes an edge ID into standard track classifications."""
    eid = edge_id.lower()
    if "pocket" in eid:
        return "pocket"
    elif "siding" in eid or "lead" in eid:
        return "passing_loop"
    elif "xov1" in eid or "xov2" in eid:
        return "crossover"
    elif "thru" in eid:
        return "express_thru"
    elif "plat" in eid:
        return "platform"
    elif "yard" in eid:
        return "yard"
    elif "c1_" in eid or "bypass" in eid:
        return "high_speed"
    elif "c2_" in eid or "c3_" in eid:
        return "regional"
    elif "depot" in eid:
        return "depot"
    return "connector"


def parse_network_geometry(force_reparse: bool = False) -> Dict[str, Any]:
    """
    Parses dense_network.net.xml and dense_network.add.xml, extracting lanes,
    platforms, station centroids, and bounds. Caches to disk.
    """
    global _CACHED_GEOMETRY, _CACHED_MTIME

    if not force_reparse and os.path.exists(GEOMETRY_CACHE_FILE):
        try:
            cache_mtime = os.path.getmtime(GEOMETRY_CACHE_FILE)
            net_mtime = os.path.getmtime(NET_FILE) if os.path.exists(NET_FILE) else 0.0
            add_mtime = os.path.getmtime(ADD_FILE) if os.path.exists(ADD_FILE) else 0.0

            # Fast path: in-memory cache matches disk version and paths match
            if _CACHED_GEOMETRY and cache_mtime == _CACHED_MTIME:
                rec_net = _CACHED_GEOMETRY.get("net_file")
                rec_add = _CACHED_GEOMETRY.get("add_file")
                if rec_net == NET_FILE_REL and rec_add == ADD_FILE_REL:
                    if cache_mtime >= net_mtime and cache_mtime >= add_mtime:
                        return _CACHED_GEOMETRY

            # Reload / validate from disk if disk cache is newer or in-memory is empty
            if cache_mtime >= net_mtime and cache_mtime >= add_mtime:
                with open(GEOMETRY_CACHE_FILE, "r") as f:
                    disk_cache = json.load(f)
                rec_net = disk_cache.get("net_file")
                rec_add = disk_cache.get("add_file")
                if rec_net == NET_FILE_REL and rec_add == ADD_FILE_REL:
                    _CACHED_GEOMETRY = disk_cache
                    _CACHED_MTIME = cache_mtime
                    return _CACHED_GEOMETRY
        except Exception:
            pass

    _CACHED_GEOMETRY = {}
    _CACHED_MTIME = 0.0

    net_tree = ET.parse(str(NET_FILE))
    net_root = net_tree.getroot()

    lanes_data: List[Dict[str, Any]] = []
    lane_coords_map: Dict[str, List[List[float]]] = {}

    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

    # 1. Parse Edges & Lanes
    for edge in net_root.findall("edge"):
        if edge.get("function") == "internal":
            continue
        eid = edge.get("id", "")
        cat = categorize_edge(eid)

        for lane in edge.findall("lane"):
            lid = lane.get("id", "")
            shape_str = lane.get("shape", "")
            if not shape_str:
                continue

            pts = []
            for token in shape_str.split():
                coords = [float(c) for c in token.split(",")[:2]]
                pts.append(coords)
                min_x = min(min_x, coords[0])
                min_y = min(min_y, coords[1])
                max_x = max(max_x, coords[0])
                max_y = max(max_y, coords[1])

            lane_coords_map[lid] = pts
            speed_kmh = float(lane.get("speed", 0.0)) * 3.6
            length_m = float(lane.get("length", 0.0))
            allow = lane.get("allow", "all")

            lanes_data.append({
                "edge_id": eid,
                "lane_id": lid,
                "category": cat,
                "speed_kmh": round(speed_kmh, 1),
                "length_m": round(length_m, 1),
                "allow": allow,
                "coordinates": pts
            })

    # 2. Parse Platforms from add.xml
    platforms_by_station: Dict[str, List[Dict[str, Any]]] = {}
    if os.path.exists(ADD_FILE):
        add_tree = ET.parse(str(ADD_FILE))
        add_root = add_tree.getroot()
        for ts in add_root.findall("trainStop"):
            pid = ts.get("id", "")
            lane = ts.get("lane", "")
            start_pos = float(ts.get("startPos", 0.0))
            end_pos = float(ts.get("endPos", 0.0))
            length_m = round(abs(end_pos - start_pos), 1)

            # Format: City_1_p1_fw, Town_3_p1_fw, or City_3_EW_p1_fw
            parts = pid.split("_")
            station_key = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else pid
            direction = parts[-1] if len(parts) >= 3 and parts[-1] in ("fw", "bw") else "fw"
            track = "_".join(parts[2:-1]) if len(parts) > 3 else (parts[2] if len(parts) > 2 else "p1")

            plat_coords = lane_coords_map.get(lane, [])

            plat_info = {
                "platform_id": pid,
                "station_name": station_key,
                "track": track,
                "direction": direction,
                "lane": lane,
                "length_m": length_m,
                "coordinates": plat_coords
            }

            if station_key not in platforms_by_station:
                platforms_by_station[station_key] = []
            platforms_by_station[station_key].append(plat_info)

    # 3. Calculate Station Centroids
    stations_data: List[Dict[str, Any]] = []
    for st_key, plats in platforms_by_station.items():
        all_x, all_y = [], []
        for p in plats:
            for c in p.get("coordinates", []):
                all_x.append(c[0])
                all_y.append(c[1])

        cx = round(sum(all_x) / max(1, len(all_x)), 2) if all_x else 0.0
        cy = round(sum(all_y) / max(1, len(all_y)), 2) if all_y else 0.0

        stations_data.append({
            "station_name": st_key,
            "display_name": STATION_DISPLAY_NAMES.get(st_key, st_key.replace("_", " ")),
            "x": cx,
            "y": cy,
            "platform_count": len(plats),
            "platforms": plats
        })

    # Sort stations logically
    stations_data.sort(key=lambda s: s["station_name"])

    # 4. Junctions, Signals & Buffer Stops
    buffer_stops_count = 0
    signals_count = 0
    for j in net_root.findall("junction"):
        if j.get("type") == "internal":
            continue
        jid = j.get("id", "")
        jtype = j.get("type", "")
        if "buf" in jid:
            buffer_stops_count += 1
        elif jtype == "rail_signal":
            signals_count += 1

    bounds = [
        round(min_x, 2) if min_x != float("inf") else 0.0,
        round(min_y, 2) if min_y != float("inf") else 0.0,
        round(max_x, 2) if max_x != float("-inf") else 30000.0,
        round(max_y, 2) if max_y != float("-inf") else 30000.0
    ]

    result = {
        "bounds": bounds,
        "lanes": lanes_data,
        "stations": stations_data,
        "signals_count": signals_count,
        "buffer_stops_count": buffer_stops_count,
        "net_file": NET_FILE_REL,
        "add_file": ADD_FILE_REL
    }

    # Save to disk cache atomically
    try:
        temp_file = f"{GEOMETRY_CACHE_FILE}.tmp.{os.getpid()}"
        with open(temp_file, "w") as f:
            json.dump(result, f)
        os.replace(temp_file, GEOMETRY_CACHE_FILE)
        _CACHED_MTIME = os.path.getmtime(GEOMETRY_CACHE_FILE)
    except Exception:
        _CACHED_MTIME = 0.0

    _CACHED_GEOMETRY = result
    return result
