"""
backend/routers/disruption.py
Endpoints for injecting, monitoring, and clearing simulation perturbations for isolated user sessions (Model B).
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from backend.schemas.models import DisruptionRequest
from backend.core.session_manager import get_user_session, UserSession

router = APIRouter(prefix="/api/disruption", tags=["Perturbations & Disruptions"])


@router.post("/inject")
def inject_disruption(
    req: DisruptionRequest,
    session: UserSession = Depends(get_user_session)
):
    """
    Injects a live disruption into the running simulation for the user's isolated session:
    - train_delay: Mechanical breakdown/stall
    - platform_blockage: Hub platform track closure
    - fleet_surge: Boarding dwell jitter
    - compound_failure: Breakdown + platform closure
    """
    mgr = session.sim_manager
    success = mgr.inject_disruption(
        mode=req.mode,
        vehicle_id=req.vehicle_id,
        platform_id=req.platform_id,
        station_id=req.station_id,
        duration=req.delay_duration_sec or 600.0
    )
    return {
        "success": success,
        "mode": req.mode,
        "session_id": session.session_id,
        "message": "Disruption applied successfully." if success else "Failed to inject disruption into simulation environment.",
        "active_disruptions": mgr.active_disruptions,
        "active_disruptions_data": mgr.active_disruptions_data,
        "recent_actions": mgr.recent_actions[:15]
    }


@router.post("/clear")
def clear_all_disruptions(
    session: UserSession = Depends(get_user_session)
):
    """Clears all active perturbations in the user's isolated session."""
    session.sim_manager.clear_disruptions()
    return {
        "success": True,
        "session_id": session.session_id,
        "message": "All active disruptions cleared."
    }


@router.get("/active")
async def get_active_disruptions(
    session: UserSession = Depends(get_user_session)
):
    """Returns currently active perturbations for the user's isolated session."""
    mgr = session.sim_manager
    return {
        "session_id": session.session_id,
        "active_disruptions": mgr.active_disruptions,
        "active_disruptions_data": mgr.active_disruptions_data
    }
