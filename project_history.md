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
