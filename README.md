# Unified Railway Simulation & Infrastructure Monorepo

Welcome to the **Unified Railway Simulation & Infrastructure Monorepo**. This repository unites microscopic track engineering, procedural network generation, commercial timetabling, rolling stock logistics, and headless SUMO simulation auditing into a single coherent codebase with full version-controlled history.

---

## 1. System Architecture

The monorepo is organized into two isolated yet tightly integrated subsystems:

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

---

## 3. Quick-Start Guide

### Prerequisites
- **Python 3.10+**
- **Eclipse SUMO** (Simulation of Urban MObility, v1.18.0+) with `sumo`, `netconvert`, and `duarouter` available on system `PATH`.

### Installation
```bash
git clone <repo-url> railway_system
cd railway_system
pip install -r requirements.txt
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
*Audits physical runtimes ($T_{\text{planned}} \ge T_{\min}$), route distance adherence ($\le 0.05\text{ km}$), turnaround intervals, and stabling synchronization.*

### Step 6: Execute Headless Simulation & Safety Audit
```bash
# Verify 24-hour simulation for Monday in continuous rakes mode:
python3 trains/scripts/verify_simulation.py 86400 -m rakes -d mon

# Sweep across all 8 operating schedules (Mon-Sun + All):
python3 trains/scripts/verify_simulation.py 86400 -m rakes --all-days
```

### Step 7: Interactive Inspection in SUMO GUI
```bash
sumo-gui -c trains/sumo_config/train_simulation.sumocfg
```

---

## 5. Subsystem Documentation Links

- **Track Network Architecture & Topology:** [tracks/README.md](tracks/README.md)
- **Track Evolution History:** [tracks/project_history.md](tracks/project_history.md)
- **Train Scheduling, Rolling Stock & SQL Database:** [trains/README.md](trains/README.md)
- **Timetable & Simulation Evolution History:** [trains/project_history.md](trains/project_history.md)
- **Unified Monorepo Milestone Log:** [project_history.md](project_history.md)
