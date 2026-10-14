# SUMO Dense Railway Network Generator

This repository is dedicated solely to generating a dense, highly structured railway **track infrastructure** network using SUMO (Simulation of Urban MObility). It produces a fully routable track map with physical speed limits, bi-directional rails, bypassing junctions, and multi-platform stations.

This network provides the foundational physical infrastructure for future downstream experiments. **Trains, rolling stock, traffic schedules, and routing live in a separate external repository** — this directory strictly maintains physical tracks, junctions, platforms, and signaling.

## Project Structure

```
.
├── scripts/
│   ├── generate_sumo_network.py  # Procedural corridor railway network generator
│   ├── plot_network.py           # Network topology visualization & rendering tool
│   ├── plot_bilevel_hub.py       # City_3 bi-level station hub plan & elevation renderer
│   ├── plot_station_layout.py    # 4-track express station layout diagram renderer
│   ├── plot_crossover.py         # High-speed universal crossover schematic renderer
│   ├── plot_passing_loop.py      # Alpine freight passing loop schematic & grade renderer
│   └── plot_terminal_pockets.py  # Terminal turnaround pocket tracks & buffer stop renderer
├── network_data/
│   ├── dense_network.nod.xml     # Generated nodes (stations, throats, signals & crossovers)
│   ├── dense_network.edg.xml     # Generated tracks (edges, lanes & physical speeds)
│   ├── dense_network.con.xml     # Station throat and crossover interlocking connections
│   ├── dense_network.add.xml     # Generated platform placements (trainStops)
│   ├── dense_network.net.xml     # The compiled, routable SUMO railway network
│   └── railway_topology.xml      # SUMO topology analyzer report (0 error nodes)
├── project_history.md            # Chronological log of how the network evolved
├── README.md                     # Comprehensive architecture and downstream usage guide
└── .gitignore                    # Git ignore specifications
```

## How to Build the Network

If you make any changes to the network layout in the generator script, you can rebuild the network by running:

```bash
python3 scripts/generate_sumo_network.py
```

This will instantly output fresh XML files into the `network_data/` directory and compile the network with `netconvert`.

## Viewing the Network Visually

### Interactive Inspection with Netedit
To inspect and interact with the physical tracks, junctions, and block signals in SUMO's graphical network editor:

```bash
netedit -s network_data/dense_network.net.xml -a network_data/dense_network.add.xml
```

### Full Network Topology Visualization
To render a high-resolution 2D overview map of the complete railway network topology, station locations, and corridor paths:

```bash
python3 scripts/plot_network.py
```
*(Saves diagram to `scripts/current_network_preview.png`)*

### City_3 Bi-Level Hub Plan & Elevation Profile
To render the dedicated plan view and cross-sectional elevation profile of the grade-separated **City_3 Bi-Level Hub**:

```bash
python3 scripts/plot_bilevel_hub.py
```
*(Saves diagram to `scripts/city3_bilevel_hub.png`)*

### 4-Track Express Station Layout
To render the detailed track schematic and geometric layout of a standard 4-track intermediate town station with express through-tracks and platform loops:

```bash
python3 scripts/plot_station_layout.py
```
*(Saves diagram to `scripts/station_4track_layout.png`)*

### High-Speed Paired Universal Crossover Schematic
To render the detailed track schematic, dimensions, and switch geometry of a mid-corridor high-speed universal crossover:

```bash
python3 scripts/plot_crossover.py
```
*(Saves diagram to `scripts/crossover_layout.png`)*

### Alpine Freight Passing Loop (*Überholgleis*) Schematic & Grade Profile
To render the detailed plan layout, switch geometry, and mountain elevation profile of the double-ended freight passing loop on Corridor 3:

```bash
python3 scripts/plot_passing_loop.py
```
*(Saves diagram to `scripts/alpine_passing_loop.png`)*

### Terminal Turn-Around Pocket Tracks & Buffer Stops Layout
To render the reversing scissors, pocket tail tracks, and dead-end buffer stops at end terminals:

```bash
python3 scripts/plot_terminal_pockets.py
```
*(Saves diagram to `scripts/terminal_pocket_tracks.png`)*

## Network Architecture & Key Corridors

The physical network consists of four major operational railway corridors, a high-speed bypass, dedicated freight spurs, a signature grade-separated interchange hub, mid-corridor universal crossovers, an alpine freight passing loop, and terminal reversing pocket tracks:

### 1. Corridor 1: East–West High-Speed Trunk
- **Route:** `City_1` $\leftrightarrow$ `Town_1` $\leftrightarrow$ `City_2` $\leftrightarrow$ `Town_2` $\leftrightarrow$ `City_3_EW` $\leftrightarrow$ `Town_3` $\leftrightarrow$ `City_4`
- **Characteristics:** Spans 27 km of double-track electrified mainline with wide horizontal curve radii ($R \ge 4,000\text{ m}$ to $17,000\text{ m}$), engineered for continuous $300\text{ km/h}$ ($83.33\text{ m/s}$) high-speed express services on concrete slab track.

### 2. Corridor 2: North–South Regional Spine
- **Route:** `City_5` $\leftrightarrow$ `Town_4` $\leftrightarrow$ `Town_5` $\leftrightarrow$ `City_3_NS` $\leftrightarrow$ `Town_6` $\leftrightarrow$ `Town_7` $\leftrightarrow$ `City_6`
- **Characteristics:** Monotonic north-south inter-city mainline with gentle curvature ($R \ge 25,000\text{ m}$), permitting speeds up to $120\text{ km/h}$ ($33.33\text{ m/s}$). It traverses `City_3` via an elevated viaduct level.

### 3. Corridor 3: Northwest Alpine Mountain Line
- **Route:** `City_2` $\leftrightarrow$ `Town_8` $\leftrightarrow$ `Town_9` $\leftrightarrow$ `Depot_1`
- **Characteristics:** Branches naturally northwest from `City_2` with smooth turnout geometry ($R = 1,974\text{ m}$) into mountain terrain, accommodating regional commuter and heavy freight trains up to $80\text{--}120\text{ km/h}$. Features a continuous mountain climb from elevation $Z = 38\text{ m}$ at `City_2` up to $Z = 165\text{ m}$ at `Depot_1` (+11.8‰ grade), equipped with an **Alpine Freight Passing Loop (*Überholgleis*)** between `Town_8` and `Town_9`.

### 4. Corridor 4: Southern Coastal Arc
- **Route:** `City_1` $\leftrightarrow$ `Town_10` $\leftrightarrow$ `Town_11` $\leftrightarrow$ `Depot_2` $\leftrightarrow$ `Town_12` $\leftrightarrow$ `City_6`
- **Characteristics:** Sweeping parabolic arc along the southern perimeter ($R \ge 1,076\text{ m}$ to $3,400\text{ m}$) providing freight routing and regional bypass capabilities.

### 5. High-Speed Diagonal Bypass & Logistics Spurs
- **High-Speed Bypass (`bypass_City_2_City_5`):** A direct 160–300 km/h chord ($R = 11,304\text{ m}$) allowing express trains to transit directly between `City_2` and `City_5` without traversing the central hub.
- **Logistics Spurs:** Dedicated spur tracks connecting `City_5` to `Depot_3` and `City_3_EW` to `Depot_4`.

### 6. Grade-Separated Bi-Level Hub (`City_3`)
At the grand crossing of Corridor 1 (East–West High-Speed Trunk) and Corridor 2 (North–South Spine), the network features a **Grade-Separated Bi-Level Station Hub**:
- **Lower Level (`City_3_EW`):** Ground / sub-grade concourse at elevation $Z = 12.0\text{ m}$ (4 passenger platforms + 4 storage/staging yards, plus 2 high-speed turn-around pocket tracks with dead-end buffer stops).
- **Upper Level (`City_3_NS`):** Elevated viaduct structure at elevation $Z = 26.0\text{ m}$ (4 passenger platforms + 4 storage/staging yards).
- **Vertical Clearance:** $14.0\text{ m}$ of clear vertical headroom between tracks, completely eliminating flat at-grade crossings and train deadlock conflicts.
- **Flyover Interchange Ramp (`transfer_City_3_EW_NS`):** A $789\text{ m}$ connecting track in the Northwest quadrant climbing at a gentle $1.77\%$ gradient ($R_{\text{min}} \ge 1,167\text{ m}$) enabling seamless bidirectional transfers between corridors.

### 7. Station Hierarchy & Capacities
- **Cities (`City_1` through `City_6`):** Major hub terminals with 4–6 passenger platforms ($800\text{--}900\text{ m}$ length) and 4–18 yard storage/layover sidings:
  - **`City_1`:** 5 platforms, 18 stabling & freight layover yards ($800\text{ m}$), 3 parallel turnaround pocket tracks.
  - **`City_2`:** 6 platforms, 4 stabling & freight layover yards ($900\text{ m}$).
  - **`City_3_EW`:** 4 platforms, 4 stabling yards ($900\text{ m}$), 2 parallel turnaround pocket tracks.
  - **`City_3_NS`:** 4 platforms, 4 stabling yards ($900\text{ m}$).
  - **`City_4`:** 5 platforms, 6 stabling yards ($800\text{ m}$), 2 parallel turnaround pocket tracks.
  - **`City_5`:** 5 platforms, 8 stabling & freight layover yards ($800\text{ m}$), 2 parallel turnaround pocket tracks.
  - **`City_6`:** 5 platforms, 4 stabling yards ($800\text{ m}$), 2 parallel turnaround pocket tracks.
- **Trunk Intermediate Towns (4-Track Layout):** 10 intermediate towns (`Town_1`, `Town_2`, `Town_3` on Corridor 1; `Town_4`, `Town_5`, `Town_6`, `Town_7` on Corridor 2; `Town_10`, `Town_11`, `Town_12` on Corridor 4) follow the real-world high-speed rail standard (e.g. Japanese Shinkansen, French LGV):
  - **2 Express Through-Tracks (`{stn}_thru_1`, `{stn}_thru_2`):** Running down the center alignment at full corridor line speed ($300\text{ km/h}$ / $83.33\text{ m/s}$ on Corridor 1; $120\text{ km/h}$ / $33.33\text{ m/s}$ on Corridors 2 and 4) with zero platform stops, allowing express services to bypass without deceleration.
  - **2 Flanking Platform Loops (`{stn}_plat_1`, `{stn}_plat_2`):** Diverging smoothly at station switch throats via long lead turnouts ($R \approx 8,000\text{ m}$) into $400\text{ m}$ passenger stopping loops speed-restricted to $50\text{ km/h}$ ($13.89\text{ m/s}$).
  - **1 Outer Yard Siding (`{stn}_yard_1`):** Siding track for maintenance and freight layovers ($20\text{ km/h}$).
- **Secondary Towns (`Town_8`, `Town_9`):** Alpine branch line intermediate stops with 2 platform loops ($400\text{ m}$) and 1 yard track.
- **Depots (`Depot_1` through `Depot_4`):** Dedicated logistics, freight, and rolling stock maintenance yards with 4 siding/pocket tracks ($500\text{ m}$ length) and no passenger platforms (`Depot_1`, `Depot_3`, `Depot_4` feature dead-end buffer stops; `Depot_2` is an inline through depot on Corridor 4).

### 8. Mid-Corridor High-Speed Universal Crossovers (*Überleitstellen*)
Along long inter-station corridor segments, the network incorporates 8 **Paired Universal Crossovers** spaced every 5–8 km (reflecting French TGV *Points de Transition* / German ICE *Überleitstellen* practice):
- **Locations (8 Interlockings, 32 Switch Nodes):**
  - **Corridor 1 (East–West Mainline):** 4 installations (`Town_1`–`City_2`, `City_2`–`Town_2`, `Town_2`–`City_3_EW`, `City_3_EW`–`Town_3`).
  - **Corridor 2 (North–South Spine):** 2 installations (`Town_4`–`Town_5`, `Town_6`–`Town_7`).
  - **Corridor 4 (Southern Coastal Arc):** 2 installations (`Town_10`–`Town_11`, `Depot_2`–`Town_12`).
- **Paired Sequential Switch Topology (4-Switch Layout):**
  - Avoids flat diamond crossing diamonds which are restricted on high-speed rail.
  - Consists of two sequential diagonal crossovers separated by an intermediate tangent buffer:
    - **Turnout 1 (150 m lead):** Diverges from Track 1 at Switch `1A` and merges onto Track 2 at Switch `2B` ($R \approx 1,000\text{ m}$, speed $160\text{ km/h}$ / $44.44\text{ m/s}$).
    - **Tangent Buffer (80 m):** Parallel tangent gap stabilizing train suspension before the next switch.
    - **Turnout 2 (150 m lead):** Diverges from Track 2 at Switch `2C` and merges onto Track 1 at Switch `1D` ($R \approx 1,000\text{ m}$, speed $160\text{ km/h}$ / $44.44\text{ m/s}$).
    - **Total Footprint:** $380\text{ m}$ total interlocking length ($150\text{ m} + 80\text{ m} + 150\text{ m}$).
  - Mainline through tracks (`T1_mid`, `T2_mid`) maintain full line speed ($300\text{ km/h}$ / $83.33\text{ m/s}$) with $0.0^\circ$ angular discrepancy.
- **Operational Capabilities for Downstream RL / Dispatching:**
  - **Wrong-Way Running (*Gleiswechselbetrieb*):** Trains can divert to the opposite track during maintenance or track blockages and return to their normal track at the next crossover without traveling all the way to a station.
  - **Dynamic In-Flight Overtakes:** Fast express trains ($300\text{ km/h}$) can cross over to run parallel to and overtake slower regional or freight trains on the adjacent track mid-corridor.
  - **Emergency Single-Line Working:** Fully signaled in both directions with bidirectional block pairs throughout all corridor approach and departure segments.

### 9. Alpine Freight Passing Loop (*Überholgleis*) on Corridor 3
Located midway along the steep mountain ascent between `Town_8` (El. $80\text{ m}$) and `Town_9` (El. $130\text{ m}$) on Corridor 3 (`c3_Town_8_Town_9`):
- **Purpose:** On real-world mountain railways (e.g. Gotthard, Brenner, Semmering), heavy freight trains climb slowly at $40\text{--}60\text{ km/h}$. Without a mid-corridor passing loop, a single freight train would throttle all following regional passenger EMUs ($120\text{ km/h}$) across the entire 4.2 km climb.
- **Geometry & Capacity:**
  - **Length:** $1,200\text{ m}$ total siding envelope ($150\text{ m}$ entry turnout + $900\text{ m}$ tangent staging siding + $150\text{ m}$ exit turnout).
  - **Capacity:** Rated for $12,000\text{ tons}$ heavy bulk freight trains.
  - **Lateral Offset:** Built at a $+8.0\text{ m}$ parallel offset (giving $6.0\text{ m}$ clear center-to-center track spacing from Track 1).
  - **Speed Limits:** Siding and turnouts permit $16.67\text{ m/s}$ ($60\text{ km/h}$), while the straight-through mainline Track 1 retains full $120\text{ km/h}$ ($33.33\text{ m/s}$).
  - **Double-Ended Switches (`swA`, `swB`):** Full entry and exit switch interlockings with rail signals (`rail_signal`) allow freight trains to seamlessly diverge, stand while being overtaken, and merge back onto the mainline with zero stopping penalty for the overtaking passenger train.

### 10. Terminal Turn-Around Pocket Tracks & Buffer Stops (*Kopfmachen*)
At major terminus stations and industrial depot boundaries (`City_1`, `City_3_EW`, `City_4`, `City_5`, `City_6`, `Depot_1`, `Depot_3`, `Depot_4`), the network incorporates dedicated parallel **Turn-Around Pocket Tracks** equipped with physical **Dead-End Buffer Stops** and **Interlocked Reversing Connections**:
- **Terminus Locations & Allocations:**
  - **`City_1` (Western High-Speed / Coastal Terminus):** 3 parallel tail tracks ($580\text{ m}$ nominal / $485\text{--}578\text{ m}$ clear standing length, speed $50\text{ km/h}$ / $13.89\text{ m/s}$, electrified $25\text{ kV}$, concrete slab) terminating at buffer stops `City_1_buf_1` through `_buf_3`, with 18 full-length ($800\text{ m}$) stabling yards providing dedicated overnight tracks for all 16 assigned passenger rakes (5 HS, 6 REG-C1, 5 REG-C4) plus 2 dedicated freight layover sidings.
  - **`City_2` (Northwest Alpine & Bypass Gateway):** 4 full-length ($900\text{ m}$) dedicated layover sidings at this tri-directional junction (Corridor 1, Corridor 3, and the Bypass) providing freight staging and intermediate regional layover capacity.
  - **`City_4` (High-Speed Eastern Terminus):** 2 parallel tail tracks ($550\text{ m}$ nominal / $548\text{ m}$ clear standing length, speed $50\text{ km/h}$ / $13.89\text{ m/s}$, electrified $25\text{ kV}$, concrete slab) terminating at buffer stops `City_4_buf_1`, `City_4_buf_2`, with 6 stabling yard tracks.
  - **`City_5` (Northern Regional / Bypass Terminus):** 2 parallel tail tracks ($580\text{ m}$ nominal / $485\text{ m}$ clear standing length, speed $50\text{ km/h}$ / $13.89\text{ m/s}$, electrified $15\text{ kV}$, ballast) terminating at buffer stops `City_5_buf_1`, `City_5_buf_2`, with 8 stabling yard tracks for the 6 assigned regional rakes (`REG-C2-01` to `06`) plus 2 dedicated freight layover sidings.
  - **`City_3_EW` (Central Bi-Level Hub):** 2 parallel high-speed tail tracks ($580\text{ m}$ nominal / $485\text{ m}$ clear standing length, electrified $25\text{ kV}$) terminating at buffer stops `City_3_EW_buf_1`, `City_3_EW_buf_2`, with 4 stabling yards at `City_3_EW` and 4 stabling yards at `City_3_NS`.
  - **`City_6` (Southern Regional Terminus):** 2 parallel tail tracks ($550\text{ m}$ nominal / $548\text{ m}$ clear standing length, speed $50\text{ km/h}$ / $13.89\text{ m/s}$, electrified $15\text{ kV}$, ballast) terminating at buffer stops `City_6_buf_1`, `City_6_buf_2`, with 4 stabling yard tracks.
  - **`Depot_1`, `Depot_3`, `Depot_4` (Electrified Logistics & Rolling Stock Depots):** 4 parallel storage pocket tracks each ($600\text{ m}$ nominal / $550\text{--}598\text{ m}$ clear standing length, speed $20\text{ km/h}$ / $5.55\text{ m/s}$, electrified $25\text{ kV}$, $12,000\text{ t}$ capacity) with dead-end buffer stops `Depot_*_buf_1` through `_buf_4`. Fully accommodates 400 m High-Speed EMUs and 420 m freight trains with zero throat switch overhang.
- **Engineering & Interlocking:**
  - **Explicit Buffer Stop Reversals:** Every buffer stop node features an explicit connection linking the forward approach edge (`_pocket_k_fw`) to the returning departure edge (`_pocket_k_bw`), transforming buffer stops into interlocked reversal points so trains can route in and out without deadlocking.
  - **Pairwise Same-Platform Interlocking:** Station throats feature deterministic pairwise turnaround connections (`plat_k_bw -> plat_k_fw` at Throat 1; `plat_k_fw -> plat_k_bw` at Throat 2) restricted strictly to matching track pairs, eliminating turnaround ambiguities and sharp cross-track switch penalties while enabling rapid same-platform cab turnarounds (*Kopfmachen*). Through tracks (`thru_1`, `thru_2`) are strictly forbidden from reversing.
  - **Buffer Stop Metadata:** Modeled with SUMO node attribute `type="dead_end"` and edge parameters `<param key="buffer_stop" value="true"/>` and `<param key="is_tail_track" value="true"/>`.
  - **Operational Utility:** In passenger operations, arriving trains pull forward into pocket tracks to clear station platform tracks for the next arriving service, reverse driving direction (*Kopfmachen*), and re-enter a platform track when ready for outbound departure. In freight depots, they serve as dedicated runaround pockets and dead-end shunting spurs.

### 11. Graduated Signal Block Density (Tapered Headway Signaling)
Real-world railway signaling does not use arbitrary constant block lengths. On open track, trains need long braking distances ($1,200\text{--}1,500\text{ m}$ at $300\text{ km/h}$), while near stations and crossover interlockings, shorter block sections ($500\text{--}600\text{ m}$) are required to compress train headway and maximize switch throughput.
- **Mathematical Cosine Taper:**
  $$\ell(s) = \ell_{\min} + \frac{1 - \cos(\pi \cdot w(s))}{2} \cdot (\ell_{\max} - \ell_{\min})$$
  where $w(s) = \min\left(1.0, \frac{\min(s, L - s)}{D_{\text{taper}}}\right)$ with a $1,800\text{ m}$ transition zone.
- **Speed-Specific Block Parameters:**
  - **High-Speed ($300\text{ km/h}$):** Transitions smoothly from $550\text{ m}$ at station and crossover throats to $1,400\text{ m}$ on open high-speed stretches.
  - **Regional ($120\text{ km/h}$):** Transitions smoothly from $500\text{ m}$ at throats to $1,000\text{ m}$ mid-corridor.
  - **Freight / Mountain ($80\text{ km/h}$):** Transitions smoothly from $500\text{ m}$ to $800\text{ m}$.
- **Benefits for Downstream Scheduling & RL:**
  - Maximizes headway throughput where deceleration and merging occur.
  - Prevents unrealistic phantom signal stops on open high-speed track.
  - Matches modern ETCS Level 2 / TVM430 high-speed block layouts.

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
  - **City Stabling & Layover Sidings (`City_1`–`City_6`):** Siding lengths are $800\text{--}900\text{ m}$.
  - **Regional Towns (`Town_1`–`Town_12`):** Platforms are $400\text{ m}$ long. Regional train length must be $\le 300\text{ m}$.
  - **Storage Yards (`Depot_1`–`Depot_4`):** Yard siding length is $500\text{ m}$.
  - *Note:* Trains longer than the platform will overhang switch throats and foul interlocking junctions.

### 3. Track Permissions & Speed Regimes
The network enforces strict speed limits and vehicle class restrictions based on civil engineering profiles:
- **High-Speed Trunk (`c1_*`, `bypass_*`):** Up to $83.33\text{ m/s}$ ($300\text{ km/h}$), strictly `rail_electric`.
- **Regional Trunk (`c2_*`, `c3_*`, `c4_*`):** Up to $33.33\text{ m/s}$ ($120\text{ km/h}$), allows both `rail` and `rail_electric`.
- **Express Through-Tracks (`*_thru_*`):** Operates at full corridor mainline speed ($83.33\text{ m/s}$ on Corridor 1; $33.33\text{ m/s}$ on Corridors 2/4), with no passenger stops.
- **High-Speed Crossover Turnouts (`*_xov1_*`, `*_xov2_*`):** Diverging speed $44.44\text{ m/s}$ ($160\text{ km/h}$) on Corridor 1; $22.22\text{ m/s}$ ($80\text{ km/h}$) on regional corridors. Mainline through tracks maintain full line speed.
- **Freight & Alpine Mountain Lines (`c3_Town_9_Depot_1`, spurs):** Up to $22.22\text{ m/s}$ ($80\text{ km/h}$).
- **Station Platform Loops (`*_plat_*`):** Speed restricted to $13.89\text{ m/s}$ ($50\text{ km/h}$).
- **Depot Yards & Siding Tracks (`*_yard_*`):** Speed restricted to $5.55\text{ m/s}$ ($20\text{ km/h}$).

### 4. Directional Edge & Platform Naming Conventions
Tracks are fully bi-directional (double-track mainlines) with consistent naming:
- **Forward Running:** Mainline edges are suffixed with `_fw` (split into ~1 km block sections: `..._fw_b0`, `..._fw_b1`, etc.). Platform stops are named `<Station>_p<PlatformNumber>_fw` on lane `<Station>_plat_<PlatformNumber>_fw_0`.
- **Backward Running:** Mainline edges are suffixed with `_bw` (split into `..._bw_b0`, `..._bw_b1`, etc.). Platform stops are named `<Station>_p<PlatformNumber>_bw` on lane `<Station>_plat_<PlatformNumber>_bw_0`.
- **Express Through-Tracks:** Non-stopping bypass tracks are designated `<Station>_thru_<N>_fw` / `<Station>_thru_<N>_bw` with metadata `<param key="is_through" value="true"/>`. Non-stopping express trains must be routed over these edges to prevent speed drops.
- **Universal Crossover Tracks:** Turnout edges are designated `<Corridor>_xov_xov1_fw` / `<Corridor>_xov_xov1_bw` (Turnout 1) and `<Corridor>_xov_xov2_fw` / `<Corridor>_xov_xov2_bw` (Turnout 2) with metadata `<param key="is_crossover" value="true"/>`. Mainline through tracks within the crossover zone are `<Corridor>_xov_T1_mid_fw` and `<Corridor>_xov_T2_mid_fw`.
- **Alpine Freight Passing Loop (*Überholgleis*):** On Corridor 3, the siding edges are designated `c3_Town_8_Town_9_loop_siding_fw` and `..._siding_bw` (speed $16.67\text{ m/s}$ / $60\text{ km/h}$) with metadata `<param key="is_passing_loop" value="true"/>`, accessed via lead turnouts `_lead_in_fw` and `_lead_out_fw`. Mainline through tracks are `_T1_mid_fw` / `_T1_mid_bw` ($33.33\text{ m/s}$).
- **Terminal Turn-Around Pocket Tracks & Buffer Stops:** Reversal tail tracks at `City_1`, `City_3_EW`, `City_4`, `City_5`, `City_6`, and `Depot_1`, `Depot_3`, `Depot_4` are designated `<Station>_pocket_<N>_fw` (inbound) and `<Station>_pocket_<N>_bw` (outbound) with metadata `<param key="buffer_stop" value="true"/>` and `<param key="is_tail_track" value="true"/>`. Trains terminate at buffer stop nodes `<Station>_buf_<N>` (`type="dead_end"`) before reversing direction.
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