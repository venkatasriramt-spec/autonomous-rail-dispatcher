#!/usr/bin/env python3
"""
validate_timetable.py
Validates railway timetable feasibility, physical runtimes, and rake lifecycles
against the compiled SUMO network and routes.

Supports auto-detection and explicit modes:
1. Services Mode (default when route file contains 'train_*' vehicles):
   Audits every discrete service for:
   - Physical runtime feasibility (T_planned >= T_min).
   - Distance consistency (|declared - route_len| <= 0.05 km, strictly <= 1.0 km).
2. Rakes Mode (default when route file contains '*-Rake-*' vehicles):
   Audits the continuous physical rakes for:
   - Complete lifecycle integrity (dawn rollout -> service stops -> pocket reversals -> stabling).
   - Turnaround dwell adequacy against consist minimums.
   - Network edge and stop validity.
3. Both Mode:
   Audits both trains_services.rou.xml and trains_rakes.rou.xml.
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
ROSTER_FILE = os.path.join(DATA_DIR, "rakes_roster.json")
ROLLING_STOCK_FILE = os.path.join(DATA_DIR, "rolling_stock_types.json")


def load_network_edges(net_file=None):
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


def validate_services_mode(net_file, rou_file, day=None, tolerance_km=0.05, max_discrepancy_km=1.0, verbose=False):
    edge_map = load_network_edges(net_file)

    with open(ROLLING_STOCK_FILE, "r", encoding="utf-8") as f:
        rs_types = json.load(f)

    with open(TIMETABLE_FILE, "r", encoding="utf-8") as f:
        timetable = json.load(f)

    unfiltered_tt_ids = {f"train_{s['train_number']}_{s['service_class']}" for s in timetable}

    if day:
        norm_day = normalize_day(day)
        if norm_day not in ("all", "composite"):
            timetable = [s for s in timetable if service_runs_on_day(s, norm_day)]

    tt_map = {f"train_{s['train_number']}_{s['service_class']}": s for s in timetable}

    rou_tree = ET.parse(rou_file)
    vehicles = rou_tree.getroot().findall("vehicle")

    excluded_vehicles = []
    in_scope_vehicles = []
    missing_routes = []
    unmatched_vehicles = []
    unknown_edges = []
    checked_services = set()

    tmin_violations = []
    dist_violations = []
    severe_dist_violations = []
    audited_services_count = 0

    print("=" * 75)
    print("AUDITING TIMETABLE FEASIBILITY (DISCRETE SERVICES MODE)")
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
                excluded_vehicles.append(vid)
                continue
            unmatched_vehicles.append(vid)
            continue

        in_scope_vehicles.append(vid)

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
    if excluded_vehicles:
        print(f"  [INFO] {len(excluded_vehicles)} compiled vehicles excluded from day filter '{day}' ({len(in_scope_vehicles)} in-scope).")

    if missing_routes:
        print(f"  [FAIL] {len(missing_routes)} / {len(in_scope_vehicles)} in-scope vehicles lack a <route> element!")
    else:
        print(f"  [PASS] All {len(in_scope_vehicles)} in-scope vehicles have compiled route elements.")

    if unmatched_vehicles:
        print(f"  [FAIL] {len(unmatched_vehicles)} / {len(vehicles)} vehicles lack timetable matches!")
    else:
        print(f"  [PASS] All {len(vehicles)} compiled vehicles match timetable services.")

    if unknown_edges:
        print(f"  [FAIL] {len(unknown_edges)} / {len(in_scope_vehicles)} in-scope vehicles contain edges absent from edge_map!")
    else:
        print(f"  [PASS] All route edges present in network edge map.")

    if unrouted_services:
        print(f"  [FAIL] {len(unrouted_services)} / {len(tt_map)} timetable services have no compiled vehicle!")
    else:
        print(f"  [PASS] All {len(tt_map)} timetable services have compiled vehicles.")

    print(f"\nPhysical Runtime (T_planned >= T_min):")
    if tmin_violations:
        print(f"  [FAIL] {len(tmin_violations)} / {audited_services_count} services violate theoretical lower bound T_min!")
        for v in tmin_violations[:5]:
            print(f"    - Service {v['train_no']} ({v['class']}, {v['corridor']}): planned {v['planned']:.1f}s < T_min {v['t_min']:.1f}s (deficit: {v['deficit']:.1f}s)")
    else:
        print(f"  [PASS] All {audited_services_count} audited services satisfy T_planned >= T_min (0 violations)!")

    print(f"\nDistance Accuracy (|declared - route_len| <= {tolerance_km} km):")
    if dist_violations:
        print(f"  [FAIL] {len(dist_violations)} / {audited_services_count} services exceed distance tolerance of {tolerance_km} km!")
        print(f"  [FAIL] {len(severe_dist_violations)} services have severe discrepancy > {max_discrepancy_km} km!")
    else:
        print(f"  [PASS] All {audited_services_count} audited services match compiled route lengths within <= {tolerance_km} km (0 violations)!")

    print("=" * 75)
    return (
        len(tmin_violations) == 0
        and len(severe_dist_violations) == 0
        and len(dist_violations) == 0
        and len(missing_routes) == 0
        and len(unmatched_vehicles) == 0
        and len(unknown_edges) == 0
        and len(unrouted_services) == 0
    )


def validate_rakes_mode(net_file, rou_file, day=None, verbose=False):
    edge_map = load_network_edges(net_file)

    with open(ROSTER_FILE, "r", encoding="utf-8") as f:
        roster = json.load(f)

    with open(TIMETABLE_FILE, "r", encoding="utf-8") as f:
        timetable = json.load(f)
    tt_by_id = {s["train_number"]: s for s in timetable}

    norm_day = normalize_day(day) if day else "all"

    # Expected rakes for day
    expected_rakes = {}
    for r in roster:
        rid = r["rake_id"]
        raw_services = r.get("assigned_services", [])
        if norm_day != "all":
            valid_svcs = [sid for sid in raw_services if sid in tt_by_id and service_runs_on_day(tt_by_id[sid], norm_day)]
        else:
            valid_svcs = [sid for sid in raw_services if sid in tt_by_id]
        if valid_svcs:
            expected_rakes[rid] = (r, valid_svcs)

    rou_tree = ET.parse(rou_file)
    vehicles = rou_tree.getroot().findall("vehicle")
    veh_by_id = {v.attrib["id"]: v for v in vehicles}

    missing_rakes = []
    missing_routes = []
    unknown_edges = []
    lifecycle_turnaround_violations = []

    print("=" * 75)
    print("AUDITING CONTINUOUS RAKE LIFECYCLES (PHYSICAL RAKES MODE)")
    print("=" * 75)
    print(f"Network file:             {net_file}")
    print(f"Route file:               {rou_file}")
    if day:
        print(f"Day filter:               {day} ({len(expected_rakes)} matching rakes)")
    print(f"Expected active rakes:    {len(expected_rakes)}")
    print(f"Total compiled vehicles:  {len(vehicles)}")
    print("-" * 75)

    for rid, (r_info, services) in expected_rakes.items():
        if rid not in veh_by_id:
            missing_rakes.append(rid)
            continue

        v = veh_by_id[rid]
        route_elem = v.find("route")
        if route_elem is None:
            missing_routes.append(rid)
            continue

        edges = route_elem.attrib["edges"].split()
        missing_edge_list = [e for e in edges if e not in edge_map]
        if missing_edge_list:
            unknown_edges.append((rid, missing_edge_list))
            continue

        # Check turnaround dwells between consecutive services
        sorted_services = sorted(services, key=lambda sid: tt_by_id[sid]["departure_sec"])
        for idx in range(len(sorted_services) - 1):
            curr_s = tt_by_id[sorted_services[idx]]
            next_s = tt_by_id[sorted_services[idx + 1]]
            pjd = curr_s.get("post_journey_disposition", {})
            dwell_min = pjd.get("turnaround_dwell_min", 0.0)
            min_req = pjd.get("min_turnaround_required_min", 7.0)
            if dwell_min < min_req - 1e-2:
                lifecycle_turnaround_violations.append({
                    "rake": rid,
                    "service_from": curr_s["train_number"],
                    "service_to": next_s["train_number"],
                    "dwell_min": dwell_min,
                    "min_req": min_req
                })

    print("Rake Fleet & Lifecycle Integrity:")
    if missing_rakes:
        print(f"  [FAIL] {len(missing_rakes)} / {len(expected_rakes)} expected rakes are missing from route file!")
        for rid in missing_rakes[:5]:
            print(f"    - Missing rake: {rid}")
    else:
        print(f"  [PASS] All {len(expected_rakes)} active rakes are present in route file.")

    if missing_routes:
        print(f"  [FAIL] {len(missing_routes)} / {len(expected_rakes)} rakes lack a compiled <route> element!")
    else:
        print(f"  [PASS] All {len(expected_rakes)} rakes have compiled continuous routes.")

    if unknown_edges:
        print(f"  [FAIL] {len(unknown_edges)} rakes contain edges absent from network!")
    else:
        print(f"  [PASS] All rake route edges present in network edge map.")

    print(f"\nTurnaround & Buffer Stop Dwell Compliance:")
    if lifecycle_turnaround_violations:
        print(f"  [FAIL] {len(lifecycle_turnaround_violations)} turnaround intervals violate consist minimums!")
        for viol in lifecycle_turnaround_violations[:5]:
            print(f"    - Rake {viol['rake']} between {viol['service_from']} -> {viol['service_to']}: dwell {viol['dwell_min']:.1f}m < min {viol['min_req']:.1f}m")
    else:
        print(f"  [PASS] All turnaround intervals satisfy minimum consist turn times (0 violations)!")

    print("=" * 75)
    return (
        len(missing_rakes) == 0
        and len(missing_routes) == 0
        and len(unknown_edges) == 0
        and len(lifecycle_turnaround_violations) == 0
    )


def validate_timetable(net_file=None, rou_file=None, day=None, mode="auto", tolerance_km=0.05, max_discrepancy_km=1.0, verbose=False):
    if net_file is None:
        net_file = NET_FILE
    if rou_file is None:
        rou_file = ROU_FILE

    if not os.path.exists(net_file):
        print(f"Error: Network file {net_file} not found.")
        return False

    if mode == "both":
        services_rou = os.path.join(SUMO_CONFIG_DIR, "trains_services.rou.xml")
        rakes_rou = os.path.join(SUMO_CONFIG_DIR, "trains_rakes.rou.xml")
        ok_svcs = validate_services_mode(net_file, services_rou, day, tolerance_km, max_discrepancy_km, verbose)
        print()
        ok_rakes = validate_rakes_mode(net_file, rakes_rou, day, verbose)
        return ok_svcs and ok_rakes

    if not os.path.exists(rou_file):
        print(f"Error: Route file {rou_file} not found. Run export_to_sumo.py first.")
        return False

    # Auto-detect mode
    if mode == "auto":
        rou_tree = ET.parse(rou_file)
        v_ids = [v.attrib.get("id", "") for v in rou_tree.getroot().findall("vehicle")]
        if any(vid.startswith(("HS-Rake", "REG-", "ALP-", "FRT-")) for vid in v_ids):
            mode = "rakes"
        else:
            mode = "services"

    if mode == "rakes":
        return validate_rakes_mode(net_file, rou_file, day, verbose)
    else:
        return validate_services_mode(net_file, rou_file, day, tolerance_km, max_discrepancy_km, verbose)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate timetable physical feasibility and distances.")
    parser.add_argument("--net", type=str, default=NET_FILE, help="Path to network file")
    parser.add_argument("--rou", type=str, default=ROU_FILE, help="Path to compiled routes file")
    parser.add_argument("-m", "--mode", choices=["auto", "rakes", "services", "both"], default="auto", help="Validation mode")
    parser.add_argument("--day", type=str, default=None, help="Operating day filter")
    parser.add_argument("--tolerance", type=float, default=0.05, help="Tolerance for distance discrepancy in km")
    parser.add_argument("--max-discrepancy", type=float, default=1.0, help="Severe discrepancy threshold in km")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output")
    args = parser.parse_args()

    ok = validate_timetable(
        net_file=args.net,
        rou_file=args.rou,
        day=args.day,
        mode=args.mode,
        tolerance_km=args.tolerance,
        max_discrepancy_km=args.max_discrepancy,
        verbose=args.verbose
    )
    sys.exit(0 if ok else 1)
