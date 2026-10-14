#!/usr/bin/env python3
"""
verify_simulation.py
Runs a headless SUMO railway simulation to independently verify:
1. Railway safety: 0 collisions, 0 teleports/deadlocks, 0 fatal simulator errors.
2. Fleet/Service completeness: all scheduled entities (continuous rakes or discrete services)
   are inserted and successfully arrive.
3. Entity representation: every expected entity is represented exactly once without duplicates.
4. Timetable schedule adherence: compares actual simulated arrival times against
   planned arrival times and verifies punctuality.
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
ROSTER_FILE = os.path.join(DATA_DIR, "rakes_roster.json")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_to_sumo import compile_sumo_files, service_runs_on_day, normalize_day, SUPPORTED_DAYS


def detect_mode_from_routes(rou_file=ROU_FILE, fallback="rakes"):
    if not os.path.exists(rou_file):
        return fallback
    try:
        rou_tree = ET.parse(rou_file)
        compiled_vehicle_elements = rou_tree.getroot().findall("vehicle")
        compiled_vehicle_ids = [v.attrib["id"] for v in compiled_vehicle_elements]
        if not compiled_vehicle_ids:
            return fallback
        is_rake_mode = any(vid.startswith(("HS-Rake", "REG-", "ALP-", "FRT-")) for vid in compiled_vehicle_ids)
        return "rakes" if is_rake_mode else "services"
    except Exception:
        return fallback


def run_verification(max_steps=86400, day="all", mode="auto", delay_tolerance_sec=300.0, verbose=False):
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

    with open(ROSTER_FILE, "r", encoding="utf-8") as f:
        roster = json.load(f)

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

    # Inspect compiled routes
    try:
        rou_tree = ET.parse(ROU_FILE)
        compiled_vehicle_elements = rou_tree.getroot().findall("vehicle")
        compiled_vehicle_ids = [v.attrib["id"] for v in compiled_vehicle_elements]
    except Exception as e:
        print(f"[!] Error parsing routes file {ROU_FILE}: {e}")
        return False

    rou_vehicles = {v.attrib["id"]: v for v in compiled_vehicle_elements} if compiled_vehicle_elements else {}

    # Auto-detect mode if needed
    if compiled_vehicle_ids:
        is_rake_mode = any(vid.startswith(("HS-Rake", "REG-", "ALP-", "FRT-")) for vid in compiled_vehicle_ids)
        active_mode = "rakes" if (mode == "rakes" or (mode == "auto" and is_rake_mode)) else "services"
    else:
        active_mode = "rakes" if mode in ("rakes", "auto") else "services"

    tt_by_id = {s["train_number"]: s for s in full_timetable}

    if active_mode == "rakes":
        expected_entities = {}
        for r in roster:
            rid = r["rake_id"]
            raw_svcs = r.get("assigned_services", [])
            if norm_day not in ("all", "composite"):
                valid_svcs = [sid for sid in raw_svcs if sid in tt_by_id and service_runs_on_day(tt_by_id[sid], norm_day)]
            else:
                valid_svcs = [sid for sid in raw_svcs if sid in tt_by_id]
            if valid_svcs:
                sorted_svcs = sorted(valid_svcs, key=lambda sid: tt_by_id[sid]["departure_sec"])
                first_s = tt_by_id[sorted_svcs[0]]
                last_s = tt_by_id[sorted_svcs[-1]]
                stabling_track = r.get("overnight_stabling_track")
                dep_sec = max(0.0, first_s["departure_sec"] - 600.0) if (stabling_track and stabling_track != first_s["origin_track"]) else first_s["departure_sec"]
                arr_sec = last_s["arrival_sec"]
                yard_transit_dwell = 0.0
                if stabling_track:
                    if stabling_track != last_s["dest_track"]:
                        yard_transit_dwell = 900.0
                    else:
                        rou_v = rou_vehicles.get(rid)
                        if rou_v is not None:
                            v_stops = rou_v.findall("stop")
                            last_stop_elem = v_stops[-1] if v_stops else None
                            stab_dwell = float(last_stop_elem.attrib.get("duration", 60.0)) if last_stop_elem is not None else 60.0
                        else:
                            stab_dwell = 60.0
                        yard_transit_dwell = stab_dwell
                stabling_completion_sec = arr_sec + yard_transit_dwell
                expected_entities[rid] = {
                    "id": rid,
                    "type": r["rolling_stock_type"],
                    "corridor": first_s.get("corridor", "Fleet"),
                    "departure_sec": dep_sec,
                    "arrival_sec": arr_sec,
                    "stabling_completion_sec": stabling_completion_sec,
                    "services_count": len(sorted_svcs),
                    "dest_train_stop_id": last_s["stops"][-1].get("train_stop_id"),
                    "dest_track": last_s["dest_track"],
                    "stabling_track": stabling_track
                }
    else:
        expected_entities = {
            f"train_{s['train_number']}_{s['service_class']}": {
                "id": f"train_{s['train_number']}_{s['service_class']}",
                "train_no": s["train_number"],
                "class": s["service_class"],
                "corridor": s.get("corridor", "N/A"),
                "departure_sec": s["stops"][0].get("departure_sec", s.get("departure_sec", 0)),
                "arrival_sec": s["stops"][-1].get("arrival_sec", s.get("arrival_sec", 0)),
                "stabling_completion_sec": s["stops"][-1].get("arrival_sec", s.get("arrival_sec", 0)),
                "dest_train_stop_id": s["stops"][-1].get("train_stop_id"),
                "dest_track": s["dest_track"],
                "stabling_track": None
            }
            for s in target_timetable
        }

    expected_services = {
        f"train_{s['train_number']}_{s['service_class']}": {
            "id": f"train_{s['train_number']}_{s['service_class']}",
            "train_no": s["train_number"],
            "class": s["service_class"],
            "corridor": s.get("corridor", "N/A"),
            "departure_sec": s["stops"][0].get("departure_sec", s.get("departure_sec", 0)),
            "arrival_sec": s["stops"][-1].get("arrival_sec", s.get("arrival_sec", 0)),
            "dest_train_stop_id": s["stops"][-1].get("train_stop_id"),
            "dest_track": s["dest_track"]
        }
        for s in target_timetable
    }

    compiled_counts = collections.Counter(compiled_vehicle_ids)
    duplicate_compiled = [vid for vid, count in compiled_counts.items() if count > 1]

    # Create temporary tripinfo and stopinfo files
    tripinfo_fd, tripinfo_path = tempfile.mkstemp(prefix="sumo_tripinfo_", suffix=".xml")
    os.close(tripinfo_fd)
    stopinfo_fd, stopinfo_path = tempfile.mkstemp(prefix="sumo_stopinfo_", suffix=".xml")
    os.close(stopinfo_fd)

    print("=" * 75)
    print(f"SUMO RAILWAY SIMULATION AUDIT & SAFETY VERIFICATION ({active_mode.upper()} MODE)")
    print("=" * 75)
    print(f"Config File:          {SUMOCFG}")
    print(f"Routes File:          {ROU_FILE}")
    print(f"Operating Schedule:   {day_label} ({len(expected_entities)} expected {active_mode})")
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
        "--tripinfo-output.write-unfinished", "true",
        "--stop-output", stopinfo_path,
        "--stop-output.write-unfinished", "true"
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:
        print(f"[!] Failed to execute SUMO binary: {e}")
        if os.path.exists(tripinfo_path):
            os.remove(tripinfo_path)
        if os.path.exists(stopinfo_path):
            os.remove(stopinfo_path)
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

    expected_in_window = {
        vid: ent for vid, ent in expected_entities.items()
        if ent["departure_sec"] < max_steps
    }
    expected_arrived = {
        vid: ent for vid, ent in expected_entities.items()
        if ent.get("stabling_completion_sec", ent["arrival_sec"]) <= max_steps
    }

    uninserted_entities = [vid for vid in expected_in_window if vid not in tripinfo_counts]
    missing_arrived = [vid for vid in expected_arrived if vid not in arrived_trips]

    unfinished_expected = [vid for vid in unfinished_trips if vid in expected_arrived]
    unfinished_beyond_cutoff = [vid for vid in unfinished_trips if vid not in expected_arrived]
    unexpected_trips = [vid for vid in tripinfo_counts if vid not in expected_entities]

    # Parse stopinfo XML for service stop arrivals and final stabling verification
    stops_by_id = collections.defaultdict(list)
    stops_by_tripid = collections.defaultdict(list)
    if os.path.exists(stopinfo_path):
        try:
            stop_tree = ET.parse(stopinfo_path)
            for stp in stop_tree.getroot().findall("stopinfo"):
                stops_by_id[stp.attrib.get("id", "")].append(stp)
                t_id = stp.attrib.get("tripId")
                if t_id:
                    stops_by_tripid[t_id].append(stp)
        except Exception as e:
            print(f"[!] Warning: failed to parse stopinfo XML: {e}")

    # 3. Schedule adherence and punctuality
    punctuality_results = []
    excessive_delays = []
    stabling_violations = []
    yard_results = []

    rou_vehicles = {v.attrib["id"]: v for v in compiled_vehicle_elements} if compiled_vehicle_elements else {}

    if active_mode == "rakes":
        # 3a. Commercial Service Schedule Adherence (evaluates each service independently)
        for s_id, s_ent in expected_services.items():
            if s_ent["departure_sec"] >= max_steps:
                continue
            if s_ent["arrival_sec"] > max_steps:
                continue

            sched_arr = float(s_ent["arrival_sec"])
            dest_ts = s_ent.get("dest_train_stop_id")
            dest_tr = s_ent.get("dest_track")

            svc_stops = stops_by_tripid.get(s_id, [])
            dest_stop = None
            if svc_stops:
                for stp in reversed(svc_stops):
                    if dest_ts and stp.attrib.get("busStop") == dest_ts:
                        dest_stop = stp
                        break
                    elif not dest_ts and dest_tr and (stp.attrib.get("lane", "").startswith(dest_tr) or dest_tr in stp.attrib.get("lane", "")):
                        dest_stop = stp
                        break
                if dest_stop is None:
                    dest_stop = svc_stops[-1]

            if dest_stop is not None:
                sim_arr = float(dest_stop.attrib.get("started"))
                diff = sim_arr - sched_arr
                p_entry = {
                    "id": s_id,
                    "train_no": s_ent["train_no"],
                    "class": s_ent["class"],
                    "corridor": s_ent.get("corridor", "N/A"),
                    "rake_id": dest_stop.attrib.get("id"),
                    "sched_arr": sched_arr,
                    "sim_arr": sim_arr,
                    "diff": diff,
                    "stop_target": dest_stop.attrib.get("busStop") or dest_stop.attrib.get("lane")
                }
                punctuality_results.append(p_entry)
                if diff > delay_tolerance_sec:
                    excessive_delays.append(p_entry)
            else:
                p_entry = {
                    "id": s_id,
                    "train_no": s_ent["train_no"],
                    "class": s_ent["class"],
                    "corridor": s_ent.get("corridor", "N/A"),
                    "rake_id": "missing",
                    "sched_arr": sched_arr,
                    "sim_arr": -1.0,
                    "diff": 999999.0,
                    "stop_target": dest_ts or dest_tr or "N/A"
                }
                excessive_delays.append(p_entry)

        # 3b. Final Stabling & Fleet Recovery Audit (separate, independent test on continuous rakes)
        for vid, t in arrived_trips.items():
            if vid in expected_entities:
                ent = expected_entities[vid]
                stab_tr = ent.get("stabling_track")
                dest_tr = ent.get("dest_track")
                sched_arr = float(ent["arrival_sec"])

                if stab_tr:
                    expected_lane = f"{stab_tr}_0"
                    sim_stops = stops_by_id.get(vid, [])
                    last_sim_stop = sim_stops[-1] if sim_stops else None

                    # Check 1: Exporter's 60-second final stabling stop exists and duration >= 60s
                    if last_sim_stop is None or last_sim_stop.attrib.get("lane") != expected_lane:
                        stabling_violations.append((vid, f"missing stabling stop on {expected_lane}"))
                    else:
                        st_dwell = float(last_sim_stop.attrib.get("ended", 0)) - float(last_sim_stop.attrib.get("started", 0))
                        if round(st_dwell, 1) < 60.0:
                            stabling_violations.append((vid, f"final stabling stop duration {st_dwell:.1f}s < 60s"))

                    # Check 2: Yard arrival adherence (independent of commercial service punctuality)
                    yard_transit_dwell = 0.0
                    if vid in rou_vehicles:
                        v_rou = rou_vehicles[vid]
                        v_stops = v_rou.findall("stop")
                        last_stop_elem = v_stops[-1] if v_stops else None
                        stab_dwell = float(last_stop_elem.attrib.get("duration", 60.0)) if last_stop_elem is not None else 60.0
                        if stab_tr != dest_tr:
                            yard_transit_dwell = 900.0
                        else:
                            yard_transit_dwell = stab_dwell

                    expected_yard_arr = ent.get("stabling_completion_sec", sched_arr + yard_transit_dwell)
                    sim_yard_arr = float(t.attrib["arrival"])
                    yard_diff = sim_yard_arr - expected_yard_arr
                    yard_results.append({
                        "id": vid,
                        "sched_yard": expected_yard_arr,
                        "sim_yard": sim_yard_arr,
                        "yard_diff": yard_diff
                    })
                    if yard_diff > delay_tolerance_sec:
                        stabling_violations.append((vid, f"yard arrival delay {yard_diff:+.1f}s > {delay_tolerance_sec:.1f}s (sim: {sim_yard_arr:.1f}s vs expected: {expected_yard_arr:.1f}s)"))
    else:
        for vid, t in arrived_trips.items():
            if vid in expected_entities:
                ent = expected_entities[vid]
                sched_arr = float(ent["arrival_sec"])
                sim_arr = float(t.attrib["arrival"])
                diff = sim_arr - sched_arr
                time_loss = float(t.attrib.get("timeLoss", 0.0))
                depart_delay = float(t.attrib.get("departDelay", 0.0))
                punctuality_results.append({
                    "id": vid,
                    "train_no": ent["train_no"],
                    "class": ent["class"],
                    "corridor": ent.get("corridor", "N/A"),
                    "sched_arr": sched_arr,
                    "sim_arr": sim_arr,
                    "diff": diff,
                    "time_loss": time_loss,
                    "depart_delay": depart_delay
                })
                if diff > delay_tolerance_sec:
                    excessive_delays.append(punctuality_results[-1])

    if os.path.exists(tripinfo_path):
        os.remove(tripinfo_path)
    if os.path.exists(stopinfo_path):
        os.remove(stopinfo_path)

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

    print(f"\n2. FLEET COMPLETION & REPRESENTATION AUDIT ({active_mode.upper()}):")
    print(f"  Scheduled {active_mode.capitalize()}: {len(expected_entities)} for {day_label}")
    print(f"  Expected in Window:  {len(expected_in_window)} scheduled to depart <= {max_steps}s")
    print(f"  Expected to Arrive:  {len(expected_arrived)} scheduled to arrive <= {max_steps}s")
    print(f"  Simulated Inserted:  {len(tripinfos)} vehicles")
    print(f"  Successfully Arrived:{len(arrived_trips)} vehicles")
    if unfinished_trips:
        print(f"  In Transit/Staging:  {len(unfinished_trips)} vehicles")

    if duplicate_compiled:
        print(f"  [FAIL] Duplicate vehicle IDs found in routes file: {duplicate_compiled[:5]}")
    else:
        print("  [PASS] Route file contains no duplicate vehicle IDs.")

    if duplicate_trips:
        print(f"  [FAIL] Duplicate vehicle trip entries detected in simulation: {duplicate_trips[:5]}")
    else:
        print("  [PASS] Every vehicle simulated was represented exactly once.")

    if unexpected_trips:
        print(f"  [FAIL] {len(unexpected_trips)} unexpected vehicles not in scheduled roster: {unexpected_trips[:5]}")
    else:
        print(f"  [PASS] All simulated vehicles correspond to expected schedule roster.")

    if uninserted_entities:
        print(f"  [FAIL] {len(uninserted_entities)} scheduled {active_mode} were never inserted into the simulation!")
        for u in uninserted_entities[:5]:
            print(f"    - Missing: {u}")
    else:
        print(f"  [PASS] All {len(expected_in_window)} in-window scheduled {active_mode} were inserted.")

    if missing_arrived:
        print(f"  [FAIL] {len(missing_arrived)} {active_mode} failed to arrive at destination by end of window!")
        for m in missing_arrived[:5]:
            print(f"    - Incomplete: {m}")
    else:
        print(f"  [PASS] All {len(expected_arrived)} expected {active_mode} completed and arrived at destination.")

    if unfinished_expected:
        print(f"  [FAIL] {len(unfinished_expected)} {active_mode} scheduled to arrive within simulation window were still unfinished/stalled:")
        for uf_id in unfinished_expected[:5]:
            uf_t = unfinished_trips[uf_id]
            print(f"    - {uf_id}: duration={uf_t.attrib.get('duration')}s, timeLoss={uf_t.attrib.get('timeLoss')}s")

    if unfinished_beyond_cutoff:
        print(f"  [INFO] {len(unfinished_beyond_cutoff)} {active_mode} still in service/transit beyond simulation cutoff ({max_steps}s).")

    print("\n3. TIMETABLE SCHEDULE ADHERENCE & PUNCTUALITY:")
    if punctuality_results:
        diffs = [p["diff"] for p in punctuality_results if p["diff"] < 900000.0]
        max_delay = max(diffs) if diffs else 0.0
        max_advance = min(diffs) if diffs else 0.0
        avg_diff = sum(diffs) / len(diffs) if diffs else 0.0
        on_time_60s = sum(1 for d in diffs if abs(d) <= 60.0)
        on_time_180s = sum(1 for d in diffs if abs(d) <= 180.0)
        total_p = len(punctuality_results)

        worst_delay = max(punctuality_results, key=lambda p: p["diff"])
        valid_p = [p for p in punctuality_results if p["diff"] < 900000.0]
        worst_advance = min(valid_p, key=lambda p: p["diff"]) if valid_p else worst_delay

        entity_label = "Services" if active_mode == "rakes" else "Runs"
        print(f"  Audited Completed {entity_label}: {total_p}")
        print(f"  On-time (within ±60s):   {on_time_60s} / {total_p} ({on_time_60s / total_p * 100:.1f}%)")
        print(f"  On-time (within ±180s):  {on_time_180s} / {total_p} ({on_time_180s / total_p * 100:.1f}%)")
        print(f"  Mean Arrival Offset:     {avg_diff:+.1f}s")
        print(f"  Max Arrival Delay:       {max_delay:+.1f}s ({worst_delay['id']}, Corridor {worst_delay['corridor']})")
        print(f"  Max Arrival Advance:     {max_advance:+.1f}s ({worst_advance['id']}, Corridor {worst_advance['corridor']})")

        if excessive_delays:
            print(f"  [FAIL] {len(excessive_delays)} {entity_label.lower()} exceeded punctuality delay tolerance of {delay_tolerance_sec:.1f}s:")
            for ed in excessive_delays[:5]:
                print(f"    - {ed['id']}: delayed by {ed['diff']:+.1f}s (sim: {ed['sim_arr']:.1f}s vs sched: {ed['sched_arr']:.1f}s)")
        else:
            print(f"  [PASS] All {total_p} completed {entity_label.lower()} adhered to timetable within <= {delay_tolerance_sec:.1f}s delay tolerance.")

        if active_mode == "rakes":
            print("\n4. FINAL YARD STABLING & FLEET RECOVERY AUDIT:")
            if yard_results:
                yard_diffs = [y["yard_diff"] for y in yard_results]
                print(f"  Audited Completed Rakes: {len(yard_results)}")
                print(f"  Yard Arrival Offset (mean): {sum(yard_diffs) / len(yard_diffs):+.1f}s (max: {max(yard_diffs):+.1f}s)")
            if stabling_violations:
                print(f"  [FAIL] {len(stabling_violations)} rake(s) violated final stabling requirements:")
                for sv in stabling_violations[:5]:
                    print(f"    - {sv[0]}: {sv[1]}")
            else:
                print(f"  [PASS] All {len(expected_entities)} physical rakes preserved final stabling stop and yard arrival requirements.")
    else:
        print("  [INFO] No completed full runs in this simulation window to audit punctuality.")

    print("=" * 75)

    success = (
        res.returncode == 0
        and len(fatal_errors) == 0
        and len(collision_warnings) == 0
        and len(teleport_warnings) == 0
        and len(duplicate_compiled) == 0
        and len(duplicate_trips) == 0
        and len(unexpected_trips) == 0
        and len(uninserted_entities) == 0
        and len(missing_arrived) == 0
        and len(unfinished_expected) == 0
        and len(excessive_delays) == 0
        and len(stabling_violations) == 0
    )

    if success:
        print("[OK] SIMULATION VERIFICATION PASSED (All railway safety & timetable criteria met)")
    else:
        print("[FAIL] SIMULATION VERIFICATION FAILED (One or more safety/performance checks failed)")

    return success


def verify_day(day, max_steps=86400, mode="auto", delay_tolerance_sec=300.0, verbose=False):
    target_mode = mode if mode != "auto" else detect_mode_from_routes(ROU_FILE)
    print(f"\n>>> Compiling SUMO files for: {day} (mode: {target_mode}) <<<")
    try:
        ok = compile_sumo_files(mode=target_mode, day=day)
    except Exception as e:
        print(f"[!] Route compilation failed with exception: {e}")
        return False

    if not ok:
        print(f"[!] Route compilation failed for day '{day}'. Stopping verification before running SUMO.")
        return False

    return run_verification(max_steps=max_steps, day=day, mode=target_mode, delay_tolerance_sec=delay_tolerance_sec, verbose=verbose)


def verify_all_days(max_steps=86400, mode="auto", delay_tolerance_sec=300.0, verbose=False):
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "all"]
    results = {}
    selected_mode = mode if mode != "auto" else detect_mode_from_routes(ROU_FILE, fallback="rakes")
    print("=" * 75)
    print("RUNNING FULL MULTI-DAY OPERATING SCHEDULE VERIFICATION")
    print("=" * 75)
    for d in days:
        print(f"\n==================== Verifying {d.upper()} ====================")
        success = verify_day(d, max_steps=max_steps, mode=selected_mode, delay_tolerance_sec=delay_tolerance_sec, verbose=verbose)
        results[d] = success
        if mode == "auto":
            selected_mode = detect_mode_from_routes(ROU_FILE, fallback=selected_mode)

    try:
        compile_sumo_files(mode=selected_mode, day="all")
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
        default=86400,
        help="Simulation horizon in seconds (default: 86400 for full 24h day)"
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["auto", "rakes", "services"],
        default="auto",
        help="Verification mode: 'rakes' (physical rakes), 'services' (discrete trips), or 'auto' (detect from routes file)"
    )
    parser.add_argument(
        "-d", "--day",
        type=str,
        default="all",
        help="Operating day to verify (Mon, Tue, Wed, Thu, Fri, Sat, Sun, or all/composite)"
    )
    parser.add_argument(
        "--all-days",
        action="store_true",
        help="Sequentially test all individual operating days (Mon through Sun) plus composite"
    )
    parser.add_argument(
        "--delay-tolerance",
        type=float,
        default=300.0,
        help="Maximum allowable arrival delay in seconds before marking a trip late (default: 300.0s)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose diagnostics including individual arrival delays"
    )
    args = parser.parse_args()

    if args.all_days:
        success = verify_all_days(
            max_steps=args.steps,
            mode=args.mode,
            delay_tolerance_sec=args.delay_tolerance,
            verbose=args.verbose
        )
    else:
        chosen_day = normalize_day(args.day) if args.day else "all"
        if chosen_day not in ("all", "composite"):
            success = verify_day(
                chosen_day,
                max_steps=args.steps,
                mode=args.mode,
                delay_tolerance_sec=args.delay_tolerance,
                verbose=args.verbose
            )
            try:
                compile_sumo_files(mode=args.mode if args.mode != "auto" else detect_mode_from_routes(ROU_FILE), day="all")
            except Exception as e:
                print(f"[!] Warning: failed to recompile composite schedule: {e}")
        else:
            comp_mode = args.mode if args.mode != "auto" else detect_mode_from_routes(ROU_FILE)
            try:
                compile_sumo_files(mode=comp_mode, day="all")
            except Exception as e:
                print(f"[!] Warning: failed to recompile schedule: {e}")
            success = run_verification(
                max_steps=args.steps,
                day=args.day,
                mode=comp_mode,
                delay_tolerance_sec=args.delay_tolerance,
                verbose=args.verbose
            )

    sys.exit(0 if success else 1)
