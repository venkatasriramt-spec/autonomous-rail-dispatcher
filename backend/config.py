"""
backend/config.py
Central configuration and filesystem path resolution for the Railway Simulation Backend.
"""

import os
import sys
from pathlib import Path
from typing import List

# Base filesystem directories
ROOT_DIR = Path(__file__).resolve().parent.parent
TRACKS_DIR = ROOT_DIR / "tracks"
TRAINS_DIR = ROOT_DIR / "trains"
DISPATCHER_DIR = ROOT_DIR / "dispatcher"
BACKEND_DIR = ROOT_DIR / "backend"

# Ensure root directory is on sys.path
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure SUMO tools are on sys.path
SUMO_HOME = os.environ.get("SUMO_HOME", "/usr/share/sumo")
SUMO_TOOLS = os.path.join(SUMO_HOME, "tools")
if os.path.exists(SUMO_TOOLS) and SUMO_TOOLS not in sys.path:
    sys.path.append(SUMO_TOOLS)

# Authoritative data files
NET_FILE = TRACKS_DIR / "network_data" / "dense_network.net.xml"
ADD_FILE = TRACKS_DIR / "network_data" / "dense_network.add.xml"
TOPOLOGY_REPORT = TRACKS_DIR / "network_data" / "railway_topology.xml"
DB_FILE = TRAINS_DIR / "data" / "trains.db"
TIMETABLE_JSON = TRAINS_DIR / "data" / "timetable.json"
RAKES_ROSTER_JSON = TRAINS_DIR / "data" / "rakes_roster.json"
ROLLING_STOCK_JSON = TRAINS_DIR / "data" / "rolling_stock_types.json"

# Simulation configurations
DAYS_DIR = TRAINS_DIR / "sumo_config" / "days"
DEFAULT_SUMOCFG = TRAINS_DIR / "sumo_config" / "train_simulation.sumocfg"

# Production Model Checkpoints
PPO_MODEL_PATH = DISPATCHER_DIR / "models" / "best_model.zip"
MAPPO_MODEL_PATH = DISPATCHER_DIR / "models" / "mappo_interlocking.pt"

# Benchmark and Evaluation Logs
WEEKLY_BENCHMARK_JSON = DISPATCHER_DIR / "logs" / "evaluations" / "weekly_audits" / "cross_comparison_24h.json"
DISRUPTION_BENCHMARK_JSON = DISPATCHER_DIR / "logs" / "evaluations" / "disruption_benchmarks" / "benchmark_results.json"
STRESS_BENCHMARK_JSON = DISPATCHER_DIR / "logs" / "evaluations" / "stress_tests" / "stress_testing_benchmark.json"
VISUAL_PROOFS_DIR = DISPATCHER_DIR / "logs" / "visual_proofs"

# Cached Web Geometry Output
GEOMETRY_CACHE_FILE = BACKEND_DIR / "network_geometry.json"

# Supported Dispatcher Paradigms
DISPATCHER_MODELS: List[str] = [
    "Centralized_PPO",
    "Hierarchical_Hybrid",
    "Decentralized_MAPPO",
    "Comm_MAPPO",
    "Multi_Train_Centralized_PPO",
    "Priority_Greedy_Heuristic",
    "FIFO_Heuristic",
    "Static_Baseline"
]

# Supported Calendar Days
CALENDAR_DAYS: List[str] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Server defaults (respects Cloud Run PORT and HOST environment variables)
DEFAULT_HOST = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("PORT", 8000))
TELEMETRY_BROADCAST_HZ = 4.0  # 4 updates per second over WebSocket
DEFAULT_MACRO_STEP_SEC = 15.0 # AI decision interval (seconds)
DEFAULT_SIM_SPEED = 1.0       # Playback multiplier
