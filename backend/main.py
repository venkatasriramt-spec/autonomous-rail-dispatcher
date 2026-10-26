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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
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
    title="Autonomous Railway Traffic Management & Simulation Platform",
    description=(
        "Production full-stack platform interfacing microscopic Eclipse SUMO railway simulation, "
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

cors_env = os.environ.get("CORS_ORIGINS")
if cors_env:
    if cors_env.strip() == "*":
        allowed_origins = ["*"]
    else:
        allowed_origins = FRONTEND_ORIGINS + [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    allowed_origins = FRONTEND_ORIGINS

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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

# Mount static frontend directory
static_dist = ROOT_DIR / "frontend" / "dist"
if static_dist.exists():
    assets_dir = static_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static_assets")

    # Serve static assets and icons
    @app.get("/favicon.svg", include_in_schema=False)
    async def serve_favicon():
        fav = static_dist / "favicon.svg"
        if fav.exists():
            return FileResponse(str(fav))
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    @app.get("/icons.svg", include_in_schema=False)
    async def serve_icons():
        ic = static_dist / "icons.svg"
        if ic.exists():
            return FileResponse(str(ic))
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    @app.get("/network_geometry.json", include_in_schema=False)
    async def serve_network_geom():
        geom_file = static_dist / "network_geometry.json"
        if geom_file.exists():
            return FileResponse(str(geom_file))
        return JSONResponse(content=sim_manager.geometry)


@app.get("/health", tags=["Health & Info"])
async def health_check():
    """Liveness probe."""
    return {"status": "healthy"}


@app.get("/api/status", tags=["Health & Info"])
async def api_status():
    """System metadata and simulation status JSON."""
    return JSONResponse(content={
        "system": "Autonomous Railway Traffic Management API",
        "version": "1.0.0",
        "status": "online",
        "docs_url": "/docs",
        "websocket_endpoint": "/ws/telemetry",
        "sim_status": sim_manager.get_status()
    })


@app.get("/", tags=["Health & Info"])
async def root_endpoint(request: Request):
    """Serves the frontend SPA index.html for browser requests, or JSON metadata for API clients."""
    accept = request.headers.get("accept", "")
    index_html = static_dist / "index.html"
    if "text/html" in accept and index_html.exists():
        return FileResponse(
            str(index_html),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

    return JSONResponse(content={
        "system": "Autonomous Railway Traffic Management API",
        "version": "1.0.0",
        "status": "online",
        "docs_url": "/docs",
        "websocket_endpoint": "/ws/telemetry",
        "sim_status": sim_manager.get_status()
    })


# Single-Page Application (SPA) client-side routing fallback
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """Fallback route serving React Router SPA routes (e.g. /simulation, /query, /about)."""
    if full_path.startswith("api/") or full_path.startswith("ws/") or full_path in ("docs", "redoc", "openapi.json", "health"):
        return JSONResponse(status_code=404, content={"detail": f"Endpoint '/{full_path}' not found"})

    target_file = static_dist / full_path
    if target_file.is_file():
        return FileResponse(str(target_file))

    index_html = static_dist / "index.html"
    if index_html.exists():
        return FileResponse(
            str(index_html),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

    return JSONResponse(status_code=404, content={"detail": "Not found"})
