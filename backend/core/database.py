"""
backend/core/database.py
SQLite access layer for commercial timetable, rolling stock types, and rake rosters.
"""

import sqlite3
from typing import Dict, Any, List, Optional
from backend.config import DB_FILE


def get_db_connection() -> sqlite3.Connection:
    """Creates a read-only SQLite connection with row factory enabled."""
    conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_train_services(
    day: Optional[str] = None,
    corridor: Optional[str] = None,
    service_class: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetches scheduled train services with optional filtering by day, corridor, or class."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            ts.train_number,
            ts.train_name,
            ts.service_class,
            ts.rolling_stock_type,
            ts.assigned_rake,
            ts.corridor,
            ts.direction,
            ts.origin_station,
            ts.origin_track,
            ts.dest_station,
            ts.dest_track,
            ts.departure_time,
            ts.departure_sec,
            ts.arrival_time,
            ts.arrival_sec,
            ts.total_distance_km
        FROM train_services ts
    """
    params = []
    conditions = []

    day_val = str(day).capitalize() if (isinstance(day, str) and day) else None
    corr_val = str(corridor) if (isinstance(corridor, str) and corridor) else None
    class_val = str(service_class) if (isinstance(service_class, str) and service_class) else None

    if day_val:
        query += " INNER JOIN service_operating_days sod ON ts.train_number = sod.train_number"
        conditions.append("sod.day_of_week = ?")
        params.append(day_val)

    if corr_val:
        conditions.append("ts.corridor = ?")
        params.append(corr_val)

    if class_val:
        conditions.append("ts.service_class = ?")
        params.append(class_val)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY ts.departure_sec ASC"

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_service_detail(train_number: str) -> Optional[Dict[str, Any]]:
    """Fetches complete service metadata including intermediate stops and bypasses."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM train_services WHERE train_number = ?", (train_number,))
    service_row = cursor.fetchone()
    if not service_row:
        conn.close()
        return None

    service = dict(service_row)

    # Fetch intermediate stops
    cursor.execute("""
        SELECT stop_sequence, station, train_stop_id, arrival_time, departure_time, dwell_sec
        FROM service_stops
        WHERE train_number = ?
        ORDER BY stop_sequence ASC
    """, (train_number,))
    service["stops"] = [dict(r) for r in cursor.fetchall()]

    # Fetch operating days
    cursor.execute("SELECT day_of_week FROM service_operating_days WHERE train_number = ?", (train_number,))
    service["operating_days"] = [r["day_of_week"] for r in cursor.fetchall()]

    conn.close()
    return service


def get_physical_rakes() -> List[Dict[str, Any]]:
    """Fetches all 31 continuous physical rakes and their assigned duty cycles."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rake_id, rolling_stock_type, home_depot, overnight_stabling_track, assigned_services_count
        FROM physical_rakes
        ORDER BY rake_id ASC
    """)
    rakes = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rakes


def get_rolling_stock_types() -> List[Dict[str, Any]]:
    """Fetches all 7 rolling stock consist specifications."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rolling_stock_types ORDER BY max_speed_kmh DESC")
    types_list = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return types_list


def get_station_timetable(
    station_name: str,
    day: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetches all scheduled train arrivals, departures, and intermediate passenger halts at a station."""
    conn = get_db_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    # Handle City_3 bi-level platforms and Town_8 passing loops
    if station_name == "City_3":
        conditions.append("(ss.station = 'City_3' OR ss.station LIKE 'City_3%')")
    elif station_name == "Town_8":
        conditions.append("(ss.station = 'Town_8' OR ss.station LIKE 'Town_8%')")
    else:
        conditions.append("ss.station = ?")
        params.append(station_name)

    query = """
        SELECT 
            ss.train_number,
            ss.stop_sequence,
            ss.station,
            ss.train_stop_id,
            ss.arrival_time,
            ss.arrival_sec,
            ss.departure_time,
            ss.departure_sec,
            ss.dwell_sec,
            ts.train_name,
            ts.service_class,
            ts.rolling_stock_type,
            ts.assigned_rake,
            ts.origin_station,
            ts.dest_station,
            ts.corridor,
            (SELECT MAX(stop_sequence) FROM service_stops s2 WHERE s2.train_number = ss.train_number) AS max_seq
        FROM service_stops ss
        JOIN train_services ts ON ss.train_number = ts.train_number
    """

    day_val = str(day).capitalize() if (isinstance(day, str) and day and day.upper() != "ALL") else None
    if day_val:
        query += " INNER JOIN service_operating_days sod ON ts.train_number = sod.train_number"
        conditions.append("sod.day_of_week = ?")
        params.append(day_val)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY COALESCE(ss.departure_sec, ss.arrival_sec) ASC"

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    movements = []
    for r in rows:
        is_origin = (r["stop_sequence"] == 1)
        is_terminus = (r["stop_sequence"] == r["max_seq"])

        if is_origin:
            move_type = "DEPARTURE"
            display_time = r["departure_time"]
            bound = r["dest_station"]
        elif is_terminus:
            move_type = "ARRIVAL"
            display_time = r["arrival_time"]
            bound = f"From {r['origin_station']}"
        else:
            move_type = "PASSENGER_HALT"
            display_time = r["departure_time"]
            bound = f"{r['dest_station']} (from {r['origin_station']})"

        movements.append({
            **r,
            "movement_type": move_type,
            "display_time": display_time,
            "bound": bound,
            "is_origin": is_origin,
            "is_terminus": is_terminus
        })

    return movements


def get_timetable_stations() -> List[Dict[str, Any]]:
    """Fetches all station nodes from timetable stop events categorized by role."""
    import re
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT station FROM service_stops ORDER BY station")
    raw_stations = [r["station"] for r in cursor.fetchall()]
    conn.close()

    cities = []
    towns = []
    depots = []

    has_city_3 = any("City_3" in s for s in raw_stations)
    if has_city_3:
        cities.append({"id": "City_3", "name": "City 3 (Central Junction - All Levels)", "category": "City"})

    for s in raw_stations:
        if s.startswith("City_"):
            label = s.replace("_", " ")
            if "EW" in s:
                label = "City 3 (East-West Platform)"
            elif "NS" in s:
                label = "City 3 (North-South Platform)"
            cities.append({"id": s, "name": label, "category": "City"})
        elif s.startswith("Town_"):
            clean_name = s.replace("_", " ")
            if "Passing_Loop" in s:
                clean_name = "Town 8 (Passing Loop)"
            towns.append({"id": s, "name": clean_name, "category": "Town"})
        elif s.startswith("Depot_"):
            depots.append({"id": s, "name": s.replace("_", " "), "category": "Depot"})

    def natural_sort_key(item):
        parts = re.split(r'(\d+)', item["id"])
        return [int(p) if p.isdigit() else p for p in parts]

    cities.sort(key=natural_sort_key)
    towns.sort(key=natural_sort_key)
    depots.sort(key=natural_sort_key)

    return cities + towns + depots

