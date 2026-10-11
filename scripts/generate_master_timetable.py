#!/usr/bin/env python3
"""
generate_master_timetable.py
Generates the comprehensive rolling stock catalog, master timetable, and physical rake rotation roster
based on the track infrastructure at /home/venkatasriramt/Desktop/tracks/network_data/.
"""

import json
import os
import math

TRAINS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(TRAINS_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# 1. ROLLING STOCK TYPES (PHYSICAL TRAIN CONSISTS)
# -----------------------------------------------------------------------------
ROLLING_STOCK_TYPES = {
    "high_speed_emu_300": {
        "type_id": "high_speed_emu_300",
        "name": "Velaro / E5 Trans-Regional High-Speed EMU",
        "service_class": "HighSpeed",
        "sumo_vclass": "rail_electric",
        "power_supply": "Electric 25kV AC (50Hz)",
        "track_gauge_mm": 1435,
        "max_speed_kmh": 300,
        "max_speed_ms": 83.33,
        "acceleration_ms2": 1.0,
        "deceleration_ms2": 1.2,
        "emergency_decel_ms2": 2.5,
        "total_length_m": 400.0,
        "carriages_count": 16,
        "gross_weight_tons": 880.0,
        "passenger_capacity": 1050,
        "gui_shape": "rail/railcar",
        "gui_color": "1.0,0.15,0.15"  # Crimson Red
    },
    "high_speed_emu_single": {
        "type_id": "high_speed_emu_single",
        "name": "InterCity High-Speed Short EMU (8-Car)",
        "service_class": "HighSpeed",
        "sumo_vclass": "rail_electric",
        "power_supply": "Electric 25kV AC (50Hz)",
        "track_gauge_mm": 1435,
        "max_speed_kmh": 300,
        "max_speed_ms": 83.33,
        "acceleration_ms2": 1.1,
        "deceleration_ms2": 1.2,
        "emergency_decel_ms2": 2.5,
        "total_length_m": 200.0,
        "carriages_count": 8,
        "gross_weight_tons": 440.0,
        "passenger_capacity": 520,
        "gui_shape": "rail/railcar",
        "gui_color": "1.0,0.4,0.1"  # Coral Orange
    },
    "regional_emu_120": {
        "type_id": "regional_emu_120",
        "name": "FLIRT Regional Commuter EMU (6-Car)",
        "service_class": "Regional",
        "sumo_vclass": "rail_electric",
        "power_supply": "Electric 15kV AC (16.7Hz) / Dual 25kV",
        "track_gauge_mm": 1435,
        "max_speed_kmh": 120,
        "max_speed_ms": 33.33,
        "acceleration_ms2": 0.85,
        "deceleration_ms2": 1.0,
        "emergency_decel_ms2": 2.0,
        "total_length_m": 160.0,
        "carriages_count": 6,
        "gross_weight_tons": 240.0,
        "passenger_capacity": 380,
        "gui_shape": "rail/railcar",
        "gui_color": "0.15,0.55,1.0"  # Azure Blue
    },
    "regional_dmu_120": {
        "type_id": "regional_dmu_120",
        "name": "Alpine Explorer DMU (4-Car Hybrid)",
        "service_class": "Regional",
        "sumo_vclass": "rail",
        "power_supply": "Diesel-Electric / Battery Hybrid",
        "track_gauge_mm": 1435,
        "max_speed_kmh": 120,
        "max_speed_ms": 33.33,
        "acceleration_ms2": 0.75,
        "deceleration_ms2": 0.95,
        "emergency_decel_ms2": 1.8,
        "total_length_m": 120.0,
        "carriages_count": 4,
        "gross_weight_tons": 180.0,
        "passenger_capacity": 240,
        "gui_shape": "rail/railcar",
        "gui_color": "0.2,0.85,0.4"  # Emerald Green
    },
    "heavy_freight_cargo": {
        "type_id": "heavy_freight_cargo",
        "name": "Heavy Mineral & Bulk Freight Train (Class 66 + Hoppers)",
        "service_class": "Freight",
        "sumo_vclass": "rail",
        "power_supply": "Diesel Heavy Locomotive",
        "track_gauge_mm": 1435,
        "max_speed_kmh": 80,
        "max_speed_ms": 22.22,
        "acceleration_ms2": 0.35,
        "deceleration_ms2": 0.5,
        "emergency_decel_ms2": 1.2,
        "total_length_m": 420.0,
        "carriages_count": 28,
        "gross_weight_tons": 3800.0,
        "passenger_capacity": 0,
        "gui_shape": "rail/cargo",
        "gui_color": "0.85,0.6,0.15"  # Amber Cargo
    },
    "intermodal_container_freight": {
        "type_id": "intermodal_container_freight",
        "name": "Intermodal Container Logistics Train",
        "service_class": "Freight",
        "sumo_vclass": "rail",
        "power_supply": "Diesel Heavy Locomotive",
        "track_gauge_mm": 1435,
        "max_speed_kmh": 80,
        "max_speed_ms": 22.22,
        "acceleration_ms2": 0.40,
        "deceleration_ms2": 0.55,
        "emergency_decel_ms2": 1.3,
        "total_length_m": 380.0,
        "carriages_count": 24,
        "gross_weight_tons": 2600.0,
        "passenger_capacity": 0,
        "gui_shape": "rail/cargo",
        "gui_color": "0.6,0.4,0.8"  # Purple Logistics
    }
}

# -----------------------------------------------------------------------------
# 2. MASTER CORRIDOR STATION SEQUENCES & PHYSICAL DISTANCES
# -----------------------------------------------------------------------------
# Corridor 1: East-West High Speed Trunk (27.4 km)
# Stations: City_1 <-> Town_1 <-> City_2 <-> Town_2 <-> City_3_EW <-> Town_3 <-> City_4
C1_STATIONS = ["City_1", "Town_1", "City_2", "Town_2", "City_3_EW", "Town_3", "City_4"]
C1_DISTANCES = [0, 4275, 8892, 13496, 18321, 22973, 27445]  # cumulative meters

# Corridor 2: North-South Regional Spine (24.2 km)
# Stations: City_5 <-> Town_4 <-> Town_5 <-> City_3_NS <-> Town_6 <-> Town_7 <-> City_6
C2_STATIONS = ["City_5", "Town_4", "Town_5", "City_3_NS", "Town_6", "Town_7", "City_6"]
C2_DISTANCES = [0, 3712, 7428, 11050, 14771, 18492, 22616]

# Corridor 3: Northwest Alpine Mountain Line (12.9 km)
# Stations: City_2 <-> Town_8 <-> Town_9 <-> Depot_1
C3_STATIONS = ["City_2", "Town_8", "Town_9", "Depot_1"]
C3_DISTANCES = [0, 4459, 8701, 12943]

# Corridor 4: Southern Coastal Arc (27.3 km)
# Stations: City_1 <-> Town_10 <-> Town_11 <-> Depot_2 <-> Town_12 <-> City_6
C4_STATIONS = ["City_1", "Town_10", "Town_11", "Depot_2", "Town_12", "City_6"]
C4_DISTANCES = [0, 4229, 8843, 14935, 21250, 27362]

def format_time(seconds):
    h = int(seconds // 3600) % 24
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# -----------------------------------------------------------------------------
# 3. TIMETABLE GENERATION LOGIC
# -----------------------------------------------------------------------------
def build_timetable():
    timetable = []
    rakes = {}

    def get_rake(rake_id, r_type):
        if rake_id not in rakes:
            rakes[rake_id] = {
                "rake_id": rake_id,
                "rolling_stock_type": r_type,
                "home_depot": "Depot_1" if "ALP" in rake_id or "FRT" in rake_id else ("Depot_3" if "C2" in rake_id else "Depot_4"),
                "assigned_services": []
            }
        return rakes[rake_id]

    # Helper to calculate realistic section run times
    def calc_run_time(d_meters, max_v, is_stop_start=False):
        # Kinematic acceleration and cruise time
        accel = 0.8
        t_acc = max_v / accel
        d_acc = 0.5 * accel * t_acc**2
        if 2 * d_acc > d_meters:
            # Triangular profile
            return 2 * math.sqrt(d_meters / accel)
        cruise_dist = d_meters - 2 * d_acc
        t_cruise = cruise_dist / max_v
        return 2 * t_acc + t_cruise

    # --- CATEGORY A: CORRIDOR 1 HIGH-SPEED EXPRESS (300 km/h) ---
    # Fast InterCity services stopping only at major cities (City_1, City_2, City_3_EW, City_4)
    # Bypasses intermediate towns (Town_1, Town_2, Town_3) at full 300 km/h via center through-tracks.
    hs_departure_offsets = [
        (6, 0, "Mon-Fri", "12001", "12002", "HS-Rake-01"),
        (7, 30, "Daily",   "12003", "12004", "HS-Rake-02"),
        (9, 0, "Mon-Fri", "12005", "12006", "HS-Rake-01"),
        (10, 30, "Daily",  "12007", "12008", "HS-Rake-03"),
        (12, 0, "Daily",   "12009", "12010", "HS-Rake-02"),
        (14, 0, "Daily",   "12011", "12012", "HS-Rake-01"),
        (16, 30, "Mon-Fri","12013", "12014", "HS-Rake-03"),
        (18, 0, "Daily",   "12015", "12016", "HS-Rake-02"),
    ]

    for h, m, days, fwd_no, rev_no, rake_id in hs_departure_offsets:
        dep_sec = h * 3600 + m * 60
        r_type = "high_speed_emu_300"
        rake = get_rake(rake_id, r_type)

        # Forward Run: City_1 -> City_4 (Eastbound)
        curr_t = dep_sec
        stops_fwd = []
        c1_city_indices = [0, 2, 4, 6]  # City_1, City_2, City_3_EW, City_4
        for idx_pos, c_idx in enumerate(c1_city_indices):
            stn = C1_STATIONS[c_idx]
            if idx_pos > 0:
                prev_dist = C1_DISTANCES[c1_city_indices[idx_pos-1]]
                cur_dist = C1_DISTANCES[c_idx]
                sec_time = calc_run_time(cur_dist - prev_dist, 83.33)
                curr_t += sec_time

            arr_t = curr_t
            dwell = 0 if idx_pos == len(c1_city_indices) - 1 else 120
            dep_t = arr_t + dwell
            curr_t = dep_t
            stops_fwd.append({
                "station": stn,
                "train_stop_id": f"{stn}_p1_fw",
                "arrival_time": format_time(arr_t),
                "arrival_sec": round(arr_t, 1),
                "departure_time": format_time(dep_t),
                "departure_sec": round(dep_t, 1),
                "dwell_sec": dwell
            })

        fwd_service = {
            "train_number": fwd_no,
            "train_name": f"Trans-Regional Express {fwd_no}",
            "service_class": "HighSpeed",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": [days] if days in ["Daily", "Mon-Fri"] else days.split(","),
            "corridor": "Corridor_1",
            "direction": "Eastbound_FW",
            "origin_station": "City_1",
            "origin_track": "City_1_plat_1_fw",
            "dest_station": "City_4",
            "dest_track": "City_4_plat_1_fw",
            "departure_time": format_time(dep_sec),
            "departure_sec": dep_sec,
            "arrival_time": stops_fwd[-1]["arrival_time"],
            "arrival_sec": stops_fwd[-1]["arrival_sec"],
            "total_distance_km": 27.45,
            "stops": stops_fwd,
            "bypassed_through_stations": ["Town_1", "Town_2", "Town_3"],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_4_pocket_1_fw",
                "buffer_stop_node": "City_4_buf_1",
                "turnaround_dwell_min": 35,
                "subsequent_service": rev_no
            }
        }
        timetable.append(fwd_service)
        rake["assigned_services"].append(fwd_no)

        # Return Run: City_4 -> City_1 (Westbound) after 40 min turnaround
        rev_dep_sec = stops_fwd[-1]["arrival_sec"] + 40 * 60
        curr_t = rev_dep_sec
        stops_rev = []
        for idx_pos, c_idx in enumerate(reversed(c1_city_indices)):
            stn = C1_STATIONS[c_idx]
            if idx_pos > 0:
                prev_dist = C1_DISTANCES[list(reversed(c1_city_indices))[idx_pos-1]]
                cur_dist = C1_DISTANCES[c_idx]
                sec_time = calc_run_time(abs(cur_dist - prev_dist), 83.33)
                curr_t += sec_time

            arr_t = curr_t
            dwell = 0 if idx_pos == len(c1_city_indices) - 1 else 120
            dep_t = arr_t + dwell
            curr_t = dep_t
            stops_rev.append({
                "station": stn,
                "train_stop_id": f"{stn}_p1_bw",
                "arrival_time": format_time(arr_t),
                "arrival_sec": round(arr_t, 1),
                "departure_time": format_time(dep_t),
                "departure_sec": round(dep_t, 1),
                "dwell_sec": dwell
            })

        rev_service = {
            "train_number": rev_no,
            "train_name": f"Trans-Regional Express {rev_no}",
            "service_class": "HighSpeed",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": [days] if days in ["Daily", "Mon-Fri"] else days.split(","),
            "corridor": "Corridor_1",
            "direction": "Westbound_BW",
            "origin_station": "City_4",
            "origin_track": "City_4_plat_1_bw",
            "dest_station": "City_1",
            "dest_track": "City_1_plat_1_bw",
            "departure_time": format_time(rev_dep_sec),
            "departure_sec": rev_dep_sec,
            "arrival_time": stops_rev[-1]["arrival_time"],
            "arrival_sec": stops_rev[-1]["arrival_sec"],
            "total_distance_km": 27.45,
            "stops": stops_rev,
            "bypassed_through_stations": ["Town_3", "Town_2", "Town_1"],
            "post_journey_disposition": {
                "action": "depot_stabling" if h >= 16 else "yard_layover",
                "staging_track": "City_1_yard_1_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 60,
                "subsequent_service": None
            }
        }
        timetable.append(rev_service)
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY B: CORRIDOR 1 LOCAL REGIONAL STOPPERS (120 km/h) ---
    # Stops at ALL stations (City_1, Town_1, City_2, Town_2, City_3_EW, Town_3, City_4)
    # Staggered between express runs, uses platform loops
    reg_c1_offsets = [
        (6, 15, "Daily",   "21001", "21002", "REG-C1-01"),
        (8, 15, "Mon-Fri", "21003", "21004", "REG-C1-02"),
        (10, 15, "Daily",  "21005", "21006", "REG-C1-01"),
        (13, 15, "Daily",  "21007", "21008", "REG-C1-02"),
        (15, 15, "Mon-Fri","21009", "21010", "REG-C1-01"),
        (17, 15, "Daily",  "21011", "21012", "REG-C1-02"),
    ]

    for h, m, days, fwd_no, rev_no, rake_id in reg_c1_offsets:
        dep_sec = h * 3600 + m * 60
        r_type = "regional_emu_120"
        rake = get_rake(rake_id, r_type)

        curr_t = dep_sec
        stops_fwd = []
        for idx, stn in enumerate(C1_STATIONS):
            if idx > 0:
                dist = C1_DISTANCES[idx] - C1_DISTANCES[idx-1]
                curr_t += calc_run_time(dist, 33.33)
            arr_t = curr_t
            dwell = 0 if idx == len(C1_STATIONS) - 1 else 60
            dep_t = arr_t + dwell
            curr_t = dep_t
            stops_fwd.append({
                "station": stn,
                "train_stop_id": f"{stn}_p2_fw",
                "arrival_time": format_time(arr_t),
                "arrival_sec": round(arr_t, 1),
                "departure_time": format_time(dep_t),
                "departure_sec": round(dep_t, 1),
                "dwell_sec": dwell
            })

        timetable.append({
            "train_number": fwd_no,
            "train_name": f"East-West Regional Local {fwd_no}",
            "service_class": "Regional",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": [days],
            "corridor": "Corridor_1",
            "direction": "Eastbound_FW",
            "origin_station": "City_1",
            "origin_track": "City_1_plat_2_fw",
            "dest_station": "City_4",
            "dest_track": "City_4_plat_2_fw",
            "departure_time": format_time(dep_sec),
            "departure_sec": dep_sec,
            "arrival_time": stops_fwd[-1]["arrival_time"],
            "arrival_sec": stops_fwd[-1]["arrival_sec"],
            "total_distance_km": 27.45,
            "stops": stops_fwd,
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_4_pocket_2_fw",
                "buffer_stop_node": "City_4_buf_2",
                "turnaround_dwell_min": 25,
                "subsequent_service": rev_no
            }
        })
        rake["assigned_services"].append(fwd_no)

        # Return Local
        rev_dep_sec = stops_fwd[-1]["arrival_sec"] + 30 * 60
        curr_t = rev_dep_sec
        stops_rev = []
        for idx, stn in enumerate(reversed(C1_STATIONS)):
            if idx > 0:
                dist = abs(C1_DISTANCES[len(C1_STATIONS)-1-idx] - C1_DISTANCES[len(C1_STATIONS)-idx])
                curr_t += calc_run_time(dist, 33.33)
            arr_t = curr_t
            dwell = 0 if idx == len(C1_STATIONS) - 1 else 60
            dep_t = arr_t + dwell
            curr_t = dep_t
            stops_rev.append({
                "station": stn,
                "train_stop_id": f"{stn}_p2_bw",
                "arrival_time": format_time(arr_t),
                "arrival_sec": round(arr_t, 1),
                "departure_time": format_time(dep_t),
                "departure_sec": round(dep_t, 1),
                "dwell_sec": dwell
            })

        timetable.append({
            "train_number": rev_no,
            "train_name": f"East-West Regional Local {rev_no}",
            "service_class": "Regional",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": [days],
            "corridor": "Corridor_1",
            "direction": "Westbound_BW",
            "origin_station": "City_4",
            "origin_track": "City_4_plat_2_bw",
            "dest_station": "City_1",
            "dest_track": "City_1_plat_2_bw",
            "departure_time": format_time(rev_dep_sec),
            "departure_sec": rev_dep_sec,
            "arrival_time": stops_rev[-1]["arrival_time"],
            "arrival_sec": stops_rev[-1]["arrival_sec"],
            "total_distance_km": 27.45,
            "stops": stops_rev,
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_1_yard_2_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 45,
                "subsequent_service": None
            }
        })
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY C: CORRIDOR 2 NORTH-SOUTH REGIONAL SPINE (120 km/h) ---
    # City_5 <-> Town_4 <-> Town_5 <-> City_3_NS <-> Town_6 <-> Town_7 <-> City_6
    c2_services = [
        (6, 30, "Daily",   "32001", "32002", "REG-C2-01"),
        (8, 0,  "Mon-Fri", "32003", "32004", "REG-C2-02"),
        (9, 30, "Daily",   "32005", "32006", "REG-C2-01"),
        (11, 0, "Daily",   "32007", "32008", "REG-C2-03"),
        (13, 0, "Daily",   "32009", "32010", "REG-C2-02"),
        (15, 0, "Mon-Fri", "32011", "32012", "REG-C2-01"),
        (17, 0, "Daily",   "32013", "32014", "REG-C2-03"),
        (19, 0, "Daily",   "32015", "32016", "REG-C2-02"),
    ]

    for h, m, days, fwd_no, rev_no, rake_id in c2_services:
        dep_sec = h * 3600 + m * 60
        r_type = "regional_emu_120"
        rake = get_rake(rake_id, r_type)

        # Southbound: City_5 -> City_6
        curr_t = dep_sec
        stops_fwd = []
        for idx, stn in enumerate(C2_STATIONS):
            if idx > 0:
                dist = C2_DISTANCES[idx] - C2_DISTANCES[idx-1]
                curr_t += calc_run_time(dist, 33.33)
            arr_t = curr_t
            dwell = 0 if idx == len(C2_STATIONS) - 1 else (90 if "City" in stn else 50)
            dep_t = arr_t + dwell
            curr_t = dep_t
            stops_fwd.append({
                "station": stn,
                "train_stop_id": f"{stn}_p1_fw",
                "arrival_time": format_time(arr_t),
                "arrival_sec": round(arr_t, 1),
                "departure_time": format_time(dep_t),
                "departure_sec": round(dep_t, 1),
                "dwell_sec": dwell
            })

        timetable.append({
            "train_number": fwd_no,
            "train_name": f"Nord-Sud InterCity Spine {fwd_no}",
            "service_class": "Regional",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": [days],
            "corridor": "Corridor_2",
            "direction": "Southbound_FW",
            "origin_station": "City_5",
            "origin_track": "City_5_plat_1_fw",
            "dest_station": "City_6",
            "dest_track": "City_6_plat_1_fw",
            "departure_time": format_time(dep_sec),
            "departure_sec": dep_sec,
            "arrival_time": stops_fwd[-1]["arrival_time"],
            "arrival_sec": stops_fwd[-1]["arrival_sec"],
            "total_distance_km": 22.62,
            "stops": stops_fwd,
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_6_pocket_1_fw",
                "buffer_stop_node": "City_6_buf_1",
                "turnaround_dwell_min": 30,
                "subsequent_service": rev_no
            }
        })
        rake["assigned_services"].append(fwd_no)

        # Northbound Return: City_6 -> City_5
        rev_dep_sec = stops_fwd[-1]["arrival_sec"] + 35 * 60
        curr_t = rev_dep_sec
        stops_rev = []
        for idx, stn in enumerate(reversed(C2_STATIONS)):
            if idx > 0:
                dist = abs(C2_DISTANCES[len(C2_STATIONS)-1-idx] - C2_DISTANCES[len(C2_STATIONS)-idx])
                curr_t += calc_run_time(dist, 33.33)
            arr_t = curr_t
            dwell = 0 if idx == len(C2_STATIONS) - 1 else (90 if "City" in stn else 50)
            dep_t = arr_t + dwell
            curr_t = dep_t
            stops_rev.append({
                "station": stn,
                "train_stop_id": f"{stn}_p1_bw",
                "arrival_time": format_time(arr_t),
                "arrival_sec": round(arr_t, 1),
                "departure_time": format_time(dep_t),
                "departure_sec": round(dep_t, 1),
                "dwell_sec": dwell
            })

        timetable.append({
            "train_number": rev_no,
            "train_name": f"Nord-Sud InterCity Spine {rev_no}",
            "service_class": "Regional",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": [days],
            "corridor": "Corridor_2",
            "direction": "Northbound_BW",
            "origin_station": "City_6",
            "origin_track": "City_6_plat_1_bw",
            "dest_station": "City_5",
            "dest_track": "City_5_plat_1_bw",
            "departure_time": format_time(rev_dep_sec),
            "departure_sec": rev_dep_sec,
            "arrival_time": stops_rev[-1]["arrival_time"],
            "arrival_sec": stops_rev[-1]["arrival_sec"],
            "total_distance_km": 22.62,
            "stops": stops_rev,
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "depot_stabling" if h >= 17 else "yard_layover",
                "staging_track": "City_5_yard_1_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 45,
                "subsequent_service": None
            }
        })
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY D: CORRIDOR 3 NORTHWEST ALPINE MOUNTAIN LINE (Hybrid DMU & Specific Days) ---
    # Exactly like the user's prompt: runs on specific days (e.g. Mon, Thu, Sun)
    # City_2 <-> Town_8 <-> Town_9 (Mountain climb)
    c3_mountain_passenger = [
        ("12763", "Alpine Scenic Shuttle 12763", ["Mon", "Thu", "Sun"], 7, 10, "ALP-Rake-01", "12764"),
        ("12765", "Alpine Glacier Express 12765", ["Tue", "Fri", "Sat"], 10, 40, "ALP-Rake-02", "12766"),
        ("12767", "Alpine Evening Shuttle 12767", ["Mon", "Thu", "Sun"], 16, 20, "ALP-Rake-01", "12768"),
    ]

    for fwd_no, name, days, h, m, rake_id, rev_no in c3_mountain_passenger:
        dep_sec = h * 3600 + m * 60
        r_type = "regional_dmu_120"
        rake = get_rake(rake_id, r_type)

        # Uphill: City_2 -> Town_9
        curr_t = dep_sec
        stops_fwd = []
        c3_sub = ["City_2", "Town_8", "Town_9"]
        for idx, stn in enumerate(c3_sub):
            if idx > 0:
                dist = C3_DISTANCES[idx] - C3_DISTANCES[idx-1]
                curr_t += calc_run_time(dist, 25.0)  # slower mountain speed limit
            arr_t = curr_t
            dwell = 0 if idx == len(c3_sub) - 1 else 90
            dep_t = arr_t + dwell
            curr_t = dep_t
            stops_fwd.append({
                "station": stn,
                "train_stop_id": f"{stn}_p1_fw",
                "arrival_time": format_time(arr_t),
                "arrival_sec": round(arr_t, 1),
                "departure_time": format_time(dep_t),
                "departure_sec": round(dep_t, 1),
                "dwell_sec": dwell
            })

        timetable.append({
            "train_number": fwd_no,
            "train_name": name,
            "service_class": "Regional",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": days,
            "corridor": "Corridor_3",
            "direction": "Uphill_FW",
            "origin_station": "City_2",
            "origin_track": "City_2_plat_3_bw",
            "dest_station": "Town_9",
            "dest_track": "Town_9_plat_1_fw",
            "departure_time": format_time(dep_sec),
            "departure_sec": dep_sec,
            "arrival_time": stops_fwd[-1]["arrival_time"],
            "arrival_sec": stops_fwd[-1]["arrival_sec"],
            "total_distance_km": 8.70,
            "stops": stops_fwd,
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "Town_9_yard_1_fw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 40,
                "subsequent_service": rev_no
            }
        })
        rake["assigned_services"].append(fwd_no)

        # Downhill Return: Town_9 -> City_2
        rev_dep_sec = stops_fwd[-1]["arrival_sec"] + 45 * 60
        curr_t = rev_dep_sec
        stops_rev = []
        for idx, stn in enumerate(reversed(c3_sub)):
            if idx > 0:
                dist = abs(C3_DISTANCES[len(c3_sub)-1-idx] - C3_DISTANCES[len(c3_sub)-idx])
                curr_t += calc_run_time(dist, 27.0)
            arr_t = curr_t
            dwell = 0 if idx == len(c3_sub) - 1 else 90
            dep_t = arr_t + dwell
            curr_t = dep_t
            stop_id = f"{stn}_p3_fw" if stn == "City_2" else f"{stn}_p1_bw"
            stops_rev.append({
                "station": stn,
                "train_stop_id": stop_id,
                "arrival_time": format_time(arr_t),
                "arrival_sec": round(arr_t, 1),
                "departure_time": format_time(dep_t),
                "departure_sec": round(dep_t, 1),
                "dwell_sec": dwell
            })

        timetable.append({
            "train_number": rev_no,
            "train_name": name.replace("Shuttle", "Return").replace("Express", "Return"),
            "service_class": "Regional",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": days,
            "corridor": "Corridor_3",
            "direction": "Downhill_BW",
            "origin_station": "Town_9",
            "origin_track": "Town_9_plat_1_bw",
            "dest_station": "City_2",
            "dest_track": "City_2_plat_3_fw",
            "departure_time": format_time(rev_dep_sec),
            "departure_sec": rev_dep_sec,
            "arrival_time": stops_rev[-1]["arrival_time"],
            "arrival_sec": stops_rev[-1]["arrival_sec"],
            "total_distance_km": 8.70,
            "stops": stops_rev,
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_2_yard_1_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 60,
                "subsequent_service": None
            }
        })
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY E: CORRIDOR 4 SOUTHERN COASTAL ARC REGIONAL (120 km/h) ---
    # City_1 <-> Town_10 <-> Town_11 <-> Depot_2 <-> Town_12 <-> City_6
    c4_services = [
        (7, 0,  "Daily",   "41001", "41002", "REG-C4-01"),
        (9, 30, "Mon-Fri", "41003", "41004", "REG-C4-02"),
        (13, 0, "Daily",   "41005", "41006", "REG-C4-01"),
        (16, 30,"Daily",   "41007", "41008", "REG-C4-02"),
    ]

    for h, m, days, fwd_no, rev_no, rake_id in c4_services:
        dep_sec = h * 3600 + m * 60
        r_type = "regional_emu_120"
        rake = get_rake(rake_id, r_type)

        # Eastbound / Counter-Clockwise: City_1 -> City_6
        curr_t = dep_sec
        stops_fwd = []
        for idx, stn in enumerate(C4_STATIONS):
            if idx > 0:
                dist = C4_DISTANCES[idx] - C4_DISTANCES[idx-1]
                curr_t += calc_run_time(dist, 33.33)
            arr_t = curr_t
            is_depot = "Depot" in stn
            dwell = 0 if idx == len(C4_STATIONS) - 1 else (0 if is_depot else 60)
            dep_t = arr_t + dwell
            curr_t = dep_t
            if not is_depot:
                stop_id = f"{stn}_p3_bw" if stn == "City_1" else f"{stn}_p1_fw"
                stops_fwd.append({
                    "station": stn,
                    "train_stop_id": stop_id,
                    "arrival_time": format_time(arr_t),
                    "arrival_sec": round(arr_t, 1),
                    "departure_time": format_time(dep_t),
                    "departure_sec": round(dep_t, 1),
                    "dwell_sec": dwell
                })

        timetable.append({
            "train_number": fwd_no,
            "train_name": f"Southern Coastal Arc {fwd_no}",
            "service_class": "Regional",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": [days],
            "corridor": "Corridor_4",
            "direction": "Eastbound_FW",
            "origin_station": "City_1",
            "origin_track": "City_1_plat_3_bw",
            "dest_station": "City_6",
            "dest_track": "City_6_plat_3_fw",
            "departure_time": format_time(dep_sec),
            "departure_sec": dep_sec,
            "arrival_time": stops_fwd[-1]["arrival_time"],
            "arrival_sec": stops_fwd[-1]["arrival_sec"],
            "total_distance_km": 27.36,
            "stops": stops_fwd,
            "bypassed_through_stations": ["Depot_2"],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_6_pocket_2_fw",
                "buffer_stop_node": "City_6_buf_2",
                "turnaround_dwell_min": 35,
                "subsequent_service": rev_no
            }
        })
        rake["assigned_services"].append(fwd_no)

        # Westbound Return: City_6 -> City_1
        rev_dep_sec = stops_fwd[-1]["arrival_sec"] + 40 * 60
        curr_t = rev_dep_sec
        stops_rev = []
        for idx, stn in enumerate(reversed(C4_STATIONS)):
            if idx > 0:
                dist = abs(C4_DISTANCES[len(C4_STATIONS)-1-idx] - C4_DISTANCES[len(C4_STATIONS)-idx])
                curr_t += calc_run_time(dist, 33.33)
            arr_t = curr_t
            is_depot = "Depot" in stn
            dwell = 0 if idx == len(C4_STATIONS) - 1 else (0 if is_depot else 60)
            dep_t = arr_t + dwell
            curr_t = dep_t
            if not is_depot:
                stop_id = f"{stn}_p3_fw" if stn == "City_1" else f"{stn}_p1_bw"
                stops_rev.append({
                    "station": stn,
                    "train_stop_id": stop_id,
                    "arrival_time": format_time(arr_t),
                    "arrival_sec": round(arr_t, 1),
                    "departure_time": format_time(dep_t),
                    "departure_sec": round(dep_t, 1),
                    "dwell_sec": dwell
                })

        timetable.append({
            "train_number": rev_no,
            "train_name": f"Southern Coastal Arc {rev_no}",
            "service_class": "Regional",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": [days],
            "corridor": "Corridor_4",
            "direction": "Westbound_BW",
            "origin_station": "City_6",
            "origin_track": "City_6_plat_3_bw",
            "dest_station": "City_1",
            "dest_track": "City_1_plat_3_fw",
            "departure_time": format_time(rev_dep_sec),
            "departure_sec": rev_dep_sec,
            "arrival_time": stops_rev[-1]["arrival_time"],
            "arrival_sec": stops_rev[-1]["arrival_sec"],
            "total_distance_km": 27.36,
            "stops": stops_rev,
            "bypassed_through_stations": ["Depot_2"],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_1_yard_2_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 60,
                "subsequent_service": None
            }
        })
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY F: HIGH-SPEED DIAGONAL BYPASS EXPRESS (300 km/h) ---
    # Direct chord connecting City_2 <-> City_5 without going through City_3
    bypass_services = [
        (8, 30, "Mon-Fri", "15001", "15002", "HS-Rake-04"),
        (13, 30, "Daily",  "15003", "15004", "HS-Rake-04"),
    ]

    for h, m, days, fwd_no, rev_no, rake_id in bypass_services:
        dep_sec = h * 3600 + m * 60
        r_type = "high_speed_emu_single"
        rake = get_rake(rake_id, r_type)
        bypass_dist = 13300.0
        sec_time = calc_run_time(bypass_dist, 83.33)

        # FWD: City_2 -> City_5
        arr_sec = dep_sec + sec_time
        timetable.append({
            "train_number": fwd_no,
            "train_name": f"Diagonal Bypass Direct {fwd_no}",
            "service_class": "HighSpeed",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": [days],
            "corridor": "Bypass_C2_C5",
            "direction": "Northeast_FW",
            "origin_station": "City_2",
            "origin_track": "City_2_plat_2_fw",
            "dest_station": "City_5",
            "dest_track": "City_5_plat_2_bw",
            "departure_time": format_time(dep_sec),
            "departure_sec": dep_sec,
            "arrival_time": format_time(arr_sec),
            "arrival_sec": round(arr_sec, 1),
            "total_distance_km": 13.30,
            "stops": [
                {"station": "City_2", "train_stop_id": "City_2_p2_fw", "arrival_time": format_time(dep_sec), "arrival_sec": dep_sec, "departure_time": format_time(dep_sec), "departure_sec": dep_sec, "dwell_sec": 0},
                {"station": "City_5", "train_stop_id": "City_5_p2_bw", "arrival_time": format_time(arr_sec), "arrival_sec": round(arr_sec, 1), "departure_time": format_time(arr_sec), "departure_sec": round(arr_sec, 1), "dwell_sec": 0}
            ],
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_5_yard_2_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 45,
                "subsequent_service": rev_no
            }
        })
        rake["assigned_services"].append(fwd_no)

        # REV: City_5 -> City_2
        rev_dep = arr_sec + 45 * 60
        rev_arr = rev_dep + sec_time
        timetable.append({
            "train_number": rev_no,
            "train_name": f"Diagonal Bypass Direct {rev_no}",
            "service_class": "HighSpeed",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": [days],
            "corridor": "Bypass_C2_C5",
            "direction": "Southwest_BW",
            "origin_station": "City_5",
            "origin_track": "City_5_plat_2_fw",
            "dest_station": "City_2",
            "dest_track": "City_2_plat_2_bw",
            "departure_time": format_time(rev_dep),
            "departure_sec": round(rev_dep, 1),
            "arrival_time": format_time(rev_arr),
            "arrival_sec": round(rev_arr, 1),
            "total_distance_km": 13.30,
            "stops": [
                {"station": "City_5", "train_stop_id": "City_5_p2_fw", "arrival_time": format_time(rev_dep), "arrival_sec": round(rev_dep, 1), "departure_time": format_time(rev_dep), "departure_sec": round(rev_dep, 1), "dwell_sec": 0},
                {"station": "City_2", "train_stop_id": "City_2_p2_bw", "arrival_time": format_time(rev_arr), "arrival_sec": round(rev_arr, 1), "departure_time": format_time(rev_arr), "departure_sec": round(rev_arr, 1), "dwell_sec": 0}
            ],
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_2_yard_2_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 60,
                "subsequent_service": None
            }
        })
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY G: CROSS-HUB FLYOVER TRANSFER INTERCHANGE (120 km/h) ---
    # Eastern Terminus (City_4) <-> City_3_EW <-> Flyover Ramp <-> City_3_NS <-> Southern Terminus (City_6)
    transfer_services = [
        (8, 45,  "Daily", "51001", "51002", "REG-XFER-01"),
        (14, 45, "Daily", "51003", "51004", "REG-XFER-01"),
    ]

    for h, m, days, fwd_no, rev_no, rake_id in transfer_services:
        dep_sec = h * 3600 + m * 60
        r_type = "regional_emu_120"
        rake = get_rake(rake_id, r_type)

        # Westbound-to-Southbound: City_4 -> City_3_EW -> Flyover Ramp -> City_3_NS -> City_6
        dist_c1_part = 27445.0 - 18321.0 # 9124m
        dist_ramp = 789.0
        dist_c2_part = 22616.0 - 11050.0 # 11566m
        total_dist = dist_c1_part + dist_ramp + dist_c2_part

        t1 = calc_run_time(dist_c1_part, 33.33)
        t_ramp = calc_run_time(dist_ramp, 22.22)
        t2 = calc_run_time(dist_c2_part, 33.33)

        c3_arr = dep_sec + t1
        c3_dep = c3_arr + 180 # 3 min transfer dwell
        c6_arr = c3_dep + t_ramp + t2

        timetable.append({
            "train_number": fwd_no,
            "train_name": f"Trans-Hub Inter-Corridor Link {fwd_no}",
            "service_class": "Regional",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": [days],
            "corridor": "Interchange_C1_C2",
            "direction": "East_to_South_Xfer",
            "origin_station": "City_4",
            "origin_track": "City_4_plat_4_bw",
            "dest_station": "City_6",
            "dest_track": "City_6_plat_4_fw",
            "departure_time": format_time(dep_sec),
            "departure_sec": dep_sec,
            "arrival_time": format_time(c6_arr),
            "arrival_sec": round(c6_arr, 1),
            "total_distance_km": round(total_dist / 1000.0, 2),
            "stops": [
                {"station": "City_4", "train_stop_id": "City_4_p4_bw", "arrival_time": format_time(dep_sec), "arrival_sec": dep_sec, "departure_time": format_time(dep_sec), "departure_sec": dep_sec, "dwell_sec": 0},
                {"station": "City_3_EW", "train_stop_id": "City_3_EW_p4_bw", "arrival_time": format_time(c3_arr), "arrival_sec": round(c3_arr, 1), "departure_time": format_time(c3_dep), "departure_sec": round(c3_dep, 1), "dwell_sec": 180},
                {"station": "City_6", "train_stop_id": "City_6_p4_fw", "arrival_time": format_time(c6_arr), "arrival_sec": round(c6_arr, 1), "departure_time": format_time(c6_arr), "departure_sec": round(c6_arr, 1), "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_3", "Town_6", "Town_7"],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_6_pocket_2_fw",
                "buffer_stop_node": "City_6_buf_2",
                "turnaround_dwell_min": 40,
                "subsequent_service": rev_no
            }
        })
        rake["assigned_services"].append(fwd_no)

        # Northbound-to-Eastbound Return: City_6 -> City_3_NS -> Flyover Ramp -> City_3_EW -> City_4
        rev_dep = c6_arr + 40 * 60
        rev_c3_arr = rev_dep + t2
        rev_c3_dep = rev_c3_arr + 180
        rev_c4_arr = rev_c3_dep + t_ramp + t1

        timetable.append({
            "train_number": rev_no,
            "train_name": f"Trans-Hub Inter-Corridor Link {rev_no}",
            "service_class": "Regional",
            "rolling_stock_type": r_type,
            "assigned_rake": rake_id,
            "service_days": [days],
            "corridor": "Interchange_C1_C2",
            "direction": "South_to_East_Xfer",
            "origin_station": "City_6",
            "origin_track": "City_6_plat_4_bw",
            "dest_station": "City_4",
            "dest_track": "City_4_plat_4_fw",
            "departure_time": format_time(rev_dep),
            "departure_sec": round(rev_dep, 1),
            "arrival_time": format_time(rev_c4_arr),
            "arrival_sec": round(rev_c4_arr, 1),
            "total_distance_km": round(total_dist / 1000.0, 2),
            "stops": [
                {"station": "City_6", "train_stop_id": "City_6_p4_bw", "arrival_time": format_time(rev_dep), "arrival_sec": round(rev_dep, 1), "departure_time": format_time(rev_dep), "departure_sec": round(rev_dep, 1), "dwell_sec": 0},
                {"station": "City_3_NS", "train_stop_id": "City_3_NS_p4_bw", "arrival_time": format_time(rev_c3_arr), "arrival_sec": round(rev_c3_arr, 1), "departure_time": format_time(rev_c3_dep), "departure_sec": round(rev_c3_dep, 1), "dwell_sec": 180},
                {"station": "City_4", "train_stop_id": "City_4_p4_fw", "arrival_time": format_time(rev_c4_arr), "arrival_sec": round(rev_c4_arr, 1), "departure_time": format_time(rev_c4_arr), "departure_sec": round(rev_c4_arr, 1), "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_7", "Town_6", "Town_3"],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_4_yard_1_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 60,
                "subsequent_service": None
            }
        })
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY H: HEAVY FREIGHT & LOGISTICS TRAINS (80 km/h) ---
    # Freight services running depot-to-depot across the network
    freight_schedules = [
        # 1. Mountain Bulk Ore: City_2 (Staging Yard) -> Alpine Passing Loop -> Depot_1
        {
            "train_number": "68101",
            "train_name": "Alpine Mineral Express 68101",
            "service_class": "Freight",
            "rolling_stock_type": "heavy_freight_cargo",
            "assigned_rake": "FRT-Rake-01",
            "service_days": ["Tue", "Thu", "Sat"],
            "corridor": "Corridor_3",
            "direction": "Inbound_Cargo_Climb",
            "origin_station": "City_2",
            "origin_track": "City_2_yard_1_bw",
            "dest_station": "Depot_1",
            "dest_track": "Depot_1_pocket_1_fw",
            "departure_time": "04:30:00",
            "departure_sec": 4 * 3600 + 30 * 60,
            "arrival_time": "05:25:00",
            "arrival_sec": 5 * 3600 + 25 * 60,
            "total_distance_km": 12.94,
            "stops": [
                {"station": "City_2", "train_stop_id": None, "arrival_time": "04:30:00", "arrival_sec": 16200, "departure_time": "04:30:00", "departure_sec": 16200, "dwell_sec": 0},
                {"station": "Town_8_Passing_Loop", "train_stop_id": None, "arrival_time": "04:55:00", "arrival_sec": 17700, "departure_time": "05:07:00", "departure_sec": 18420, "dwell_sec": 720}, # holds 12 mins for passenger overtakes
                {"station": "Depot_1", "train_stop_id": None, "arrival_time": "05:25:00", "arrival_sec": 19500, "departure_time": "05:25:00", "departure_sec": 19500, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_8", "Town_9"],
            "post_journey_disposition": {
                "action": "depot_stabling",
                "staging_track": "Depot_1_pocket_1_fw",
                "buffer_stop_node": "Depot_1_buf_1",
                "turnaround_dwell_min": 240,
                "subsequent_service": "68102"
            }
        },
        # 2. Return Ore Empty Cars: Depot_1 -> Alpine Loop -> City_2
        {
            "train_number": "68102",
            "train_name": "Alpine Mineral Return 68102",
            "service_class": "Freight",
            "rolling_stock_type": "heavy_freight_cargo",
            "assigned_rake": "FRT-Rake-01",
            "service_days": ["Tue", "Thu", "Sat"],
            "corridor": "Corridor_3",
            "direction": "Outbound_Empty_Descent",
            "origin_station": "Depot_1",
            "origin_track": "Depot_1_pocket_1_bw",
            "dest_station": "City_2",
            "dest_track": "City_2_yard_1_fw",
            "departure_time": "11:00:00",
            "departure_sec": 11 * 3600,
            "arrival_time": "11:45:00",
            "arrival_sec": 11 * 3600 + 45 * 60,
            "total_distance_km": 12.94,
            "stops": [
                {"station": "Depot_1", "train_stop_id": None, "arrival_time": "11:00:00", "arrival_sec": 39600, "departure_time": "11:00:00", "departure_sec": 39600, "dwell_sec": 0},
                {"station": "City_2", "train_stop_id": None, "arrival_time": "11:45:00", "arrival_sec": 42300, "departure_time": "11:45:00", "departure_sec": 42300, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_9", "Town_8"],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_2_yard_1_fw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 180,
                "subsequent_service": None
            }
        },
        # 3. Intermodal Container Freight: City_5 -> Depot_3 (Northern Logistics Spur)
        {
            "train_number": "68201",
            "train_name": "Northern Container Feeder 68201",
            "service_class": "Freight",
            "rolling_stock_type": "intermodal_container_freight",
            "assigned_rake": "FRT-Rake-02",
            "service_days": ["Mon", "Wed", "Fri"],
            "corridor": "Spur_City_5_Depot_3",
            "direction": "Spur_Inbound",
            "origin_station": "City_5",
            "origin_track": "City_5_yard_1_bw",
            "dest_station": "Depot_3",
            "dest_track": "Depot_3_pocket_1_fw",
            "departure_time": "05:00:00",
            "departure_sec": 5 * 3600,
            "arrival_time": "05:35:00",
            "arrival_sec": 5 * 3600 + 35 * 60,
            "total_distance_km": 6.8,
            "stops": [
                {"station": "City_5", "train_stop_id": None, "arrival_time": "05:00:00", "arrival_sec": 18000, "departure_time": "05:00:00", "departure_sec": 18000, "dwell_sec": 0},
                {"station": "Depot_3", "train_stop_id": None, "arrival_time": "05:35:00", "arrival_sec": 20100, "departure_time": "05:35:00", "departure_sec": 20100, "dwell_sec": 0}
            ],
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "depot_stabling",
                "staging_track": "Depot_3_pocket_1_fw",
                "buffer_stop_node": "Depot_3_buf_1",
                "turnaround_dwell_min": 300,
                "subsequent_service": "68202"
            }
        },
        # 4. Return Container Freight: Depot_3 -> City_5
        {
            "train_number": "68202",
            "train_name": "Northern Container Feeder 68202",
            "service_class": "Freight",
            "rolling_stock_type": "intermodal_container_freight",
            "assigned_rake": "FRT-Rake-02",
            "service_days": ["Mon", "Wed", "Fri"],
            "corridor": "Spur_City_5_Depot_3",
            "direction": "Spur_Outbound",
            "origin_station": "Depot_3",
            "origin_track": "Depot_3_pocket_1_bw",
            "dest_station": "City_5",
            "dest_track": "City_5_yard_1_fw",
            "departure_time": "14:00:00",
            "departure_sec": 14 * 3600,
            "arrival_time": "14:35:00",
            "arrival_sec": 14 * 3600 + 35 * 60,
            "total_distance_km": 6.8,
            "stops": [
                {"station": "Depot_3", "train_stop_id": None, "arrival_time": "14:00:00", "arrival_sec": 50400, "departure_time": "14:00:00", "departure_sec": 50400, "dwell_sec": 0},
                {"station": "City_5", "train_stop_id": None, "arrival_time": "14:35:00", "arrival_sec": 52500, "departure_time": "14:35:00", "departure_sec": 52500, "dwell_sec": 0}
            ],
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_5_yard_1_fw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 360,
                "subsequent_service": None
            }
        },
        # 5. Coastal Industrial Cargo: Depot_2 -> City_6
        {
            "train_number": "68301",
            "train_name": "Coastal Bulk Cargo 68301",
            "service_class": "Freight",
            "rolling_stock_type": "heavy_freight_cargo",
            "assigned_rake": "FRT-Rake-03",
            "service_days": ["Tue", "Thu", "Sat"],
            "corridor": "Corridor_4",
            "direction": "Eastbound_Cargo",
            "origin_station": "Depot_2",
            "origin_track": "Depot_2_yard_1_fw",
            "dest_station": "City_6",
            "dest_track": "City_6_pocket_1_fw",
            "departure_time": "03:30:00",
            "departure_sec": 3 * 3600 + 30 * 60,
            "arrival_time": "04:40:00",
            "arrival_sec": 4 * 3600 + 40 * 60,
            "total_distance_km": 12.4,
            "stops": [
                {"station": "Depot_2", "train_stop_id": None, "arrival_time": "03:30:00", "arrival_sec": 12600, "departure_time": "03:30:00", "departure_sec": 12600, "dwell_sec": 0},
                {"station": "City_6", "train_stop_id": None, "arrival_time": "04:40:00", "arrival_sec": 16800, "departure_time": "04:40:00", "departure_sec": 16800, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_12"],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_6_pocket_1_fw",
                "buffer_stop_node": "City_6_buf_1",
                "turnaround_dwell_min": 180,
                "subsequent_service": "68302"
            }
        },
        # 6. Coastal Industrial Cargo Return: City_6 -> Depot_2
        {
            "train_number": "68302",
            "train_name": "Coastal Bulk Cargo Return 68302",
            "service_class": "Freight",
            "rolling_stock_type": "heavy_freight_cargo",
            "assigned_rake": "FRT-Rake-03",
            "service_days": ["Tue", "Thu", "Sat"],
            "corridor": "Corridor_4",
            "direction": "Westbound_Cargo",
            "origin_station": "City_6",
            "origin_track": "City_6_pocket_1_bw",
            "dest_station": "Depot_2",
            "dest_track": "Depot_2_yard_1_bw",
            "departure_time": "08:30:00",
            "departure_sec": 8 * 3600 + 30 * 60,
            "arrival_time": "09:40:00",
            "arrival_sec": 9 * 3600 + 40 * 60,
            "total_distance_km": 12.4,
            "stops": [
                {"station": "City_6", "train_stop_id": None, "arrival_time": "08:30:00", "arrival_sec": 30600, "departure_time": "08:30:00", "departure_sec": 30600, "dwell_sec": 0},
                {"station": "Depot_2", "train_stop_id": None, "arrival_time": "09:40:00", "arrival_sec": 34800, "departure_time": "09:40:00", "departure_sec": 34800, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_12"],
            "post_journey_disposition": {
                "action": "depot_stabling",
                "staging_track": "Depot_2_yard_1_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 240,
                "subsequent_service": None
            }
        }
    ]

    for f_srv in freight_schedules:
        timetable.append(f_srv)
        rk = get_rake(f_srv["assigned_rake"], f_srv["rolling_stock_type"])
        rk["assigned_services"].append(f_srv["train_number"])

    # Sort master timetable by departure time
    timetable.sort(key=lambda s: s["departure_sec"])

    return ROLLING_STOCK_TYPES, timetable, rakes

def main():
    rs_types, timetable, rakes = build_timetable()

    rs_path = os.path.join(DATA_DIR, "rolling_stock_types.json")
    with open(rs_path, "w", encoding="utf-8") as f:
        json.dump(rs_types, f, indent=2)

    tt_path = os.path.join(DATA_DIR, "timetable.json")
    with open(tt_path, "w", encoding="utf-8") as f:
        json.dump(timetable, f, indent=2)

    rk_path = os.path.join(DATA_DIR, "rakes_roster.json")
    with open(rk_path, "w", encoding="utf-8") as f:
        json.dump(list(rakes.values()), f, indent=2)

    print("=" * 65)
    print("MASTER RAILWAY TIMETABLE & FLEET GENERATED")
    print("=" * 65)
    print(f"Rolling stock models defined : {len(rs_types)}")
    print(f"Total scheduled train runs   : {len(timetable)}")
    print(f"Physical rakes in roster     : {len(rakes)}")
    print(f"Data files written to        : {DATA_DIR}")
    print("=" * 65)

if __name__ == "__main__":
    main()
