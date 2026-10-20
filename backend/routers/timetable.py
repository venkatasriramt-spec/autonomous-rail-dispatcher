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
    get_rolling_stock_types
)

router = APIRouter(prefix="/api/timetable", tags=["Commercial Timetable & Fleet"])


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
