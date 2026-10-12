#!/usr/bin/env python3
"""
validate_timetable.py
Validates the railway timetable against the physical compiled SUMO network and routes.

Audits every service for:
1. Physical runtime feasibility:
   T_min = sum(L_i / min(v_i, v_train)) + sum(D_j)
   Asserts that planned journey time T_planned >= T_min.
2. Distance consistency:
   Asserts that declared timetable distance (total_distance_km) matches compiled route length
   within a strict tolerance (|declared - route_len| <= 0.05 km, and strictly no discrepancy > 1.0 km).
"""

import os
import sys
import json
import argparse
import xml.etree.ElementTree as ET

TRAINS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(TRAINS_DIR, "data")
SUMO_CONFIG_DIR = os.path.join(TRAINS_DIR, "sumo_config")
NET_FILE = "/home/venkatasriramt/Desktop/tracks/network_data/dense_network.net.xml"
ROU_FILE = os.path.join(SUMO_CONFIG_DIR, "trains.rou.xml")
TIMETABLE_FILE = os.path.join(DATA_DIR, "timetable.json")
ROLLING_STOCK_FILE = os.path.join(DATA_DIR, "rolling_stock_types.json")


def load_network_edges(net_file=NET_FILE):
    """Loads length and max speed for all non-internal edges in the network."""
    tree = ET.parse(net_file)
    edge_map = {}
    for edge in tree.getroot().findall("edge"):
        eid = edge.attrib["id"]
        if eid.startswith(":"):
            continue
        lanes = edge.findall("lane")
        if lanes:
            length = float(lanes[0].attrib.get("length", 0.0))
            speed = max(float(l.attrib.get("speed", 0.0)) for l in lanes)
            edge_map[eid] = (length, speed)
    return edge_map


def validate_timetable(tolerance_km=0.05, max_discrepancy_km=1.0, verbose=False):
    if not os.path.exists(ROU_FILE):
        print(f"Error: Route file {ROU_FILE} not found. Run export_to_sumo.py first.")
        return False

    edge_map = load_network_edges(NET_FILE)

    with open(ROLLING_STOCK_FILE, "r", encoding="utf-8") as f:
        rs_types = json.load(f)

    with open(TIMETABLE_FILE, "r", encoding="utf-8") as f:
        timetable = json.load(f)

    tt_map = {f"train_{s['train_number']}_{s['service_class']}": s for s in timetable}

    rou_tree = ET.parse(ROU_FILE)
    vehicles = rou_tree.getroot().findall("vehicle")

    tmin_violations = []
    dist_violations = []
    severe_dist_violations = []

    print("=" * 75)
    print("AUDITING TIMETABLE FEASIBILITY AGAINST PHYSICAL NETWORK")
    print("=" * 75)
    print(f"Total timetable services: {len(timetable)}")
    print(f"Total compiled vehicles:  {len(vehicles)}")
    print(f"Distance tolerance:       <= {tolerance_km} km (strict limit: <= {max_discrepancy_km} km)")
    print("-" * 75)

    for v in vehicles:
        vid = v.attrib["id"]
        vtype = v.attrib["type"]
        vmax = rs_types[vtype]["max_speed_ms"]

        route_elem = v.find("route")
        if route_elem is None:
            continue
        edges = route_elem.attrib["edges"].split()

        route_len_m = sum(edge_map[e][0] for e in edges if e in edge_map)
        edge_time = sum(edge_map[e][0] / min(edge_map[e][1], vmax) for e in edges if e in edge_map)
        dwell_time = sum(float(s.attrib.get("duration", 0)) for s in v.findall("stop"))
        t_min = edge_time + dwell_time

        svc = tt_map.get(vid)
        if not svc:
            continue

        dep_sec = svc["stops"][0]["departure_sec"]
        arr_sec = svc["stops"][-1]["arrival_sec"]
        planned_duration = arr_sec - dep_sec

        route_len_km = route_len_m / 1000.0
        declared_km = float(svc["total_distance_km"])
        dist_diff_km = abs(declared_km - route_len_km)

        # Check T_min feasibility
        if planned_duration < t_min - 1e-3:
            tmin_violations.append({
                "id": vid,
                "train_no": svc["train_number"],
                "class": svc["service_class"],
                "corridor": svc.get("corridor"),
                "planned": planned_duration,
                "t_min": t_min,
                "deficit": t_min - planned_duration
            })

        # Check distance consistency
        if dist_diff_km > tolerance_km:
            dist_violations.append({
                "id": vid,
                "train_no": svc["train_number"],
                "class": svc["service_class"],
                "corridor": svc.get("corridor"),
                "declared": declared_km,
                "actual": route_len_km,
                "diff": dist_diff_km
            })
            if dist_diff_km > max_discrepancy_km:
                severe_dist_violations.append(vid)

    print(f"Physical Runtime (T_planned >= T_min):")
    if tmin_violations:
        print(f"  [FAIL] {len(tmin_violations)} / {len(vehicles)} services violate theoretical lower bound T_min!")
        for v in tmin_violations[:5]:
            print(f"    - Service {v['train_no']} ({v['class']}, {v['corridor']}): planned {v['planned']:.1f}s < T_min {v['t_min']:.1f}s (deficit: {v['deficit']:.1f}s)")
        if len(tmin_violations) > 5:
            print(f"    ... and {len(tmin_violations) - 5} more")
    else:
        print(f"  [PASS] All {len(vehicles)} services satisfy T_planned >= T_min (0 violations)!")

    print(f"\nDistance Accuracy (|declared - route_len| <= {tolerance_km} km):")
    if dist_violations:
        print(f"  [FAIL] {len(dist_violations)} / {len(vehicles)} services exceed distance tolerance of {tolerance_km} km!")
        print(f"  [FAIL] {len(severe_dist_violations)} services have severe discrepancy > {max_discrepancy_km} km!")
        for d in dist_violations[:5]:
            print(f"    - Service {d['train_no']} ({d['class']}, {d['corridor']}): declared {d['declared']:.2f} km vs actual {d['actual']:.2f} km (diff: {d['diff']:.2f} km)")
        if len(dist_violations) > 5:
            print(f"    ... and {len(dist_violations) - 5} more")
    else:
        print(f"  [PASS] All {len(vehicles)} services match compiled route lengths within <= {tolerance_km} km (0 violations)!")

    print("=" * 75)
    success = (len(tmin_violations) == 0) and (len(severe_dist_violations) == 0) and (len(dist_violations) == 0)
    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate timetable physical feasibility and distances.")
    parser.add_argument("--tolerance", type=float, default=0.05, help="Tolerance for distance discrepancy in km")
    parser.add_argument("--max-discrepancy", type=float, default=1.0, help="Severe discrepancy threshold in km")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output")
    args = parser.parse_args()

    ok = validate_timetable(tolerance_km=args.tolerance, max_discrepancy_km=args.max_discrepancy, verbose=args.verbose)
    sys.exit(0 if ok else 1)
