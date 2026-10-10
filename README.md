# SUMO Dense Railway Network Generator

This repository is dedicated solely to generating a dense, highly structured railway **track infrastructure** network using SUMO (Simulation of Urban MObility). It produces a fully routable track map with physical speed limits, bi-directional rails, bypassing junctions, and multi-platform stations.

This network provides the foundational physical infrastructure for future downstream experiments. **Trains, rolling stock, traffic schedules, and routing live in a separate external repository** — this directory strictly maintains physical tracks, junctions, platforms, and signaling.

## Project Structure

```
.
├── scripts/
│   ├── generate_sumo_network.py  # Procedural corridor railway network generator
│   └── plot_network.py           # Network topology visualization & rendering tool
├── network_data/
│   ├── dense_network.nod.xml     # Generated nodes (stations, throats & signals)
│   ├── dense_network.edg.xml     # Generated tracks (edges, lanes & physical speeds)
│   ├── dense_network.con.xml     # Station throat interlocking switch connections
│   ├── dense_network.add.xml     # Generated platform placements (trainStops)
│   ├── dense_network.net.xml     # The compiled, routable SUMO railway network
│   └── railway_topology.xml      # SUMO topology analyzer report (0 error nodes)
├── project_history.md            # Chronological log of how the network evolved
├── README.md
└── .gitignore
```

## How to Build the Network

If you make any changes to the network layout in the generator script, you can rebuild the network by running:

```bash
python3 scripts/generate_sumo_network.py
```

This will instantly output fresh XML files into the `network_data/` directory and compile the network with `netconvert`.

## Viewing the Network Visually

To inspect and interact with the physical tracks, junctions, and block signals in Netedit:

```bash
netedit -s network_data/dense_network.net.xml -a network_data/dense_network.add.xml
```

To render a 2D high-resolution map of the entire network:

```bash
python3 scripts/plot_network.py
```

## Repository Conventions

- This folder is strictly dedicated to **tracks, junctions, signals, and stations**. Trains and scheduling are maintained externally.
- The generated `.xml` network files are intentionally tracked by Git — they are the primary deliverable of this repository.
- Python caches and virtual environments are ignored via `.gitignore`.

---

## Downstream Usage Guide: Working with This Track Data

Anyone consuming this repository's track network for train simulation, timetable scheduling, or Reinforcement Learning (RL) dispatching should adhere to the following specifications and constraints:

### 1. Essential Deliverable Files
To run a simulation on this track infrastructure, your external configuration must reference:
- **Network Graph:** `network_data/dense_network.net.xml` (the compiled track topography, junctions, and block signals).
- **Platform Additionals:** `network_data/dense_network.add.xml` (all physical station platform `<trainStop>` definitions).

### 2. Required Rolling Stock Configuration (`<vType>`)
When defining train types in your downstream repository:
- **Vehicle Class (`vClass`):** Must be set to either `rail_electric` (for high-speed EMUs) or `rail` (for regional or freight locomotives). Do **not** use `passenger` or default vehicle classes; non-rail vehicles are prohibited from entering these tracks.
- **Train Length vs. Platform Fit:**
  - **High-Speed Cities (`City_1`–`City_6`):** Platforms are $800\text{--}900\text{ m}$ long. High-speed train length should be $\le 600\text{ m}$.
  - **Regional Towns (`Town_1`–`Town_12`):** Platforms are $400\text{ m}$ long. Regional train length must be $\le 300\text{ m}$.
  - **Storage Yards (`Depot_1`–`Depot_4`):** Yard siding length is $500\text{ m}$.
  - *Note:* Trains longer than the platform will overhang switch throats and foul interlocking junctions.

### 3. Track Permissions & Speed Regimes
The network enforces strict speed limits and vehicle class restrictions based on civil engineering profiles:
- **High-Speed Trunk (`c1_*`, `bypass_*`):** Up to $83.33\text{ m/s}$ ($300\text{ km/h}$), strictly `rail_electric`.
- **Regional Trunk (`c2_*`, `c3_*`, `c4_*`):** Up to $33.33\text{ m/s}$ ($120\text{ km/h}$), allows both `rail` and `rail_electric`.
- **Freight & Alpine Mountain Lines (`c3_Town_9_Depot_1`, spurs):** Up to $22.22\text{ m/s}$ ($80\text{ km/h}$).
- **Station Platform Tracks (`*_plat_*`):** Speed restricted to $13.89\text{ m/s}$ ($50\text{ km/h}$).
- **Depot Yards & Siding Tracks (`*_yard_*`):** Speed restricted to $5.55\text{ m/s}$ ($20\text{ km/h}$).

### 4. Directional Edge & Platform Naming Conventions
Tracks are fully bi-directional (double-track mainlines) with consistent naming:
- **Forward Running:** Mainline edges are suffixed with `_fw` (split into ~1 km block sections: `..._fw_b0`, `..._fw_b1`, etc.). Platform stops are named `<Station>_p<PlatformNumber>_fw` on lane `<Station>_plat_<PlatformNumber>_fw_0`.
- **Backward Running:** Mainline edges are suffixed with `_bw` (split into `..._bw_b0`, `..._bw_b1`, etc.). Platform stops are named `<Station>_p<PlatformNumber>_bw` on lane `<Station>_plat_<PlatformNumber>_bw_0`.
- **Storage / Maintenance Yards:** Non-platform tracks are designated `<Station>_yard_<N>_fw` / `<Station>_yard_<N>_bw` with parameter `<param key="is_yard" value="true"/>`.

### 5. Embedded Infrastructure Telemetry (`<param>` Tags)
For RL reward functions, energy modeling, or maintenance algorithms, all running edges expose metadata parameters:
- `voltage`: Overhead catenary voltage (`25000` V, `15000` V, or `none`).
- `capacity_tons`: Maximum permissible axle/train weight (`2500`, `5000`, or `12000` tons).
- `gauge`: Track gauge in millimeters (`1435` standard gauge).
- `material`: Track construction type (`concrete`, `ballast`, or `wood`).
- `wear_rate`: Empirical rail wear degradation coefficient per vehicle passage.

### 6. Minimal Downstream `.sumocfg` Example
In your external train project, hook into this track network like this:

```xml
<configuration>
    <input>
        <net-file value="path/to/network/network_data/dense_network.net.xml"/>
        <additional-files value="path/to/network/network_data/dense_network.add.xml"/>
        <route-files value="your_train_routes.rou.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <step-length value="1.0"/>
    </time>
    <processing>
        <collision.action value="warn"/>
        <time-to-teleport value="-1"/>
    </processing>
</configuration>
```