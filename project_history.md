# Project History

A chronological log of how this abstract SUMO railway network evolved, from initial concept to the current programmatic data pipeline.

---

### 8 October 2026 — Project Initialization & Pivot to SUMO

**Objective:** Create a clean, dense, programmatic railway network to act as a safe, abstract testing ground for Train Scheduling Reinforcement Learning (RL), abandoning the messy real-world OpenStreetMap (OSM) data from previous ARTEMIS projects.

#### Phase 1: The Move to Abstract Networks
- Identified that previous iterations (`ARTEMIS` and `ARTEMIS_Switzerland`) suffered from severe data quality issues when parsing real-world tracks and GTFS schedules. The noise in the data prevented the RL models from learning scheduling logic.
- Decided to completely restart with a **fake, abstract network** to ensure 100% control over edge cases, topology, and routing.
- Initially wrote a basic `NetworkX` script (`network_builder.py`) to map out a Hub-and-Spoke model with 7 stations in pure Python.

#### Phase 2: Pivoting to SUMO
- Based on external suggestions, we pivoted from a custom `NetworkX` simulator to **SUMO (Simulation of Urban MObility)**. 
- SUMO natively handles train kinematics (acceleration, braking), multiple platforms, track speed limits, block signaling, and provides the `TraCI` interface, which is the industry standard for Reinforcement Learning in transit.
- Decided to use a **Procedural Generation (Python)** approach instead of drawing tracks manually in Netedit, allowing us to instantly spin up massive, mathematically perfect rail networks.
- Installed `sumo`, `sumo-tools`, and `sumo-doc` on the virtual machine via `apt-get`.

#### Phase 3: The Dense Network Generator
- Created `scripts/generate_sumo_network.py`, an automated XML builder.
- Designed a structured, hierarchical 10-station topology:
  - **Capital Hub:** A massive central station acting as the primary routing bottleneck (4 platforms).
  - **Regional Cities:** North, East, and West Cities with 2-3 platforms each.
  - **Suburban Stops:** 5 smaller single-platform local stops dotted along the main lines.
  - **High-Speed Bypass:** A diagonal 160km/h route allowing trains to travel directly from the North to the East without congesting the Capital.
- Enforced realism by making every track **bi-directional** (separate forward and backward lanes) and automatically letting SUMO enforce physics limitations (e.g., dynamically reducing speed limits on sharp 90-degree junction turns).
- Automated the execution of `netconvert` within the python script to instantly compile the `.nod.xml`, `.edg.xml`, and `.add.xml` files into the final `dense_network.net.xml`.

#### Phase 4: Project Structuring & Version Control
- Cleaned up the repository, removing the old `NetworkX` scripts and temporary image files.
- Organized the repository into a production-ready structure:
  - `scripts/` for the Python generators.
  - `network_data/` for the compiled SUMO XML outputs.
- Created a `.gitignore` to explicitly ignore Python caches while ensuring the generated `.xml` network files *are* tracked by Git (since the goal of this repo is to produce those exact files).
- Created the main `README.md` to document execution instructions and `netedit` viewing commands.
- Initialized Git tracking and staged the initial files for commit.

#### Phase 5: Curves, Elevation, and Physics Profiles
- Rewrote the generator to use **cubic Bezier curves** (via custom `cubic_bezier` function) for smooth track routing instead of straight segments.
- Added a third axis (**elevation, z-coordinate**) to every node, enabling realistic terrain: mountains, valleys, overpasses, and grade changes.
- Embedded **physics profiles** directly into each track as edge parameters: speed limit, vehicle allow-list (rail, rail_electric), maximum tonnage, electrification voltage, track gauge, rail material, and wear rate — these become core state variables for future RL environments.
- Updated track profiles:
  - `high_speed`: 300 km/h, concrete slab, 25 kV, 2500 ton capacity
  - `regional`: 120 km/h, ballast/concrete, 15 kV, 5000 ton capacity
  - `freight`: 80 km/h, wood sleepers, no voltage, 12000 ton capacity
- These changes were committed as `950f466: feat: add curves, elevation, and physics profiles`.

#### Phase 6: Pivot to Fully Random Procedural Layouts
- Redesigned the generator from a deterministic 10-station layout to a **fully random but reproducible** network (via `random.seed(42)`).
- **Location types:** 6 cities (major hubs), 12 towns (regional stops), and 4 depots (freight/maintenance yards — no passenger platforms). Each has a random position (±15 km), elevation (0–400 m), and track orientation.
- **Connectivity:** Built a **minimum spanning tree (Kruskal's algorithm)** to guarantee full connectivity, then added extra random "loop" edges to create alternative routes and redundancy.
- **Complex yards:** Each location is a multi-track yard with platform tracks, yard/storage tracks, and dedicated "throat" junctions for smooth merging/diverging. Tracks connect throat-to-throat across the network using cubic Bezier curves that follow terrain.
- **Output:** The same three XML sources (`nod.xml`, `edg.xml`, `add.xml`) are generated and compiled via `netconvert` into `dense_network.net.xml`, preserving bi-directional tracks, curved shapes, elevation, and physics profiles.
- This phase represents the current state of the working tree — run the generator to produce a fresh, valid SUMO network ready for RL experiments.

### 10 October 2026 — Realism Overhaul & Simulation Verification

**Objective:** Eliminate critical topological and geometric flaws (disconnected entry lanes, 14% grade spikes, switch angle conflicts) and establish an operational train simulation pipeline.

#### Phase 7: Geometry, Interlocking, and Physics Fixes
- **Tangent Vector Alignment & Lead Tracks:** Introduced straight tangent approach leads at station throats and wide turning radii for reverse curves, ensuring zero angular discrepancy at switch nodes.
- **Arc-Length Parameterized Elevation:** Replaced parametric $t$ elevation interpolation with cumulative 2D horizontal arc-length ($s$) parameterization and flat throat approaches, guaranteeing maximum track gradient $\le 1.5\%\text{--}2.0\%$ everywhere and eliminating all 14% micro-segment slope anomalies.
- **Explicit Throat Interlocking (`dense_network.con.xml`):** Generated formal interlocking connection tables mapping inbound mainline tracks cleanly to station platforms, and platform exits to outbound mainlines, eliminating hairpin turns across throats and reducing topology error nodes to zero (`broken="0"`).
- **Curvature-Aware Speed Profiling:** Embedded dynamic civil engineering speed limit calculations ($v = \sqrt{R_{\min} \cdot a_{\text{lat}}}$) into block generation.
- **Simulation Pipeline (`duarouter` & `.sumocfg`):** Added automated generation of 70 multi-class train routes (high-speed express, regional commuter, and freight) compiled via `duarouter`, along with `dense_network.sumocfg` for immediate testing in `sumo` or `sumo-gui`.

#### Phase 8: Isolation of Track Infrastructure & Natural Railway Corridor Overhaul
- **Separation of Concerns (Tracks Only):** Completely removed all train-related simulation files (`.rou.xml`, `.trips.xml`, `.sumocfg`) and routing toolchains (`duarouter`). Trains and schedules are now isolated in a dedicated downstream repository, keeping this directory 100% focused on physical track infrastructure (rails, switches, block signals, platforms).
- **Elimination of Extreme Twists and Jagged Turns:** Replaced arbitrary lateral offsets and perpendicular station orientations with continuous, physics-grounded railway corridors:
  - *Corridor 1 (East-West Trunk):* Sweeps across 27 km with minimum curvature radii $R \ge 4,000\text{ m}$ to $17,000\text{ m}$, matching real-world 300 km/h high-speed rail standards.
  - *Corridor 2 (North-South Spine):* Straight, monotonic inter-city alignment passing cleanly through City_3 grand crossing hub ($R \ge 25,000\text{ m}$).
  - *Corridor 3 (Northwest Alpine Line):* Branches naturally northwest from City_2 with smooth turnout geometry ($R = 1,974\text{ m}$) into mountain terrain.
  - *Corridor 4 (Southern Coastal Arc):* Parabolic curve eliminating all $180^\circ$ hairpin loops and unnatural troughs ($R \ge 1,076\text{ m}$ to $3,400\text{ m}$).
  - *Diagonal Bypass & Spurs:* Direct high-speed bypass ($R = 11,304\text{ m}$) and smooth logistics depot spurs ($R \ge 960\text{ m}$).
- **Topology Verification:** `railway_topology.xml` confirmed with **0 broken nodes**, 0 driving angle conflicts, and 0 disconnected lanes.

#### Phase 9: Grade-Separated Bi-Level Hub & Flyover Interchange Ramp at City_3
- **Motivation:** In Phase 8, `City_3` served as the central junction where Corridor 1 (East-West High-Speed Trunk) and Corridor 2 (North-South Regional Spine) intersected at a shared vertical grade ($Z = 20\text{ m}$). While functional, this flat junction risked severe throughput bottlenecks, scheduling gridlock, and conflicting crossing movements between high-speed and regional trains.
- **Bi-Level Station Architecture:**
  - Split `City_3` into two vertically segregated, grade-separated levels:
    - **Lower Level (`City_3_EW`):** Sub-grade concourse at elevation $Z = 12.0\text{ m}$ servicing the East-West High-Speed Trunk with 4 passenger platforms ($900\text{ m}$ length) and 2 storage/staging yards.
    - **Upper Level (`City_3_NS`):** Elevated viaduct structure at elevation $Z = 26.0\text{ m}$ servicing the North-South Regional Spine with 4 passenger platforms ($900\text{ m}$ length) and 1 storage/staging yard.
    - **Vertical Headroom:** A full $14.0\text{ m}$ of vertical clearance between the crossing alignments, completely eliminating at-grade diamond crossings and collision hazards.
- **Grade-Separated Flyover Interchange Ramp (`transfer_City_3_EW_NS`):**
  - Designed and constructed a dedicated $789\text{ m}$ connecting track in the Northwest quadrant linking the western throat of `City_3_EW` (`City_3_EW_Throat1`) to the northern throat of `City_3_NS` (`City_3_NS_Throat1`).
  - Climbs from $Z = 12.0\text{ m}$ to $Z = 26.0\text{ m}$ with a gentle $1.77\%$ civil engineering gradient, comfortably below the maximum permissible railway grade ($\le 2.0\%$).
  - Smooth curvature with minimum turning radius $R_{\min} \ge 1,167\text{ m}$, enabling safe, high-capacity bidirectional transfers between Corridor 1 and Corridor 2 without interfering with through traffic.
- **Dedicated Visualization Tooling:**
  - Implemented `scripts/plot_bilevel_hub.py` to generate a high-resolution dual-panel diagnostic visualizer:
    1. A spatial plan view mapping platform alignments, yard tracks, throat junctions, and the curved flyover ramp in the junction bounding box ($X \in [4200, 6200]$, $Y \in [500, 2500]$).
    2. A cross-sectional elevation profile along the intersecting corridors demonstrating the $14\text{ m}$ vertical clearance and the $1.77\%$ ramp gradient.
  - Automatically exports to `scripts/city3_bilevel_hub.png`.
- **Topological & Compilation Verification:**
  - Recompiled the entire network via `netconvert` with zero fatal errors or broken nodes.
  - Validated `network_data/railway_topology.xml`: confirmed clean topology across all 164 nodes, 374 edges, 126 train stops, and 458 explicit connections.

#### Phase 10: Express Through-Tracks at Intermediate Towns (4-Track Stations)
- **Motivation:** In previous network iterations, all intermediate town stations (`Town_1` through `Town_12`) only had platform stopping tracks speed-restricted to $13.89\text{ m/s}$ ($50\text{ km/h}$). Non-stopping high-speed express trains on Corridor 1 ($300\text{ km/h}$) and fast regional trains on Corridors 2 and 4 ($120\text{ km/h}$) were artificially forced to brake down to $50\text{ km/h}$ through every intermediate town, causing massive travel time penalties and unrealistic energy consumption.
- **4-Track Station Architecture (Shinkansen / LGV Standard):**
  - Upgraded 10 intermediate towns (`Town_1`, `Town_2`, `Town_3` on Corridor 1; `Town_4`, `Town_5`, `Town_6`, `Town_7` on Corridor 2; `Town_10`, `Town_11`, `Town_12` on Corridor 4) to the standard 4-track (+1 yard) layout:
    - **2 Center Express Through-Tracks (`{stn}_thru_1`, `{stn}_thru_2`):** Positioned along the mainline centerline at offsets $\pm 2.5\text{ m}$. They operate at full corridor line speed ($300\text{ km/h}$ / $83.33\text{ m/s}$ on Corridor 1; $120\text{ km/h}$ / $33.33\text{ m/s}$ on Corridors 2 and 4). They feature zero `<trainStop>` platforms, allowing express services to run through intermediate towns without decelerating.
    - **2 Flanking Platform Loops (`{stn}_plat_1`, `{stn}_plat_2`):** Positioned at lateral offsets $\pm 8.5\text{ m}$, speed-restricted to $13.89\text{ m/s}$ ($50\text{ km/h}$), each equipped with a $340\text{ m}$ `<trainStop>` platform for stopping passenger trains.
    - **1 Outer Service Siding (`{stn}_yard_1`):** At lateral offset $+14.5\text{ m}$, speed $5.55\text{ m/s}$ ($20\text{ km/h}$) for maintenance and freight layovers.
- **Turnout Lead Distance & Switch Geometry:**
  - Extended station throat switch lead distance `t_dist` to $220.0\text{ m}$ for stations with express through-tracks.
  - Yields an effective switch lead radius of $R \approx 8,000\text{ m}$, ensuring through-trains maintain mainline speed with zero angular discrepancy or speed reduction warnings.
- **Platform Inset Geometry:**
  - Positioned platform `<trainStop>` elements strictly between `t_lead + 30.0` and `t_lead + length - 30.0` on the platform loops, ensuring that stopped trains rest entirely on parallel tangent tracks and never foul turnout switch blades.
- **Variable Shadowing Bug Resolution:**
  - Resolved a coordinate shadowing bug in `build_angled_yard` where `for y in range(yards):` accidentally clobbered the station's Y-coordinate parameter (`y = -3200` was overwritten to `0`), restoring geographic alignment across southern arc stations (`Town_10`).
- **Topological & Compilation Verification:**
  - Compiled `network_data/dense_network.net.xml` with `netconvert`.
  - Evaluated `network_data/railway_topology.xml`: confirmed **0 broken nodes**, 0 driving angle conflicts, and 0 disconnected lanes across 158 nodes, 398 edges, 116 train stops, and 518 explicit connections.
- **Visualization Suite:**
  - Updated `scripts/plot_network.py` with distinct neon cyan (`#00f0ff`) rendering for express through-tracks, regenerating `scripts/current_network_preview.png`.
  - Implemented `scripts/plot_station_layout.py` which renders `scripts/station_4track_layout.png`, providing a clean engineering schematic of through-tracks, platform loops, island platforms, and switch throat tapers.


