#!/usr/bin/env python3
"""
export_to_sumo.py
Compiles the JSON timetable and rolling stock types into SUMO-compatible files:
1. sumo_config/trains.trips.xml (trips with scheduled train stops)
2. sumo_config/trains.rou.xml (compiled via duarouter)
3. sumo_config/train_simulation.sumocfg (complete SUMO configuration)
"""

import json
import os
import sys
import subprocess
import xml.etree.ElementTree as ET
from xml.dom import minidom

TRAINS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(TRAINS_DIR, "data")
SUMO_CONFIG_DIR = os.path.join(TRAINS_DIR, "sumo_config")
NETWORK_DATA_DIR = "/home/venkatasriramt/Desktop/tracks/network_data"

os.makedirs(SUMO_CONFIG_DIR, exist_ok=True)

NET_FILE = os.path.join(NETWORK_DATA_DIR, "dense_network.net.xml")
ADD_FILE = os.path.join(NETWORK_DATA_DIR, "dense_network.add.xml")
TRIPS_FILE = os.path.join(SUMO_CONFIG_DIR, "trains.trips.xml")
ROU_FILE = os.path.join(SUMO_CONFIG_DIR, "trains.rou.xml")
SUMOCFG_FILE = os.path.join(SUMO_CONFIG_DIR, "train_simulation.sumocfg")

def prettify(elem):
    return minidom.parseString(ET.tostring(elem, 'utf-8')).toprettyxml(indent="    ")

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

def compile_sumo_files(day="all", max_services=None):
    if isinstance(day, int):
        max_services = day
        day = "all"

    norm_day = normalize_day(day)
    if norm_day not in SUPPORTED_DAYS:
        raise ValueError(
            f"Invalid operating day '{day}'. Supported days: {', '.join(SUPPORTED_DAYS)}"
        )

    with open(os.path.join(DATA_DIR, "rolling_stock_types.json"), "r") as f:
        rs_types = json.load(f)

    with open(os.path.join(DATA_DIR, "timetable.json"), "r") as f:
        timetable = json.load(f)

    total_services = len(timetable)

    # Filter by operating day
    if norm_day != "all":
        timetable = [s for s in timetable if service_runs_on_day(s, norm_day)]
        print(f"Exporting schedule for {norm_day}: {len(timetable)} of {total_services} services")
    else:
        print(f"Exporting composite schedule (all days): {len(timetable)} services")

    if max_services:
        timetable = timetable[:max_services]
        print(f"Capped at first {max_services} services for debugging")

    root = ET.Element("routes")

    # 1. Rolling stock vType definitions
    for t_id, r in rs_types.items():
        vtype = ET.SubElement(root, "vType", id=t_id, **{
            "vClass": r["sumo_vclass"],
            "length": str(r["total_length_m"]),
            "maxSpeed": str(r["max_speed_ms"]),
            "accel": str(r["acceleration_ms2"]),
            "decel": str(r["deceleration_ms2"]),
            "emergencyDecel": str(r["emergency_decel_ms2"]),
            "guiShape": r.get("gui_shape", "rail/railcar"),
            "color": r.get("gui_color", "1,0,0")
        })

    # 2. Train trips and stops
    # We sort trips by departure second for duarouter (using origin stop departure time)
    timetable_sorted = sorted(
        timetable,
        key=lambda s: s["stops"][0]["departure_sec"] if (s.get("stops") and "departure_sec" in s["stops"][0]) else s["departure_sec"]
    )

    for s in timetable_sorted:
        dep_sec = s["stops"][0]["departure_sec"] if (s.get("stops") and "departure_sec" in s["stops"][0]) else s["departure_sec"]
        trip_id = f"train_{s['train_number']}_{s['service_class']}"
        trip_elem = ET.SubElement(root, "trip", id=trip_id, **{
            "type": s["rolling_stock_type"],
            "from": s["origin_track"],
            "to": s["dest_track"],
            "depart": f"{dep_sec:.1f}"
        })

        # Add intermediate stops (skip origin and destination if redundant)
        stops = s.get("stops", [])
        if len(stops) > 2:
            # Intermediate stops are from index 1 to len-2
            for stp in stops[1:-1]:
                dwell = stp.get("dwell_sec", 60)
                if stp.get("train_stop_id"):
                    ET.SubElement(trip_elem, "stop", **{
                        "trainStop": stp["train_stop_id"],
                        "duration": str(int(dwell))
                    })
                elif "Passing_Loop" in stp.get("station", ""):
                    ET.SubElement(trip_elem, "stop", **{
                        "lane": "c3_Town_8_Town_9_loop_siding_fw_0",
                        "duration": str(int(dwell))
                    })

    # Write trips.xml
    with open(TRIPS_FILE, "w", encoding="utf-8") as f:
        f.write(prettify(root))
    print(f"1. Written train trips XML: {TRIPS_FILE}")

    # 3. Run duarouter to compile exact edge routes
    print("2. Running duarouter to compute exact edge sequences...")
    cmd = [
        "duarouter",
        "--net-file", NET_FILE,
        "--additional-files", ADD_FILE,
        "--route-files", TRIPS_FILE,
        "--output-file", ROU_FILE,
        "--routing-algorithm", "astar",
        "--repair", "true"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Duarouter Error:")
        print(res.stderr)
        return False

    # Verify that the compiled route count matches the selected services
    try:
        rou_tree = ET.parse(ROU_FILE)
        compiled_routes = len(rou_tree.getroot().findall("vehicle"))
    except Exception as e:
        print(f"Error parsing compiled routes file {ROU_FILE}: {e}")
        return False

    if compiled_routes != len(timetable):
        print(
            f"Error: Compiled route count mismatch! Expected {len(timetable)} routes, but found {compiled_routes} in {ROU_FILE}."
        )
        return False

    print(f"   Compiled routes file successfully: {ROU_FILE} ({compiled_routes}/{len(timetable)} routes verified)")

    # 4. Generate train_simulation.sumocfg
    cfg_root = ET.Element("configuration")
    input_elem = ET.SubElement(cfg_root, "input")
    ET.SubElement(input_elem, "net-file", value=NET_FILE)
    ET.SubElement(input_elem, "additional-files", value=ADD_FILE)
    ET.SubElement(input_elem, "route-files", value=ROU_FILE)

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
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Compiles timetable schedules into SUMO trips and routes filtered by operating day."
    )
    parser.add_argument(
        "pos_day",
        nargs="?",
        default=None,
        help="Operating day (Mon, Tue, Wed, Thu, Fri, Sat, Sun, or all/composite)"
    )
    parser.add_argument(
        "-d", "--day",
        type=str,
        default=None,
        help="Operating day to export (Mon, Tue, Wed, Thu, Fri, Sat, Sun, or all/composite)"
    )
    parser.add_argument(
        "--max-services",
        type=int,
        default=None,
        help="Cap maximum number of services to export"
    )
    args = parser.parse_args()

    if args.pos_day and args.pos_day.isdigit() and args.max_services is None:
        chosen_day = args.day or "all"
        max_svcs = int(args.pos_day)
    else:
        chosen_day = args.day or args.pos_day or os.environ.get("SUMO_DAY") or os.environ.get("SIMULATION_DAY") or "all"
        max_svcs = args.max_services

    try:
        success = compile_sumo_files(day=chosen_day, max_services=max_svcs)
        if not success:
            sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
