"""
backend/routers/simulation.py
Simulation control and configuration endpoints.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException

from backend.config import DISPATCHER_MODELS, CALENDAR_DAYS
from backend.schemas.models import (
    SimulationControlRequest,
    SimulationConfigRequest,
    SimulationStatusResponse
)
from backend.core.sim_manager import sim_manager

router = APIRouter(prefix="/api/sim", tags=["Simulation Control"])


@router.get("/status", response_model=SimulationStatusResponse)
def get_simulation_status():
    """Retrieves current simulation status, time, active trains, and KPIs."""
    return sim_manager.get_status()


@router.post("/control")
def control_simulation(req: SimulationControlRequest):
    """Executes a play, pause, step, or reset command."""
    action = req.action.lower()

    if req.speed is not None and req.speed > 0:
        sim_manager.speed_multiplier = req.speed

    if action == "play":
        success = sim_manager.play()
    elif action == "pause":
        success = sim_manager.pause()
    elif action == "step":
        success = sim_manager.step()
    elif action == "reset":
        success = sim_manager.reset()
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action '{req.action}'. Expected play, pause, step, reset.")

    return {
        "success": success,
        "action": action,
        "current_status": sim_manager.get_status()
    }


@router.post("/config")
def configure_simulation(req: SimulationConfigRequest):
    """Updates simulation settings such as calendar day, dispatcher model, speed, or mode."""
    status = sim_manager.configure(
        day=req.day,
        model=req.model,
        mode=req.mode,
        speed=req.speed,
        start_time_sec=req.start_time_sec
    )
    return {
        "success": True,
        "updated_status": status
    }


@router.get("/models", response_model=List[str])
async def list_available_models():
    """Lists all 8 supported AI and heuristic dispatcher paradigms."""
    return DISPATCHER_MODELS


@router.get("/days", response_model=List[str])
async def list_calendar_days():
    """Lists all 7 supported calendar days."""
    return CALENDAR_DAYS
