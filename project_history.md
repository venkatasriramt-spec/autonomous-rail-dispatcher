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
