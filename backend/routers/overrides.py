"""
backend/routers/overrides.py
Endpoints for Human-in-the-Loop manual dispatcher interventions for isolated user sessions (Model B).
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends
from backend.schemas.models import ManualOverrideRequest
from backend.core.session_manager import get_user_session, UserSession, session_manager

router = APIRouter(prefix="/api/override", tags=["Human-in-the-Loop Overrides"])


@router.post("/action")
async def apply_manual_override(
    req: ManualOverrideRequest,
    session: Optional[UserSession] = Depends(get_user_session)
):
    """
    Applies an operator manual intervention overriding AI decisions for the user's isolated session:
    - platform_switch: Force alternate platform track (1..6)
    - departure_hold: Force timetable hold (30s, 60s, 120s)
    - bypass_divert: Force high-speed bypass or passing loop diversion
    - release_hold: Clear active hold immediately
    """
    if not isinstance(session, UserSession):
        session = session_manager.get_or_create("default")
    mgr = session.sim_manager
    success = mgr.manual_override(
        vehicle_id=req.vehicle_id,
        override_type=req.override_type,
        target_platform=req.target_platform,
        hold_duration=req.hold_duration_sec
    )
    return {
        "success": success,
        "session_id": session.session_id,
        "vehicle_id": req.vehicle_id,
        "override_type": req.override_type,
        "active_overrides": mgr.active_overrides,
        "recent_actions": mgr.recent_actions[:15]
    }


@router.get("/recent")
async def get_recent_actions(
    session: Optional[UserSession] = Depends(get_user_session)
):
    """Returns the most recent AI and manual dispatch decisions for the user's isolated session."""
    if not isinstance(session, UserSession):
        session = session_manager.get_or_create("default")
    mgr = session.sim_manager
    return {
        "session_id": session.session_id,
        "total_actions_taken": mgr.total_actions_count,
        "recent_actions": mgr.recent_actions
    }
