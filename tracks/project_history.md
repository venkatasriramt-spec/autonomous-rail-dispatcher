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

#### Phase 11: Mid-Corridor High-Speed Universal Crossovers (*Überleitstellen*)
- **Motivation:** On long inter-city rail lines (such as the 27 km East–West high-speed corridor and the 24 km North–South regional spine), operating without mid-corridor crossovers created extreme operational vulnerability. Any track maintenance, stalled freight train, or signal anomaly forced trains into single-line working or complete service suspension across the entire 10–15 km section between stations. Furthermore, fast express trains ($300\text{ km/h}$) running behind slower local or freight services could not overtake mid-corridor.
- **Paired Universal Crossover Engineering (4-Switch Interlocking Layout):**
  - Designed and implemented sequential paired universal crossovers avoiding high-speed diamond frogs (modeled after French LGV *Points de Transition* / German ICE *Überleitstellen*):
    - **Total Footprint:** $380\text{ m}$ total interlocking zone ($150\text{ m}$ turnout lead + $80\text{ m}$ tangent buffer + $150\text{ m}$ turnout lead).
    - **Turnout Geometry & Curvature:** Natural rail cubic spline transitions with effective curve radius $R \approx 1,000\text{ m}$ and $0.0^\circ$ departure/arrival tangent discrepancy relative to the mainline tracks.
    - **Speed Limits:** High-speed mainline through tracks retain full $300\text{ km/h}$ ($83.33\text{ m/s}$) line speed; diagonal turnout tracks permit $160\text{ km/h}$ ($44.44\text{ m/s}$) on high-speed corridors and $80\text{ km/h}$ ($22.22\text{ m/s}$) on regional corridors.
  - Installed 8 universal crossovers (32 switch nodes) across the trunk railway corridors:
    - 4 on Corridor 1 (East–West Mainline): `c1_Town_1_City_2_xov` (~km 6.5), `c1_City_2_Town_2_xov` (~km 11.5), `c1_Town_2_City_3_EW_xov` (~km 16.5), `c1_City_3_EW_Town_3_xov` (~km 21.5).
    - 2 on Corridor 2 (North–South Spine): `c2_Town_4_Town_5_xov` (~km 5.5), `c2_Town_6_Town_7_xov` (~km 17.0).
    - 2 on Corridor 4 (Southern Coastal Arc): `c4_Town_10_Town_11_xov`, `c4_Depot_2_Town_12_xov`.
- **Bidirectional Block Signaling & Reverse Running:**
  - Implemented `generate_bidi_blocks` across all approach, mid-zone, and departure blocks with paired `<edge ... bidi="..." />` attributes.
  - Enabled dynamic wrong-way running (*Gleiswechselbetrieb* / *banalisation des voies*), permitting trains to divert around track maintenance or blockage and return to their designated track at the next crossover.
  - Integrated alternate departure routing in station throat interlockings to support bidirectional dispatching.
- **Topological & Compilation Verification:**
  - Compiled `network_data/dense_network.net.xml` with `netconvert`.
  - Evaluated `network_data/railway_topology.xml`: confirmed **0 broken nodes**, 0 driving angle conflicts, and 0 disconnected lanes across 186 nodes, 458 edges, 116 train stops, and 566 explicit connections.
  - All 32 crossover switch nodes validated cleanly with `in="3" out="3"`.
- **Visualization Suite:**
  - Updated `scripts/plot_network.py` with amber (`#f59e0b`) rendering and diamond markers for crossover installations, regenerating `scripts/current_network_preview.png`.
  - Implemented `scripts/plot_crossover.py` producing `scripts/crossover_layout.png`, showing a detailed CAD-level engineering schematic of the 380 m paired crossover layout with dimensions, switch points, track centers, and speed limits.

#### Phase 12: Graduated Block Signaling, Alpine Freight Passing Loop (*Überholgleis*), and Terminal Turn-Around Pocket Tracks (*Kopfmachen*)
- **Motivation:** Three realism defects remained on the physical track infrastructure:
  1. *Uniform Signal Block Density:* Mainline tracks previously used static ~1,000 m block sections regardless of proximity to station throats or open high-speed stretches, causing artificial capacity bottlenecks near station throats where braking/accelerating trains require tighter headway compression (~500 m), and sub-optimal high-speed braking buffers on open 300 km/h stretches.
  2. *Mountain Line Freight Bottleneck:* On Corridor 3 (`Town_8` to `Town_9`), trains climb a steep mountain gradient (+11.8‰ / 50 m elevation gain over 4.2 km). Without a mid-corridor passing siding, heavy 12,000 t freight trains crawling uphill at 40–60 km/h blocked all following regional passenger services across the entire mountain district.
  3. *Dead-End Terminal Reversal Deadlocks:* Major terminus stations (`City_4`, `City_6`) and logistics depots (`Depot_1`, `Depot_3`, `Depot_4`) lacked tail tracks and buffer stops. Arriving trains had no operational infrastructure to clear passenger platforms, reverse driving direction (*Kopfmachen*), or lay over without occupying revenue platforms or fouling mainline throats.

- **Feature A: Graduated Signal Block Density (Tapered Headway Signaling):**
  - Engineered a mathematical cosine taper function `compute_graduated_block_splits`:
    $$\ell(s) = \ell_{\min} + \frac{1 - \cos(\pi \cdot w(s))}{2} \cdot (\ell_{\max} - \ell_{\min})$$
    where $w(s) = \min\left(1.0, \frac{\min(s, L - s)}{D_{\text{taper}}}\right)$ with a $1,800\text{ m}$ transition zone.
  - Slices blocks smoothly from $550\text{ m}$ near station throats / crossover switches up to $1,400\text{ m}$ on open high-speed track ($300\text{ km/h}$), from $500\text{ m}$ up to $1,000\text{ m}$ on regional corridors ($120\text{ km/h}$), and $500\text{ m}$ to $800\text{ m}$ on freight lines ($80\text{ km/h}$).
  - Dynamically slices bidirectional track shapes at exact arc-length splits using `slice_points_by_distance`, preserving curvature and 3D elevations.

- **Feature B: Alpine Freight Passing Loop (*Überholgleis*) on Corridor 3:**
  - Designed and implemented a double-ended $1,200\text{ m}$ freight passing siding midway between `Town_8` and `Town_9` on Corridor 3 (`c3_Town_8_Town_9_loop`):
    - **Siding Envelope:** $150\text{ m}$ lead turnout (`lead_in`) + $900\text{ m}$ parallel tangent siding (`siding`) + $150\text{ m}$ lead turnout (`lead_out`).
    - **Lateral Offset:** Built at $+8.0\text{ m}$ parallel offset ($6.0\text{ m}$ clear spacing from Track 1).
    - **Capacity & Track Limits:** Rated for $12,000\text{ t}$ heavy bulk freight trains at $16.67\text{ m/s}$ ($60\text{ km/h}$). Straight through-track retains full line speed ($33.33\text{ m/s}$ / $120\text{ km/h}$).
    - **Interlocking:** Entry turnout `swA` and exit turnout `swB` equipped with `rail_signal` nodes and complete forward/backward switch connection matrices in `dense_network.con.xml`.

- **Feature C: Terminal Turn-Around Pocket Tracks & Buffer Stops (*Kopfmachen* Infrastructure):**
  - Constructed dedicated parallel tail tracks and dead-end buffer stops at end terminals:
    - **`City_4` (High-Speed Eastern Terminus):** 2 parallel tail tracks ($450\text{ m}$ length, speed $13.89\text{ m/s}$ / $50\text{ km/h}$, $25\text{ kV}$ electric, concrete slab) terminating at buffer stops `City_4_buf_1`, `City_4_buf_2`.
    - **`City_6` (Southern Regional Terminus):** 2 parallel tail tracks ($450\text{ m}$ length, speed $13.89\text{ m/s}$ / $50\text{ km/h}$, $15\text{ kV}$ electric, ballast) terminating at buffer stops `City_6_buf_1`, `City_6_buf_2`.
    - **`Depot_1`, `Depot_3`, `Depot_4` (Heavy Freight Logistics Termini):** 4 parallel storage pocket tracks each ($300\text{ m}$ length, speed $5.55\text{ m/s}$ / $20\text{ km/h}$, $12,000\text{ t}$ capacity, wood sleepers) with dead-end buffer stops `Depot_*_buf_1` through `_buf_4`.
  - **Buffer Stop Modeling:** Modeled using SUMO node attribute `type="dead_end"` and edge parameters `<param key="buffer_stop" value="true"/>` and `<param key="is_tail_track" value="true"/>`.
  - **Interlocking:** Outbound platform edges feed into all pocket tracks through throat interlocking Throat 2 scissors fan, and reversing departures connect directly back into platform departure edges.

- **Topological & Compilation Verification:**
  - Compiled cleanly with `netconvert`: **Exit code 0**.
  - Evaluated `network_data/railway_topology.xml`: **0 error nodes**, **0 broken nodes**, **0 angle conflicts**, **0 disconnected lanes** across 288 nodes, 696 edges, 116 train stops, and 903 explicit connections.
  - All 16 buffer stop dead-end nodes validated cleanly as `railNodeType in="1" out="1"`.
  - All 34 switches (32 crossover switches + 2 passing loop switches) validated with 0 geometric defects.

- **Visualization Suite:**
  - Updated `scripts/plot_network.py` with rose (`#f43f5e`) pocket tracks, lime (`#a3e635`) passing siding, square buffer stops, and comprehensive multi-class legend, regenerating `scripts/current_network_preview.png`.
  - Implemented `scripts/plot_passing_loop.py` producing `scripts/alpine_passing_loop.png`, showcasing the 2D plan view of the siding and the +11.8‰ mountain grade profile.
  - Implemented `scripts/plot_terminal_pockets.py` producing `scripts/terminal_pocket_tracks.png`, showcasing 4-panel multi-terminal layouts for `City_4`, `City_6`, `Depot_1`, and `Depot_3`.

---

### 12 October 2026 — Fleet Lifecycle Operations & Buffer Stop Reversals

#### Phase 13: Full Rolling Stock Lifecycle Track Infrastructure Overhaul
- **Motivation:** To support realistic fleet lifecycle operations from morning depot rollout to evening stabling—preventing train consist overhangs, vehicle access restrictions, and dead-end trapping—seven fundamental track engineering changes were implemented:
  1. *Depot Pocket & Siding Expansion:* Increased pocket track lengths at `Depot_1`, `Depot_3`, and `Depot_4` from $300\text{ m}$ to **$500\text{ m}$**, accommodating full $400\text{ m}$ High-Speed EMUs (`high_speed_emu_300`) and $420\text{ m}$ freight consists (`heavy_freight_cargo`) without switch foul or throat overhang.
  2. *Depot & Access Spur Electrification:* Updated the `freight` profile to `allow="rail rail_electric"` and `voltage="25000"`, enabling electric passenger EMUs (such as Corridor 1 rakes `HS-Rake-01` through `10`) to physically enter and stable at their designated home base (`Depot_4`) via `spur_City_3_EW_Depot_4`.
  3. *Buffer Stop Reversing Connections:* Injected explicit `<connection from="..._fw" to="..._bw"/>` elements across all 21 buffer stop nodes (`*_buf_*`). This transforms dead-end stubs into interlocked reversing points, preventing trains from getting permanently trapped in pocket tracks.
  4. *Western Terminus Turnaround (`City_1`):* Added 3 parallel electrified high-speed pocket tracks (`City_1_pocket_1_fw/bw` through `_3_fw/bw`, $L=450\text{ m}$) with buffer stops (`City_1_buf_1/2/3`) extending west of `City_1_Throat1`. Inbound Corridor 1 trains arriving on `City_1_plat_*_bw` can now pull into a pocket track, reverse, and return east on Corridor 1 via `City_1_plat_*_fw` without being forced onto Corridor 4.
  5. *Northern Terminus Turnaround (`City_5`):* Added 2 parallel regional pocket tracks (`City_5_pocket_1_fw/bw`, `City_5_pocket_2_fw/bw`, $L=450\text{ m}$) with buffer stops (`City_5_buf_1/2`) north of `City_5_Throat1`, enabling Corridor 2 and Bypass terminating trains to reverse without travelling 6 km down the freight spur into `Depot_3`.
  6. *Bi-Directional Throat Interlocking Routing (Same-Platform Turnarounds):* Wired scissors crossover connections at station throats linking platform backward edges to forward edges (`plat_bw -> plat_fw` at Throat 1; `plat_fw -> plat_bw` at Throat 2). Trains can now execute fast cab-swap reversals directly at station platforms (*Kopfmachen*).
  7. *Overnight Stabling Sidings:* Expanded yard tracks at `City_1` from 2 to 5 electrified stabling tracks ($L=800\text{ m}$) and at `City_4` from 2 to 4 stabling tracks, providing overnight stabling capacity for high-speed rakes directly at their commercial departure terminals.

- **Topological & Compilation Verification:**
  - Recompiled cleanly via `netconvert`: **Exit code 0**.
  - Evaluated `network_data/railway_topology.xml`: **0 error nodes**, **0 broken nodes**, **0 angle conflicts**, **0 disconnected lanes** across 294 nodes, 712 edges, 116 train stops, and 1,029 explicit connections.
  - All 21 buffer stop nodes validated cleanly as `railNodeType in="1" out="1"`.
  - Audited against `/home/venkatasriramt/Desktop/trains/scripts/export_to_sumo.py`: all 242 trips compiled with **100% verified routes** (242/242).

---

### 13 October 2026 — Interlocking Refinements & Dedicated Freight Layover Capacity

#### Phase 14: Terminal Yard Ladder Expansion, Pocket Clearance & Interlocking Disambiguation
- **Motivation:** Following an operational capacity audit against full-lifecycle fleet requirements (31 physical trainsets), severe bottlenecks, switch geometry penalties, and track clearance deficits were resolved:
  1. *Yard Ladder Capacity Expansion:*
     - `City_1`: Expanded stabling yard tracks from 5 to **16 dedicated electrified tracks** ($L=800\text{ m}$), eliminating the -11 track deficit and providing an individual physical home for all 16 assigned trainsets (5 HS, 6 REG-C1, 5 REG-C4).
     - `City_5`: Expanded stabling yard tracks from 2 to **6 dedicated electrified tracks** ($L=800\text{ m}$), providing full individual capacity for all 6 assigned regional rakes (`REG-C2-01` to `06`).
     - `City_3_EW` & `City_3_NS`: Expanded from 2 & 1 to **4 yard tracks each** ($L=900\text{ m}$), plus 2 high-speed pocket tracks at `City_3_EW` for on-site staging at the central bi-level interchange hub.
     - `City_4`: Expanded to **6 stabling tracks** ($L=800\text{ m}$).
     - `City_6`: Expanded to **4 stabling tracks** ($L=800\text{ m}$).
  2. *Pocket Track Clearance Extension (≥500 m Clear Standing Length):*
     - Accounted for junction cluster boundary clipping (~73m) at major station throats by increasing nominal pocket lengths to **550m–600m** (`City_1` 580m, `City_4` 550m, `City_5` 580m, `City_6` 550m, `City_3_EW` 580m, `Depot_1/3/4` 600m).
     - Verified netconvert lane lengths: every pocket track across the network maintains between **485.6m and 598.8m** clear lane standing length, ensuring 400m High-Speed EMUs (`high_speed_emu_300`) and 420m freights (`heavy_freight_cargo`) clear fouling points with 85m to 178m margin.
  3. *Throat Turnaround Disambiguation & Interlocking Refinement:*
     - Replaced all-to-all cross-platform permutations with deterministic pairwise same-track reversals (`for fw, bw in zip(plat_fw, plat_bw): connect bw -> fw`).
     - Strictly excluded express through-tracks (`*_thru_*`) from turnaround connections.
     - Scaled station switch lead lengths with track counts (`lead_extra`), easing turnout fan angles from $22^\circ$ down to $<10^\circ$ ($R > 300\text{ m}$).
  4. *Compilation & Geometry Verification:*
     - **Microscopic Overlaps:** 0 warnings (reduced from 9 to 0).
     - **Sharp Turnout Speed Reductions:** 1 warning across the entire network (reduced from 105 to 1, a 99% reduction).
     - **Topology Audit:** 0 error nodes, 0 broken nodes, 0 angle conflicts, 0 disconnected lanes across 296 nodes, 738 edges, 116 train stops.
     - **Downstream Routing:** Tested against `trains/scripts/export_to_sumo.py` with 100% verified route compilation across all continuous rakes.

#### Phase 15: Strategic Freight Layover Capacity Expansion at City Hubs (`City_1`, `City_2`, `City_5`)
- **Motivation:** In downstream operational simulations, heavy freight trains running across Corridor 1, Corridor 2, Corridor 3, and the High-Speed Diagonal Bypass required dedicated staging sidings at intermediate and terminus city junctions without blocking passenger platform tracks or passenger EMU overnight stabling berths:
  1. *Western Terminus Freight Capacity (`City_1`):* Expanded stabling yard tracks from 16 to **18 dedicated full-length ($800\text{ m}$) electrified tracks**, providing 2 dedicated freight layover sidings alongside the 16 passenger EMU stabling berths (5 HS, 6 REG-C1, 5 REG-C4).
  2. *Northern Terminus Freight Capacity (`City_5`):* Expanded stabling yard tracks from 6 to **8 dedicated full-length ($800\text{ m}$) tracks**, allocating 2 dedicated freight layover sidings alongside the 6 regional passenger rakes (`REG-C2-01` to `06`).
  3. *Alpine & Bypass Junction Staging (`City_2`):* Expanded stabling yard tracks from 2 to **4 dedicated full-length ($900\text{ m}$) tracks**, doubling siding capacity at this critical tri-directional nodal junction where Corridor 1 (East-West Trunk), Corridor 3 (Alpine Mountain Line), and the High-Speed Diagonal Bypass (`bypass_City_2_City_5`) converge.
- **Topological & Compilation Verification:**
  - Recompiled cleanly via `netconvert` with zero fatal errors: **Exit code 0**.
  - Evaluated `network_data/railway_topology.xml`: **0 error nodes**, **0 broken nodes**, **0 angle conflicts**, **0 disconnected lanes** across **291 nodes**, **776 plain edges**, **116 train stops**, and **1,614 explicit connections** in `dense_network.con.xml` (**3,932 compiled connections** in `dense_network.net.xml`).
  - All 23 buffer stop dead-end nodes validated cleanly as `railNodeType in="1" out="1"`.
  - All 34 switches (32 crossover switches + 2 passing loop switches) validated with 0 geometric defects.

---

### 14 October 2026 — Monorepo Architecture Integration

#### Phase 16: Unified Railway Monorepo Namespace Restructuring
- **Motivation:** To unite track infrastructure generation and train timetabling/simulation under a single repository while preserving 100% of historical Git commits, documentation, and metadata:
  1. *Subdirectory Namespace Isolation:* Relocated all track network files, compilation scripts, visualization tools, and documentation into a dedicated `tracks/` subdirectory.
  2. *Dependency Specification:* Added `requirements.txt` for `matplotlib` and `numpy` visualization tooling and cleaned legacy virtual environments.
  3. *Zero-Data-Loss History Preservation:* Prepared repository tree for non-conflicting Git merge with the `trains` repository via `--allow-unrelated-histories`.

#### Phase 17: Post-Merge Visualization Tooling & Script Robustness
- **Visualization Script Corrections:**
  - `scripts/plot_bilevel_hub.py`: Fixed station legend key lookups from non-existent `yard_5` tracks to `City_3_EW_yard_1_fw` and `City_3_NS_yard_1_fw`, resolving KeyError warnings during schematic generation.
  - *Dynamic Path Resolution:* Upgraded all rendering and generation scripts (`plot_*.py`, `generate_sumo_network.py`) with dynamic root/sibling/subfolder path detection, ensuring they execute reliably from any working directory.
  - *Environment Cleanup:* Removed broken legacy test virtual environment (`test_venv`).
