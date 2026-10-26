"""
backend/routers/simulation.py
Simulation control and configuration endpoints supporting per-user isolated sessions (Model B).
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Response

from backend.config import DISPATCHER_MODELS, CALENDAR_DAYS
from backend.schemas.models import (
    SimulationControlRequest,
    SimulationConfigRequest,
    SimulationStatusResponse
)
from backend.core.session_manager import get_user_session, UserSession, session_manager

router = APIRouter(prefix="/api/sim", tags=["Simulation Control"])


@router.get("/status", response_model=SimulationStatusResponse)
def get_simulation_status(
    response: Response,
    session: UserSession = Depends(get_user_session)
):
    """Retrieves current simulation status, time, active trains, and KPIs for the user's isolated session."""
    response.headers["X-Session-ID"] = session.session_id
    return session.sim_manager.get_status()


@router.get("/telemetry")
def get_simulation_telemetry(
    response: Response,
    session: UserSession = Depends(get_user_session)
):
    """Retrieves real-time telemetry snapshot for the user's isolated session."""
    response.headers["X-Session-ID"] = session.session_id
    mgr = session.sim_manager
    status = mgr.get_status()
    return {
        "session_id": session.session_id,
        "status": status,
        "kpis": {
            "sim_time_sec": status.get("sim_time_sec", 21600.0),
            "time_formatted": status.get("time_formatted", "06:00:00"),
            "active_trains_count": status.get("active_trains_count", 0),
            "mean_delay_sec": status.get("mean_delay_sec", 0.0),
            "punctuality_pct": status.get("punctuality_pct", 100.0),
            "total_actions_taken": status.get("total_actions_taken", 0),
        },
        "trains": mgr.trains_cache,
        "platforms": mgr.platforms_cache,
        "recent_actions": mgr.recent_actions[:15],
    }


@router.post("/control")
def control_simulation(
    req: SimulationControlRequest,
    response: Response,
    session: UserSession = Depends(get_user_session)
):
    """Executes a play, pause, step, reset, or speed command in the user's isolated session."""
    response.headers["X-Session-ID"] = session.session_id
    mgr = session.sim_manager
    action = req.action.lower()

    if req.speed is not None and req.speed > 0:
        mgr.speed_multiplier = req.speed

    if action == "play":
        success = mgr.play()
    elif action == "pause":
        success = mgr.pause()
    elif action == "step":
        success = mgr.step()
    elif action == "reset":
        success = mgr.reset(start_time_sec=req.start_time_sec)
    elif action in ("set_speed", "speed"):
        success = True
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{req.action}'. Expected play, pause, step, reset, set_speed."
        )

    return {
        "success": success,
        "action": action,
        "session_id": session.session_id,
        "current_status": mgr.get_status(),
        "trains": mgr.trains_cache,
        "platforms": mgr.platforms_cache
    }


@router.post("/config")
def configure_simulation(
    req: SimulationConfigRequest,
    response: Response,
    session: UserSession = Depends(get_user_session)
):
    """Updates simulation settings (day, AI model, speed, mode) for the user's isolated session."""
    response.headers["X-Session-ID"] = session.session_id
    status = session.sim_manager.configure(
        day=req.day,
        model=req.model,
        mode=req.mode,
        speed=req.speed,
        start_time_sec=req.start_time_sec
    )
    return {
        "success": True,
        "session_id": session.session_id,
        "updated_status": status
    }


@router.get("/sessions")
async def list_active_sessions():
    """Lists currently active user simulation sessions."""
    return {
        "active_sessions_count": len(session_manager._sessions),
        "sessions": session_manager.list_sessions()
    }


@router.get("/models", response_model=List[str])
async def list_available_models():
    """Lists all 8 supported AI and heuristic dispatcher paradigms."""
    return DISPATCHER_MODELS


@router.get("/days", response_model=List[str])
async def list_calendar_days():
    """Lists all 7 supported calendar days."""
    return CALENDAR_DAYS
