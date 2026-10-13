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
    },
    "electric_trunk_freight": {
        "type_id": "electric_trunk_freight",
        "name": "Vectron E-Cargo Trunk Fast Freight (Class 193 + Flatcars)",
        "service_class": "Freight",
        "sumo_vclass": "rail_electric",
        "power_supply": "Electric 15kV / 25kV Multi-System",
        "track_gauge_mm": 1435,
        "max_speed_kmh": 100,
        "max_speed_ms": 27.78,
        "acceleration_ms2": 0.45,
        "deceleration_ms2": 0.60,
        "emergency_decel_ms2": 1.4,
        "total_length_m": 400.0,
        "carriages_count": 24,
        "gross_weight_tons": 2400.0,
        "passenger_capacity": 0,
        "gui_shape": "rail/cargo",
        "gui_color": "0.2,0.65,0.85"  # Steel Cyan Cargo
    }
}

# -----------------------------------------------------------------------------
# 2. MASTER CORRIDOR STATION SEQUENCES & PHYSICAL DISTANCES
# -----------------------------------------------------------------------------
# Corridor 1: East-West High Speed Trunk (28.2 km)
# Stations: City_1 <-> Town_1 <-> City_2 <-> Town_2 <-> City_3_EW <-> Town_3 <-> City_4
C1_STATIONS = ["City_1", "Town_1", "City_2", "Town_2", "City_3_EW", "Town_3", "City_4"]
C1_DISTANCES = [0, 4816, 9330, 13917, 18646, 23268, 28200]  # cumulative meters

# Corridor 2: North-South Regional Spine (23.2 km)
# Stations: City_5 <-> Town_4 <-> Town_5 <-> City_3_NS <-> Town_6 <-> Town_7 <-> City_6
C2_STATIONS = ["City_5", "Town_4", "Town_5", "City_3_NS", "Town_6", "Town_7", "City_6"]
C2_DISTANCES = [0, 4161, 7783, 11315, 15024, 18587, 23161]

# Corridor 3: Northwest Alpine Mountain Line (14.4 km)
# Stations: City_2 <-> Town_8 <-> Town_9 <-> Depot_1
C3_STATIONS = ["City_2", "Town_8", "Town_9", "Depot_1"]
C3_DISTANCES = [0, 5274, 9850, 14438]

# Corridor 4: Southern Coastal Arc (29.3 km)
# Stations: City_1 <-> Town_10 <-> Town_11 <-> Depot_2 <-> Town_12 <-> City_6
C4_STATIONS = ["City_1", "Town_10", "Town_11", "Depot_2", "Town_12", "City_6"]
C4_DISTANCES = [0, 5215, 9770, 14260, 22210, 29252]

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
            home = "Depot_4"
            if "ALP" in rake_id or "FRT-Rake-01" in rake_id:
                home = "Depot_1"
            elif "C4" in rake_id or "FRT-Rake-03" in rake_id:
                home = "Depot_2"
            elif "C2" in rake_id or "FRT-Rake-02" in rake_id:
                home = "Depot_3"
            elif "FRT-Rake-04" in rake_id or "C1" in rake_id or "HS" in rake_id or "XFER" in rake_id:
                home = "Depot_4"
            rakes[rake_id] = {
                "rake_id": rake_id,
                "rolling_stock_type": r_type,
                "home_depot": home,
                "assigned_services": []
            }
        return rakes[rake_id]

    MIN_TURNAROUND_BY_CONSIST = {
        "high_speed_emu_300": 12.0,        # 400m 16-car EMU: 12.0 min rapid dual-crew turnaround
        "high_speed_emu_single": 12.0,     # 200m 8-car EMU: 12.0 min
        "regional_emu_120": 7.0,           # 160m 6-car commuter EMU: 7.0 min rapid dual-crew turnaround
        "regional_dmu_120": 7.0,           # 120m 4-car hybrid DMU: 7.0 min
        "heavy_freight_cargo": 30.0,       # Heavy freight: 30 min shunting and brake check
        "intermodal_container_freight": 30.0,
        "electric_trunk_freight": 25.0
    }

    def is_peak_hour(dep_sec):
        hour = int((dep_sec // 3600) % 24)
        minute = int((dep_sec % 3600) // 60)
        # Morning peak: 07:00 - 09:30
        if (7 <= hour < 9) or (hour == 9 and minute <= 30):
            return True
        # Evening peak: 16:00 - 18:45
        if (16 <= hour < 18) or (hour == 18 and minute <= 45):
            return True
        return False

    def get_calibrated_dwell(stn, service_class="Regional", is_terminal=False, dep_sec=0, r_type=None):
        """
        Calibrates stop dwell times dynamically based on station hierarchy, time of day, and consist capacity:
        - Terminal stations: 0s (handled by post-journey turnaround / layover)
        - City_3 Bi-Level Interchange:
            * Flyover Transfer (multi-level connection): 210s peak / 180s off-peak
            * Regional / High-Speed Spine: 180s peak / 150s off-peak
        - Major City Hubs (City_1, City_2, City_4, City_5, City_6):
            * HighSpeed 300 (16 cars, 1,050 pax): 150s peak / 120s off-peak
            * HighSpeed Single (8 cars, 520 pax): 120s peak / 90s off-peak
            * Regional EMU / DMU: 110s peak / 90s off-peak
        - Alpine Mountain stations (Town_8, Town_9):
            * 75s (scenic tourists, heavy luggage)
        - Intermediate Town platform loops (Town_1..Town_7, Town_10..Town_12):
            * 55s peak on Corridor 2 / 60s peak on other corridors / 45s off-peak (rapid exchange)
        """
        if is_terminal:
            return 0
        is_peak = is_peak_hour(dep_sec)
        if stn in ["City_3_EW", "City_3_NS"]:
            if service_class == "Interchange":
                return 210 if is_peak else 180
            return 180 if is_peak else 150
        elif "City" in stn:
            if r_type == "high_speed_emu_300" or service_class == "HighSpeed":
                return 150 if is_peak else 120
            elif r_type == "high_speed_emu_single":
                return 120 if is_peak else 90
            else:
                return 110 if is_peak else 90
        elif stn in ["Town_8", "Town_9"]:
            return 75
        elif stn in ["Town_4", "Town_5", "Town_6", "Town_7"]:
            return 55 if is_peak else 45
        elif "Town" in stn:
            return 60 if is_peak else 45
        return 60

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
    # TAKTFAHRPLAN: Eastbound departs at :00, Westbound departs at :30 past the hour.
    # PEAK SURGE: 30-min headway compression during 07:00-09:00 and 16:00-18:30 rush hours.
    hs_departure_offsets = [
        # (fwd_h, fwd_m, rev_h, rev_m, days, fwd_no, rev_no, rake_id)
        # Morning Early + Peak Surge
        (6, 0, 6, 35, "Mon-Fri", "12001", "12002", "HS-Rake-01"),
        (7, 0, 7, 35, "Daily",   "12003", "12004", "HS-Rake-02"),
        (7, 30, 8, 5, "Mon-Fri", "12017", "12018", "HS-Rake-03"),
        (8, 0, 8, 35, "Mon-Fri", "12005", "12006", "HS-Rake-01"),
        (8, 30, 9, 5, "Mon-Fri", "12019", "12020", "HS-Rake-05"),
        (9, 0, 9, 35, "Daily",   "12031", "12032", "HS-Rake-03"),
        # Midday Regular Clockface Cadence
        (10, 0, 10, 35, "Daily",  "12007", "12008", "HS-Rake-02"),
        (11, 0, 11, 35, "Daily",  "12033", "12034", "HS-Rake-06"),
        (12, 0, 12, 35, "Daily",  "12009", "12010", "HS-Rake-01"),
        (13, 0, 13, 35, "Daily",  "12035", "12036", "HS-Rake-05"),
        (14, 0, 14, 35, "Daily",  "12011", "12012", "HS-Rake-02"),
        (15, 0, 15, 35, "Daily",  "12037", "12038", "HS-Rake-06"),
        # Evening Peak Surge
        (16, 0, 16, 35, "Mon-Fri","12013", "12014", "HS-Rake-03"),
        (16, 30, 17, 5, "Mon-Fri","12021", "12022", "HS-Rake-01"),
        (17, 0, 17, 35, "Mon-Fri","12025", "12026", "HS-Rake-05"),
        (17, 30, 18, 5, "Mon-Fri","12023", "12024", "HS-Rake-06"),
        (18, 0, 18, 35, "Daily",  "12015", "12016", "HS-Rake-02"),
        # Evening Clockface Base
        (19, 0, 19, 35, "Daily",  "12039", "12040", "HS-Rake-03"),
        (20, 0, 20, 35, "Daily",  "12027", "12028", "HS-Rake-01"),
        (21, 0, 21, 35, "Daily",  "12041", "12042", "HS-Rake-06"),
        (22, 0, 22, 35, "Daily",  "12029", "12030", "HS-Rake-02"),
    ]

    for fh, fm, rh, rm, days, fwd_no, rev_no, rake_id in hs_departure_offsets:
        dep_sec = fh * 3600 + fm * 60
        r_type = "high_speed_emu_300"
        rake = get_rake(rake_id, r_type)

        # Forward Run: City_1 -> City_4 (Eastbound) on :00 pulse
        # Calibrated physical inter-station runtimes on 300 km/h trunk:
        # City_1 -> City_2 (307s), City_2 -> City_3_EW (284s), City_3_EW -> City_4 (271s), sum = 862s
        hs_leg_runtimes_fwd = [307.0, 284.0, 271.0]
        curr_t = dep_sec
        stops_fwd = []
        c1_city_indices = [0, 2, 4, 6]  # City_1, City_2, City_3_EW, City_4
        for idx_pos, c_idx in enumerate(c1_city_indices):
            stn = C1_STATIONS[c_idx]
            if idx_pos > 0:
                curr_t += hs_leg_runtimes_fwd[idx_pos - 1]

            arr_t = curr_t
            dwell = get_calibrated_dwell(stn, "HighSpeed", idx_pos == len(c1_city_indices) - 1, dep_sec=dep_sec, r_type=r_type)
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

        rev_dep_sec = rh * 3600 + rm * 60
        turnaround_dwell_min = round((rev_dep_sec - stops_fwd[-1]["arrival_sec"]) / 60.0, 1)
        min_required = MIN_TURNAROUND_BY_CONSIST[r_type]
        if turnaround_dwell_min < min_required:
            raise ValueError(
                f"Infeasible turnaround for service {fwd_no} -> {rev_no}: "
                f"allocated dwell {turnaround_dwell_min} min is less than required minimum {min_required} min "
                f"for consist model {r_type}."
            )
        turnaround_mode = "rapid_dual_crew" if turnaround_dwell_min <= (min_required + 3.0) else "standard_cab_swap"

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
            "departure_time": stops_fwd[0]["departure_time"],
            "departure_sec": stops_fwd[0]["departure_sec"],
            "arrival_time": stops_fwd[-1]["arrival_time"],
            "arrival_sec": stops_fwd[-1]["arrival_sec"],
            "total_distance_km": 28.21,
            "stops": stops_fwd,
            "bypassed_through_stations": ["Town_1", "Town_2", "Town_3"],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_4_pocket_1_fw",
                "buffer_stop_node": "City_4_buf_1",
                "turnaround_dwell_min": turnaround_dwell_min,
                "min_turnaround_required_min": min_required,
                "turnaround_mode": turnaround_mode,
                "subsequent_service": rev_no
            }
        }
        timetable.append(fwd_service)
        rake["assigned_services"].append(fwd_no)

        # Return Run: City_4 -> City_1 (Westbound) on :35 / :05 pulse
        # Calibrated runtimes: City_4 -> City_3_EW (311s), City_3_EW -> City_2 (284s), City_2 -> City_1 (269s), sum = 864s
        hs_leg_runtimes_rev = [311.0, 284.0, 269.0]
        curr_t = rev_dep_sec
        stops_rev = []
        for idx_pos, c_idx in enumerate(reversed(c1_city_indices)):
            stn = C1_STATIONS[c_idx]
            if idx_pos > 0:
                curr_t += hs_leg_runtimes_rev[idx_pos - 1]

            arr_t = curr_t
            dwell = get_calibrated_dwell(stn, "HighSpeed", idx_pos == len(c1_city_indices) - 1, dep_sec=rev_dep_sec, r_type=r_type)
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
            "departure_time": stops_rev[0]["departure_time"],
            "departure_sec": stops_rev[0]["departure_sec"],
            "arrival_time": stops_rev[-1]["arrival_time"],
            "arrival_sec": stops_rev[-1]["arrival_sec"],
            "total_distance_km": 28.21,
            "stops": stops_rev,
            "bypassed_through_stations": ["Town_3", "Town_2", "Town_1"],
            "post_journey_disposition": {
                "action": "depot_stabling" if rh >= 16 else "yard_layover",
                "staging_track": "City_1_yard_1_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 60,
                "min_turnaround_required_min": MIN_TURNAROUND_BY_CONSIST[r_type],
                "turnaround_mode": "extended_layover",
                "subsequent_service": None
            }
        }
        timetable.append(rev_service)
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY B: CORRIDOR 1 LOCAL REGIONAL STOPPERS (120 km/h) ---
    # Stops at ALL stations (City_1, Town_1, City_2, Town_2, City_3_EW, Town_3, City_4)
    # Staggered between express runs, uses platform loops
    # TAKTFAHRPLAN: Eastbound departs at :15, Westbound departs at :55 past the hour (and :25 in peak).
    # PEAK SURGE: 30-min commuter frequency during morning (07:15, 07:45, 08:15, 08:45) and evening (16:15, 16:45, 17:15, 17:45, 18:15).
    reg_c1_offsets = [
        # (fh, fm, rh, rm, days, fwd_no, rev_no, rake_id)
        # Early Morning
        (5, 15, 5, 55, "Daily",   "21021", "21022", "REG-C1-05"),
        (6, 15, 6, 55, "Daily",   "21001", "21002", "REG-C1-01"),
        # Morning Peak Surge (30-min headway)
        (7, 15, 7, 55, "Mon-Fri", "21013", "21014", "REG-C1-03"),
        (7, 45, 8, 25, "Mon-Fri", "21015", "21016", "REG-C1-04"),
        (8, 15, 8, 55, "Mon-Fri", "21003", "21004", "REG-C1-02"),
        (8, 45, 9, 25, "Mon-Fri", "21029", "21030", "REG-C1-06"),
        (9, 15, 9, 55, "Daily",   "21035", "21036", "REG-C1-05"),
        # Midday Regular Cadence (60-min hourly clockface)
        (10, 15, 10, 55, "Daily",  "21005", "21006", "REG-C1-01"),
        (11, 15, 11, 55, "Daily",  "21023", "21024", "REG-C1-03"),
        (12, 15, 12, 55, "Daily",  "21037", "21038", "REG-C1-05"),
        (13, 15, 13, 55, "Daily",  "21007", "21008", "REG-C1-02"),
        (14, 15, 14, 55, "Daily",  "21025", "21026", "REG-C1-04"),
        (15, 15, 15, 55, "Mon-Fri","21009", "21010", "REG-C1-05"),
        # Evening Peak Surge (30-min headway)
        (16, 15, 16, 55, "Mon-Fri","21017", "21018", "REG-C1-03"),
        (16, 45, 17, 25, "Mon-Fri","21031", "21032", "REG-C1-05"),
        (17, 15, 17, 55, "Daily",  "21011", "21012", "REG-C1-02"),
        (17, 45, 18, 25, "Mon-Fri","21019", "21020", "REG-C1-04"),
        (18, 15, 18, 55, "Mon-Fri","21033", "21034", "REG-C1-06"),
        # Late Evening Clockface Base
        (19, 15, 19, 55, "Daily",  "21027", "21028", "REG-C1-01"),
        (20, 15, 20, 55, "Daily",  "21039", "21040", "REG-C1-04"),
        (21, 15, 21, 55, "Daily",  "21041", "21042", "REG-C1-03"),
    ]

    for fh, fm, rh, rm, days, fwd_no, rev_no, rake_id in reg_c1_offsets:
        dep_sec = fh * 3600 + fm * 60
        r_type = "regional_emu_120"
        rake = get_rake(rake_id, r_type)

        # Forward Local: City_1 -> City_4 across 6 sections
        # Calibrated runtimes: [246s, 227s, 200s, 234s, 200s, 222s] = 1329s
        c1_reg_runtimes_fwd = [246.0, 227.0, 200.0, 234.0, 200.0, 222.0]
        curr_t = dep_sec
        stops_fwd = []
        for idx, stn in enumerate(C1_STATIONS):
            if idx > 0:
                curr_t += c1_reg_runtimes_fwd[idx - 1]
            arr_t = curr_t
            dwell = get_calibrated_dwell(stn, "Regional", idx == len(C1_STATIONS) - 1, dep_sec=dep_sec, r_type=r_type)
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

        rev_dep_sec = rh * 3600 + rm * 60
        turnaround_dwell_min = round((rev_dep_sec - stops_fwd[-1]["arrival_sec"]) / 60.0, 1)
        min_required = MIN_TURNAROUND_BY_CONSIST[r_type]
        if turnaround_dwell_min < min_required:
            raise ValueError(
                f"Infeasible turnaround for service {fwd_no} -> {rev_no}: "
                f"allocated dwell {turnaround_dwell_min} min is less than required minimum {min_required} min "
                f"for consist model {r_type}."
            )
        turnaround_mode = "rapid_dual_crew" if turnaround_dwell_min <= (min_required + 3.0) else "standard_cab_swap"

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
            "departure_time": stops_fwd[0]["departure_time"],
            "departure_sec": stops_fwd[0]["departure_sec"],
            "arrival_time": stops_fwd[-1]["arrival_time"],
            "arrival_sec": stops_fwd[-1]["arrival_sec"],
            "total_distance_km": 28.20,
            "stops": stops_fwd,
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_4_pocket_2_fw",
                "buffer_stop_node": "City_4_buf_2",
                "turnaround_dwell_min": turnaround_dwell_min,
                "min_turnaround_required_min": min_required,
                "turnaround_mode": turnaround_mode,
                "subsequent_service": rev_no
            }
        })
        rake["assigned_services"].append(fwd_no)

        # Return Local: City_4 -> City_1 across 6 sections
        # Calibrated runtimes: [249s, 231s, 203s, 229s, 196s, 219s] = 1327s
        c1_reg_runtimes_rev = [249.0, 231.0, 203.0, 229.0, 196.0, 219.0]
        curr_t = rev_dep_sec
        stops_rev = []
        for idx, stn in enumerate(reversed(C1_STATIONS)):
            if idx > 0:
                curr_t += c1_reg_runtimes_rev[idx - 1]
            arr_t = curr_t
            dwell = get_calibrated_dwell(stn, "Regional", idx == len(C1_STATIONS) - 1, dep_sec=rev_dep_sec, r_type=r_type)
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
            "departure_time": stops_rev[0]["departure_time"],
            "departure_sec": stops_rev[0]["departure_sec"],
            "arrival_time": stops_rev[-1]["arrival_time"],
            "arrival_sec": stops_rev[-1]["arrival_sec"],
            "total_distance_km": 28.20,
            "stops": stops_rev,
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_1_yard_2_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 45,
                "min_turnaround_required_min": MIN_TURNAROUND_BY_CONSIST[r_type],
                "turnaround_mode": "extended_layover",
                "subsequent_service": None
            }
        })
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY C: CORRIDOR 2 NORTH-SOUTH REGIONAL SPINE (120 km/h) ---
    # City_5 <-> Town_4 <-> Town_5 <-> City_3_NS <-> Town_6 <-> Town_7 <-> City_6
    # TAKTFAHRPLAN: Southbound departs at :10, Northbound departs at :45 past the hour.
    # PEAK SURGE: 30-min commuter frequency during morning (07:10, 07:40, 08:10, 08:40) and evening (16:10, 16:40, 17:10, 17:40, 18:10).
    c2_services = [
        # (fh, fm, rh, rm, days, fwd_no, rev_no, rake_id)
        # Early Morning Commuter
        (5, 10, 5, 45, "Daily",   "32025", "32026", "REG-C2-01"),
        (6, 10, 6, 45, "Daily",   "32001", "32002", "REG-C2-02"),
        # Morning Peak Surge (30-min headway)
        (7, 10, 7, 45, "Mon-Fri", "32017", "32018", "REG-C2-04"),
        (7, 40, 8, 15, "Mon-Fri", "32019", "32020", "REG-C2-05"),
        (8, 10, 8, 45, "Mon-Fri", "32003", "32004", "REG-C2-02"),
        (8, 40, 9, 15, "Mon-Fri", "32033", "32034", "REG-C2-06"),
        (9, 10, 9, 45, "Daily",   "32005", "32006", "REG-C2-01"),
        # Midday Regular Cadence (60-min hourly clockface)
        (10, 10, 10, 45, "Daily", "32039", "32040", "REG-C2-04"),
        (11, 10, 11, 45, "Daily", "32007", "32008", "REG-C2-03"),
        (12, 10, 12, 45, "Daily", "32027", "32028", "REG-C2-04"),
        (13, 10, 13, 45, "Daily", "32009", "32010", "REG-C2-02"),
        (14, 10, 14, 45, "Daily", "32029", "32030", "REG-C2-05"),
        (15, 10, 15, 45, "Mon-Fri","32011", "32012", "REG-C2-01"),
        # Evening Peak Surge (30-min headway)
        (16, 10, 16, 45, "Mon-Fri","32021", "32022", "REG-C2-04"),
        (16, 40, 17, 15, "Mon-Fri","32035", "32036", "REG-C2-06"),
        (17, 10, 17, 45, "Daily", "32013", "32014", "REG-C2-03"),
        (17, 40, 18, 15, "Mon-Fri","32037", "32038", "REG-C2-01"),
        (18, 10, 18, 45, "Mon-Fri","32023", "32024", "REG-C2-05"),
        # Late Evening Base
        (19, 10, 19, 45, "Daily", "32015", "32016", "REG-C2-02"),
        (20, 10, 20, 45, "Daily", "32041", "32042", "REG-C2-05"),
        (21, 10, 21, 45, "Daily", "32031", "32032", "REG-C2-03"),
        (22, 10, 22, 45, "Daily", "32043", "32044", "REG-C2-02"),
    ]

    for fh, fm, rh, rm, days, fwd_no, rev_no, rake_id in c2_services:
        dep_sec = fh * 3600 + fm * 60
        r_type = "regional_emu_120"
        rake = get_rake(rake_id, r_type)

        # Southbound: City_5 -> City_6 across 6 sections
        # Calibrated runtimes: [226s, 177s, 197s, 172s, 174s, 212s] = 1158s
        c2_reg_runtimes_fwd = [226.0, 177.0, 197.0, 172.0, 174.0, 212.0]
        curr_t = dep_sec
        stops_fwd = []
        for idx, stn in enumerate(C2_STATIONS):
            if idx > 0:
                curr_t += c2_reg_runtimes_fwd[idx - 1]
            arr_t = curr_t
            dwell = get_calibrated_dwell(stn, "Regional", idx == len(C2_STATIONS) - 1, dep_sec=dep_sec, r_type=r_type)
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

        rev_dep_sec = rh * 3600 + rm * 60
        turnaround_dwell_min = round((rev_dep_sec - stops_fwd[-1]["arrival_sec"]) / 60.0, 1)
        min_required = MIN_TURNAROUND_BY_CONSIST[r_type]
        if turnaround_dwell_min < min_required:
            raise ValueError(
                f"Infeasible turnaround for service {fwd_no} -> {rev_no}: "
                f"allocated dwell {turnaround_dwell_min} min is less than required minimum {min_required} min "
                f"for consist model {r_type}."
            )
        turnaround_mode = "rapid_dual_crew" if turnaround_dwell_min <= (min_required + 3.0) else "standard_cab_swap"

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
            "departure_time": stops_fwd[0]["departure_time"],
            "departure_sec": stops_fwd[0]["departure_sec"],
            "arrival_time": stops_fwd[-1]["arrival_time"],
            "arrival_sec": stops_fwd[-1]["arrival_sec"],
            "total_distance_km": 23.16,
            "stops": stops_fwd,
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_6_pocket_1_fw",
                "buffer_stop_node": "City_6_buf_1",
                "turnaround_dwell_min": turnaround_dwell_min,
                "min_turnaround_required_min": min_required,
                "turnaround_mode": turnaround_mode,
                "subsequent_service": rev_no
            }
        })
        rake["assigned_services"].append(fwd_no)

        # Northbound Return: City_6 -> City_5 across 6 sections
        # Calibrated runtimes: [239s, 179s, 198s, 167s, 177s, 199s] = 1159s
        c2_reg_runtimes_rev = [239.0, 179.0, 198.0, 167.0, 177.0, 199.0]
        curr_t = rev_dep_sec
        stops_rev = []
        for idx, stn in enumerate(reversed(C2_STATIONS)):
            if idx > 0:
                curr_t += c2_reg_runtimes_rev[idx - 1]
            arr_t = curr_t
            dwell = get_calibrated_dwell(stn, "Regional", idx == len(C2_STATIONS) - 1, dep_sec=rev_dep_sec, r_type=r_type)
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
            "departure_time": stops_rev[0]["departure_time"],
            "departure_sec": stops_rev[0]["departure_sec"],
            "arrival_time": stops_rev[-1]["arrival_time"],
            "arrival_sec": stops_rev[-1]["arrival_sec"],
            "total_distance_km": 23.16,
            "stops": stops_rev,
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "depot_stabling" if rh >= 17 else "yard_layover",
                "staging_track": "City_5_yard_1_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 45,
                "min_turnaround_required_min": MIN_TURNAROUND_BY_CONSIST[r_type],
                "turnaround_mode": "extended_layover",
                "subsequent_service": None
            }
        })
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY D: CORRIDOR 3 NORTHWEST ALPINE MOUNTAIN LINE (Hybrid DMU & Specific Days) ---
    # TAKTFAHRPLAN: Uphill departs City_2 at :10 (connecting from EB C1 Express), Downhill departs Town_9 at :40
    # PEAK SURGE: Commuter relief runs at 08:10 (AM peak) and 17:10 (PM peak).
    c3_mountain_passenger = [
        # (fwd_no, name, days, fh, fm, rh, rm, rake_id, rev_no)
        ("12763", "Alpine Scenic Shuttle 12763", ["Mon", "Thu", "Sun"], 7, 10, 7, 40, "ALP-Rake-01", "12764"),
        ("12771", "Alpine Morning Commuter 12771", ["Mon-Fri"], 8, 10, 8, 38, "ALP-Rake-02", "12772"),
        ("12765", "Alpine Glacier Express 12765", ["Tue", "Fri", "Sat"], 10, 10, 10, 40, "ALP-Rake-02", "12766"),
        ("12775", "Alpine Midday Shuttle 12775", ["Daily"], 11, 10, 11, 40, "ALP-Rake-01", "12776"),
        ("12769", "Alpine Panorama Express 12769", ["Daily"], 13, 10, 13, 40, "ALP-Rake-02", "12770"),
        ("12777", "Alpine Afternoon Express 12777", ["Daily"], 14, 10, 14, 40, "ALP-Rake-01", "12778"),
        ("12767", "Alpine Evening Shuttle 12767", ["Mon", "Thu", "Sun"], 16, 10, 16, 40, "ALP-Rake-01", "12768"),
        ("12773", "Alpine Evening Commuter 12773", ["Mon-Fri"], 17, 10, 17, 38, "ALP-Rake-01", "12774"),
        ("12779", "Alpine Twilight Express 12779", ["Daily"], 18, 10, 18, 38, "ALP-Rake-02", "12780"),
    ]

    for fwd_no, name, days, fh, fm, rh, rm, rake_id, rev_no in c3_mountain_passenger:
        dep_sec = fh * 3600 + fm * 60
        r_type = "regional_dmu_120"
        rake = get_rake(rake_id, r_type)

        # Uphill: City_2 -> Town_9 across 2 sections
        # Calibrated runtimes: City_2 -> Town_8 (263s), Town_8 -> Town_9 (197s), sum = 460s (+75s dwell = 535s)
        c3_reg_runtimes_fwd = [263.0, 197.0]
        curr_t = dep_sec
        stops_fwd = []
        c3_sub = ["City_2", "Town_8", "Town_9"]
        for idx, stn in enumerate(c3_sub):
            if idx > 0:
                curr_t += c3_reg_runtimes_fwd[idx - 1]
            arr_t = curr_t
            dwell = get_calibrated_dwell(stn, "Alpine", idx == len(c3_sub) - 1, dep_sec=dep_sec, r_type=r_type)
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

        rev_dep_sec = rh * 3600 + rm * 60
        turnaround_dwell_min = round((rev_dep_sec - stops_fwd[-1]["arrival_sec"]) / 60.0, 1)
        min_required = MIN_TURNAROUND_BY_CONSIST[r_type]
        if turnaround_dwell_min < min_required:
            raise ValueError(
                f"Infeasible turnaround for service {fwd_no} -> {rev_no}: "
                f"allocated dwell {turnaround_dwell_min} min is less than required minimum {min_required} min "
                f"for consist model {r_type}."
            )
        turnaround_mode = "rapid_dual_crew" if turnaround_dwell_min <= (min_required + 3.0) else "standard_cab_swap"

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
            "departure_time": stops_fwd[0]["departure_time"],
            "departure_sec": stops_fwd[0]["departure_sec"],
            "arrival_time": stops_fwd[-1]["arrival_time"],
            "arrival_sec": stops_fwd[-1]["arrival_sec"],
            "total_distance_km": 9.85,
            "stops": stops_fwd,
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "Town_9_yard_1_fw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": turnaround_dwell_min,
                "min_turnaround_required_min": min_required,
                "turnaround_mode": turnaround_mode,
                "subsequent_service": rev_no
            }
        })
        rake["assigned_services"].append(fwd_no)

        # Downhill Return: Town_9 -> City_2 across 2 sections
        # Calibrated runtimes: Town_9 -> Town_8 (221s), Town_8 -> City_2 (239s), sum = 460s (+75s dwell = 535s)
        c3_reg_runtimes_rev = [221.0, 239.0]
        curr_t = rev_dep_sec
        stops_rev = []
        for idx, stn in enumerate(reversed(c3_sub)):
            if idx > 0:
                curr_t += c3_reg_runtimes_rev[idx - 1]
            arr_t = curr_t
            dwell = get_calibrated_dwell(stn, "Alpine", idx == len(c3_sub) - 1, dep_sec=rev_dep_sec, r_type=r_type)
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
            "train_name": name.replace("Shuttle", "Return").replace("Express", "Return").replace(fwd_no, rev_no),
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
            "departure_time": stops_rev[0]["departure_time"],
            "departure_sec": stops_rev[0]["departure_sec"],
            "arrival_time": stops_rev[-1]["arrival_time"],
            "arrival_sec": stops_rev[-1]["arrival_sec"],
            "total_distance_km": 9.85,
            "stops": stops_rev,
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_2_yard_1_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 60,
                "min_turnaround_required_min": MIN_TURNAROUND_BY_CONSIST[r_type],
                "turnaround_mode": "extended_layover",
                "subsequent_service": None
            }
        })
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY E: CORRIDOR 4 SOUTHERN COASTAL ARC REGIONAL (120 km/h) ---
    # TAKTFAHRPLAN: Eastbound departs City_1 at :20, Westbound departs City_6 at :55
    # PEAK SURGE: 30-min commuter frequency during morning (07:20, 07:50, 08:20, 08:50, 09:20) and evening (16:20, 16:50, 17:20, 17:50).
    c4_services = [
        # (fh, fm, rh, rm, days, fwd_no, rev_no, rake_id)
        # Early Morning
        (6, 20, 6, 55, "Daily",   "41013", "41014", "REG-C4-04"),
        (7, 20, 7, 55, "Daily",   "41001", "41002", "REG-C4-01"),
        # Morning Peak Surge (30-min headway)
        (7, 50, 8, 25, "Mon-Fri", "41019", "41020", "REG-C4-05"),
        (8, 20, 8, 55, "Mon-Fri", "41009", "41010", "REG-C4-03"),
        (8, 50, 9, 25, "Mon-Fri", "41021", "41022", "REG-C4-01"),
        (9, 20, 9, 55, "Mon-Fri", "41003", "41004", "REG-C4-02"),
        # Midday Base (60-min hourly cadence)
        (10, 20, 10, 55, "Daily", "41027", "41028", "REG-C4-03"),
        (11, 20, 11, 55, "Daily", "41015", "41016", "REG-C4-04"),
        (12, 20, 12, 55, "Daily", "41029", "41030", "REG-C4-03"),
        (13, 20, 13, 55, "Daily", "41005", "41006", "REG-C4-01"),
        (14, 20, 14, 55, "Daily", "41031", "41032", "REG-C4-03"),
        (15, 20, 15, 55, "Daily", "41033", "41034", "REG-C4-05"),
        (16, 20, 16, 55, "Daily", "41007", "41008", "REG-C4-02"),
        # Evening Peak Surge (30-min headway)
        (16, 50, 17, 25, "Mon-Fri", "41023", "41024", "REG-C4-05"),
        (17, 20, 17, 55, "Mon-Fri", "41011", "41012", "REG-C4-03"),
        (17, 50, 18, 25, "Mon-Fri", "41025", "41026", "REG-C4-02"),
        # Evening Base & Night Connectivity
        (18, 20, 18, 55, "Daily", "41035", "41036", "REG-C4-05"),
        (19, 20, 19, 55, "Daily", "41017", "41018", "REG-C4-01"),
        (20, 20, 20, 55, "Daily", "41037", "41038", "REG-C4-04"),
        (21, 20, 21, 55, "Daily", "41039", "41040", "REG-C4-02"),
    ]

    for fh, fm, rh, rm, days, fwd_no, rev_no, rake_id in c4_services:
        dep_sec = fh * 3600 + fm * 60
        r_type = "regional_emu_120"
        rake = get_rake(rake_id, r_type)

        # Eastbound / Counter-Clockwise: City_1 -> City_6 across 4 passenger sections (bypassing Depot_2)
        # Calibrated runtimes: City_1->Town_10 (265s), Town_10->Town_11 (204s), Town_11->Town_12 (600s), Town_12->City_6 (286s) = 1355s
        c4_passenger_stations = ["City_1", "Town_10", "Town_11", "Town_12", "City_6"]
        c4_reg_runtimes_fwd = [265.0, 204.0, 600.0, 286.0]
        curr_t = dep_sec
        stops_fwd = []
        for idx, stn in enumerate(c4_passenger_stations):
            if idx > 0:
                curr_t += c4_reg_runtimes_fwd[idx - 1]
            arr_t = curr_t
            dwell = 0 if idx == len(c4_passenger_stations) - 1 else get_calibrated_dwell(stn, "Regional", dep_sec=dep_sec, r_type=r_type)
            dep_t = arr_t + dwell
            curr_t = dep_t
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

        rev_dep_sec = rh * 3600 + rm * 60
        turnaround_dwell_min = round((rev_dep_sec - stops_fwd[-1]["arrival_sec"]) / 60.0, 1)
        min_required = MIN_TURNAROUND_BY_CONSIST[r_type]
        if turnaround_dwell_min < min_required:
            raise ValueError(
                f"Infeasible turnaround for service {fwd_no} -> {rev_no}: "
                f"allocated dwell {turnaround_dwell_min} min is less than required minimum {min_required} min "
                f"for consist model {r_type}."
            )
        turnaround_mode = "rapid_dual_crew" if turnaround_dwell_min <= (min_required + 3.0) else "standard_cab_swap"

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
            "departure_time": stops_fwd[0]["departure_time"],
            "departure_sec": stops_fwd[0]["departure_sec"],
            "arrival_time": stops_fwd[-1]["arrival_time"],
            "arrival_sec": stops_fwd[-1]["arrival_sec"],
            "total_distance_km": 29.25,
            "stops": stops_fwd,
            "bypassed_through_stations": ["Depot_2"],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_6_pocket_2_fw",
                "buffer_stop_node": "City_6_buf_2",
                "turnaround_dwell_min": turnaround_dwell_min,
                "min_turnaround_required_min": min_required,
                "turnaround_mode": turnaround_mode,
                "subsequent_service": rev_no
            }
        })
        rake["assigned_services"].append(fwd_no)

        # Westbound Return: City_6 -> City_1 across 4 passenger sections
        # Calibrated runtimes: City_6->Town_12 (313s), Town_12->Town_11 (600s), Town_11->Town_10 (208s), Town_10->City_1 (242s) = 1363s
        c4_reg_runtimes_rev = [313.0, 600.0, 208.0, 242.0]
        curr_t = rev_dep_sec
        stops_rev = []
        for idx, stn in enumerate(reversed(c4_passenger_stations)):
            if idx > 0:
                curr_t += c4_reg_runtimes_rev[idx - 1]
            arr_t = curr_t
            dwell = 0 if idx == len(c4_passenger_stations) - 1 else get_calibrated_dwell(stn, "Regional", dep_sec=rev_dep_sec, r_type=r_type)
            dep_t = arr_t + dwell
            curr_t = dep_t
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
            "departure_time": stops_rev[0]["departure_time"],
            "departure_sec": stops_rev[0]["departure_sec"],
            "arrival_time": stops_rev[-1]["arrival_time"],
            "arrival_sec": stops_rev[-1]["arrival_sec"],
            "total_distance_km": 29.25,
            "stops": stops_rev,
            "bypassed_through_stations": ["Depot_2"],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_1_yard_2_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 60,
                "min_turnaround_required_min": MIN_TURNAROUND_BY_CONSIST[r_type],
                "turnaround_mode": "extended_layover",
                "subsequent_service": None
            }
        })
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY F: HIGH-SPEED DIAGONAL BYPASS EXPRESS (300 km/h) ---
    # Direct chord connecting City_2 <-> City_5 without going through City_3
    # TAKTFAHRPLAN: Northeast departs City_2 at :25, Southwest departs City_5 at :55
    # PEAK SURGE: Direct chord commuter relief runs during morning (07:25, 08:25) and evening (17:25, 18:25).
    bypass_services = [
        # (fh, fm, rh, rm, days, fwd_no, rev_no, rake_id)
        # Morning Peak Surge & Midday Base
        (7, 25, 7, 55, "Mon-Fri", "15007", "15008", "HS-Rake-04"),
        (8, 25, 8, 55, "Mon-Fri", "15001", "15002", "HS-Rake-04"),
        (10, 25, 10, 55, "Daily",  "15011", "15012", "HS-Rake-04"),
        (13, 25, 13, 55, "Daily",  "15003", "15004", "HS-Rake-04"),
        (15, 25, 15, 55, "Daily",  "15013", "15014", "HS-Rake-04"),
        # Evening Peak Surge & Night Base
        (17, 25, 17, 55, "Mon-Fri", "15005", "15006", "HS-Rake-04"),
        (18, 25, 18, 55, "Mon-Fri", "15009", "15010", "HS-Rake-04"),
        (20, 25, 20, 55, "Daily",  "15015", "15016", "HS-Rake-04"),
    ]

    for fh, fm, rh, rm, days, fwd_no, rev_no, rake_id in bypass_services:
        dep_sec = fh * 3600 + fm * 60
        r_type = "high_speed_emu_single"
        rake = get_rake(rake_id, r_type)
        # Calibrated runtimes: City_2 -> City_5 (473s), City_5 -> City_2 (365s)
        sec_time_fwd = 473.0
        sec_time_rev = 365.0

        # FWD: City_2 -> City_5
        arr_sec = dep_sec + sec_time_fwd
        rev_dep = rh * 3600 + rm * 60
        turnaround_dwell_min = round((rev_dep - arr_sec) / 60.0, 1)
        min_required = MIN_TURNAROUND_BY_CONSIST[r_type]
        if turnaround_dwell_min < min_required:
            raise ValueError(
                f"Infeasible turnaround for service {fwd_no} -> {rev_no}: "
                f"allocated dwell {turnaround_dwell_min} min is less than required minimum {min_required} min "
                f"for consist model {r_type}."
            )
        turnaround_mode = "rapid_dual_crew" if turnaround_dwell_min <= (min_required + 3.0) else "standard_cab_swap"

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
            "origin_track": "City_2_plat_5_fw",
            "dest_station": "City_5",
            "dest_track": "City_5_plat_2_bw",
            "departure_time": format_time(dep_sec),
            "departure_sec": dep_sec,
            "arrival_time": format_time(arr_sec),
            "arrival_sec": round(arr_sec, 1),
            "total_distance_km": 14.75,
            "stops": [
                {"station": "City_2", "train_stop_id": "City_2_p5_fw", "arrival_time": format_time(dep_sec), "arrival_sec": dep_sec, "departure_time": format_time(dep_sec), "departure_sec": dep_sec, "dwell_sec": 0},
                {"station": "City_5", "train_stop_id": "City_5_p2_bw", "arrival_time": format_time(arr_sec), "arrival_sec": round(arr_sec, 1), "departure_time": format_time(arr_sec), "departure_sec": round(arr_sec, 1), "dwell_sec": 0}
            ],
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_5_yard_2_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": turnaround_dwell_min,
                "min_turnaround_required_min": min_required,
                "turnaround_mode": turnaround_mode,
                "subsequent_service": rev_no
            }
        })
        rake["assigned_services"].append(fwd_no)

        # REV: City_5 -> City_2
        rev_arr = rev_dep + sec_time_rev
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
            "dest_track": "City_2_plat_5_bw",
            "departure_time": format_time(rev_dep),
            "departure_sec": round(rev_dep, 1),
            "arrival_time": format_time(rev_arr),
            "arrival_sec": round(rev_arr, 1),
            "total_distance_km": 14.75,
            "stops": [
                {"station": "City_5", "train_stop_id": "City_5_p2_fw", "arrival_time": format_time(rev_dep), "arrival_sec": round(rev_dep, 1), "departure_time": format_time(rev_dep), "departure_sec": round(rev_dep, 1), "dwell_sec": 0},
                {"station": "City_2", "train_stop_id": "City_2_p5_bw", "arrival_time": format_time(rev_arr), "arrival_sec": round(rev_arr, 1), "departure_time": format_time(rev_arr), "departure_sec": round(rev_arr, 1), "dwell_sec": 0}
            ],
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_2_plat_5_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 60,
                "min_turnaround_required_min": MIN_TURNAROUND_BY_CONSIST[r_type],
                "turnaround_mode": "extended_layover",
                "subsequent_service": None
            }
        })
        rake["assigned_services"].append(rev_no)

    # --- CATEGORY G: CROSS-HUB FLYOVER TRANSFER INTERCHANGE (120 km/h) ---
    # Eastern Terminus (City_4) <-> City_3_EW <-> Flyover Ramp <-> City_3_NS <-> Southern Terminus (City_6)
    # TAKTFAHRPLAN: East-to-South departs at :05, South-to-East departs at :35
    # PEAK SURGE: Hourly commuter frequency during morning (07:05, 08:05, 09:05) and evening (16:05, 17:05, 18:05) peaks.
    transfer_services = [
        # (fh, fm, rh, rm, days, fwd_no, rev_no, rake_id)
        # Morning Peak Surge
        (7, 5, 7, 35,   "Mon-Fri", "51009", "51010", "REG-XFER-02"),
        (8, 5, 8, 35,   "Daily",   "51001", "51002", "REG-XFER-01"),
        (9, 5, 9, 35,   "Mon-Fri", "51011", "51012", "REG-XFER-01"),
        # Midday Regular Cadence
        (10, 5, 10, 35, "Daily",   "51017", "51018", "REG-XFER-02"),
        (11, 5, 11, 35, "Daily",   "51005", "51006", "REG-XFER-02"),
        (12, 5, 12, 35, "Daily",   "51019", "51020", "REG-XFER-01"),
        (14, 5, 14, 35, "Daily",   "51003", "51004", "REG-XFER-01"),
        (15, 5, 15, 35, "Daily",   "51021", "51022", "REG-XFER-02"),
        # Evening Peak Surge
        (16, 5, 16, 35, "Mon-Fri", "51013", "51014", "REG-XFER-01"),
        (17, 5, 17, 35, "Mon-Fri", "51007", "51008", "REG-XFER-02"),
        (18, 5, 18, 35, "Mon-Fri", "51015", "51016", "REG-XFER-02"),
        # Evening Base & Late Night
        (19, 5, 19, 35, "Daily",   "51023", "51024", "REG-XFER-01"),
        (20, 5, 20, 35, "Daily",   "51025", "51026", "REG-XFER-02"),
    ]

    for fh, fm, rh, rm, days, fwd_no, rev_no, rake_id in transfer_services:
        dep_sec = fh * 3600 + fm * 60
        r_type = "regional_emu_120"
        rake = get_rake(rake_id, r_type)

        # Westbound-to-Southbound: City_4 -> City_3_EW -> Flyover Ramp -> City_3_NS -> City_6
        # Calibrated runtimes: City_4 -> City_3_EW (415s), City_3_EW -> City_6 (616s)
        t1 = 415.0
        t2 = 616.0

        c3_arr = dep_sec + t1
        dwell_fwd = get_calibrated_dwell("City_3_EW", "Interchange", dep_sec=dep_sec, r_type=r_type)
        c3_dep = c3_arr + dwell_fwd
        c6_arr = c3_dep + t2

        rev_dep = rh * 3600 + rm * 60
        turnaround_dwell_min = round((rev_dep - c6_arr) / 60.0, 1)
        min_required = MIN_TURNAROUND_BY_CONSIST[r_type]
        if turnaround_dwell_min < min_required:
            raise ValueError(
                f"Infeasible turnaround for service {fwd_no} -> {rev_no}: "
                f"allocated dwell {turnaround_dwell_min} min is less than required minimum {min_required} min "
                f"for consist model {r_type}."
            )
        turnaround_mode = "rapid_dual_crew" if turnaround_dwell_min <= (min_required + 3.0) else "standard_cab_swap"

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
            "total_distance_km": 23.36,
            "stops": [
                {"station": "City_4", "train_stop_id": "City_4_p4_bw", "arrival_time": format_time(dep_sec), "arrival_sec": dep_sec, "departure_time": format_time(dep_sec), "departure_sec": dep_sec, "dwell_sec": 0},
                {"station": "City_3_EW", "train_stop_id": "City_3_EW_p4_bw", "arrival_time": format_time(c3_arr), "arrival_sec": round(c3_arr, 1), "departure_time": format_time(c3_dep), "departure_sec": round(c3_dep, 1), "dwell_sec": dwell_fwd},
                {"station": "City_6", "train_stop_id": "City_6_p4_fw", "arrival_time": format_time(c6_arr), "arrival_sec": round(c6_arr, 1), "departure_time": format_time(c6_arr), "departure_sec": round(c6_arr, 1), "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_3", "Town_6", "Town_7"],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_6_pocket_2_fw",
                "buffer_stop_node": "City_6_buf_2",
                "turnaround_dwell_min": turnaround_dwell_min,
                "min_turnaround_required_min": min_required,
                "turnaround_mode": turnaround_mode,
                "subsequent_service": rev_no
            }
        })
        rake["assigned_services"].append(fwd_no)

        # Northbound-to-Eastbound Return: City_6 -> City_3_NS -> Flyover Ramp -> City_3_EW -> City_4
        # Calibrated runtimes: City_6 -> City_3_NS (488s), City_3_NS -> City_4 (516s)
        t_rev_1 = 488.0
        t_rev_2 = 516.0
        rev_c3_arr = rev_dep + t_rev_1
        dwell_rev = get_calibrated_dwell("City_3_NS", "Interchange", dep_sec=rev_dep, r_type=r_type)
        rev_c3_dep = rev_c3_arr + dwell_rev
        rev_c4_arr = rev_c3_dep + t_rev_2

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
            "total_distance_km": 23.36,
            "stops": [
                {"station": "City_6", "train_stop_id": "City_6_p4_bw", "arrival_time": format_time(rev_dep), "arrival_sec": round(rev_dep, 1), "departure_time": format_time(rev_dep), "departure_sec": round(rev_dep, 1), "dwell_sec": 0},
                {"station": "City_3_NS", "train_stop_id": "City_3_NS_p4_bw", "arrival_time": format_time(rev_c3_arr), "arrival_sec": round(rev_c3_arr, 1), "departure_time": format_time(rev_c3_dep), "departure_sec": round(rev_c3_dep, 1), "dwell_sec": dwell_rev},
                {"station": "City_4", "train_stop_id": "City_4_p4_fw", "arrival_time": format_time(rev_c4_arr), "arrival_sec": round(rev_c4_arr, 1), "departure_time": format_time(rev_c4_arr), "departure_sec": round(rev_c4_arr, 1), "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_7", "Town_6", "Town_3"],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_4_yard_1_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 60,
                "min_turnaround_required_min": MIN_TURNAROUND_BY_CONSIST[r_type],
                "turnaround_mode": "extended_layover",
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
            "arrival_time": "05:02:00",
            "arrival_sec": 5 * 3600 + 2 * 60,
            "total_distance_km": 14.44,
            "stops": [
                {"station": "City_2", "train_stop_id": None, "arrival_time": "04:30:00", "arrival_sec": 16200, "departure_time": "04:30:00", "departure_sec": 16200, "dwell_sec": 0},
                {"station": "Town_8_Passing_Loop", "train_stop_id": None, "arrival_time": "04:40:00", "arrival_sec": 16800, "departure_time": "04:52:00", "departure_sec": 17520, "dwell_sec": 720}, # holds 12 mins for passenger overtakes
                {"station": "Depot_1", "train_stop_id": None, "arrival_time": "05:02:00", "arrival_sec": 18120, "departure_time": "05:02:00", "departure_sec": 18120, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_8", "Town_9"],
            "post_journey_disposition": {
                "action": "depot_stabling",
                "staging_track": "Depot_1_pocket_1_fw",
                "buffer_stop_node": "Depot_1_buf_1",
                "turnaround_dwell_min": 358.0,
                "min_turnaround_required_min": 30.0,
                "turnaround_mode": "shunting_and_inspection",
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
            "arrival_time": "11:19:00",
            "arrival_sec": 11 * 3600 + 19 * 60,
            "total_distance_km": 14.44,
            "stops": [
                {"station": "Depot_1", "train_stop_id": None, "arrival_time": "11:00:00", "arrival_sec": 39600, "departure_time": "11:00:00", "departure_sec": 39600, "dwell_sec": 0},
                {"station": "City_2", "train_stop_id": None, "arrival_time": "11:19:00", "arrival_sec": 40740, "departure_time": "11:19:00", "departure_sec": 40740, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_9", "Town_8"],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_2_yard_1_fw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 180,
                "min_turnaround_required_min": 30.0,
                "turnaround_mode": "extended_layover",
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
            "arrival_time": "05:10:00",
            "arrival_sec": 5 * 3600 + 10 * 60,
            "total_distance_km": 5.62,
            "stops": [
                {"station": "City_5", "train_stop_id": None, "arrival_time": "05:00:00", "arrival_sec": 18000, "departure_time": "05:00:00", "departure_sec": 18000, "dwell_sec": 0},
                {"station": "Depot_3", "train_stop_id": None, "arrival_time": "05:10:00", "arrival_sec": 18600, "departure_time": "05:10:00", "departure_sec": 18600, "dwell_sec": 0}
            ],
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "depot_stabling",
                "staging_track": "Depot_3_pocket_1_fw",
                "buffer_stop_node": "Depot_3_buf_1",
                "turnaround_dwell_min": 530.0,
                "min_turnaround_required_min": 30.0,
                "turnaround_mode": "container_loading_and_inspection",
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
            "arrival_time": "14:10:00",
            "arrival_sec": 14 * 3600 + 10 * 60,
            "total_distance_km": 5.62,
            "stops": [
                {"station": "Depot_3", "train_stop_id": None, "arrival_time": "14:00:00", "arrival_sec": 50400, "departure_time": "14:00:00", "departure_sec": 50400, "dwell_sec": 0},
                {"station": "City_5", "train_stop_id": None, "arrival_time": "14:10:00", "arrival_sec": 51000, "departure_time": "14:10:00", "departure_sec": 51000, "dwell_sec": 0}
            ],
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_5_yard_1_fw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 360,
                "min_turnaround_required_min": 30.0,
                "turnaround_mode": "extended_layover",
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
            "arrival_time": "03:44:30",
            "arrival_sec": 3 * 3600 + 44 * 60 + 30,
            "total_distance_km": 14.26,
            "stops": [
                {"station": "Depot_2", "train_stop_id": None, "arrival_time": "03:30:00", "arrival_sec": 12600, "departure_time": "03:30:00", "departure_sec": 12600, "dwell_sec": 0},
                {"station": "City_6", "train_stop_id": None, "arrival_time": "03:44:30", "arrival_sec": 13470, "departure_time": "03:44:30", "departure_sec": 13470, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_12"],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_6_pocket_1_fw",
                "buffer_stop_node": "City_6_buf_1",
                "turnaround_dwell_min": 285.5,
                "min_turnaround_required_min": 30.0,
                "turnaround_mode": "shunting_and_inspection",
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
            "arrival_time": "08:44:30",
            "arrival_sec": 8 * 3600 + 44 * 60 + 30,
            "total_distance_km": 14.26,
            "stops": [
                {"station": "City_6", "train_stop_id": None, "arrival_time": "08:30:00", "arrival_sec": 30600, "departure_time": "08:30:00", "departure_sec": 30600, "dwell_sec": 0},
                {"station": "Depot_2", "train_stop_id": None, "arrival_time": "08:44:30", "arrival_sec": 31470, "departure_time": "08:44:30", "departure_sec": 31470, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_12"],
            "post_journey_disposition": {
                "action": "depot_stabling",
                "staging_track": "Depot_2_yard_1_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 240,
                "min_turnaround_required_min": 30.0,
                "turnaround_mode": "depot_inspection",
                "subsequent_service": None
            }
        },
        # 7. Nocturnal Mountain Bulk Ore: City_2 -> Alpine Loop -> Depot_1
        {
            "train_number": "68103",
            "train_name": "Alpine Nocturnal Mineral 68103",
            "service_class": "Freight",
            "rolling_stock_type": "heavy_freight_cargo",
            "assigned_rake": "FRT-Rake-01",
            "service_days": ["Mon", "Wed", "Fri"],
            "corridor": "Corridor_3",
            "direction": "Inbound_Cargo_Climb",
            "origin_station": "City_2",
            "origin_track": "City_2_yard_1_bw",
            "dest_station": "Depot_1",
            "dest_track": "Depot_1_pocket_1_fw",
            "departure_time": "22:30:00",
            "departure_sec": 22 * 3600 + 30 * 60,
            "arrival_time": "23:02:00",
            "arrival_sec": 23 * 3600 + 2 * 60,
            "total_distance_km": 14.44,
            "stops": [
                {"station": "City_2", "train_stop_id": None, "arrival_time": "22:30:00", "arrival_sec": 81000, "departure_time": "22:30:00", "departure_sec": 81000, "dwell_sec": 0},
                {"station": "Town_8_Passing_Loop", "train_stop_id": None, "arrival_time": "22:40:00", "arrival_sec": 81600, "departure_time": "22:52:00", "departure_sec": 82320, "dwell_sec": 720},
                {"station": "Depot_1", "train_stop_id": None, "arrival_time": "23:02:00", "arrival_sec": 82920, "departure_time": "23:02:00", "departure_sec": 82920, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_8", "Town_9"],
            "post_journey_disposition": {
                "action": "depot_stabling",
                "staging_track": "Depot_1_pocket_1_fw",
                "buffer_stop_node": "Depot_1_buf_1",
                "turnaround_dwell_min": 178.0,
                "min_turnaround_required_min": 30.0,
                "turnaround_mode": "shunting_and_inspection",
                "subsequent_service": "68104"
            }
        },
        # 8. Nocturnal Mountain Return: Depot_1 -> Alpine Loop -> City_2
        {
            "train_number": "68104",
            "train_name": "Alpine Nocturnal Mineral Return 68104",
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
            "departure_time": "02:00:00",
            "departure_sec": 2 * 3600,
            "arrival_time": "02:19:00",
            "arrival_sec": 2 * 3600 + 19 * 60,
            "total_distance_km": 14.44,
            "stops": [
                {"station": "Depot_1", "train_stop_id": None, "arrival_time": "02:00:00", "arrival_sec": 7200, "departure_time": "02:00:00", "departure_sec": 7200, "dwell_sec": 0},
                {"station": "City_2", "train_stop_id": None, "arrival_time": "02:19:00", "arrival_sec": 8340, "departure_time": "02:19:00", "departure_sec": 8340, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_9", "Town_8"],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_2_yard_1_fw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 105.0,
                "min_turnaround_required_min": 30.0,
                "turnaround_mode": "extended_layover",
                "subsequent_service": None
            }
        },
        # 9. Nocturnal Northern Container Feeder: City_5 -> Depot_3
        {
            "train_number": "68203",
            "train_name": "Northern Container Nocturnal 68203",
            "service_class": "Freight",
            "rolling_stock_type": "intermodal_container_freight",
            "assigned_rake": "FRT-Rake-02",
            "service_days": ["Tue", "Thu", "Sat"],
            "corridor": "Spur_City_5_Depot_3",
            "direction": "Spur_Inbound",
            "origin_station": "City_5",
            "origin_track": "City_5_yard_1_bw",
            "dest_station": "Depot_3",
            "dest_track": "Depot_3_pocket_1_fw",
            "departure_time": "23:00:00",
            "departure_sec": 23 * 3600,
            "arrival_time": "23:10:00",
            "arrival_sec": 23 * 3600 + 10 * 60,
            "total_distance_km": 5.62,
            "stops": [
                {"station": "City_5", "train_stop_id": None, "arrival_time": "23:00:00", "arrival_sec": 82800, "departure_time": "23:00:00", "departure_sec": 82800, "dwell_sec": 0},
                {"station": "Depot_3", "train_stop_id": None, "arrival_time": "23:10:00", "arrival_sec": 83400, "departure_time": "23:10:00", "departure_sec": 83400, "dwell_sec": 0}
            ],
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "depot_stabling",
                "staging_track": "Depot_3_pocket_1_fw",
                "buffer_stop_node": "Depot_3_buf_1",
                "turnaround_dwell_min": 200.0,
                "min_turnaround_required_min": 30.0,
                "turnaround_mode": "container_loading_and_inspection",
                "subsequent_service": "68204"
            }
        },
        # 10. Nocturnal Northern Container Return: Depot_3 -> City_5
        {
            "train_number": "68204",
            "train_name": "Northern Container Nocturnal Return 68204",
            "service_class": "Freight",
            "rolling_stock_type": "intermodal_container_freight",
            "assigned_rake": "FRT-Rake-02",
            "service_days": ["Wed", "Fri", "Sun"],
            "corridor": "Spur_City_5_Depot_3",
            "direction": "Spur_Outbound",
            "origin_station": "Depot_3",
            "origin_track": "Depot_3_pocket_1_bw",
            "dest_station": "City_5",
            "dest_track": "City_5_yard_1_fw",
            "departure_time": "02:30:00",
            "departure_sec": 2 * 3600 + 30 * 60,
            "arrival_time": "02:40:00",
            "arrival_sec": 2 * 3600 + 40 * 60,
            "total_distance_km": 5.62,
            "stops": [
                {"station": "Depot_3", "train_stop_id": None, "arrival_time": "02:30:00", "arrival_sec": 9000, "departure_time": "02:30:00", "departure_sec": 9000, "dwell_sec": 0},
                {"station": "City_5", "train_stop_id": None, "arrival_time": "02:40:00", "arrival_sec": 9600, "departure_time": "02:40:00", "departure_sec": 9600, "dwell_sec": 0}
            ],
            "bypassed_through_stations": [],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_5_yard_1_fw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 115.0,
                "min_turnaround_required_min": 30.0,
                "turnaround_mode": "extended_layover",
                "subsequent_service": None
            }
        },
        # 11. Nocturnal Coastal Industrial Cargo: Depot_2 -> City_6
        {
            "train_number": "68303",
            "train_name": "Coastal Bulk Nocturnal Cargo 68303",
            "service_class": "Freight",
            "rolling_stock_type": "heavy_freight_cargo",
            "assigned_rake": "FRT-Rake-03",
            "service_days": ["Mon", "Wed", "Fri"],
            "corridor": "Corridor_4",
            "direction": "Eastbound_Cargo",
            "origin_station": "Depot_2",
            "origin_track": "Depot_2_yard_1_fw",
            "dest_station": "City_6",
            "dest_track": "City_6_pocket_1_fw",
            "departure_time": "21:30:00",
            "departure_sec": 21 * 3600 + 30 * 60,
            "arrival_time": "21:44:30",
            "arrival_sec": 21 * 3600 + 44 * 60 + 30,
            "total_distance_km": 14.26,
            "stops": [
                {"station": "Depot_2", "train_stop_id": None, "arrival_time": "21:30:00", "arrival_sec": 77400, "departure_time": "21:30:00", "departure_sec": 77400, "dwell_sec": 0},
                {"station": "City_6", "train_stop_id": None, "arrival_time": "21:44:30", "arrival_sec": 78270, "departure_time": "21:44:30", "departure_sec": 78270, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_12"],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_6_pocket_1_fw",
                "buffer_stop_node": "City_6_buf_1",
                "turnaround_dwell_min": 195.5,
                "min_turnaround_required_min": 30.0,
                "turnaround_mode": "shunting_and_inspection",
                "subsequent_service": "68304"
            }
        },
        # 12. Nocturnal Coastal Cargo Return: City_6 -> Depot_2
        {
            "train_number": "68304",
            "train_name": "Coastal Bulk Nocturnal Return 68304",
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
            "departure_time": "01:00:00",
            "departure_sec": 1 * 3600,
            "arrival_time": "01:14:30",
            "arrival_sec": 1 * 3600 + 14 * 60 + 30,
            "total_distance_km": 14.26,
            "stops": [
                {"station": "City_6", "train_stop_id": None, "arrival_time": "01:00:00", "arrival_sec": 3600, "departure_time": "01:00:00", "departure_sec": 3600, "dwell_sec": 0},
                {"station": "Depot_2", "train_stop_id": None, "arrival_time": "01:14:30", "arrival_sec": 4470, "departure_time": "01:14:30", "departure_sec": 4470, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_12"],
            "post_journey_disposition": {
                "action": "depot_stabling",
                "staging_track": "Depot_2_yard_1_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 80.0,
                "min_turnaround_required_min": 30.0,
                "turnaround_mode": "depot_inspection",
                "subsequent_service": None
            }
        },
        # 13. Nocturnal East-West Trunk Fast Freight: City_1 -> City_4
        {
            "train_number": "68401",
            "train_name": "Trans-Corridor E-Freight Express 68401",
            "service_class": "Freight",
            "rolling_stock_type": "electric_trunk_freight",
            "assigned_rake": "FRT-Rake-04",
            "service_days": ["Daily"],
            "corridor": "Corridor_1",
            "direction": "Eastbound_FW",
            "origin_station": "City_1",
            "origin_track": "City_1_plat_2_fw",
            "dest_station": "City_4",
            "dest_track": "City_4_plat_2_fw",
            "departure_time": "23:15:00",
            "departure_sec": 23 * 3600 + 15 * 60,
            "arrival_time": "23:37:00",
            "arrival_sec": 23 * 3600 + 37 * 60,
            "total_distance_km": 28.20,
            "stops": [
                {"station": "City_1", "train_stop_id": "City_1_p2_fw", "arrival_time": "23:15:00", "arrival_sec": 83700, "departure_time": "23:15:00", "departure_sec": 83700, "dwell_sec": 0},
                {"station": "City_4", "train_stop_id": "City_4_p2_fw", "arrival_time": "23:37:00", "arrival_sec": 85020, "departure_time": "23:37:00", "departure_sec": 85020, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_1", "City_2", "Town_2", "City_3_EW", "Town_3"],
            "post_journey_disposition": {
                "action": "turnaround",
                "staging_track": "City_4_pocket_2_fw",
                "buffer_stop_node": "City_4_buf_2",
                "turnaround_dwell_min": 113.0,
                "min_turnaround_required_min": 25.0,
                "turnaround_mode": "standard_cab_swap",
                "subsequent_service": "68402"
            }
        },
        # 14. Nocturnal East-West Trunk Fast Freight Return: City_4 -> City_1
        {
            "train_number": "68402",
            "train_name": "Trans-Corridor E-Freight Express 68402",
            "service_class": "Freight",
            "rolling_stock_type": "electric_trunk_freight",
            "assigned_rake": "FRT-Rake-04",
            "service_days": ["Daily"],
            "corridor": "Corridor_1",
            "direction": "Westbound_BW",
            "origin_station": "City_4",
            "origin_track": "City_4_plat_2_bw",
            "dest_station": "City_1",
            "dest_track": "City_1_plat_2_bw",
            "departure_time": "01:30:00",
            "departure_sec": 1 * 3600 + 30 * 60,
            "arrival_time": "01:52:00",
            "arrival_sec": 1 * 3600 + 52 * 60,
            "total_distance_km": 28.20,
            "stops": [
                {"station": "City_4", "train_stop_id": "City_4_p2_bw", "arrival_time": "01:30:00", "arrival_sec": 5400, "departure_time": "01:30:00", "departure_sec": 5400, "dwell_sec": 0},
                {"station": "City_1", "train_stop_id": "City_1_p2_bw", "arrival_time": "01:52:00", "arrival_sec": 6720, "departure_time": "01:52:00", "departure_sec": 6720, "dwell_sec": 0}
            ],
            "bypassed_through_stations": ["Town_3", "City_3_EW", "Town_2", "City_2", "Town_1"],
            "post_journey_disposition": {
                "action": "yard_layover",
                "staging_track": "City_1_yard_2_bw",
                "buffer_stop_node": None,
                "turnaround_dwell_min": 1283.0,
                "min_turnaround_required_min": 25.0,
                "turnaround_mode": "extended_layover",
                "subsequent_service": None
            }
        }
    ]
    for f_srv in freight_schedules:
        timetable.append(f_srv)
        rk = get_rake(f_srv["assigned_rake"], f_srv["rolling_stock_type"])
        rk["assigned_services"].append(f_srv["train_number"])

    # --- FULL TURNAROUND & DISPOSITION CHAIN ENGINE (FLAW 3 REMEDIATION) ---
    # Connect every intermediate service to its subsequent service for that physical rake,
    # calculate the true turnaround dwell time, classify turnaround mode, and strictly validate consist minimums.
    svc_by_no = {s["train_number"]: s for s in timetable}
    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def expand_days(svc):
        days = svc.get("service_days", [])
        res = set()
        for d in days:
            if d == "Daily":
                res.update(DAYS)
            elif d == "Mon-Fri":
                res.update(["Mon", "Tue", "Wed", "Thu", "Fri"])
            elif d in DAYS:
                res.add(d)
        return res

    for rake_id, rk in rakes.items():
        svcs = rk["assigned_services"]
        if not svcs:
            continue

        svc_objs = [svc_by_no[no] for no in svcs]

        # Process operating days (evaluate dense weekday schedules first so weekday links take precedence)
        days_sorted = sorted(range(7), key=lambda d: len([s for s in svc_objs if DAYS[d] in expand_days(s)]), reverse=True)

        for d_idx in days_sorted:
            day_name = DAYS[d_idx]
            day_svcs = sorted([s for s in svc_objs if day_name in expand_days(s)], key=lambda s: s["departure_sec"])
            if not day_svcs:
                continue

            for i in range(len(day_svcs) - 1):
                curr_s = day_svcs[i]
                next_s = day_svcs[i + 1]

                disp = curr_s["post_journey_disposition"]
                if disp["subsequent_service"] is not None:
                    continue

                gap_sec = next_s["stops"][0]["arrival_sec"] - curr_s["arrival_sec"]
                if gap_sec < 0:
                    raise ValueError(
                        f"Infeasible overlapping booking for rake {rake_id} ({curr_s['rolling_stock_type']}) between "
                        f"service {curr_s['train_number']} (arr {curr_s['arrival_time']} at {curr_s['dest_station']}) and "
                        f"service {next_s['train_number']} (dep {next_s['departure_time']} from {next_s['origin_station']}): "
                        f"allocated gap {gap_sec}s is negative."
                    )

                if gap_sec > 18 * 3600:
                    continue

                dwell_min = round(gap_sec / 60.0, 1)
                r_type = curr_s["rolling_stock_type"]
                min_req = MIN_TURNAROUND_BY_CONSIST[r_type]
                if dwell_min < min_req:
                    raise ValueError(
                        f"Infeasible turnaround for rake {rake_id} ({r_type}) between "
                        f"service {curr_s['train_number']} (arr {curr_s['arrival_time']} at {curr_s['dest_station']}) and "
                        f"service {next_s['train_number']} (dep {next_s['departure_time']} from {next_s['origin_station']}): "
                        f"allocated dwell {dwell_min} min is less than required minimum {min_req} min."
                    )

                # Classify turnaround mode
                if "freight" in r_type or curr_s["service_class"] == "Freight":
                    if r_type == "intermodal_container_freight":
                        mode = "container_loading_and_inspection"
                    elif curr_s["dest_station"].startswith("Depot"):
                        mode = "depot_inspection"
                    else:
                        mode = "shunting_and_inspection"
                    action = "depot_stabling" if curr_s["dest_station"].startswith("Depot") else "yard_layover"
                else:
                    if dwell_min <= (min_req + 3.0):
                        mode = "rapid_dual_crew"
                        action = "turnaround"
                    elif dwell_min <= 30.0:
                        mode = "standard_cab_swap"
                        action = "turnaround"
                    else:
                        mode = "extended_layover"
                        action = "yard_layover"

                staging_track = disp.get("staging_track")
                if not staging_track:
                    staging_track = f"{curr_s['dest_station']}_pocket_1_fw" if action == "turnaround" else f"{curr_s['dest_station']}_yard_1_bw"

                disp["action"] = action
                disp["staging_track"] = staging_track
                disp["turnaround_dwell_min"] = dwell_min
                disp["min_turnaround_required_min"] = min_req
                disp["turnaround_mode"] = mode
                disp["subsequent_service"] = next_s["train_number"]

            # Permit link across midnight to next day's first service when station matches
            last_s = day_svcs[-1]
            disp = last_s["post_journey_disposition"]
            if disp["subsequent_service"] is None:
                next_day_name = DAYS[(d_idx + 1) % 7]
                next_day_svcs = sorted([s for s in svc_objs if next_day_name in expand_days(s)], key=lambda s: s["departure_sec"])
                if next_day_svcs:
                    next_first = next_day_svcs[0]
                    if last_s["dest_station"] == next_first["origin_station"] and next_first["stops"][0]["arrival_sec"] < last_s["arrival_sec"]:
                        overnight_gap_sec = (86400.0 - last_s["arrival_sec"]) + next_first["stops"][0]["arrival_sec"]
                        if overnight_gap_sec <= 4 * 3600:
                            overnight_dwell_min = round(overnight_gap_sec / 60.0, 1)
                            r_type = last_s["rolling_stock_type"]
                            min_req = MIN_TURNAROUND_BY_CONSIST[r_type]
                            if "freight" in r_type or last_s["service_class"] == "Freight":
                                if r_type == "intermodal_container_freight":
                                    mode = "container_loading_and_inspection"
                                elif last_s["dest_station"].startswith("Depot"):
                                    mode = "depot_inspection"
                                else:
                                    mode = "shunting_and_inspection"
                                action = "depot_stabling" if last_s["dest_station"].startswith("Depot") else "yard_layover"
                            else:
                                if overnight_dwell_min <= (min_req + 3.0):
                                    mode = "rapid_dual_crew"
                                    action = "turnaround"
                                elif overnight_dwell_min <= 30.0:
                                    mode = "standard_cab_swap"
                                    action = "turnaround"
                                else:
                                    mode = "extended_layover"
                                    action = "yard_layover"

                            staging_track = disp.get("staging_track")
                            if not staging_track:
                                staging_track = f"{last_s['dest_station']}_pocket_1_fw" if action == "turnaround" else f"{last_s['dest_station']}_yard_1_bw"

                            disp["action"] = action
                            disp["staging_track"] = staging_track
                            disp["turnaround_dwell_min"] = overnight_dwell_min
                            disp["min_turnaround_required_min"] = min_req
                            disp["turnaround_mode"] = mode
                            disp["subsequent_service"] = next_first["train_number"]

        # Order rk["assigned_services"] topologically following rotation cycle
        all_succs = {s["train_number"]: s["post_journey_disposition"]["subsequent_service"] for s in svc_objs}
        all_preds = {succ: pred for pred, succ in all_succs.items() if succ is not None}
        starts = [s["train_number"] for s in svc_objs if s["train_number"] not in all_preds]
        if starts:
            ordered = []
            curr = starts[0]
            while curr and curr not in ordered:
                ordered.append(curr)
                curr = all_succs.get(curr)
            for no in svcs:
                if no not in ordered:
                    ordered.append(no)
            rk["assigned_services"] = ordered
        else:
            rk["assigned_services"] = [s["train_number"] for s in sorted(svc_objs, key=lambda s: s["departure_sec"])]

        # Final service of duty cycle for rake: end-of-day stabling
        end_svc_no = rk["assigned_services"][-1]
        end_s = svc_by_no[end_svc_no]
        disp = end_s["post_journey_disposition"]
        first_s = svc_by_no[rk["assigned_services"][0]]
        overnight_gap_sec = (first_s["stops"][0]["arrival_sec"] - end_s["arrival_sec"]) % 86400.0
        overnight_dwell_min = round(overnight_gap_sec / 60.0, 1)

        if end_s["dest_station"].startswith("Depot") or end_s["dest_station"] == rk["home_depot"]:
            action = "depot_stabling"
            mode = "depot_inspection"
        else:
            action = "yard_layover"
            mode = "extended_layover"

        staging_track = disp.get("staging_track") or f"{end_s['dest_station']}_yard_1_bw"
        disp["action"] = action
        disp["staging_track"] = staging_track
        disp["buffer_stop_node"] = None
        disp["turnaround_dwell_min"] = overnight_dwell_min
        disp["min_turnaround_required_min"] = MIN_TURNAROUND_BY_CONSIST[end_s["rolling_stock_type"]]
        disp["turnaround_mode"] = mode
        disp["subsequent_service"] = None

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
