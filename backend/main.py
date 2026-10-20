"""
backend/main.py
Master FastAPI application for the Autonomous Railway Traffic Management Platform.
"""

import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("railway_api")

from backend.config import ROOT_DIR, BACKEND_DIR
from backend.core.sim_manager import sim_manager
from backend.core.network_geometry import parse_network_geometry
from backend.routers import (
    simulation_router,
    websocket_router,
    network_router,
    timetable_router,
    analytics_router,
    disruption_router,
    overrides_router
)


from backend.schemas.models import SimulationMode


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler for server startup and clean shutdown."""
    logger.info("Initializing Autonomous Railway Simulation API...")
    loop = asyncio.get_running_loop()
    sim_manager.set_event_loop(loop)

    # Configure from environment variables if passed from launcher or reloaded worker
    env_mode = os.environ.get("SIM_MODE")
    env_day = os.environ.get("SIM_DAY")
    env_model = os.environ.get("SIM_MODEL")
    env_speed = os.environ.get("SIM_SPEED")

    sim_mode = SimulationMode(env_mode) if env_mode in ("LIVE_SUMO", "DEMO_REPLAY") else None
    speed_val = float(env_speed) if env_speed else None

    if any([env_mode, env_day, env_model, speed_val is not None]):
        sim_manager.configure(
            day=env_day,
            model=env_model,
            mode=sim_mode,
            speed=speed_val
        )

    # Pre-parse and cache network geometry in memory
    try:
        parse_network_geometry()
        logger.info("Railway network geometry cached.")
    except Exception as e:
        logger.warning(f"Could not pre-cache geometry: {e}")

    yield

    logger.info("Shutting down Railway Simulation API...")
    sim_manager.reset()
    logger.info("Simulation cleaned up cleanly.")


app = FastAPI(
    title="Autonomous Railway Traffic Management & Simulation API",
    description=(
        "Production backend interfacing microscopic Eclipse SUMO railway simulation, "
        "8-paradigm AI dispatching models (PPO, MAPPO, Comm-MAPPO, Hybrid, Heuristics), "
        "and real-time WebSocket telemetry for interactive web dashboards."
    ),
    version="1.0.0",
    lifespan=lifespan
)

FRONTEND_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080"
]

# Configure CORS for all frontend development servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Subsystem Routers
app.include_router(simulation_router)
app.include_router(websocket_router)
app.include_router(network_router)
app.include_router(timetable_router)
app.include_router(analytics_router)
app.include_router(disruption_router)
app.include_router(overrides_router)

# Mount static frontend directory if built
static_dist = ROOT_DIR / "frontend" / "dist"
if static_dist.exists():
    app.mount("/app", StaticFiles(directory=str(static_dist), html=True), name="frontend")


@app.get("/", tags=["Health & Info"])
async def root_status():
    """API Root providing system metadata and health check."""
    return JSONResponse(content={
        "system": "Autonomous Railway Traffic Management API",
        "version": "1.0.0",
        "status": "online",
        "docs_url": "/docs",
        "websocket_endpoint": "/ws/telemetry",
        "sim_status": sim_manager.get_status()
    })


@app.get("/health", tags=["Health & Info"])
async def health_check():
    """Liveness probe."""
    return {"status": "healthy"}
