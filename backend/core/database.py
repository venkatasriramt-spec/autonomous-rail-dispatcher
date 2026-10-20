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
