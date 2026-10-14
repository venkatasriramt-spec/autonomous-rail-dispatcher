#!/usr/bin/env python3
"""
export_to_sumo.py
Compiles railway timetable schedules and rolling stock rosters into SUMO-compatible files.

Supports dual-mode export:
1. --mode rakes (default):
   Compiles the 31 continuous physical rakes with complete lifecycles:
   - Dawn rollout from overnight stabling sidings
   - Revenue passenger transit legs with intermediate scheduled platform stops
   - Terminal turnaround shunting into pocket tail tracks (*Kopfmachen* buffer reversals)
   - Mid-day stabling yard layovers
   - End-of-day return to resting stabling sidings
2. --mode services:
   Compiles the 242 discrete service trips for isolated slot timetable auditing.
3. --mode both:
   Compiles both rakes and services route files.
"""

import json
import os
import sys
import subprocess
import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom

TRAINS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(TRAINS_DIR, "data")
SUMO_CONFIG_DIR = os.path.join(TRAINS_DIR, "sumo_config")

def find_network_data_dir():
    if "TRACKS_DIR" in os.environ and os.path.isdir(os.environ["TRACKS_DIR"]):
        return os.environ["TRACKS_DIR"]
    candidates = [
        os.path.join(os.path.dirname(TRAINS_DIR), "tracks", "network_data"),
        os.path.join(TRAINS_DIR, "tracks", "network_data"),
        os.path.join(TRAINS_DIR, "..", "tracks", "network_data"),
        "/home/venkatasriramt/Desktop/tracks/network_data",
    ]
    for c in candidates:
        if os.path.isdir(c) and os.path.exists(os.path.join(c, "dense_network.net.xml")):
            return c
    return candidates[0]

NETWORK_DATA_DIR = find_network_data_dir()

os.makedirs(SUMO_CONFIG_DIR, exist_ok=True)

NET_FILE = os.path.join(NETWORK_DATA_DIR, "dense_network.net.xml")
ADD_FILE = os.path.join(NETWORK_DATA_DIR, "dense_network.add.xml")
TRIPS_FILE = os.path.join(SUMO_CONFIG_DIR, "trains.trips.xml")
ROU_FILE = os.path.join(SUMO_CONFIG_DIR, "trains.rou.xml")
SUMOCFG_FILE = os.path.join(SUMO_CONFIG_DIR, "train_simulation.sumocfg")

def prettify(elem):
    return minidom.parseString(ET.tostring(elem, "utf-8")).toprettyxml(indent="    ")

DAY_NAME_MAP = {
    "mon": "Mon", "monday": "Mon",
    "tue": "Tue", "tuesday": "Tue",
    "wed": "Wed", "wednesday": "Wed",
    "thu": "Thu", "thursday": "Thu",
    "fri": "Fri", "friday": "Fri",
    "sat": "Sat", "saturday": "Sat",
    "sun": "Sun", "sunday": "Sun",
    "all": "all", "composite": "all"
}

SUPPORTED_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "all"]

def normalize_day(day_str):
    if not day_str:
        return "all"
    key = str(day_str).strip().lower()
    return DAY_NAME_MAP.get(key, day_str)

def expand_service_days(svc):
    days = svc.get("service_days", [])
    if isinstance(days, str):
        days = [days]
    res = set()
    for d in days:
        for part in d.replace(",", " ").replace("/", " ").split():
            if part in ("Daily", "daily"):
                res.update(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
            elif part in ("Mon-Fri", "mon-fri"):
                res.update(["Mon", "Tue", "Wed", "Thu", "Fri"])
            else:
                norm = normalize_day(part)
                if norm in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
                    res.add(norm)
    return res

def service_runs_on_day(svc, target_day):
    norm = normalize_day(target_day)
    if norm in ("all", "composite"):
        return True
    return norm in expand_service_days(svc)

def add_vtypes(root, rs_types):
    for t_id, r in rs_types.items():
        ET.SubElement(root, "vType", id=t_id, **{
            "vClass": r["sumo_vclass"],
            "length": str(r["total_length_m"]),
            "maxSpeed": str(r["max_speed_ms"]),
            "accel": str(r["acceleration_ms2"]),
            "decel": str(r["deceleration_ms2"]),
            "emergencyDecel": str(r["emergency_decel_ms2"]),
            "guiShape": r.get("gui_shape", "rail/railcar"),
            "color": r.get("gui_color", "1,0,0")
        })

def compile_routes_with_duarouter(trips_file, output_rou_file):
    cmd = [
        "duarouter",
        "--net-file", NET_FILE,
        "--additional-files", ADD_FILE,
        "--route-files", trips_file,
        "--output-file", output_rou_file,
        "--routing-algorithm", "astar",
        "--repair", "true"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Duarouter Error on {trips_file}:", file=sys.stderr)
        print(res.stderr, file=sys.stderr)
        return False
    return True

def export_rakes_mode(timetable, roster, rs_types, norm_day, max_rakes=None):
    tt_by_id = {s["train_number"]: s for s in timetable}
    root = ET.Element("routes")
    add_vtypes(root, rs_types)

    rake_entries = []
    for r in roster:
        rake_id = r["rake_id"]
        rs_type = r["rolling_stock_type"]
        raw_services = r.get("assigned_services", [])
        
        # Filter services by day if needed
        if norm_day != "all":
            valid_services = [
                sid for sid in raw_services
                if sid in tt_by_id and service_runs_on_day(tt_by_id[sid], norm_day)
            ]
        else:
            valid_services = [sid for sid in raw_services if sid in tt_by_id]

        if not valid_services:
            continue

        services = sorted(valid_services, key=lambda sid: tt_by_id[sid]["departure_sec"])
        first_s = tt_by_id[services[0]]
        last_s = tt_by_id[services[-1]]

        stabling_track = r.get("overnight_stabling_track")
        start_from = stabling_track if stabling_track else first_s["origin_track"]
        if stabling_track and stabling_track != first_s["origin_track"]:
            stn_stab = stabling_track.split("_yard")[0].split("_plat")[0]
            stn_orig = first_s.get("origin_station", "")
            rollout_lead = 1800.0 if stn_stab != stn_orig else 600.0
            start_dep = max(0.0, first_s["departure_sec"] - rollout_lead)
        else:
            start_dep = first_s["departure_sec"]
        end_to = stabling_track if stabling_track else last_s["dest_track"]

        stops_xml = []
        # Dawn rollout stop if starting in yard
        if stabling_track and stabling_track != first_s["origin_track"]:
            orig_ts = first_s["stops"][0].get("train_stop_id")
            first_svc_id = f"train_{first_s['train_number']}_{first_s['service_class']}"
            if orig_ts:
                stops_xml.append(("trainStop", orig_ts, None, str(first_s["departure_sec"]), None, first_svc_id))
            else:
                orig_lane = f"{first_s['origin_track']}_0"
                if stops_xml and stops_xml[-1][0] == "lane" and stops_xml[-1][1] == orig_lane:
                    stops_xml[-1] = (stops_xml[-1][0], stops_xml[-1][1], stops_xml[-1][2], str(first_s["departure_sec"]), None, first_svc_id)
                else:
                    stops_xml.append(("lane", orig_lane, "60", str(first_s["departure_sec"]), None, first_svc_id))

        for idx, sid in enumerate(services):
            s = tt_by_id[sid]
            svc_trip_id = f"train_{s['train_number']}_{s['service_class']}"
            # Intermediate station stops
            for stp in s.get("stops", [])[1:-1]:
                ts = stp.get("train_stop_id")
                dwell = stp.get("dwell_sec", 60)
                arr_sec = stp.get("arrival_sec")
                dep_sec_stop = stp.get("departure_sec")
                arr_str = f"{float(arr_sec):.2f}" if arr_sec is not None else None
                dep_str = f"{float(dep_sec_stop):.2f}" if dep_sec_stop is not None else None
                if ts:
                    stops_xml.append(("trainStop", ts, str(int(dwell)), dep_str, arr_str, svc_trip_id))
                elif "Passing_Loop" in stp.get("station", ""):
                    stops_xml.append(("lane", "c3_Town_8_Town_9_loop_siding_fw_0", str(int(dwell)), dep_str, arr_str, svc_trip_id))

            # Destination platform alighting stop
            dest_ts = s["stops"][-1].get("train_stop_id")
            dest_arr = s["stops"][-1].get("arrival_sec") or s.get("arrival_sec")
            dest_arr_str = f"{float(dest_arr):.2f}" if dest_arr is not None else None
            if dest_ts:
                stops_xml.append(("trainStop", dest_ts, "60", None, dest_arr_str, svc_trip_id))
            elif s.get("dest_track"):
                dest_lane = f"{s['dest_track']}_0"
                stops_xml.append(("lane", dest_lane, "60", None, dest_arr_str, svc_trip_id))

            # Turnaround or mid-day yard layover
            pjd = s.get("post_journey_disposition", {})
            staging = pjd.get("staging_track")
            if idx < len(services) - 1:
                next_s = tt_by_id[services[idx + 1]]
                next_svc_id = f"train_{next_s['train_number']}_{next_s['service_class']}"
                dep_sec = next_s["departure_sec"]
                curr_arr = s["stops"][-1].get("arrival_sec") or s.get("arrival_sec", 0.0)
                turnaround_gap = dep_sec - curr_arr

                effective_staging = staging
                if not effective_staging and turnaround_gap > 1200.0:
                    stabling = r.get("overnight_stabling_track")
                    if stabling and "yard" in stabling and stabling.startswith(s["dest_station"]):
                        effective_staging = stabling

                if effective_staging:
                    first_plat_arr = next_s["stops"][0].get("arrival_sec")
                    target_until = dep_sec - 300.0
                    if first_plat_arr is not None and first_plat_arr < target_until:
                        target_until = first_plat_arr
                    target_until = max(curr_arr, target_until)
                    if s["dest_track"].startswith("City_1_plat") and effective_staging.startswith("City_1_yard"):
                        p_idx = 1 if "HS" in rake_id else (2 if "REG-C1" in rake_id else 3)
                        stops_xml.append(("lane", f"City_1_pocket_{p_idx}_fw_0", "1", None, None, None))
                    stops_xml.append(("lane", f"{effective_staging}_0", "60", str(target_until), None, None))
                next_orig_ts = next_s["stops"][0].get("train_stop_id")
                if next_orig_ts:
                    stops_xml.append(("trainStop", next_orig_ts, None, str(next_s["departure_sec"]), None, next_svc_id))
                else:
                    next_lane = f"{next_s['origin_track']}_0"
                    prev = stops_xml[-1] if stops_xml else None
                    # Merge only if the previous stop is a lane stop at the same lane AND
                    # has no tripId (staging/yard stop) or already carries next service's tripId.
                    # If it carries the arriving service's tripId (with arrival data), emit
                    # a separate stop to preserve the arrival record for that service.
                    if (prev and prev[0] == "lane" and prev[1] == next_lane
                            and (prev[5] is None or prev[5] == next_svc_id)):
                        stops_xml[-1] = (prev[0], prev[1], prev[2], str(next_s["departure_sec"]), prev[4], next_svc_id)
                    else:
                        stops_xml.append(("lane", next_lane, "60", str(next_s["departure_sec"]), None, next_svc_id))
            else:
                # End-of-day stabling
                if stabling_track:
                    if s["dest_track"].startswith("City_1_plat") and stabling_track.startswith("City_1_yard"):
                        p_idx = 1 if "HS" in rake_id else (2 if "REG-C1" in rake_id else 3)
                        stops_xml.append(("lane", f"City_1_pocket_{p_idx}_fw_0", "1", None, None, None))
                    stops_xml.append(("lane", f"{stabling_track}_0", "60", None, None, None))

        rake_entries.append((start_dep, rake_id, rs_type, start_from, end_to, stops_xml))

    # Sort rakes by departure second
    rake_entries.sort(key=lambda x: x[0])
    if max_rakes:
        rake_entries = rake_entries[:max_rakes]

    for start_dep, rake_id, rs_type, start_from, end_to, stops_xml in rake_entries:
        trip_elem = ET.SubElement(root, "trip", id=rake_id, **{
            "type": rs_type,
            "from": start_from,
            "to": end_to,
            "depart": f"{start_dep:.1f}"
        })
        for stop_type, target, duration, until, arrival, trip_id_val in stops_xml:
            attrs = {}
            if stop_type == "trainStop":
                attrs["trainStop"] = target
            else:
                attrs["lane"] = target
            if duration:
                attrs["duration"] = duration
            if until:
                attrs["until"] = until
            if arrival:
                attrs["arrival"] = arrival
            if trip_id_val:
                attrs["tripId"] = trip_id_val
            ET.SubElement(trip_elem, "stop", **attrs)

    rakes_trips_path = os.path.join(SUMO_CONFIG_DIR, "trains_rakes.trips.xml")
    rakes_rou_path = os.path.join(SUMO_CONFIG_DIR, "trains_rakes.rou.xml")
    with open(rakes_trips_path, "w", encoding="utf-8") as f:
        f.write(prettify(root))
    print(f"1. Written continuous rakes trips XML: {rakes_trips_path} ({len(rake_entries)} rakes)")

    print("2. Running duarouter to compile continuous rake routes...")
    if not compile_routes_with_duarouter(rakes_trips_path, rakes_rou_path):
        return False
    print(f"   Compiled rakes route file: {rakes_rou_path}")
    return rakes_rou_path, len(rake_entries)

def export_services_mode(timetable, rs_types, norm_day, max_services=None):
    root = ET.Element("routes")
    add_vtypes(root, rs_types)

    timetable_sorted = sorted(
        timetable,
        key=lambda s: s["stops"][0]["departure_sec"] if (s.get("stops") and "departure_sec" in s["stops"][0]) else s["departure_sec"]
    )
    if max_services:
        timetable_sorted = timetable_sorted[:max_services]

    for s in timetable_sorted:
        dep_sec = s["stops"][0]["departure_sec"] if (s.get("stops") and "departure_sec" in s["stops"][0]) else s["departure_sec"]
        trip_id = f"train_{s['train_number']}_{s['service_class']}"
        trip_elem = ET.SubElement(root, "trip", id=trip_id, **{
            "type": s["rolling_stock_type"],
            "from": s["origin_track"],
            "to": s["dest_track"],
            "depart": f"{dep_sec:.1f}"
        })

        stops = s.get("stops", [])
        if len(stops) > 2:
            for stp in stops[1:-1]:
                dwell = stp.get("dwell_sec", 60)
                arr_sec = stp.get("arrival_sec")
                dep_sec_stop = stp.get("departure_sec")
                attrs = {"duration": str(int(dwell)), "tripId": trip_id}
                if arr_sec is not None:
                    attrs["arrival"] = f"{float(arr_sec):.2f}"
                if dep_sec_stop is not None:
                    attrs["until"] = f"{float(dep_sec_stop):.2f}"

                if stp.get("train_stop_id"):
                    attrs["trainStop"] = stp["train_stop_id"]
                    ET.SubElement(trip_elem, "stop", **attrs)
                elif "Passing_Loop" in stp.get("station", ""):
                    attrs["lane"] = "c3_Town_8_Town_9_loop_siding_fw_0"
                    ET.SubElement(trip_elem, "stop", **attrs)

    services_trips_path = os.path.join(SUMO_CONFIG_DIR, "trains_services.trips.xml")
    services_rou_path = os.path.join(SUMO_CONFIG_DIR, "trains_services.rou.xml")
    with open(services_trips_path, "w", encoding="utf-8") as f:
        f.write(prettify(root))
    print(f"1. Written discrete services trips XML: {services_trips_path} ({len(timetable_sorted)} services)")

    print("2. Running duarouter to compile discrete service routes...")
    if not compile_routes_with_duarouter(services_trips_path, services_rou_path):
        return False
    print(f"   Compiled services route file: {services_rou_path}")
    return services_rou_path, len(timetable_sorted)

def write_sumocfg(active_rou_file):
    cfg_root = ET.Element("configuration")
    input_elem = ET.SubElement(cfg_root, "input")

    try:
        net_val = os.path.relpath(NET_FILE, SUMO_CONFIG_DIR)
        add_val = os.path.relpath(ADD_FILE, SUMO_CONFIG_DIR)
        rou_val = os.path.relpath(active_rou_file, SUMO_CONFIG_DIR)
    except ValueError:
        net_val = NET_FILE
        add_val = ADD_FILE
        rou_val = active_rou_file

    ET.SubElement(input_elem, "net-file", value=net_val)
    ET.SubElement(input_elem, "additional-files", value=add_val)
    ET.SubElement(input_elem, "route-files", value=rou_val)

    time_elem = ET.SubElement(cfg_root, "time")
    ET.SubElement(time_elem, "begin", value="0")
    ET.SubElement(time_elem, "step-length", value="1.0")

    proc_elem = ET.SubElement(cfg_root, "processing")
    ET.SubElement(proc_elem, "collision.action", value="warn")
    ET.SubElement(proc_elem, "time-to-teleport", value="-1")

    gui_elem = ET.SubElement(cfg_root, "gui_only")
    ET.SubElement(gui_elem, "gui-settings-file", value="viewsettings.xml")

    with open(SUMOCFG_FILE, "w", encoding="utf-8") as f:
        f.write(prettify(cfg_root))
    print(f"3. Written master simulation config: {SUMOCFG_FILE}")

def compile_sumo_files(mode="rakes", day="all", max_limit=None):
    norm_day = normalize_day(day)
    if norm_day not in SUPPORTED_DAYS:
        raise ValueError(
            f"Invalid operating day '{day}'. Supported days: {', '.join(SUPPORTED_DAYS)}"
        )

    with open(os.path.join(DATA_DIR, "rolling_stock_types.json"), "r", encoding="utf-8") as f:
        rs_types = json.load(f)

    with open(os.path.join(DATA_DIR, "timetable.json"), "r", encoding="utf-8") as f:
        timetable = json.load(f)

    with open(os.path.join(DATA_DIR, "rakes_roster.json"), "r", encoding="utf-8") as f:
        roster = json.load(f)

    if norm_day != "all":
        day_timetable = [s for s in timetable if service_runs_on_day(s, norm_day)]
        print(f"Operating day: {norm_day} ({len(day_timetable)} of {len(timetable)} services match)")
    else:
        day_timetable = timetable
        print(f"Operating day: Composite (All Days) ({len(timetable)} services)")

    if mode in ("rakes", "both"):
        rakes_res = export_rakes_mode(day_timetable, roster, rs_types, norm_day, max_rakes=max_limit)
        if not rakes_res:
            return False

    if mode in ("services", "both"):
        services_res = export_services_mode(day_timetable, rs_types, norm_day, max_services=max_limit)
        if not services_res:
            return False

    # Set default trains.rou.xml and trains.trips.xml based on mode
    if mode == "services":
        src_rou = os.path.join(SUMO_CONFIG_DIR, "trains_services.rou.xml")
        src_trips = os.path.join(SUMO_CONFIG_DIR, "trains_services.trips.xml")
    else:
        src_rou = os.path.join(SUMO_CONFIG_DIR, "trains_rakes.rou.xml")
        src_trips = os.path.join(SUMO_CONFIG_DIR, "trains_rakes.trips.xml")

    # Copy to master trains.rou.xml and trains.trips.xml
    with open(src_rou, "r", encoding="utf-8") as f_src, open(ROU_FILE, "w", encoding="utf-8") as f_dst:
        f_dst.write(f_src.read())
    with open(src_trips, "r", encoding="utf-8") as f_src, open(TRIPS_FILE, "w", encoding="utf-8") as f_dst:
        f_dst.write(f_src.read())

    write_sumocfg(ROU_FILE)
    print(f"Master simulation active routes set to mode '{mode}'.")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compiles railway timetable schedules into SUMO trips and routes (Dual-Mode: rakes / services)."
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["rakes", "services", "both"],
        default="rakes",
        help="Export mode: 'rakes' (31 continuous physical rakes, default), 'services' (242 discrete trips), or 'both'"
    )
    parser.add_argument(
        "-d", "--day",
        type=str,
        default="all",
        help="Operating day to export (Mon, Tue, Wed, Thu, Fri, Sat, Sun, or all/composite)"
    )
    parser.add_argument(
        "pos_arg",
        nargs="?",
        default=None,
        help="Positional argument: day name (e.g. Mon, all) or max services limit"
    )
    parser.add_argument(
        "--max-limit",
        type=int,
        default=None,
        help="Cap maximum number of rakes or services to export"
    )
    args = parser.parse_args()

    chosen_day = args.day
    max_lim = args.max_limit
    chosen_mode = args.mode

    if args.pos_arg:
        if args.pos_arg.isdigit():
            max_lim = int(args.pos_arg)
        elif args.pos_arg.lower() in ["rakes", "services", "both"]:
            chosen_mode = args.pos_arg.lower()
        else:
            chosen_day = args.pos_arg

    try:
        success = compile_sumo_files(mode=chosen_mode, day=chosen_day, max_limit=max_lim)
        if not success:
            sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
