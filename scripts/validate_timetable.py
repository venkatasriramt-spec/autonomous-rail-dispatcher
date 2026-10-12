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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_to_sumo import service_runs_on_day, normalize_day, SUPPORTED_DAYS

TRAINS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(TRAINS_DIR, "data")
SUMO_CONFIG_DIR = os.path.join(TRAINS_DIR, "sumo_config")
NET_FILE = os.environ.get(
    "TRACKS_NET_FILE",
    "/home/venkatasriramt/Desktop/tracks/network_data/dense_network.net.xml"
)
ROU_FILE = os.path.join(SUMO_CONFIG_DIR, "trains.rou.xml")
TIMETABLE_FILE = os.path.join(DATA_DIR, "timetable.json")
ROLLING_STOCK_FILE = os.path.join(DATA_DIR, "rolling_stock_types.json")


def load_network_edges(net_file=None):
    """Loads length and max speed for all non-internal edges in the network."""
    if net_file is None:
        net_file = NET_FILE
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


def validate_timetable(net_file=None, rou_file=None, day=None, tolerance_km=0.05, max_discrepancy_km=1.0, verbose=False):
    if net_file is None:
        net_file = NET_FILE
    if rou_file is None:
        rou_file = ROU_FILE

    if not os.path.exists(rou_file):
        print(f"Error: Route file {rou_file} not found. Run export_to_sumo.py first.")
        return False

    if not os.path.exists(net_file):
        print(f"Error: Network file {net_file} not found.")
        return False

    edge_map = load_network_edges(net_file)

    with open(ROLLING_STOCK_FILE, "r", encoding="utf-8") as f:
        rs_types = json.load(f)

    with open(TIMETABLE_FILE, "r", encoding="utf-8") as f:
        timetable = json.load(f)

    unfiltered_tt_ids = {f"train_{s['train_number']}_{s['service_class']}" for s in timetable}

    if day:
        norm_day = normalize_day(day)
        if norm_day not in SUPPORTED_DAYS:
            raise ValueError(f"Invalid operating day '{day}'. Supported days: {', '.join(SUPPORTED_DAYS)}")
        if norm_day not in ("all", "composite"):
            timetable = [s for s in timetable if service_runs_on_day(s, norm_day)]

    tt_map = {f"train_{s['train_number']}_{s['service_class']}": s for s in timetable}

    rou_tree = ET.parse(rou_file)
    vehicles = rou_tree.getroot().findall("vehicle")

    missing_routes = []
    unmatched_vehicles = []
    unknown_edges = []
    checked_services = set()

    tmin_violations = []
    dist_violations = []
    severe_dist_violations = []
    audited_services_count = 0

    print("=" * 75)
    print("AUDITING TIMETABLE FEASIBILITY AGAINST PHYSICAL NETWORK")
    print("=" * 75)
    print(f"Network file:             {net_file}")
    print(f"Route file:               {rou_file}")
    if day:
        print(f"Day filter:               {day} ({len(timetable)} matching services)")
    print(f"Total timetable services: {len(timetable)}")
    print(f"Total compiled vehicles:  {len(vehicles)}")
    print(f"Distance tolerance:       <= {tolerance_km} km (strict limit: <= {max_discrepancy_km} km)")
    print("-" * 75)

    for v in vehicles:
        vid = v.attrib["id"]
        vtype = v.attrib.get("type", "")
        rs_info = rs_types.get(vtype)
        vmax = rs_info["max_speed_ms"] if rs_info else 55.56

        if vid not in tt_map:
            if vid in unfiltered_tt_ids:
                # Skip vehicle belonging to known service excluded from the selected day
                continue
            unmatched_vehicles.append(vid)
            continue

        route_elem = v.find("route")
        if route_elem is None:
            missing_routes.append(vid)
            continue

        svc = tt_map[vid]
        checked_services.add(vid)

        edges = route_elem.attrib["edges"].split()
        missing_edge_list = [e for e in edges if e not in edge_map]
        if missing_edge_list:
            unknown_edges.append({
                "id": vid,
                "train_no": svc["train_number"],
                "missing_edges": missing_edge_list
            })
            continue

        route_len_m = sum(edge_map[e][0] for e in edges)
        edge_time = sum(edge_map[e][0] / min(edge_map[e][1], vmax) for e in edges)
        dwell_time = sum(float(s.attrib.get("duration", 0)) for s in v.findall("stop"))
        t_min = edge_time + dwell_time

        dep_sec = svc["stops"][0]["departure_sec"]
        arr_sec = svc["stops"][-1]["arrival_sec"]
        planned_duration = arr_sec - dep_sec

        audited_services_count += 1

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

    unrouted_services = [s_id for s_id in tt_map if s_id not in checked_services]

    print("Vehicle and Route Integrity:")
    if missing_routes:
        print(f"  [FAIL] {len(missing_routes)} / {len(vehicles)} vehicles lack a <route> element!")
        for vid in missing_routes[:5]:
            print(f"    - Vehicle {vid}")
    else:
        print(f"  [PASS] All {len(vehicles)} vehicles have compiled route elements.")

    if unmatched_vehicles:
        print(f"  [FAIL] {len(unmatched_vehicles)} / {len(vehicles)} vehicles lack timetable matches!")
        for vid in unmatched_vehicles[:5]:
            print(f"    - Vehicle {vid}")
    else:
        print(f"  [PASS] All {len(vehicles)} compiled vehicles match timetable services.")

    if unknown_edges:
        print(f"  [FAIL] {len(unknown_edges)} / {len(vehicles)} vehicles contain edges absent from edge_map!")
        for ue in unknown_edges[:5]:
            print(f"    - Vehicle {ue['id']}: missing edges {ue['missing_edges']}")
    else:
        print(f"  [PASS] All route edges present in network edge map.")

    if unrouted_services:
        print(f"  [FAIL] {len(unrouted_services)} / {len(tt_map)} timetable services have no compiled vehicle!")
        for s_id in unrouted_services[:5]:
            print(f"    - Timetable service {s_id}")
        if len(unrouted_services) > 5:
            print(f"    ... and {len(unrouted_services) - 5} more")
    else:
        print(f"  [PASS] All {len(tt_map)} timetable services have compiled vehicles.")

    print(f"\nPhysical Runtime (T_planned >= T_min):")
    if tmin_violations:
        print(f"  [FAIL] {len(tmin_violations)} / {audited_services_count} services violate theoretical lower bound T_min!")
        for v in tmin_violations[:5]:
            print(f"    - Service {v['train_no']} ({v['class']}, {v['corridor']}): planned {v['planned']:.1f}s < T_min {v['t_min']:.1f}s (deficit: {v['deficit']:.1f}s)")
        if len(tmin_violations) > 5:
            print(f"    ... and {len(tmin_violations) - 5} more")
    else:
        print(f"  [PASS] All {audited_services_count} audited services satisfy T_planned >= T_min (0 violations)!")

    print(f"\nDistance Accuracy (|declared - route_len| <= {tolerance_km} km):")
    if dist_violations:
        print(f"  [FAIL] {len(dist_violations)} / {audited_services_count} services exceed distance tolerance of {tolerance_km} km!")
        print(f"  [FAIL] {len(severe_dist_violations)} services have severe discrepancy > {max_discrepancy_km} km!")
        for d in dist_violations[:5]:
            print(f"    - Service {d['train_no']} ({d['class']}, {d['corridor']}): declared {d['declared']:.2f} km vs actual {d['actual']:.2f} km (diff: {d['diff']:.2f} km)")
        if len(dist_violations) > 5:
            print(f"    ... and {len(dist_violations) - 5} more")
    else:
        print(f"  [PASS] All {audited_services_count} audited services match compiled route lengths within <= {tolerance_km} km (0 violations)!")

    print("=" * 75)
    success = (
        len(tmin_violations) == 0
        and len(severe_dist_violations) == 0
        and len(dist_violations) == 0
        and len(missing_routes) == 0
        and len(unmatched_vehicles) == 0
        and len(unknown_edges) == 0
        and len(unrouted_services) == 0
    )
    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate timetable physical feasibility and distances.")
    parser.add_argument("--net", type=str, default=NET_FILE, help="Path to network file (defaults to TRACKS_NET_FILE env or standard dense_network.net.xml)")
    parser.add_argument("--rou", type=str, default=ROU_FILE, help="Path to compiled routes file (defaults to trains.rou.xml)")
    parser.add_argument("--day", type=str, default=None, help="Operating day filter (e.g. Mon, Wed, Sat, all)")
    parser.add_argument("--tolerance", type=float, default=0.05, help="Tolerance for distance discrepancy in km")
    parser.add_argument("--max-discrepancy", type=float, default=1.0, help="Severe discrepancy threshold in km")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output")
    args = parser.parse_args()

    ok = validate_timetable(
        net_file=args.net,
        rou_file=args.rou,
        day=args.day,
        tolerance_km=args.tolerance,
        max_discrepancy_km=args.max_discrepancy,
        verbose=args.verbose
    )
    sys.exit(0 if ok else 1)
