# Autonomous Railway Traffic Management Platform — Backend API

Welcome to the **Autonomous Railway Traffic Management Backend API** subsystem. This production-grade FastAPI and WebSocket service bridges microscopic Eclipse SUMO simulation, eight AI/heuristic train dispatching models, commercial timetabling databases, and real-time frontend user interfaces.

---

## 1. System Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               Modern Web UI Dashboard                                 │
│          (Interactive Canvas/WebGL Map, KPI Gauges, Gantt, Controls & Overrides)       │
└─────────────────────────────────▲────────────────────────────▲─────────────────────────┘
                                  │                            │
                     HTTP REST API│                            │WebSocket Streaming
             (Configuration, Overrides, Data)         (Positions, Delays, Platforms, Actions)
                                  │                            │
┌─────────────────────────────────┴────────────────────────────┴─────────────────────────┐
│                           FastAPI Simulation Backend Server                            │
│                                                                                        │
│  [Routers]                                                                             │
│  ├── /api/sim        - Lifecycle & Playback Controls (play, pause, step, speed)        │
│  ├── /ws/telemetry   - Real-Time WebSocket Telemetry Broadcast (4-10 Hz)               │
│  ├── /api/network    - 2D Track Vector Geometry, Station Centroids, Platform Bounds    │
│  ├── /api/timetable  - SQLite Service Schedules (242 runs), 31 Rakes, Station Boards   │
│  ├── /api/analytics  - Authoritative 56-Run Weekly Benchmarks, Diurnal Curves          │
│  ├── /api/disruption - Mechanical Breakdowns, Platform Closures, Fleet Surge Jitter    │
│  └── /api/override   - Human-in-the-Loop Manual Interventions (Holds, Platform Swaps)  │
│                                                                                        │
│  [Core Engine]                                                                         │
│  ├── SimulationManager   - Thread-safe SUMO/TraCI lifecycle & Step Controller          │
│  ├── DispatcherBridge    - Model Factory (Centralized PPO, MAPPO, Comm-MAPPO, Hybrid)  │
│  ├── NetworkGeometry     - XML-to-Vector Parser & Cache (776 lanes, 18 stations)       │
│  ├── DatabaseEngine      - Normalized SQLite Query Engine (trains.db)                  │
│  └── TelemetryStreamer   - Async WebSocket Client Hub                                  │
└────────────────────────┬─────────────────────────────────────┬─────────────────────────┘
                         │                                     │
                         ▼                                     ▼
      ┌────────────────────────────────────┐ ┌───────────────────────────────────────────┐
      │  Microscopic Eclipse SUMO (TraCI)  │ │         Trained Deep RL Policies          │
      │  - Physical Signaling & Collision  │ │  - Centralized PPO (best_model.zip)       │
      │  - 1-Second Micro-Step Dynamics    │ │  - Decentralized MAPPO (7 Agents, .pt)    │
      │  - Platform Dwells & Turnarounds   │ │  - Comm-MAPPO & Hierarchical Hybrid       │
      └────────────────────────────────────┘ └───────────────────────────────────────────┘
```

---

## 2. Directory Layout

```
backend/
├── config.py                 # Central filesystem paths, constants, and server defaults
├── main.py                   # Master FastAPI application, CORS, and lifecycle mounts
├── run_server.py             # CLI entrypoint with customizable host, port, mode, and day
├── test_backend.py           # Comprehensive end-to-end unit test and validation suite
├── requirements.txt          # Python dependency specifications
├── network_geometry.json     # Cached web-ready 2D vector geometry for track rendering
├── core/
│   ├── sim_manager.py        # Master SimulationManager thread orchestrating SUMO & AI
│   ├── dispatcher_bridge.py  # Model loader & inference wrapper for all 8 paradigms
│   ├── network_geometry.py   # XML parser extracting 776 track lanes and 116 platforms
│   ├── database.py           # Read-only SQLite query engine for trains.db
│   └── telemetry_streamer.py # Real-time WebSocket connection hub & broadcaster
├── routers/
│   ├── simulation.py         # POST /api/sim/control, POST /api/sim/config, GET /api/sim/status
│   ├── websocket.py          # WS /ws/telemetry
│   ├── network.py            # GET /api/network/geometry, stations, platforms, bounds
│   ├── timetable.py          # GET /api/timetable/stations, station/{station_name}, services, rakes
│   ├── analytics.py          # GET /api/analytics/weekly-summary, diurnal, stress-test
│   ├── disruption.py         # POST /api/disruption/inject, clear, active
│   └── overrides.py          # POST /api/override/action, recent
└── schemas/
    └── models.py             # Pydantic models for type safety, validation, and serialization
```

---

## 3. Quick-Start & Operational Commands

### 1. Launch Backend Server
```bash
# Launch server with default settings (Host: 0.0.0.0, Port: 8000, Centralized PPO, Monday)
python3 backend/run_server.py

# Launch in DEMO_REPLAY mode (instant animated telemetry without needing local SUMO)
python3 backend/run_server.py --mode DEMO_REPLAY --port 8000

# Launch with hot reloading enabled for API development
python3 backend/run_server.py --reload --port 8000

# Launch on a specific calendar day with a specific AI model
python3 backend/run_server.py --day Sat --model Hierarchical_Hybrid
```

### 2. Run Comprehensive Test Suite
```bash
# Validates database queries, geometry parser, all REST endpoints, and live HTTP server
python3 backend/test_backend.py
```

### 3. Interactive Documentation
Once the server is running, navigate to:
* **Interactive Swagger UI:** `http://localhost:8000/docs`
* **ReDoc Documentation:** `http://localhost:8000/redoc`
* **Root Health Check:** `http://localhost:8000/`

---

## 4. API Endpoints Reference

### A. Simulation Lifecycle & Controls (`/api/sim`)
* `GET /api/sim/status`: Returns current status (`STOPPED`, `RUNNING`, `PAUSED`), mode, sim time, active trains count, mean delay, punctuality, active disruptions, active overrides, and total actions.
* `GET /api/sim/telemetry`: Complete real-time snapshot alternative to WebSockets. Returns current KPIs, active trains list, platform occupancy, network status, active disruptions metadata, active overrides, and recent action event stream.
* `POST /api/sim/control`: Sends playback or speed control commands:
  ```json
  { "action": "play" }   // "play", "pause", "step", "reset", "set_speed"
  { "action": "set_speed", "speed": 5.0 }
  ```
* `POST /api/sim/config`: Dynamically updates simulation parameters:
  ```json
  {
    "day": "Mon",
    "model": "Centralized_PPO",
    "speed": 5.0,
    "mode": "LIVE_SUMO"
  }
  ```
* `GET /api/sim/models`: Returns list of all 8 supported AI and heuristic models (supports shorthand aliases such as `MAPPO`, `FIFO`, `PPO`, `DQN`, `Hybrid` via `MODEL_ALIASES`).
* `GET /api/sim/days`: Returns list of all 7 calendar days (`Mon` through `Sun`).

### B. Live WebSocket Telemetry (`/ws/telemetry`)
* **Endpoint:** `ws://localhost:8000/ws/telemetry`
* **Rate:** Broadcasts at 4 Hz (customizable).
* **Frame Structure:**
  ```json
  {
    "kpis": {
      "sim_time_sec": 25200.0,
      "time_formatted": "07:00:00",
      "active_trains_count": 24,
      "mean_delay_sec": 14.2,
      "max_delay_sec": 84.0,
      "punctuality_pct": 98.4,
      "total_knock_on_events": 0,
      "total_actions_taken": 42
    },
    "trains": [
      {
        "id": "HS_300_01",
        "x": 12450.5,
        "y": 18230.1,
        "angle": 88.5,
        "speed_kmh": 285.0,
        "delay_sec": 0.0,
        "vtype": "high_speed_emu_300",
        "priority": 1.0,
        "length_m": 400.0,
        "upcoming_station": "City_2",
        "is_at_stop": false
      }
    ],
    "platforms": [
      {
        "platform_id": "City_3_p1_fw",
        "station_name": "City_3",
        "track": "p1",
        "is_occupied": true,
        "occupying_train_id": "REG_120_04",
        "dwell_rem_sec": 30.0
      }
    ],
    "recent_actions": [
      {
        "time_formatted": "06:58:30",
        "vehicle_id": "FRT_Hvy_02",
        "action_type": "diverted_to_passing_loop",
        "details": "Diverted into Alpine Passing Loop siding for high-speed overtake",
        "dispatcher_model": "Centralized_PPO"
      }
    ],
    "sim_status": "RUNNING",
    "dispatcher_model": "Centralized_PPO",
    "calendar_day": "Mon",
    "speed_multiplier": 2.0
  }
  ```

### C. Network Infrastructure (`/api/network`)
* `GET /api/network/geometry`: Complete 2D vector geometry for all 776 track lanes categorized into:
  - `high_speed`: Main line and High-Speed Bypass chords
  - `regional`: Standard trunk lines
  - `passing_loop`: 1,200m Alpine freight passing loop
  - `pocket`: Terminal buffer turnaround tracks
  - `platform`: Station platform loops
  - `crossover`: Universal turnout crossovers
  - `yard`: Stabling yards and freight depots
* `GET /api/network/stations`: 18 stations with geographic centroids and platform counts.
* `GET /api/network/platforms`: All 116 microscopic platform tracks with physical lengths.
* `GET /api/network/bounds`: Coordinate bounding box `[min_x, min_y, max_x, max_y]`.

### D. Timetable & Fleet (`/api/timetable`)
* `GET /api/timetable/stations`: Returns 24 station query entries categorized by functional role (`City`, `Town`, `Depot`) with multi-level platform aggregation (`City_3`, `City_3_EW`, `City_3_NS`, `Town_8_Passing_Loop`).
* `GET /api/timetable/station/{station_name}?day=Mon`: Station-centric schedule board of all scheduled departures, arrivals, and intermediate halts for the requested station and operating day:
  ```json
  [
    {
      "train_number": "12001",
      "train_name": "Express Sunrise",
      "service_class": "high_speed_express",
      "origin_station": "City_1",
      "dest_station": "City_4",
      "train_stop_id": "City_1_p1_fw",
      "arrival_time": null,
      "departure_time": "06:00:00",
      "dwell_sec": 120,
      "movement_type": "DEPARTURE",
      "display_time": "06:00:00",
      "bound": "To City_4",
      "is_origin": 1,
      "is_terminus": 0
    }
  ]
  ```
* `GET /api/timetable/services`: Query scheduled services with filters (`?day=Mon&corridor=Corridor_1&service_class=high_speed_express`).
* `GET /api/timetable/services/{train_number}`: Detailed service with intermediate stops and timings.
* `GET /api/timetable/rakes`: Fleet roster of 31 continuous physical rakes, rolling stock types, and daily duty cycles.
* `GET /api/timetable/rolling-stock`: Specifications for all 7 physical consist models with speeds, lengths, and power regimes.

### E. Analytics & Benchmarking (`/api/analytics`)
* `GET /api/analytics/weekly-summary`: Summary metrics from the authoritative 56-run weekly benchmark across all 8 models.
* `GET /api/analytics/diurnal?day=Mon`: 24-hour hour-by-hour fleet delay progression and diurnal curves by model.
* `GET /api/analytics/stress-test`: Multi-scenario disruption stress test results (Phases A & B).

### F. Perturbations & Human-in-the-Loop (`/api/disruption` & `/api/override`)
* `POST /api/disruption/inject`: Injects mechanical breakdowns, platform closures, fleet surge dwell jitter, or compound failures:
  ```json
  {
    "mode": "train_delay",            // "train_delay" | "platform_blockage" | "fleet_surge" | "compound_failure"
    "vehicle_id": "REG_C2_02",        // Optional: auto-resolves to active vehicle if omitted
    "platform_id": "City_1_plat_1_fw",// Optional: auto-resolves to hub platform if omitted
    "delay_duration_sec": 600.0
  }
  ```
  Returns `success` boolean, `mode`, `active_disruptions`, `active_disruptions_data` (structured tracking records with timestamps, auto-expiry, and target entities), `recent_actions` audit log, and confirmation `message`.
* `POST /api/disruption/clear`: Clears all active perturbations and restores speed limits.
* `GET /api/disruption/active`: Returns list of currently active injected disruptions, structured metadata, and remaining durations.
* `POST /api/override/action`: Applies manual operator intervention:
  ```json
  {
    "vehicle_id": "HS_300_01",
    "override_type": "platform_switch",
    "target_platform": 4
  }
  ```
* `GET /api/override/recent`: Returns recent manual intervention event history.

---

## 5. Subsystem Links & References

* **Monorepo Architecture:** [Root README](../README.md)
* **Frontend Web Dashboard:** [frontend/README.md](../frontend/README.md)
* **Physical Track Network:** [tracks/README.md](../tracks/README.md)
* **Fleet Management & Timetables:** [trains/README.md](../trains/README.md)
* **Autonomous Dispatcher AI:** [dispatcher/README.md](../dispatcher/README.md)
* **Unified Milestones & History:** [project_history.md](../project_history.md)

