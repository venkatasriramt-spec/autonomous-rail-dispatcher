"""
backend/routers/disruption.py
Endpoints for injecting, monitoring, and clearing simulation perturbations.
"""

from typing import List, Dict, Any
from fastapi import APIRouter
from backend.schemas.models import DisruptionRequest
from backend.core.sim_manager import sim_manager

router = APIRouter(prefix="/api/disruption", tags=["Perturbations & Disruptions"])


@router.post("/inject")
def inject_disruption(req: DisruptionRequest):
    """
    Injects a live disruption into the running simulation:
    - train_delay: Mechanical breakdown/stall
    - platform_blockage: Hub platform track closure
    - fleet_surge: Boarding dwell jitter
    - compound_failure: Breakdown + platform closure
    """
    success = sim_manager.inject_disruption(
        mode=req.mode,
        vehicle_id=req.vehicle_id,
        platform_id=req.platform_id,
        duration=req.delay_duration_sec or 600.0
    )
    return {
        "success": success,
        "mode": req.mode,
        "message": "Disruption applied successfully." if success else "Failed to inject disruption into simulation environment.",
        "active_disruptions": sim_manager.active_disruptions,
        "active_disruptions_data": sim_manager.active_disruptions_data,
        "recent_actions": sim_manager.recent_actions[:15]
    }


@router.post("/clear")
def clear_all_disruptions():
    """Clears all active perturbations."""
    sim_manager.clear_disruptions()
    return {
        "success": True,
        "message": "All active disruptions cleared."
    }


@router.get("/active")
async def get_active_disruptions():
    """Returns currently active perturbations."""
    return {
        "active_disruptions": sim_manager.active_disruptions,
        "active_disruptions_data": sim_manager.active_disruptions_data
    }
