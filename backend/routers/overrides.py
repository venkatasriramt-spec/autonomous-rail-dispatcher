"""
backend/routers/overrides.py
Endpoints for Human-in-the-Loop manual dispatcher interventions.
"""

from typing import List, Dict, Any
from fastapi import APIRouter
from backend.schemas.models import ManualOverrideRequest
from backend.core.sim_manager import sim_manager

router = APIRouter(prefix="/api/override", tags=["Human-in-the-Loop Overrides"])


@router.post("/action")
async def apply_manual_override(req: ManualOverrideRequest):
    """
    Applies an operator manual intervention overriding AI decisions:
    - platform_switch: Force alternate platform track (1..6)
    - departure_hold: Force timetable hold (30s, 60s, 120s)
    - bypass_divert: Force high-speed bypass or passing loop diversion
    - release_hold: Clear active hold immediately
    """
    success = sim_manager.manual_override(
        vehicle_id=req.vehicle_id,
        override_type=req.override_type,
        target_platform=req.target_platform,
        hold_duration=req.hold_duration_sec
    )
    return {
        "success": success,
        "vehicle_id": req.vehicle_id,
        "override_type": req.override_type,
        "active_overrides": sim_manager.active_overrides,
        "recent_actions": sim_manager.recent_actions[:15]
    }


@router.get("/recent")
async def get_recent_actions():
    """Returns the most recent AI and manual dispatch decisions."""
    return {
        "total_actions_taken": sim_manager.total_actions_count,
        "recent_actions": sim_manager.recent_actions
    }
