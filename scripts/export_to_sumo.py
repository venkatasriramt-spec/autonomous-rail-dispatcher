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
import subprocess
import xml.etree.ElementTree as ET
from xml.dom import minidom

TRAINS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(TRAINS_DIR, "data")
SUMO_CONFIG_DIR = os.path.join(TRAINS_DIR, "sumo_config")
NETWORK_DATA_DIR = "/home/venkatasriramt/Desktop/network/network_data"

os.makedirs(SUMO_CONFIG_DIR, exist_ok=True)

NET_FILE = os.path.join(NETWORK_DATA_DIR, "dense_network.net.xml")
ADD_FILE = os.path.join(NETWORK_DATA_DIR, "dense_network.add.xml")
TRIPS_FILE = os.path.join(SUMO_CONFIG_DIR, "trains.trips.xml")
ROU_FILE = os.path.join(SUMO_CONFIG_DIR, "trains.rou.xml")
SUMOCFG_FILE = os.path.join(SUMO_CONFIG_DIR, "train_simulation.sumocfg")

def prettify(elem):
    return minidom.parseString(ET.tostring(elem, 'utf-8')).toprettyxml(indent="    ")

def compile_sumo_files(max_services=None):
    with open(os.path.join(DATA_DIR, "rolling_stock_types.json"), "r") as f:
        rs_types = json.load(f)

    with open(os.path.join(DATA_DIR, "timetable.json"), "r") as f:
        timetable = json.load(f)

    if max_services:
        timetable = timetable[:max_services]

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
    # We sort trips by departure second for duarouter
    timetable_sorted = sorted(timetable, key=lambda s: s["departure_sec"])

    for s in timetable_sorted:
        trip_id = f"train_{s['train_number']}_{s['service_class']}"
        trip_elem = ET.SubElement(root, "trip", id=trip_id, **{
            "type": s["rolling_stock_type"],
            "from": s["origin_track"],
            "to": s["dest_track"],
            "depart": f"{s['departure_sec']:.1f}"
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
        "--ignore-errors", "true",
        "--repair", "true"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Duarouter Warning / Error:")
        print(res.stderr)
    else:
        print(f"   Compiled routes file successfully: {ROU_FILE}")

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

if __name__ == "__main__":
    compile_sumo_files()
