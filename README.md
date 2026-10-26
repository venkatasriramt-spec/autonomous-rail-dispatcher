# Autonomous Rail Dispatcher

Welcome to the **Autonomous Rail Dispatcher** (`autonomous-rail-dispatcher`) monorepo. This repository unites microscopic track engineering, procedural network generation, commercial timetabling, rolling stock logistics, and autonomous reinforcement learning dispatching into a single coherent codebase with full version-controlled history.

---

## 1. System Architecture

The monorepo is organized into five isolated yet tightly integrated subsystems:

```
.
├── tracks/                       # Physical Track Infrastructure & Network Generation
│   ├── network_data/             # Compiled SUMO XML definitions (net, edg, nod, con, add)
│   │   ├── dense_network.net.xml # Routable microscopic track network
│   │   ├── dense_network.add.xml # Platform definitions (<trainStop>)
│   │   ├── dense_network.edg.xml # Track edges, lanes, physical speed limits
│   │   ├── dense_network.nod.xml # Station throats, switches, buffer stops
│   │   ├── dense_network.con.xml # Interlocking connections & turnouts
│   │   └── railway_topology.xml  # Verified topology report (0 error nodes)
│   ├── scripts/                  # Procedural network generators & schematic renderers
│   │   ├── generate_sumo_network.py # Master procedural network generator
│   │   ├── plot_network.py          # 2D network overview renderer
│   │   ├── plot_bilevel_hub.py      # City 3 bi-level hub schematic renderer
│   │   ├── plot_station_layout.py   # 4-track express station layout renderer
│   │   ├── plot_crossover.py        # Universal crossover schematic renderer
│   │   ├── plot_passing_loop.py     # Alpine freight passing loop renderer
│   │   └── plot_terminal_pockets.py # Buffer stop & pocket track renderer
│   ├── README.md                 # Detailed tracks subsystem documentation
│   ├── project_history.md        # Chronological history of network evolution
│   └── requirements.txt          # Tracks plotting dependencies (matplotlib, numpy)
│
├── trains/                       # Fleet Management, Timetabling & Simulation Runtime
│   ├── data/                     # Authoritative railway data specifications
│   │   ├── rolling_stock_types.json # 7 physical train consist definitions
│   │   ├── timetable.json           # 242 scheduled train runs with calibrated dwells
│   │   ├── rakes_roster.json        # 31 physical rakes and daily duty cycles
│   │   └── trains.db                # Normalized SQLite relational database
│   ├── scripts/                  # Timetable compilers & simulation auditors
│   │   ├── generate_master_timetable.py # Procedural master schedule generator
│   │   ├── export_to_db.py              # Synchronizes JSON datasets into SQLite
│   │   ├── export_to_sumo.py            # Compiles XML trips & routes via duarouter
│   │   ├── validate_timetable.py        # Validates timetable against physical tracks
│   │   └── verify_simulation.py         # Headless SUMO simulation & safety validator
│   ├── sumo_config/              # Compiled microscopic simulation route files
│   │   ├── train_simulation.sumocfg     # Master SUMO simulation configuration
│   │   ├── trains_rakes.rou.xml         # 31 continuous physical rakes full-day routes
│   │   ├── trains_services.rou.xml      # 242 discrete scheduled service routes
│   │   └── viewsettings.xml             # High-contrast dark railway visual theme
│   ├── README.md                 # Detailed trains subsystem documentation
│   ├── project_history.md        # Chronological history of timetable & fleet evolution
│   └── requirements.txt          # Trains runtime dependencies
│
├── dispatcher/                   # Autonomous AI Train Dispatching, Dynamic Rerouting & Rescheduling
│   ├── envs/                     # Gymnasium environment & TraCI microscopic bridges
│   │   ├── railway_dispatch_env.py # Gymnasium SMDP train dispatching environment
│   │   ├── multi_agent_railway_env.py # Decentralized multi-agent environment (CTDE)
│   │   ├── observation_builder.py  # 28-feature state extraction & platform mappings
│   │   ├── multi_agent_builder.py  # Localized station (24-dim) & corridor (14-dim) observations
│   │   ├── marl_zones.py           # Station interlocking and corridor zone partitioning
│   │   ├── action_handler.py       # Microscopic execution (reroute, replaceStop, resume)
│   │   └── reward_engine.py        # Multi-class priority & secondary delay formulation
│   ├── agents/                   # Dispatcher policies & benchmark heuristics
│   │   ├── baseline_dispatchers.py # Static (no-op), FIFO, and Priority heuristic controllers
│   │   ├── mappo_agent.py          # Multi-Agent PPO actor-critic architectures (PyTorch)
│   │   ├── multi_train_ppo.py      # Concurrent multi-train centralized PPO controller
│   │   ├── comm_mappo_agent.py     # Communicative MAPPO with inter-agent message passing
│   │   └── hybrid_dispatcher.py    # Hierarchical Lookahead Ensemble (Tiers 1–3)
│   ├── scenarios/                # Controlled disruption & perturbation generators
│   │   └── perturbations.py        # Mechanical breakdowns, platform blockages, stochastic delays
│   ├── training/                 # Deep RL training infrastructure
│   │   ├── train.py                # Multi-core CPU PPO training runner
│   │   ├── train_curriculum.py     # Automated progressive wave curriculum runner
│   │   ├── train_multiday_option1.py # Multi-calendar day generalization runner
│   │   ├── train_mappo.py          # Multi-agent PPO training pipeline
│   │   ├── train_mappo_curriculum.py # 4-wave diurnal MAPPO curriculum trainer
│   │   ├── train_and_benchmark_all.py # End-to-end multi-stage training & benchmarking pipeline
│   │   ├── retrain_500k.py         # 500,000-step scaled retraining pipeline
│   │   └── callbacks.py            # Real-time KPI logger & best model checkpointing
│   ├── evaluation/               # Empirical benchmarking & visual analytics
│   │   ├── evaluate.py             # Comparative benchmark suite runner (Frontiers 1 & 2)
│   │   ├── audit_marl_comparison.py # Multi-agent MARL vs Centralized PPO empirical benchmark
│   │   ├── visualizer.py           # Publication-ready Matplotlib chart generator (disruption)
│   │   ├── visualize_stress_test.py # Publication-ready chart generator (stress testing)
│   │   ├── visualize_weekly_audit.py # Publication-ready 8-model visualizer (7-day 24h audits)
│   │   ├── visualize_marl.py       # 4-panel MARL vs Centralized comparative visualizer
│   │   ├── audit_cross_comparison_24h.py # Authoritative 56-run weekly benchmarking engine (all 7 days × 8 models)
│   │   ├── audit_full_day_parallel.py # 7-day continuous fleet evaluation
│   │   ├── audit_weekly_calendar.py # Weekday vs weekend morning peak audit
│   │   ├── audit_stress_testing.py # Multi-scenario stress benchmark (delays & blockages)
│   │   └── audit_stress_24h_all_days.py # 24-hour multi-day stress testing (Phases A & B)
│   ├── models/                   # Saved model weights (best_model.zip, mappo_*.pt)
│   ├── logs/                     # Hierarchical logs (evaluations/, visual_proofs/, tensorboard/)
│   └── README.md                 # Detailed Dispatcher AI subsystem documentation
│
├── backend/                      # Production FastAPI & WebSocket Simulation Server
│   ├── main.py                   # Master FastAPI application, CORS & lifecycle
│   ├── run_server.py             # CLI entrypoint (host, port, mode, day, model)
│   ├── config.py                 # Central filesystem paths & constants
│   ├── test_backend.py           # End-to-end unit test & validation suite
│   ├── core/                     # SimManager, DispatcherBridge, NetworkGeometry, Streamer
│   ├── routers/                  # Simulation, WebSocket, Network, Timetable, Analytics, Overrides, Disruption
│   ├── schemas/                  # Pydantic models for REST endpoints and WebSocket frames
│   └── README.md                 # Detailed backend documentation & API specifications
│
├── frontend/                     # Modern React 19 + Vite 8 Web Application
│   ├── src/
│   │   ├── pages/                # HomePage, SimulationPage, QueryPage, AboutPage
│   │   ├── components/           # Navigation, ErrorBoundary, Footer
│   │   ├── App.jsx               # Client-side router & global state
│   │   └── index.css             # High-contrast dark cyber-railway design system
│   ├── package.json              # React 19, Lucide-React, Canvas 2D telemetry dependencies
│   ├── vite.config.js            # Port 5173 dev server & WebSocket reverse-proxy
│   └── README.md                 # Detailed frontend architecture & development guide
│
├── README.md                     # Monorepo architecture & quick-start guide
├── project_history.md             # Unified monorepo milestones & integration log
├── requirements.txt              # Unified monorepo Python dependencies
└── .gitignore                    # Root-level ignore rules
```

---

## 2. Subsystems Overview

### A. Tracks Infrastructure Subsystem (`tracks/`)
- **Procedural Network Synthesis:** Generates 4 natural railway corridors, a high-speed bypass, dedicated freight spurs, a grade-separated bi-level interchange hub (`City_3`), mid-corridor universal crossovers, an alpine freight passing loop, and terminal reversing pocket tracks (*Kopfmachen*).
- **Physical Engineering Realism:** Models realistic curvature radii ($R \ge 3,500\text{ m}$ for 300 km/h high-speed rail), 1.77% gradients, bi-directional signaled tracks, 800m+ express platforms, and dedicated freight layover sidings.
- **Topological Integrity:** Evaluated cleanly with `netconvert` and SUMO's topology analyzer: **0 error nodes**, **0 broken nodes**, **0 angle conflicts**, **0 disconnected lanes** across 291 nodes, 776 edges, 116 train stops, and 1,614 explicit connections.
- *For detailed track documentation, see [tracks/README.md](tracks/README.md).*

### B. Fleet & Timetabling Subsystem (`trains/`)
- **Rolling Stock Fleet:** 7 physical consist models (`high_speed_emu_300`, `high_speed_emu_single`, `regional_emu_120`, `regional_dmu_120`, `heavy_freight_cargo`, `intermodal_container_freight`, `electric_trunk_freight`).
- **Master Timetable (*Taktfahrplan*):** 242 daily train runs operating on a clockface cadence with morning and evening peak commuter surges, full-day density scaling, calibrated station dwells, and a nocturnal freight wave.
- **Continuous Physical Rakes:** 31 physical trainsets tracked throughout their full daily lifecycle: dawn rollout from dedicated stabling sidings, revenue runs, station platform halts, terminal pocket reversals, midday yard layovers, and overnight resting.
- **Microscopic Safety & Adherence:** Tested under microscopic simulation with headless SUMO: **0 collisions**, **0 teleports**, **0 fatal errors**, and **100% schedule punctuality**.
- *For detailed trains documentation, see [trains/README.md](trains/README.md).*

### C. Autonomous Dispatcher AI Subsystem (`dispatcher/`)
- **Tri-Factor Traffic Management (TMS):** Combines dynamic rerouting (Alpine Passing Loop siding overtakes, High-Speed Bypass), real-time platform track assignment at multi-track city hubs, and departure dispatch holding with safety guardrails (siding reservations, duplicate stop suppression, and vehicle-level bypass adaptation).
- **Deep Reinforcement Learning (PPO, MAPPO, & Hybrids):** Compact continuous observation vectors with discrete single-agent, multi-train, communicative multi-agent, and hierarchical ensemble action spaces trained on multi-core CPU.
- **Production Guardrails (Frontiers 1 & 2):** Dispatch-by-Exception action gating cuts redundant actions by **48.8%**; Smart Interlocking platform calibration drops Sunday delay from 185s to **8.87s** and Tuesday/Friday delays to **10.8s**.
- **Decentralized Interlocking & Communication (Frontiers 3 & 4):** Centralized Training with Decentralized Execution (CTDE) partitioning the network into 7 autonomous control agents (6 station-masters + 1 corridor line controller). Comm-MAPPO adds inter-agent continuous message passing and vehicle-level platform locking, cutting action churn by **90.4%** (1,095 actions vs 11,449 actions).
- **Authoritative 8-Model 7-Day Cross-Comparison (56 Parallel 24-Hour Runs):** Benchmarked across all 1,446 weekly train runs in 56 parallel 24-hour simulations (11,568 simulated train journeys):
  - **Hierarchical Hybrid Lookahead Ensemble** and **Priority Greedy** achieve top-tier performance, matching the lowest weekly mean delay (**46.89s**) and highest punctuality (**96.7%** / 96.58% weighted) with 913 knock-ons.
  - **Centralized PPO** establishes the Pareto optimum for operator workload: matching heuristic delays (**50.07s**) and 96.3% punctuality with an **89.2% reduction in dispatcher actions** (only **649 weekly actions** vs 5,792–6,004 for heuristics).
  - **Multi-Train PPO** executes concurrent multi-consist dispatching (71.80s delay, 2,577 actions).
  - **Static Baseline** averages 236.20s delay with 10,878 knock-on events.
- **Automated Pipeline:** Full multi-wave curriculum retraining and 8-model cross-comparison verification automated via [`dispatcher/training/train_and_benchmark_all.py`](dispatcher/training/train_and_benchmark_all.py).
- *For detailed AI dispatcher documentation, see [dispatcher/README.md](dispatcher/README.md).*

### D. Production FastAPI & WebSocket Simulation Server (`backend/`)
- **Microscopic TraCI Bridge:** Thread-safe simulation manager orchestrating live Eclipse SUMO execution, step throttling, variable speed multipliers (1x–20x), custom reset timestamps (defaults to 06:00:00), and dual-mode runtime (`LIVE_SUMO` and zero-dependency `DEMO_REPLAY`).
- **Unified Dispatcher Bridge:** Polymorphic loader supporting all 8 AI, heuristic, and baseline dispatcher models with seamless in-flight switching and shorthand aliasing (`MODEL_ALIASES`).
- **2D Vector Track Geometry:** Microscopic XML parser extracting 2,413 track lanes with curvature coordinates, physical speed limits, switch throat connections, and functional categories (including spurs), pre-cached for sub-millisecond retrieval.
- **High-Frequency WebSocket & REST Telemetry:** Broadcasts 4 Hz real-time vehicle vectors (enriched with commercial train numbers, names, and routes), platform occupancies, recent dispatcher decisions, simulation KPIs, 24-hour cycle completion flags, and cumulative daily summaries at `/ws/telemetry` alongside `/api/sim/telemetry`.
- **Relational Timetable Engine:** High-performance read-only SQLite queries serving the 242-run timetable, 31-rake roster, station schedule boards with multi-level platform aggregation, and 7 rolling stock specifications.
- **Human-in-the-Loop & Perturbation Injection:** REST endpoints for injecting mechanical breakdowns, platform track closures, fleet surge dwell jitter, compound failures, and manual platform/hold overrides with structured event logging and auto-target resolution.
- *For detailed backend documentation, see [backend/README.md](backend/README.md).*

### E. Modern Web UI & Simulation Dashboard (`frontend/`)
- **Interactive Full-Stack Architecture:** Built with React 19 and Vite 8, featuring 4 fully functional pages:
  - **Overview Home (`/`):** Project blueprint, headline KPIs (2,413 lanes, 18 stations, 96.7% AI punctuality, 242 services), subsystem feature cards, quick launcher, direct benchmark deep-links, and academic contributor attributions.
  - **Real-Time Simulation (`/simulation`):** High-frequency 60 FPS Canvas 2D vector track renderer drawing UIC dual rails, ballast, cross-ties, switches, buffer stops, and signals. Features automatic bounds centering, live WebSocket telemetry bridge (`/ws/telemetry`), spatial UI workbench (resizable/collapsible sidebar and draggable Station Focus card), 24-Hour Cycle Completion Modal ("Replay 06:00" and "Advance to Next Day"), screen-space Canvas HUD alert banners, Google Maps-style infrastructure navigation with peer cycling, real-time train filtering, operational time jumps (Dawn, Peak, Midday, Rush), 8-model dispatcher AI selector, calendar day switcher, de-jittered optimistic speed slider (1x–20x), dropdown incident injection modal, executive AI decision stream with severity badges, and manual dispatch override panel.
  - **Railway Fleet & Timetable Explorer (`/query`):** Diagnostic railway intelligence console featuring 4 interactive views:
    1. *Services Directory:* 242 scheduled train runs with intermediate stops, advanced multi-field bidirectional sorting, and client-side pagination (15/25/50/all per page).
    2. *Station Schedule Board:* 18-station chronological movements with multi-level platform aggregation (`City_3`, `Town_8`), day filtering, sorting, and pagination.
    3. *Physical Rakes Roster:* 31 continuous physical rakes with stabling facilities, sorting, and pagination.
    4. *Rolling Stock Specifications:* Full engineering parameters for all 7 consist models.
  - **System Architecture & Metrics Blueprint (`/about`):** Detailed formalization of the Markov Decision Process (MDP state space $S_t \in \mathbb{R}^{28}$, action space $A_t \in \text{MultiDiscrete}([3, 7, 4])$, multi-objective reward $R_t$), **5-Tier Architecture Diagram** with Data & Infrastructure Persistence, deep-link hash anchor navigation (`#benchmark`, etc.), floating CSS tooltips, authoritative 56-run benchmark analysis, and an **Interactive Diurnal Timeline** with Fritsch-Carlson Monotone Cubic Spline curve interpolation, day/model pill selectors, morning/evening key metrics ribbon, and explanatory narrative cards.
- **Resilient UI Runtime:** Protected with React Error Boundaries, `ScrollToTop` route restoration with reduced motion detection, zero console errors, high-contrast cyber-railway dark design, and reactive telemetry reconnection.
- *For detailed frontend documentation, see [frontend/README.md](frontend/README.md).*

### F. Operational Foundations & Track Design Inspirations
While the railway network graph is entirely synthetic and fictional, its scheduling philosophy and physical track engineering are directly inspired by proven gold-standard international railway practices:
- **Periodic Integrated Timetable (*Taktfahrplan* Inspiration):** The master schedule operates on symmetrical, repeating clockface departure cadences (e.g., :00, :15, :30, :45) inspired by the Swiss *Taktfahrplan* network paradigm. This maximizes passenger interchange synchronization while creating predictable harmonic headway spacing.
- **Scissors Crossovers (Double X-Crossings):** Station throats and inter-corridor junctions incorporate prototypical double scissors crossovers (paired universal X-crossings), permitting simultaneous parallel routing and dynamic opposite-track diversions during track maintenance or platform congestion.
- **Dynamic Passing Loops & Overtake Sidings:** High-speed corridors feature grade-separated passing loops and alpine sidings where autonomous AI dispatchers hold slower heavy-freight consists to let express passenger trains overtake without speed degradation.
- **Diamond Crossings & Ladder Turnouts:** Multi-track junction throat networks model physical turnout geometry and speed restrictions (diverging routes restricted to 40–80 km/h; mainline through-tracks up to 300 km/h).

---

## 3. Quick-Start Guide

### Prerequisites
- **Python 3.10+**
- **Eclipse SUMO** (Simulation of Urban MObility, v1.18.0+) with `sumo`, `netconvert`, and `duarouter` available on system `PATH`.
- **Node.js (v18+) & npm** (for building and running the modern React 19 frontend).

### Installation
```bash
git clone https://github.com/venkatasriramt-spec/autonomous-rail-dispatcher.git
cd autonomous-rail-dispatcher
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

---

## 4. Operational Workflow & Execution Pipeline

The complete pipeline from track synthesis to simulation verification can be run sequentially:

### Step 1: Generate & Compile Physical Tracks
```bash
python3 tracks/scripts/generate_sumo_network.py
```
*Outputs compiled network XML files into `tracks/network_data/`.*

### Step 2: Render Track Schematics & Layout Plots (Optional)
```bash
python3 tracks/scripts/plot_network.py          # Full 2D railway network overview map
python3 tracks/scripts/plot_bilevel_hub.py      # City_3 bi-level grade-separated hub
python3 tracks/scripts/plot_station_layout.py   # 4-track express station layout
python3 tracks/scripts/plot_crossover.py        # Paired high-speed universal crossovers
python3 tracks/scripts/plot_passing_loop.py     # Alpine freight passing loop & grade
python3 tracks/scripts/plot_terminal_pockets.py # Terminus pocket tracks & buffer stops
```

### Step 3: Generate Timetable & Sync Database
```bash
python3 trains/scripts/generate_master_timetable.py
python3 trains/scripts/export_to_db.py
```
*Generates `trains/data/timetable.json`, `trains/data/rakes_roster.json`, and populates `trains/data/trains.db`.*

### Step 4: Compile Microscopic SUMO Routes
```bash
# Compile both continuous rakes and discrete services routes:
python3 trains/scripts/export_to_sumo.py --mode both
```
*Executes `duarouter` against `tracks/network_data/dense_network.net.xml` and generates verified route files in `trains/sumo_config/`.*

### Step 5: Validate Timetable Feasibility
```bash
python3 trains/scripts/validate_timetable.py --mode both
```
*Audits physical runtimes ($`T_{\text{planned}} \ge T_{\min}`$), route distance adherence ($`\Delta d \le 0.05\text{ km}`$), turnaround intervals, and stabling synchronization.*

### Step 6: Execute Headless Simulation & Safety Audit
```bash
# Verify 24-hour simulation for Monday in continuous rakes mode:
python3 trains/scripts/verify_simulation.py 86400 -m rakes -d mon

# Sweep across all 8 operating schedules (Mon-Sun + All):
python3 trains/scripts/verify_simulation.py 86400 -m rakes --all-days
```

### Step 7: Train & Evaluate Autonomous Dispatcher AI
```bash
# Automated end-to-end retraining & 6-model benchmark suite:
python3 dispatcher/training/train_and_benchmark_all.py

# Multi-Agent MARL (MAPPO) 3-stage curriculum training (16 parallel workers):
python3 dispatcher/training/train_mappo_curriculum.py

# Train single-agent PPO dispatcher:
python3 dispatcher/training/train.py --timesteps 5000 --start-time 21600 --horizon 3600

# Benchmark AI vs Static, FIFO, and Priority Baselines:
python3 dispatcher/evaluation/evaluate.py --model dispatcher/models/best_model.zip --disruption train_delay

# Frontier 3: Multi-Agent MARL vs Centralized PPO empirical benchmark:
python3 dispatcher/evaluation/audit_marl_comparison.py

# Run full 7-day 24-hour microscopic cross-comparison audit (7 days × 8 dispatchers = 56 parallel runs):
python3 dispatcher/evaluation/audit_cross_comparison_24h.py

# Run peak morning disruption stress-test benchmark (4 failure scenarios):
python3 dispatcher/evaluation/audit_stress_testing.py

# Render all publication-quality visual proof suites:
python3 dispatcher/evaluation/visualizer.py --json dispatcher/logs/evaluations/disruption_benchmarks/benchmark_results.json --output-dir dispatcher/logs/visual_proofs
python3 dispatcher/evaluation/visualize_stress_test.py --json dispatcher/logs/evaluations/stress_tests/stress_testing_benchmark.json --output-dir dispatcher/logs/visual_proofs
python3 dispatcher/evaluation/visualize_weekly_audit.py --json dispatcher/logs/evaluations/weekly_audits/cross_comparison_24h.json --output-dir dispatcher/logs/visual_proofs
python3 dispatcher/evaluation/visualize_marl.py
```

### Step 8: Interactive Inspection in SUMO GUI
```bash
sumo-gui -c trains/sumo_config/train_simulation.sumocfg
```

### Step 9: Launch Full-Stack Web Simulation Platform
```bash
# Terminal 1: Start FastAPI & WebSocket Server (Port 8000)
python3 backend/run_server.py --port 8000 --host 127.0.0.1

# Terminal 2: Start Modern React 19 Frontend (Port 5173)
cd frontend
npm install
npm run dev
```
*Open [http://127.0.0.1:5173](http://127.0.0.1:5173) in your browser to interact with the real-time simulation, timetable queries, and analytics.*

---

## 5. Subsystem Documentation Links

- **Track Network Architecture & Topology:** [tracks/README.md](tracks/README.md)
- **Track Evolution History:** [tracks/project_history.md](tracks/project_history.md)
- **Train Scheduling, Rolling Stock & SQL Database:** [trains/README.md](trains/README.md)
- **Timetable & Simulation Evolution History:** [trains/project_history.md](trains/project_history.md)
- **Autonomous Dispatcher AI & RL System:** [dispatcher/README.md](dispatcher/README.md)
- **Dispatcher Training Roadmap & Verification:** [dispatcher/MODEL_TRAINING_PLAN.md](dispatcher/MODEL_TRAINING_PLAN.md)
- **Dispatcher Logs & Evaluation Reference:** [dispatcher/logs/LOGS_MAP.md](dispatcher/logs/LOGS_MAP.md)
- **FastAPI Backend API & Streaming Architecture:** [backend/README.md](backend/README.md)
- **Modern Web UI & Simulation Dashboard:** [frontend/README.md](frontend/README.md)
- **Unified Monorepo Milestone Log:** [project_history.md](project_history.md)

---

## 6. Academic Attribution, Contributors & License

* **Project:** Autonomous Rail Dispatcher (Project 1, Vellore Institute of Technology - VIT)
* **Contributors:**
  * **Venkata Sriram Topalli** ([@venkatasriramt-spec](https://github.com/venkatasriramt-spec))
  * **Ayush M Singh** ([@AYUSHMSINGH2004](https://github.com/AYUSHMSINGH2004))
  * **Avanish Kushwaha** ([@avanish06](https://github.com/avanish06))
* **License:** [MIT License](LICENSE)

