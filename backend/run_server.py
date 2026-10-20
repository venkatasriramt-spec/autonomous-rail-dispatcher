"""
backend/run_server.py
CLI entrypoint to launch the FastAPI railway simulation server.
"""

import os
import sys
import argparse
import uvicorn
from pathlib import Path

# Ensure ROOT_DIR on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import DEFAULT_HOST, DEFAULT_PORT, DISPATCHER_MODELS, CALENDAR_DAYS
from backend.core.sim_manager import sim_manager
from backend.schemas.models import SimulationMode


def main():
    parser = argparse.ArgumentParser(description="Autonomous Railway Traffic Management & Simulation API Server")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help=f"Host address (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port number (default: {DEFAULT_PORT})")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload for development")
    parser.add_argument("--mode", type=str, choices=["LIVE_SUMO", "DEMO_REPLAY"], default="LIVE_SUMO", help="Simulation mode")
    parser.add_argument("--day", type=str, choices=CALENDAR_DAYS, default="Mon", help="Starting calendar day")
    parser.add_argument("--model", type=str, choices=DISPATCHER_MODELS, default="Centralized_PPO", help="Starting AI dispatcher model")
    parser.add_argument("--speed", type=float, default=1.0, help="Initial simulation speed multiplier")

    args = parser.parse_args()

    # Pass configuration to worker processes via environment variables
    os.environ["SIM_MODE"] = args.mode
    os.environ["SIM_DAY"] = args.day
    os.environ["SIM_MODEL"] = args.model
    os.environ["SIM_SPEED"] = str(args.speed)

    # Pre-configure manager
    sim_mode = SimulationMode.LIVE_SUMO if args.mode == "LIVE_SUMO" else SimulationMode.DEMO_REPLAY
    sim_manager.configure(
        day=args.day,
        model=args.model,
        mode=sim_mode,
        speed=args.speed
    )

    print(f"=================================================================")
    print(f"  Autonomous Railway Traffic Management Platform - Backend API  ")
    print(f"=================================================================")
    print(f"  Host:                 http://{args.host}:{args.port}")
    print(f"  Interactive API Docs: http://localhost:{args.port}/docs")
    print(f"  WebSocket Telemetry:  ws://localhost:{args.port}/ws/telemetry")
    print(f"  Initial Day:          {args.day}")
    print(f"  Initial AI Model:     {args.model}")
    print(f"  Simulation Mode:      {args.mode}")
    print(f"=================================================================")

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
