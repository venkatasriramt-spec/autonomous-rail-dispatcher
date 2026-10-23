"""
backend/routers/timetable.py
Endpoints for commercial timetable services, rake rosters, and rolling stock types.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from backend.core.database import (
    get_train_services,
    get_service_detail,
    get_physical_rakes,
    get_rolling_stock_types,
    get_station_timetable,
    get_timetable_stations
)

router = APIRouter(prefix="/api/timetable", tags=["Commercial Timetable & Fleet"])


@router.get("/stations")
async def list_timetable_stations():
    """Returns all station nodes with scheduled passenger and freight services categorized by role."""
    return get_timetable_stations()


@router.get("/station/{station_name}")
async def get_station_board(
    station_name: str,
    day: Optional[str] = Query(None, description="Filter by calendar day (e.g. Mon, Tue, ..., Sun, or ALL)")
):
    """Returns all scheduled departures, arrivals, and intermediate halts for a specific station hub or town."""
    return get_station_timetable(station_name=station_name, day=day)


@router.get("/services")
async def list_train_services(
    day: Optional[str] = None,
    corridor: Optional[str] = None,
    service_class: Optional[str] = None
):
    """Returns scheduled train services with optional filtering."""
    return get_train_services(day=day, corridor=corridor, service_class=service_class)


@router.get("/services/{train_number}")
async def get_service_by_number(train_number: str):
    """Returns detailed service metadata including intermediate stops and operating schedule."""
    detail = get_service_detail(train_number)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Train service '{train_number}' not found.")
    return detail


@router.get("/rakes")
async def list_physical_rakes():
    """Returns the fleet roster of 31 continuous physical rakes and daily duty cycles."""
    return get_physical_rakes()


@router.get("/rolling-stock")
async def list_rolling_stock_types():
    """Returns specifications for all 7 physical train consist classes."""
    return get_rolling_stock_types()

