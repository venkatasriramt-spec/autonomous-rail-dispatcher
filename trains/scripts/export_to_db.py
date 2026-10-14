#!/usr/bin/env python3
"""
export_to_db.py
Converts the JSON timetable, rolling stock types, and rake roster into a normalized
relational SQLite database (data/trains.db) with indexes and useful query views.
"""

import sqlite3
import json
import os

TRAINS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(TRAINS_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "trains.db")

def convert_to_sqlite():
    rs_path = os.path.join(DATA_DIR, "rolling_stock_types.json")
    tt_path = os.path.join(DATA_DIR, "timetable.json")
    rk_path = os.path.join(DATA_DIR, "rakes_roster.json")

    with open(rs_path, "r", encoding="utf-8") as f:
        rs_types = json.load(f)

    with open(tt_path, "r", encoding="utf-8") as f:
        timetable = json.load(f)

    with open(rk_path, "r", encoding="utf-8") as f:
        rakes = json.load(f)

    # Connect to SQLite
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Enable foreign keys
    cur.execute("PRAGMA foreign_keys = ON;")

    # 1. Table: rolling_stock_types
    cur.execute("""
    CREATE TABLE rolling_stock_types (
        type_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        service_class TEXT NOT NULL,
        sumo_vclass TEXT NOT NULL,
        power_supply TEXT NOT NULL,
        track_gauge_mm INTEGER NOT NULL,
        max_speed_kmh INTEGER NOT NULL,
        max_speed_ms REAL NOT NULL,
        acceleration_ms2 REAL NOT NULL,
        deceleration_ms2 REAL NOT NULL,
        total_length_m REAL NOT NULL,
        carriages_count INTEGER NOT NULL,
        gross_weight_tons REAL NOT NULL,
        passenger_capacity INTEGER NOT NULL,
        gui_shape TEXT,
        gui_color TEXT
    );
    """)

    # 2. Table: physical_rakes
    cur.execute("""
    CREATE TABLE physical_rakes (
        rake_id TEXT PRIMARY KEY,
        rolling_stock_type TEXT NOT NULL,
        home_depot TEXT NOT NULL,
        FOREIGN KEY (rolling_stock_type) REFERENCES rolling_stock_types(type_id)
    );
    """)

    # 3. Table: train_services
    cur.execute("""
    CREATE TABLE train_services (
        train_number TEXT PRIMARY KEY,
        train_name TEXT NOT NULL,
        service_class TEXT NOT NULL,
        rolling_stock_type TEXT NOT NULL,
        assigned_rake TEXT NOT NULL,
        corridor TEXT NOT NULL,
        direction TEXT NOT NULL,
        origin_station TEXT NOT NULL,
        origin_track TEXT NOT NULL,
        dest_station TEXT NOT NULL,
        dest_track TEXT NOT NULL,
        departure_time TEXT NOT NULL,
        departure_sec REAL NOT NULL,
        arrival_time TEXT NOT NULL,
        arrival_sec REAL NOT NULL,
        total_distance_km REAL NOT NULL,
        FOREIGN KEY (rolling_stock_type) REFERENCES rolling_stock_types(type_id),
        FOREIGN KEY (assigned_rake) REFERENCES physical_rakes(rake_id)
    );
    """)

    # 4. Table: service_operating_days
    cur.execute("""
    CREATE TABLE service_operating_days (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        train_number TEXT NOT NULL,
        day_of_week TEXT NOT NULL,
        FOREIGN KEY (train_number) REFERENCES train_services(train_number)
    );
    """)

    # 5. Table: service_stops
    cur.execute("""
    CREATE TABLE service_stops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        train_number TEXT NOT NULL,
        stop_sequence INTEGER NOT NULL,
        station TEXT NOT NULL,
        train_stop_id TEXT,
        arrival_time TEXT NOT NULL,
        arrival_sec REAL NOT NULL,
        departure_time TEXT NOT NULL,
        departure_sec REAL NOT NULL,
        dwell_sec REAL NOT NULL,
        FOREIGN KEY (train_number) REFERENCES train_services(train_number)
    );
    """)

    # 6. Table: service_bypasses
    cur.execute("""
    CREATE TABLE service_bypasses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        train_number TEXT NOT NULL,
        station TEXT NOT NULL,
        FOREIGN KEY (train_number) REFERENCES train_services(train_number)
    );
    """)

    # 7. Table: service_post_disposition
    cur.execute("""
    CREATE TABLE service_post_disposition (
        train_number TEXT PRIMARY KEY,
        action TEXT NOT NULL,
        staging_track TEXT,
        buffer_stop_node TEXT,
        turnaround_dwell_min REAL,
        min_turnaround_required_min REAL,
        turnaround_mode TEXT,
        subsequent_service TEXT,
        FOREIGN KEY (train_number) REFERENCES train_services(train_number)
    );
    """)

    # Populate rolling_stock_types
    for t_id, r in rs_types.items():
        cur.execute("""
        INSERT INTO rolling_stock_types VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["type_id"], r["name"], r["service_class"], r["sumo_vclass"],
            r["power_supply"], r["track_gauge_mm"], r["max_speed_kmh"], r["max_speed_ms"],
            r["acceleration_ms2"], r["deceleration_ms2"], r["total_length_m"],
            r["carriages_count"], r["gross_weight_tons"], r["passenger_capacity"],
            r["gui_shape"], r["gui_color"]
        ))

    # Populate physical_rakes
    for rk in rakes:
        cur.execute("""
        INSERT INTO physical_rakes VALUES (?, ?, ?)
        """, (rk["rake_id"], rk["rolling_stock_type"], rk["home_depot"]))

    # Populate train_services, days, stops, bypasses, dispositions
    for s in timetable:
        cur.execute("""
        INSERT INTO train_services VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            s["train_number"], s["train_name"], s["service_class"], s["rolling_stock_type"],
            s["assigned_rake"], s["corridor"], s["direction"], s["origin_station"],
            s["origin_track"], s["dest_station"], s["dest_track"], s["departure_time"],
            s["departure_sec"], s["arrival_time"], s["arrival_sec"], s["total_distance_km"]
        ))

        # Operating days
        days = s.get("service_days", [])
        if "Daily" in days:
            expanded_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        elif "Mon-Fri" in days:
            expanded_days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        else:
            expanded_days = days

        for d in expanded_days:
            cur.execute("""
            INSERT INTO service_operating_days (train_number, day_of_week) VALUES (?, ?)
            """, (s["train_number"], d))

        # Stops
        for seq, stp in enumerate(s.get("stops", [])):
            cur.execute("""
            INSERT INTO service_stops (train_number, stop_sequence, station, train_stop_id, arrival_time, arrival_sec, departure_time, departure_sec, dwell_sec)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s["train_number"], seq + 1, stp["station"], stp["train_stop_id"],
                stp["arrival_time"], stp["arrival_sec"], stp["departure_time"],
                stp["departure_sec"], stp["dwell_sec"]
            ))

        # Bypasses
        for bp in s.get("bypassed_through_stations", []):
            cur.execute("""
            INSERT INTO service_bypasses (train_number, station) VALUES (?, ?)
            """, (s["train_number"], bp))

        # Post-journey disposition
        disp = s.get("post_journey_disposition", {})
        if disp:
            cur.execute("""
            INSERT INTO service_post_disposition VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s["train_number"], disp.get("action"), disp.get("staging_track"),
                disp.get("buffer_stop_node"), disp.get("turnaround_dwell_min"),
                disp.get("min_turnaround_required_min", 10.0), disp.get("turnaround_mode", "standard_cab_swap"),
                disp.get("subsequent_service")
            ))

    # Create helpful indexes
    cur.execute("CREATE INDEX idx_services_corridor ON train_services(corridor);")
    cur.execute("CREATE INDEX idx_services_dep_sec ON train_services(departure_sec);")
    cur.execute("CREATE INDEX idx_stops_stn ON service_stops(station);")
    cur.execute("CREATE INDEX idx_days_dow ON service_operating_days(day_of_week);")

    conn.commit()
    conn.close()

    print(f"Successfully converted JSON timetable into SQLite database: {DB_PATH}")

if __name__ == "__main__":
    convert_to_sqlite()
