#!/usr/bin/env python3
"""
verify_simulation.py
Runs a headless SUMO railway simulation to independently verify:
1. Railway safety: 0 collisions, 0 teleports/deadlocks, 0 fatal simulator errors.
2. Service completeness: all scheduled trains are inserted and successfully arrive.
3. Trip representation: every expected trip is represented exactly once without duplicates.
4. Timetable schedule adherence: compares actual simulated arrival times against
   planned timetable arrival times and verifies punctuality.
"""

import subprocess
import os
import sys
import json
import argparse
import tempfile
import collections
import xml.etree.ElementTree as ET

TRAINS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(TRAINS_DIR, "data")
SUMO_CONFIG_DIR = os.path.join(TRAINS_DIR, "sumo_config")
SUMOCFG = os.path.join(SUMO_CONFIG_DIR, "train_simulation.sumocfg")
ROU_FILE = os.path.join(SUMO_CONFIG_DIR, "trains.rou.xml")
TIMETABLE_FILE = os.path.join(DATA_DIR, "timetable.json")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_to_sumo import compile_sumo_files, service_runs_on_day, normalize_day, SUPPORTED_DAYS


def run_verification(max_steps=86400, day="all", delay_tolerance_sec=300.0, verbose=False):
    if not os.path.exists(SUMOCFG):
        print(f"[!] Error: SUMO configuration file not found at {SUMOCFG}")
        return False
    if not os.path.exists(ROU_FILE):
        print(f"[!] Error: Routes file not found at {ROU_FILE}. Run export_to_sumo.py first.")
        return False
    if not os.path.exists(TIMETABLE_FILE):
        print(f"[!] Error: Timetable file not found at {TIMETABLE_FILE}")
        return False

    with open(TIMETABLE_FILE, "r", encoding="utf-8") as f:
        full_timetable = json.load(f)

    norm_day = normalize_day(day)
    if norm_day not in SUPPORTED_DAYS:
        print(f"[!] Error: Invalid day '{day}'. Supported days: {', '.join(SUPPORTED_DAYS)}")
        return False

    if norm_day in ("all", "composite"):
        target_timetable = full_timetable
        day_label = "Composite (All Days)"
    else:
        target_timetable = [s for s in full_timetable if service_runs_on_day(s, norm_day)]
        day_label = norm_day

    expected_services = {
        f"train_{s['train_number']}_{s['service_class']}": s
        for s in target_timetable
    }

    # Inspect compiled routes
    try:
        rou_tree = ET.parse(ROU_FILE)
        compiled_vehicle_elements = rou_tree.getroot().findall("vehicle")
        compiled_vehicle_ids = [v.attrib["id"] for v in compiled_vehicle_elements]
    except Exception as e:
        print(f"[!] Error parsing routes file {ROU_FILE}: {e}")
        return False

    compiled_counts = collections.Counter(compiled_vehicle_ids)
    duplicate_compiled = [vid for vid, count in compiled_counts.items() if count > 1]

    # Create temporary tripinfo file
    tripinfo_fd, tripinfo_path = tempfile.mkstemp(prefix="sumo_tripinfo_", suffix=".xml")
    os.close(tripinfo_fd)

    print("=" * 75)
    print("SUMO RAILWAY SIMULATION AUDIT & SAFETY VERIFICATION")
    print("=" * 75)
    print(f"Config File:          {SUMOCFG}")
    print(f"Routes File:          {ROU_FILE}")
    print(f"Operating Schedule:   {day_label} ({len(expected_services)} scheduled services)")
    print(f"Compiled Vehicles:    {len(compiled_vehicle_ids)} in route file")
    print(f"Simulation Horizon:   {max_steps} seconds ({max_steps / 3600:.1f} hours)")
    print(f"Punctuality Limit:    <= {delay_tolerance_sec:.1f}s arrival delay")
    print("-" * 75)

    cmd = [
        "sumo",
        "-c", SUMOCFG,
        "--end", str(max_steps),
        "--collision.action", "warn",
        "--duration-log.statistics", "true",
        "--no-step-log", "true",
        "--tripinfo-output", tripinfo_path,
        "--tripinfo-output.write-unfinished", "true"
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:
        print(f"[!] Failed to execute SUMO binary: {e}")
        if os.path.exists(tripinfo_path):
            os.remove(tripinfo_path)
        return False

    stderr_lines = res.stderr.splitlines()

    # 1. Safety audit: collisions, teleports, errors
    collision_warnings = [line.strip() for line in stderr_lines if "collision" in line.lower()]
    teleport_warnings = [line.strip() for line in stderr_lines if "teleport" in line.lower()]
    fatal_errors = [line.strip() for line in stderr_lines if "error:" in line.lower()]
    emergency_brakes = [line.strip() for line in stderr_lines if "emergency braking" in line.lower()]

    # 2. Tripinfo parsing: completion, arrival, duplicates
    tripinfos = []
    if os.path.exists(tripinfo_path):
        try:
            tree = ET.parse(tripinfo_path)
            tripinfos = tree.getroot().findall("tripinfo")
        except Exception as e:
            print(f"[!] Warning: failed to parse tripinfo XML: {e}")

    tripinfo_counts = collections.Counter(t.attrib.get("id") for t in tripinfos)
    duplicate_trips = [vid for vid, count in tripinfo_counts.items() if count > 1]

    arrived_trips = {}
    unfinished_trips = {}
    for t in tripinfos:
        vid = t.attrib.get("id", "")
        arr_val = float(t.attrib.get("arrival", -1.0))
        vaporized = t.attrib.get("vaporized", "")
        if arr_val >= 0.0 and not vaporized:
            arrived_trips[vid] = t
        else:
            unfinished_trips[vid] = t

    # Expected within simulation time window
    expected_in_window = {
        vid: s for vid, s in expected_services.items()
        if (s["stops"][0].get("departure_sec", s.get("departure_sec", 0))) < max_steps
    }
    expected_arrived = {
        vid: s for vid, s in expected_services.items()
        if s["stops"][-1].get("arrival_sec", 0) <= max_steps
    }

    if max_steps >= 86400:
        uninserted_services = [vid for vid in expected_services if vid not in tripinfo_counts]
        missing_arrived = [vid for vid in expected_services if vid not in arrived_trips]
    else:
        uninserted_services = [vid for vid in expected_in_window if vid not in tripinfo_counts]
        missing_arrived = [vid for vid in expected_arrived if vid not in arrived_trips]

    unexpected_trips = [vid for vid in tripinfo_counts if vid not in expected_services]

    # 3. Schedule adherence and punctuality
    punctuality_results = []
    excessive_delays = []
    for vid, t in arrived_trips.items():
        if vid in expected_services:
            svc = expected_services[vid]
            sched_arr = float(svc["stops"][-1]["arrival_sec"])
            sim_arr = float(t.attrib["arrival"])
            diff = sim_arr - sched_arr
            time_loss = float(t.attrib.get("timeLoss", 0.0))
            depart_delay = float(t.attrib.get("departDelay", 0.0))
            punctuality_results.append({
                "id": vid,
                "train_no": svc["train_number"],
                "class": svc["service_class"],
                "corridor": svc.get("corridor", "N/A"),
                "sched_arr": sched_arr,
                "sim_arr": sim_arr,
                "diff": diff,
                "time_loss": time_loss,
                "depart_delay": depart_delay
            })
            if diff > delay_tolerance_sec:
                excessive_delays.append(punctuality_results[-1])

    # Clean up temporary tripinfo file
    if os.path.exists(tripinfo_path):
        os.remove(tripinfo_path)

    # ------------------ PRINT AUDIT REPORT ------------------
    print("\n1. RAILWAY SAFETY & INCIDENT AUDIT:")
    if collision_warnings:
        print(f"  [FAIL] {len(collision_warnings)} collision warning(s) detected during simulation!")
        for c in collision_warnings[:5]:
            print(f"    - {c}")
    else:
        print("  [PASS] 0 collisions detected (clean train movements).")

    if teleport_warnings:
        print(f"  [FAIL] {len(teleport_warnings)} teleport warning(s) detected (deadlocks/gridlock)!")
        for tp in teleport_warnings[:5]:
            print(f"    - {tp}")
    else:
        print("  [PASS] 0 teleports or deadlocks detected.")

    if fatal_errors:
        print(f"  [FAIL] {len(fatal_errors)} fatal simulator error(s) encountered!")
        for err in fatal_errors[:5]:
            print(f"    - {err}")
    else:
        print("  [PASS] 0 fatal simulator errors.")

    if emergency_brakes and verbose:
        print(f"  [INFO] {len(emergency_brakes)} emergency braking warning(s) recorded in logs.")

    print("\n2. SERVICE COMPLETION & REPRESENTATION AUDIT:")
    print(f"  Scheduled Services:  {len(expected_services)} for {day_label}")
    print(f"  Expected in Window:  {len(expected_in_window)} scheduled to depart <= {max_steps}s")
    print(f"  Expected to Arrive:  {len(expected_arrived)} scheduled to arrive <= {max_steps}s")
    print(f"  Simulated Inserted:  {len(tripinfos)} trips")
    print(f"  Successfully Arrived:{len(arrived_trips)} trips")
    if unfinished_trips:
        print(f"  Unfinished/Stalled:  {len(unfinished_trips)} trips")

    if duplicate_compiled:
        print(f"  [FAIL] Duplicate vehicle IDs found in routes file: {duplicate_compiled[:5]}")
    else:
        print("  [PASS] Route file contains no duplicate vehicle IDs.")

    if duplicate_trips:
        print(f"  [FAIL] Duplicate vehicle trip entries detected in simulation: {duplicate_trips[:5]}")
    else:
        print("  [PASS] Every trip simulated was represented exactly once.")

    if unexpected_trips:
        print(f"  [FAIL] {len(unexpected_trips)} unexpected vehicle trip(s) not in scheduled timetable: {unexpected_trips[:5]}")
    else:
        print("  [PASS] All simulated vehicles correspond to expected timetable services.")

    if uninserted_services:
        print(f"  [FAIL] {len(uninserted_services)} scheduled service(s) were never inserted into the simulation!")
        for u in uninserted_services[:5]:
            print(f"    - Missing service: {u}")
    else:
        print(f"  [PASS] All {len(expected_in_window)} in-window scheduled services were inserted.")

    if missing_arrived:
        print(f"  [FAIL] {len(missing_arrived)} service(s) failed to arrive at destination by end of window!")
        for m in missing_arrived[:5]:
            print(f"    - Incomplete service: {m}")
    else:
        print(f"  [PASS] All {len(expected_arrived)} expected services completed and arrived at destination.")

    if unfinished_trips and max_steps >= 86400:
        print(f"  [FAIL] {len(unfinished_trips)} train(s) were still running or stalled at simulation end:")
        for uf_id, uf_t in list(unfinished_trips.items())[:5]:
            print(f"    - {uf_id}: duration={uf_t.attrib.get('duration')}s, timeLoss={uf_t.attrib.get('timeLoss')}s")
    elif unfinished_trips:
        print(f"  [INFO] {len(unfinished_trips)} train(s) still in transit at partial simulation cutoff ({max_steps}s).")

    print("\n3. TIMETABLE SCHEDULE ADHERENCE & PUNCTUALITY:")
    if punctuality_results:
        diffs = [p["diff"] for p in punctuality_results]
        max_delay = max(diffs)
        max_advance = min(diffs)
        avg_diff = sum(diffs) / len(diffs)
        on_time_60s = sum(1 for d in diffs if abs(d) <= 60.0)
        on_time_180s = sum(1 for d in diffs if abs(d) <= 180.0)
        total_p = len(punctuality_results)

        worst_delay_svc = max(punctuality_results, key=lambda p: p["diff"])
        worst_advance_svc = min(punctuality_results, key=lambda p: p["diff"])

        print(f"  Audited Arrived Trains:  {total_p}")
        print(f"  On-time (within ±60s):   {on_time_60s} / {total_p} ({on_time_60s / total_p * 100:.1f}%)")
        print(f"  On-time (within ±180s):  {on_time_180s} / {total_p} ({on_time_180s / total_p * 100:.1f}%)")
        print(f"  Mean Arrival Offset:     {avg_diff:+.1f}s")
        print(f"  Max Arrival Delay:       {max_delay:+.1f}s ({worst_delay_svc['id']}, Corridor {worst_delay_svc['corridor']})")
        print(f"  Max Arrival Advance:     {max_advance:+.1f}s ({worst_advance_svc['id']}, Corridor {worst_advance_svc['corridor']})")

        if excessive_delays:
            print(f"  [FAIL] {len(excessive_delays)} train(s) exceeded punctuality delay tolerance of {delay_tolerance_sec:.1f}s:")
            for ed in excessive_delays[:5]:
                print(f"    - Service {ed['train_no']} ({ed['class']}): delayed by {ed['diff']:+.1f}s (sim: {ed['sim_arr']:.1f}s vs sched: {ed['sched_arr']:.1f}s)")
        else:
            print(f"  [PASS] All {total_p} arrived trains adhered to timetable within <= {delay_tolerance_sec:.1f}s delay tolerance.")

        if verbose:
            print("\n  Top 10 Arrival Discrepancies:")
            sorted_by_abs = sorted(punctuality_results, key=lambda p: abs(p["diff"]), reverse=True)
            for p in sorted_by_abs[:10]:
                print(f"    - {p['id']} ({p['class']}): sched={p['sched_arr']:.1f}s, sim={p['sim_arr']:.1f}s, delta={p['diff']:+.1f}s, timeLoss={p['time_loss']:.1f}s")
    else:
        print("  [INFO] No completed trips in this simulation window to audit punctuality.")

    print("=" * 75)

    success = (
        res.returncode == 0
        and len(fatal_errors) == 0
        and len(collision_warnings) == 0
        and len(teleport_warnings) == 0
        and len(duplicate_compiled) == 0
        and len(duplicate_trips) == 0
        and len(unexpected_trips) == 0
        and len(uninserted_services) == 0
        and len(missing_arrived) == 0
        and (len(unfinished_trips) == 0 if max_steps >= 86400 else True)
        and len(excessive_delays) == 0
    )

    if success:
        print("[OK] SIMULATION VERIFICATION PASSED (All railway safety & timetable criteria met)")
    else:
        print("[FAIL] SIMULATION VERIFICATION FAILED (One or more safety/performance checks failed)")

    return success


def verify_day(day, max_steps=86400, delay_tolerance_sec=300.0, verbose=False):
    print(f"\n>>> Compiling SUMO files for: {day} <<<")
    try:
        ok = compile_sumo_files(day=day)
    except Exception as e:
        print(f"[!] Route compilation failed with exception: {e}")
        return False

    if not ok:
        print(f"[!] Route compilation failed for day '{day}'. Stopping verification before running SUMO.")
        return False

    return run_verification(max_steps=max_steps, day=day, delay_tolerance_sec=delay_tolerance_sec, verbose=verbose)


def verify_all_days(max_steps=86400, delay_tolerance_sec=300.0, verbose=False):
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "all"]
    results = {}
    print("=" * 75)
    print("RUNNING FULL MULTI-DAY OPERATING SCHEDULE VERIFICATION")
    print("=" * 75)
    for d in days:
        print(f"\n==================== Verifying {d.upper()} ====================")
        success = verify_day(d, max_steps=max_steps, delay_tolerance_sec=delay_tolerance_sec, verbose=verbose)
        results[d] = success

    # Restore composite schedule
    try:
        compile_sumo_files(day="all")
    except Exception as e:
        print(f"[!] Warning: failed to recompile composite schedule: {e}")

    print("\n" + "=" * 75)
    print("MULTI-DAY VERIFICATION SUMMARY")
    print("=" * 75)
    all_ok = True
    for d, ok in results.items():
        status = "PASSED" if ok else "FAILED"
        print(f"  Day {d:5s}: {status}")
        if not ok:
            all_ok = False
    print("=" * 75)
    if all_ok:
        print("[OK] ALL OPERATING DAYS PASSED COMPREHENSIVE VERIFICATION")
    else:
        print("[FAIL] ONE OR MORE OPERATING DAYS FAILED VERIFICATION")
    return all_ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verify SUMO railway network simulation runs cleanly with full safety, completion, and timetable adherence checks."
    )
    parser.add_argument(
        "steps",
        nargs="?",
        type=int,
        default=None,
        help="Max simulation steps in seconds (default: 86400 for full-day verification)"
    )
    parser.add_argument(
        "-d", "--day",
        type=str,
        default=None,
        help="Compile and verify a specific operating day (Mon, Tue, Wed, Thu, Fri, Sat, Sun, all)"
    )
    parser.add_argument(
        "--all-days",
        action="store_true",
        help="Compile and verify all 7 operating days and the composite schedule"
    )
    parser.add_argument(
        "--delay-tolerance",
        type=float,
        default=300.0,
        help="Maximum allowed arrival delay in seconds before failing (default: 300.0s / 5 minutes)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose per-service arrival delays and details"
    )
    args = parser.parse_args()

    steps = args.steps if args.steps is not None else 86400

    if args.all_days:
        ok = verify_all_days(max_steps=steps, delay_tolerance_sec=args.delay_tolerance, verbose=args.verbose)
        sys.exit(0 if ok else 1)
    elif args.day:
        ok = verify_day(args.day, max_steps=steps, delay_tolerance_sec=args.delay_tolerance, verbose=args.verbose)
        sys.exit(0 if ok else 1)
    else:
        ok = run_verification(max_steps=steps, day="all", delay_tolerance_sec=args.delay_tolerance, verbose=args.verbose)
        sys.exit(0 if ok else 1)
