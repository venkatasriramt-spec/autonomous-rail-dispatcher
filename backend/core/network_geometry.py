"""
backend/core/network_geometry.py
Extracts, formats, and caches 2D railway network geometry for frontend rendering.
"""

import os
import json
import math
import re
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
    elif "xov" in eid or "crossover" in eid:
        return "crossover"
    elif "throat" in eid or eid.startswith(":"):
        return "switch"
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
    platforms, station centroids, switch connections, and bounds. Caches to disk.
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

    # 1. Parse Edges & Lanes (including switch/throat connections)
    for edge in net_root.findall("edge"):
        eid = edge.get("id", "")
        cat = categorize_edge(eid)
        is_internal = edge.get("function") == "internal"

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

            # Filter out unrealistic internal loopbacks, U-turns, and circular hairpin lanes generated by netconvert
            if is_internal and len(pts) >= 2:
                dx = pts[-1][0] - pts[0][0]
                dy = pts[-1][1] - pts[0][1]
                direct_dist = math.hypot(dx, dy)
                path_len = sum(math.hypot(pts[k+1][0] - pts[k][0], pts[k+1][1] - pts[k][1]) for k in range(len(pts)-1))

                start_angle = math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0])
                end_angle = math.atan2(pts[-1][1] - pts[-2][1], pts[-1][0] - pts[-2][0])
                diff = abs(start_angle - end_angle)
                if diff > math.pi:
                    diff = 2 * math.pi - diff
                deg = math.degrees(diff)

                # Real railway turnouts have gentle deflection angles (<35 deg); drop loopbacks
                if deg > 42.0 or (direct_dist > 5.0 and path_len > 1.35 * direct_dist):
                    continue

            lanes_data.append({
                "edge_id": eid,
                "lane_id": lid,
                "category": cat,
                "speed_kmh": round(speed_kmh, 1),
                "length_m": round(length_m, 1),
                "allow": allow,
                "is_internal": is_internal,
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
    edges_to_buf = {}
    for e in net_root.findall("edge"):
        to_j = e.get("to", "")
        if "buf" in to_j:
            edges_to_buf[to_j] = e

    buffer_stops: List[Dict[str, Any]] = []
    signals: List[Dict[str, Any]] = []

    for j in net_root.findall("junction"):
        if j.get("type") == "internal":
            continue
        jid = j.get("id", "")
        jtype = j.get("type", "")
        jx = round(float(j.get("x", 0)), 2)
        jy = round(float(j.get("y", 0)), 2)

        if "buf" in jid or jtype == "dead_end":
            angle_deg = 0.0
            lane_id = None
            edge = edges_to_buf.get(jid)
            if edge is not None:
                shape = edge.get("shape", "")
                pts = [[float(c) for c in t.split(",")[:2]] for t in shape.split()]
                if len(pts) >= 2:
                    dx = pts[-1][0] - pts[-2][0]
                    dy = pts[-1][1] - pts[-2][1]
                    angle_deg = round(math.degrees(math.atan2(dy, dx)), 1)
                lanes = edge.findall("lane")
                if lanes:
                    lane_id = lanes[0].get("id")

            parts = jid.split("_")
            st_name = parts[0] + ("_" + parts[1] if len(parts) > 1 and parts[1] not in ("buf", "pocket") else "")

            buffer_stops.append({
                "id": jid,
                "name": jid.replace("_", " ") + " Buffer Stop",
                "station_name": st_name,
                "x": jx,
                "y": jy,
                "angle_deg": angle_deg,
                "lane_id": lane_id
            })
        elif jtype == "rail_signal":
            if "Throat" in jid:
                sig_type = "interlocking_throat"
                sname = jid.replace("_", " ") + " Signal"
            elif "xov" in jid:
                sig_type = "crossover_signal"
                sname = jid.replace("_", " ") + " Interlock"
            elif "sig" in jid:
                sig_type = "block_signal"
                sname = jid.replace("_", " ") + " Block Signal"
            else:
                sig_type = "rail_signal"
                sname = jid.replace("_", " ") + " Signal"

            signals.append({
                "id": jid,
                "name": sname,
                "x": jx,
                "y": jy,
                "signal_type": sig_type
            })

    # 5. Extract High-Level Track Feature Complexes (Crossovers, Loops, Bypasses)
    track_features: List[Dict[str, Any]] = []

    # A. Crossover complexes (grouped by corridor e.g. c1_City_2_Town_2_xov)
    xov_groups: Dict[str, List[Any]] = {}
    for e in net_root.findall("edge"):
        eid = e.get("id", "")
        if "xov" in eid.lower():
            m = re.search(r"(c\d+_.+?_xov)", eid)
            base = m.group(1) if m else "crossover"
            xov_groups.setdefault(base, []).append(e)

    for base, edges in sorted(xov_groups.items()):
        all_pts = []
        max_speed = 0.0
        for e in edges:
            for l in e.findall("lane"):
                max_speed = max(max_speed, float(l.get("speed", 0.0)) * 3.6)
                shape = l.get("shape", "")
                for t in shape.split():
                    all_pts.append([float(c) for c in t.split(",")[:2]])
        if all_pts:
            cx = round(sum(p[0] for p in all_pts) / len(all_pts), 2)
            cy = round(sum(p[1] for p in all_pts) / len(all_pts), 2)
            parts = base.split("_")
            st1 = parts[1] if len(parts) > 1 else "Corridor"
            st2 = parts[2] if len(parts) > 2 else "Corridor"
            track_features.append({
                "id": base,
                "type": "crossover",
                "name": f"{st1} ↔ {st2} High-Speed Crossover Zone",
                "x": cx,
                "y": cy,
                "speed_kmh": round(max_speed, 1),
                "lane_count": len(edges),
                "description": f"High-speed diamond crossover zone connecting bidirectional tracks ({round(max_speed)} km/h)"
            })

    # B. Express Thru Bypasses and Passing Loops
    loop_groups: Dict[str, List[Any]] = {}
    for e in net_root.findall("edge"):
        eid = e.get("id", "")
        if ("thru" in eid.lower() or "pocket" in eid.lower() or "siding" in eid.lower()) and not eid.startswith(":"):
            m = re.match(r"^([^_]+_[^_]+)_(thru|pocket|siding)", eid)
            base = m.group(1) + "_" + m.group(2) if m else eid
            loop_groups.setdefault(base, []).append(e)

    for base, edges in sorted(loop_groups.items()):
        all_pts = []
        max_speed = 0.0
        is_thru = "thru" in base
        for e in edges:
            for l in e.findall("lane"):
                max_speed = max(max_speed, float(l.get("speed", 0.0)) * 3.6)
                shape = l.get("shape", "")
                for t in shape.split():
                    all_pts.append([float(c) for c in t.split(",")[:2]])
        if all_pts:
            cx = round(sum(p[0] for p in all_pts) / len(all_pts), 2)
            cy = round(sum(p[1] for p in all_pts) / len(all_pts), 2)
            ft_type = "express_thru" if is_thru else "passing_loop"
            clean_name = base.replace("_", " ") + (" Bypass Lines" if is_thru else " Siding Pocket")
            track_features.append({
                "id": base,
                "type": ft_type,
                "name": clean_name,
                "x": cx,
                "y": cy,
                "speed_kmh": round(max_speed, 1),
                "lane_count": len(edges),
                "description": f"Express non-stopping bypass corridor ({round(max_speed)} km/h)" if is_thru else f"Overtaking siding and train holding bay ({round(max_speed)} km/h)"
            })

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
        "signals_count": len(signals),
        "buffer_stops_count": len(buffer_stops),
        "buffer_stops": buffer_stops,
        "signals": signals,
        "track_features": track_features,
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
