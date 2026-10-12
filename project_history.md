# Project History

A chronological log of how the train scheduling, rolling stock rotation, and timetable compilation system evolved, from initial concept to the current programmatic data pipeline.

---

### 11 October 2026 — Project Initialization, Rolling Stock Modeling, and Master Scheduling Pipeline

**Objective:** Build an autonomous, realistic train scheduling and fleet management system in `/home/venkatasriramt/Desktop/trains` that operates directly on top of the physical track infrastructure from `/home/venkatasriramt/Desktop/tracks`.

#### Phase 1: Separation of Concerns & Repository Architecture
- Established `/home/venkatasriramt/Desktop/trains` as the dedicated downstream repository for rolling stock, timetables, train rotation, and simulation execution.
- Linked directly against the track graph (`dense_network.net.xml`) and platform additions (`dense_network.add.xml`) in `/home/venkatasriramt/Desktop/tracks/network_data/`.
- Configured local Git author credentials for `Venkata Sriram Topalli <venkatasriramt@gmail.com>` (GitHub: `venkatasriramt-spec`) to ensure all repository commits are correctly attributed.

#### Phase 2: Rolling Stock Fleet Specification (`data/rolling_stock_types.json`)
- Designed 6 realistic physical rolling stock models with engineering, electrical, and geometric constraints:
  1. **`high_speed_emu_300`**: 16-car, 400.0 m length, 300 km/h (83.33 m/s), 25 kV AC electric, 880 t gross weight (1,050 passenger capacity). Designed for Corridor 1 East–West Trunk express services; strictly fits 800m+ City platforms.
  2. **`high_speed_emu_single`**: 8-car, 200.0 m length, 300 km/h, 25 kV AC electric, 440 t gross weight (520 passenger capacity). Designed for the High-Speed Diagonal Bypass (`City_2` $\leftrightarrow$ `City_5`).
  3. **`regional_emu_120`**: 6-car, 160.0 m length, 120 km/h (33.33 m/s), dual-voltage 15 kV / 25 kV electric, 240 t gross weight (380 passenger capacity). Designed for stopping services on Corridors 1, 2, 4, and the Bi-Level Hub Flyover Transfer. Fits 400m town platform loops.
  4. **`regional_dmu_120`**: 4-car, 120.0 m length, 120 km/h, diesel-electric hybrid, 180 t gross weight (240 passenger capacity). Designed for the Northwest Alpine Mountain Line (`City_2` $\leftrightarrow$ `Town_9`).
  5. **`heavy_freight_cargo`**: 28-wagon, 420.0 m length, 80 km/h (22.22 m/s), heavy diesel cargo locomotive, 3,800 t gross weight. Modeled for bulk mineral runs and utilizing the Alpine Passing Loop siding.
  6. **`intermodal_container_freight`**: 24-wagon, 380.0 m length, 80 km/h, heavy diesel cargo locomotive, 2,600 t gross weight. Modeled for container logistics between `City_5` and dead-end pocket tracks at `Depot_3`.

#### Phase 3: Master Timetable Generation (`data/timetable.json`)
- Created `scripts/generate_master_timetable.py` to procedurally generate a realistic 72-train daily and multi-day timetable.
- Structured across 7 key operational corridors:
  - **Corridor 1 High-Speed Express (16 runs)**: 300 km/h mainline runs between `City_1` and `City_4`, bypassing intermediate towns (`Town_1`, `Town_2`, `Town_3`) at full speed via central through-tracks (`_thru_1`, `_thru_2`).
  - **Corridor 1 Regional Stoppers (12 runs)**: Stopping at all intermediate town platform loops (`_plat_1`, `_plat_2`) with 60s dwell times.
  - **Corridor 2 North–South Spine (16 runs)**: Connecting `City_5` and `City_6` across the elevated viaduct level at `City_3_NS`.
  - **Corridor 3 Northwest Alpine Mountain Line (6 runs)**: Operating on specific days (e.g., Train #12763 on Monday, Thursday, Sunday) between `City_2` and `Town_9`.
  - **Corridor 4 Southern Coastal Arc (8 runs)**: Connecting `City_1` and `City_6` via `Town_10`, `Town_11`, and `Town_12`.
  - **High-Speed Diagonal Bypass (4 runs)**: Direct transit along `bypass_City_2_City_5` avoiding the central hub.
  - **Trans-Hub Bi-Level Flyover Transfer (4 runs)**: Linking Eastern and Southern termini (`City_4` $\leftrightarrow$ `City_6`) via the 789 m, 1.77% gradient flyover ramp (`transfer_City_3_EW_NS`).
  - **Heavy Freight & Logistics Services (6 runs)**: Bulk ore trains utilizing the Alpine Passing Loop (`Town_8_Passing_Loop`) with a 12-minute scheduled hold for passenger overtakes, and logistics feeders to `Depot_3` and `Depot_2`.
- Implemented **Post-Journey Dispositions**:
  - `turnaround`: Arriving trains clear platform tracks, pull into terminal pocket tracks (`City_4_pocket_1/2`, `City_6_pocket_1/2`), reverse cabs (*Kopfmachen*), and form subsequent scheduled return services.
  - `depot_stabling`: Off-peak transfers to maintenance depots.
  - `yard_layover`: Staging in outer yard sidings (`_yard_1/2`).

#### Phase 4: Physical Rake Roster & Duty Cycles (`data/rakes_roster.json`)
- Mapped 17 physical trainsets (rakes) to daily duty cycles, tracking continuous equipment utilization across outbound and return services.

#### Phase 5: Relational Database Integration (`scripts/export_to_db.py` & `data/trains.db`)
- Created `scripts/export_to_db.py` to synchronize JSON timetable and rolling stock data into a normalized SQLite relational database (`trains.db`).
- Built 7 normalized tables: `rolling_stock_types`, `physical_rakes`, `train_services`, `service_operating_days`, `service_stops`, `service_bypasses`, and `service_post_disposition`.
- Created SQL indexes on corridors, departure seconds, stop stations, and days of week for sub-millisecond query performance.

#### Phase 6: Microscopic Route Compilation (`scripts/export_to_sumo.py`)
- Created `scripts/export_to_sumo.py` to convert timetable schedules into SUMO XML trips (`sumo_config/trains.trips.xml`).
- Handled both passenger `<trainStop>` platforms and freight siding lane stops (`c3_Town_8_Town_9_loop_siding_fw_0`).
- Resolved directional track alignments at station throats:
  - Corrected departure and arrival edge assignments (`_fw` vs `_bw`) for reversing routes and branch lines.
- Executed `duarouter` against `dense_network.net.xml` and `dense_network.add.xml`.
- **Validation**: Successfully compiled **72 out of 72 vehicles (100% routing success)** into `sumo_config/trains.rou.xml` with zero disconnected lane errors.

#### Phase 7: Simulation Verification & GUI Tooling (`scripts/verify_simulation.py`)
- Created `scripts/verify_simulation.py` to execute headless SUMO simulation runs.
- Ran a 30,000-second verification simulation in SUMO:
  - **Fatal Errors**: `0`
  - **Collisions**: `0`
  - **Emergency Teleports**: `0`
  - **Average Depart Delay**: `0.14s`
  - **Average Waiting Time**: `0.00s`
- Created `sumo_config/viewsettings.xml` with an optimized dark railway theme and high-contrast train coloring for interactive inspection in `sumo-gui`.
- Authored comprehensive `README.md` documenting the complete data model, commands, and SQL queries.

---

### 11 October 2026 (Evening) — Comprehensive Timetable Realism Overhaul: Flaws 1 to 5

**Objective:** Systematically address and resolve the 5 structural flaws identified in the initial scheduling system: implementing clockface symmetry (*Taktfahrplan*), peak commuter surges, calibrated dwells and turnarounds, scaling density to 152 services across 28 rakes, and introducing a nocturnal freight wave with electric trunk freight.

#### Phase 8: Systematic Resolution of Timetable & Fleet Flaws

1. **Flaw 1: Coordinated Clockface Timetable (*Taktfahrplan*) & Synchronized Hub Pulses**
   - Eliminated arbitrary fractional departure offsets in favor of memorable repeating cadences:
     - Corridor 1 High-Speed Express: `:00` Eastbound (`City_1` $\to$ `City_4`), `:30` Westbound (`City_4` $\to$ `City_1`).
     - Corridor 1 Regional Local: `:15` Eastbound, `:45` Westbound.
     - Corridor 2 North–South Spine: `:10` Southbound (`City_5` $\to$ `City_6`), `:40` Northbound (`City_6` $\to$ `City_5`).
     - Corridor 3 Alpine Line: `:10` Uphill, `:40` Downhill (interconnected with Corridor 1 pulses at `City_2`).
     - Corridor 4 Southern Coastal Arc: `:20` Eastbound, `:50` Westbound.
     - High-Speed Diagonal Bypass: `:25` Northeast, `:55` Southwest.
     - Trans-Hub Flyover Link: `:05` East-to-South, `:35` South-to-East.
   - Synchronized turnaround return trips to clockface departure minutes rather than raw float arrival offsets.

2. **Flaw 2: Morning & Evening Peak Headway Surges**
   - Injected compressed 30-minute peak relief headway surges during 07:00–09:00 (AM peak) and 16:00–18:30 (PM peak).
   - High-Speed Express surges to half-hourly frequency (07:00, 07:30, 08:00, 08:30; 16:00, 16:30, 17:00, 17:30, 18:00).
   - Regional Local surges to half-hourly frequency (07:15, 07:45, 08:15; 16:15, 17:15, 17:45).
   - North–South Spine surges to half-hourly frequency (07:10, 07:40, 08:10; 16:10, 17:10, 18:10).
   - Coastal Arc commuter relief runs added at 08:20 and 17:20.

3. **Flaw 3: Calibrated Dwell Times & Consist-Scaled Turnarounds**
   - Replaced flat dwell times with an operational passenger exchange hierarchy via `get_calibrated_dwell()`:
     - Intermediate Towns: 45s (rapid commuter exchange).
     - Alpine Mountain halts: 75s (tourist luggage and scenic boarding).
     - Major City hubs (`City_1`, `City_2`, `City_4`, `City_5`, `City_6`): 90s (Regional) / 120s (HighSpeed).
     - `City_3` Bi-Level Interchange: 150s (Regional Spine) / 180s (Flyover Link).
     - Alpine Passing Loop siding: 720s (12-minute freight hold for overtakes).
   - Consist-scaled turnaround constraints defined via `MIN_TURNAROUND_BY_CONSIST`:
     - 400m High-Speed EMU: minimum 15.0 min.
     - 200m High-Speed Single: minimum 12.0 min.
     - 160m Regional EMU: minimum 10.0 min.
     - Heavy Freight Cargo: minimum 30.0 min.
     - Electric Trunk Freight: minimum 25.0 min.
   - Updated database schema in `scripts/export_to_db.py` to add `min_turnaround_required_min` and `turnaround_mode` (`rapid_dual_crew`, `standard_cab_swap`, `extended_layover`, `shunting_and_inspection`, `container_loading_and_inspection`, `depot_inspection`).

4. **Flaw 4: Full-Day Density Scaling (152 Scheduled Runs across 28 Physical Rakes)**
   - Expanded timetable from 72 to **152 scheduled train runs**, bridging early morning (05:00–07:00), midday regular clockface cadences (10:00–15:00), and late evening (19:00–23:30).
   - Expanded active rolling stock roster from 17 to **28 physical rakes**:
     - 6 High-Speed trainsets (`HS-Rake-01` to `06`)
     - 5 Corridor 1 Regional EMUs (`REG-C1-01` to `05`)
     - 5 Corridor 2 Regional Spine EMUs (`REG-C2-01` to `05`)
     - 2 Alpine Hybrid DMUs (`ALP-Rake-01`, `02`)
     - 4 Coastal Arc EMUs (`REG-C4-01` to `04`)
     - 2 Trans-Hub Interchange EMUs (`REG-XFER-01`, `02`)
     - 4 Freight locomotives & sets (`FRT-Rake-01` to `04`)
   - Distributed rolling stock across all 4 maintenance facilities:
     - `Depot_1` (Mountain): 3 rakes
     - `Depot_2` (Coastal): 5 rakes
     - `Depot_3` (Northern): 6 rakes
     - `Depot_4` (Central & Trunk): 14 rakes

5. **Flaw 5: Dedicated Nocturnal Freight Corridor Wave (21:30–05:25)**
   - Introduced a 7th rolling stock model: **`electric_trunk_freight`** (Vectron Class 193 25kV electric locomotive + 24 container flatcars, 2,400 t, 100 km/h, `sumo_vclass="rail_electric"`).
   - Injected 8 nocturnal freight services utilizing mainline capacity while daytime passenger services sleep:
     - Nocturnal Mountain Bulk Ore: #68103 (22:30 dep City_2 $\to$ Depot_1) & #68104 (02:00 dep Depot_1 $\to$ City_2).
     - Nocturnal Northern Container Feeder: #68203 (23:00 dep City_5 $\to$ Depot_3) & #68204 (02:30 dep Depot_3 $\to$ City_5).
     - Nocturnal Coastal Heavy Cargo: #68303 (21:30 dep Depot_2 $\to$ City_6) & #68304 (01:00 dep City_6 $\to$ Depot_2).
     - Cross-Corridor East–West Electric Fast Freight: #68401 (23:15 dep City_1 $\to$ City_4 non-stop) & #68402 (01:30 dep City_4 $\to$ City_1 non-stop).

#### Phase 9: Full 24-Hour Simulation & Verification Results
- **Duarouter Microscopic Route Compilation**:
  - Input: 152 trips in `sumo_config/trains.trips.xml`.
  - Compiled: **152 out of 152 vehicles (100% routing success)** in `sumo_config/trains.rou.xml`.
  - Errors / Disconnected Edges: `0`.
- **Full 24-Hour SUMO Microscopic Simulation (`86,400` steps)**:
  - Duration: `86,400 seconds (24 hours simulated)`.
  - Performance: `9.27s CPU execution time (9,320x real-time speed)`.
  - Average Fleet Speed: `19.82 m/s (~71.4 km/h inclusive of all intermediate dwells and layovers)`.
  - Collisions: `0`.
  - Teleports: `0`.
  - Deadlocks: `0`.
  - Fatal Errors: `0`.
- **Relational Database (`data/trains.db`) Status**:
  - `rolling_stock_types`: 7 records
  - `physical_rakes`: 28 records
  - `train_services`: 152 records
  - `service_stops`: 752 records
  - `service_post_disposition`: 152 records with calibrated dwell and turnaround mode attribution.

---

### 11 October 2026 (Night) — Timetable Quality Audit & Bug Fixes: Consist Turnarounds & Freight Days

**Objective:** Address code review findings regarding turnaround feasibility constraints under fixed clockface return pulses and calendar day alignment for nocturnal freight returns.

#### Phase 10: Turnaround Feasibility Enforcement & Freight Day Corrections
1. **Consist Minimum Turnaround Validation & Pulse Offsets (`scripts/generate_master_timetable.py`)**:
   - Identified that fixed return pulses caused turnaround dwell times to fall short of consist physical minimums:
     - Corridor 1 HighSpeed Express: 12.8 min dwell fell short of 15.0 min minimum for `high_speed_emu_300`. Adjusted Westbound pulses from `:30` to `:35` (and peak from `:00` to `:05`), raising dwell to 17.8 min–18.8 min.
     - Corridor 1 Regional Stopper: 4.4 min dwell fell short of 10.0 min minimum for `regional_emu_120`. Adjusted Westbound pulses from `:45` to `:55` (and peak from `:15` to `:25`), raising dwell to 14.4 min.
     - Corridor 2 Regional Spine: 7.5 min dwell fell short of 10.0 min minimum for `regional_emu_120`. Adjusted Northbound pulses from `:40` to `:45` (and peak from `:10` to `:15`), raising dwell to 12.5 min.
     - Corridor 4 Coastal Arc: 9.1 min dwell fell short of 10.0 min minimum for `regional_emu_120`. Adjusted Westbound pulses from `:50` to `:55`, raising dwell to 14.1 min.
   - Decoupled `turnaround_mode` labeling (`rapid_dual_crew` vs `standard_cab_swap`) from minimum dwell legality.
   - Enforced defensive runtime assertions across all corridors: raised `ValueError` if `turnaround_dwell_min < MIN_TURNAROUND_BY_CONSIST[r_type]`.
2. **Calendar Day Correction for Nocturnal Freight Returns**:
   - Fixed service days for nocturnal freight return runs departing after midnight (01:00–02:30) following late-night outbound runs:
     - #68104 (Alpine Mineral Return, dep 02:00): corrected from Mon/Wed/Fri to `["Tue", "Thu", "Sat"]` (following #68103 departing 22:30 Mon/Wed/Fri).
     - #68204 (Northern Container Return, dep 02:30): corrected from Tue/Thu/Sat to `["Wed", "Fri", "Sun"]` (following #68203 departing 23:00 Tue/Thu/Sat).
     - #68304 (Coastal Bulk Cargo Return, dep 01:00): corrected from Mon/Wed/Fri to `["Tue", "Thu", "Sat"]` (following #68303 departing 21:30 Mon/Wed/Fri).
3. **Pipeline Regeneration & Simulation Validation**:
   - Re-executed full toolchain: `generate_master_timetable.py` $\to$ `export_to_db.py` $\to$ `export_to_sumo.py` $\to$ `verify_simulation.py 86400`.
   - Result: 0 turnaround violations, 152/152 vehicles compiled in Duarouter, 24-hour SUMO simulation verified with 0 fatal errors, 0 collisions, 0 teleports.

---

### 11 October 2026 (Night) — Flaw 2 Remediation: Morning & Evening Peak Headway Surges (*Spitzenverkehr*)

**Objective:** Fully eliminate uniform off-peak vs. peak-hour scheduling density (Flaw 2) by engineering heavy, compressed commuter peak headways (15–30 min intervals) during rush hours, contrasted with 60–120 min off-peak cadences, and integrating dedicated peak relief trainsets.

#### Phase 11: Network-Wide Peak Headway Surge Implementation
1. **Corridor-by-Corridor Rush-Hour Headway Compression**:
   - **Corridor 1 Regional Stopper (Expanded to 34 runs)**:
     - Injected morning peak relief run `#21029`/`#21030` at 08:45 Eastbound / 09:25 Westbound.
     - Injected evening peak relief runs `#21031`/`#21032` (16:45 dep) and `#21033`/`#21034` (18:15 dep).
     - Result: Continuous **30-minute commuter cadence** across the entire morning peak (07:15, 07:45, 08:15, 08:45) and evening peak (16:15, 16:45, 17:15, 17:45, 18:15).
   - **Corridor 2 North–South Spine (Expanded to 38 runs)**:
     - Injected morning rush relief run `#32033`/`#32034` (08:40 Southbound / 09:15 Northbound).
     - Injected evening rush relief runs `#32035`/`#32036` (16:40 Southbound / 17:15 Northbound) and `#32037`/`#32038` (17:40 Southbound / 18:15 Northbound).
     - Result: Continuous **30-minute commuter cadence** throughout both peak windows (07:10, 07:40, 08:10, 08:40 AM; 16:10, 16:40, 17:10, 17:40, 18:10 PM) contrasting with 60-min midday baseline.
   - **Corridor 4 Southern Coastal Arc (Expanded to 26 runs)**:
     - Injected morning peak relief runs `#41019`/`#41020` (07:50 dep) and `#41021`/`#41022` (08:50 dep).
     - Injected evening peak relief runs `#41023`/`#41024` (16:50 dep) and `#41025`/`#41026` (17:50 dep).
     - Result: Compressed 30-min headway throughout both commuter windows.
   - **Corridor 3 Alpine Mountain Line (Expanded to 12 runs)**:
     - Added weekday commuter shuttles `#12771`/`#12772` (08:10 AM) and `#12773`/`#12774` (17:10 PM) providing daily connectivity for mountain residents.
   - **Diagonal High-Speed Bypass (Expanded to 10 runs)**:
     - Added rush-hour direct chord runs at 07:25 AM and 18:25 PM.
   - **Trans-Hub Bi-Level Flyover Transfer (Expanded to 16 runs)**:
     - Added rush-hour interchange links at 07:05 AM, 09:05 AM, 16:05 PM, and 18:05 PM, achieving hourly transfer connectivity during peaks vs 3-hour off-peak intervals.

2. **Fleet Expansion & Dedicated Peak Relief Trainsets**:
   - Expanded active rolling stock roster from 28 to **31 physical rakes**:
     - Added `REG-C1-06` (Depot 4): dedicated peak-only commuter EMU.
     - Added `REG-C2-06` (Depot 3): dedicated peak-only commuter EMU.
     - Added `REG-C4-05` (Depot 2): dedicated peak-only commuter EMU.
   - Modeled realistic suburban duty cycles: peak rakes activate during morning rush, stable in station yard sidings during midday off-peak, and redeploy for evening rush.

3. **Hourly Temporal Density Contrast**:
   - **AM Peak (07:00–08:59)**: 41 scheduled departures (18–23 departures/hr).
   - **PM Peak (16:00–18:59)**: 52 scheduled departures (16–22 departures/hr).
   - **Midday Off-Peak (10:00–15:59)**: 48 departures across 6 hours (avg 8 departures/hr).
   - **Late Night (19:00–23:59)**: 19 departures across 5 hours (avg 3.8 departures/hr).

4. **Microscopic Simulation Validation**:
   - `data/trains.db`: 188 services, 920 stops, 188 post-journey dispositions with 0 turnaround violations.
   - `duarouter`: Compiled **188 out of 188 vehicles (100% routing success)** into `trains.rou.xml`.
   - Full 24-hour SUMO simulation (`86,400s`):
     - Inserted: 188 vehicles.
     - Running / Waiting: 0.
     - Average Fleet Speed: 19.96 m/s (~71.9 km/h).
     - Average Depart Delay: **0.00s**.
     - Average Waiting Time: **0.60s**.
     - Fatal Errors: **0**.
     - Collisions: **0**.
     - Teleports: **0**.

---

### 11 October 2026 (Night) — Flaw 3 Remediation: Dynamic Calibrated Dwells & Consist-Scaled Turnarounds

**Objective:** Systematically eliminate flat station dwells and unverified turnaround buffers (Flaw 3) by introducing dynamic time-of-day and consist-scaled passenger exchange models, resolving all physical turnaround infeasibilities across rake duty cycles, and deploying a comprehensive rake turnaround and disposition chaining engine.

#### Phase 12: Dynamic Station Dwells & Full Turnaround Chaining Engine

1. **Dynamic Calibrated Dwell Model (`get_calibrated_dwell`)**:
   - Replaced flat static dwells with an operational hierarchy sensitive to peak commuter volumes (AM: 07:00–09:30, PM: 16:00–18:45) and train consist carrying capacity:
     - **Major City Hubs (`City_1`, `City_2`, `City_4`, `City_5`, `City_6`)**:
       - 16-car HighSpeed 300 (1,050 pax): **150s peak** / **120s off-peak**.
       - 8-car HighSpeed Single (520 pax): **120s peak** / **90s off-peak**.
       - Regional EMU / DMU (240–380 pax): **110s peak** / **90s off-peak**.
     - **Bi-Level Interchange Hub (`City_3_EW`, `City_3_NS`)**:
       - Flyover Transfer (multi-level commuter connection): **210s peak (3.5 min)** / **180s off-peak**.
       - Mainline Regional / Spine: **180s peak (3.0 min)** / **150s off-peak**.
     - **Intermediate Town Platform Loops (`Town_1`..`Town_7`, `Town_10`..`Town_12`)**:
       - Corridor 2 Spine Towns: **55s peak** / **45s off-peak**.
       - Other Corridors: **60s peak** / **45s off-peak**.
     - **Alpine Mountain Halts (`Town_8`, `Town_9`)**: **75s** (scenic tourists, heavy luggage).
     - **Freight Passing Loop Siding (`Town_8_Passing_Loop`)**: **720s (12 min)** scheduled hold for express overtakes.

2. **Resolution of Rake Duty Cycle Infeasibilities**:
   - Discovered and eliminated 3 physical turnaround violations in previous rake assignments:
     - **`REG-C2-01`**: Service #32026 arrived `City_5` at 06:07:28 followed by #32001 departing at 06:10:00 (infeasible 2.5 min turnaround vs 10.0 min required). Reassigned #32001/#32002 to `REG-C2-02` (which started later), expanding #32026's buffer to a healthy 182.5 min layover.
     - **`REG-C4-05`**: Service #41020 arrived `City_1` at 08:46:59 followed by #41021 departing at 08:50:00 (infeasible 3.0 min turnaround). Reassigned #41021/#41022 to `REG-C4-01` (resting at `City_1` following #41002 arrival at 08:16:59), expanding the #41002 → #41021 layover to 33.0 min.
     - **`REG-C4-05`**: Service #41024 arrived `City_1` at 17:45:54 followed by #41025 departing at 17:50:00 (infeasible 4.1 min turnaround). Reassigned #41025/#41026 to `REG-C4-02` (resting at `City_1`), expanding the turnaround to 34.1 min.
   - Calibrated downhill Alpine commuter departures #12772 (from 08:40 to 08:38) and #12774 (from 17:40 to 17:38) at `Town_9`, providing an 18.1 min turnaround and arriving at `City_2` platform 3 ahead of Westbound express arrivals, eliminating junction interlock signal holds.

3. **Turnaround & Disposition Chaining Engine (`scripts/generate_master_timetable.py`)**:
   - Engineered an automated post-processing engine that traverses each rake's chronological service sequence:
     - **157 Intermediate Services**: Exact subsequent service linked via `subsequent_service`, true elapsed turnaround minutes calculated, and validated against `min_turnaround_required_min`.
     - **31 Final Daily Services**: Stabled overnight with calculated multi-hour maintenance inspection buffers (`subsequent_service: None`).
     - **Operational Turnaround Mode Attribution**:
       - `extended_layover` (Midday / Off-Peak Yard Staging): 84 services.
       - `rapid_dual_crew` (*Kurzwende* / Dual-Crew Cab Swap): 56 services.
       - `standard_cab_swap` (Single-Driver Walk & Re-Cab): 38 services.
       - `shunting_and_inspection` (Freight Siding Shunt & Brake Test): 5 services.
       - `container_loading_and_inspection` (Intermodal Gantry Logistics): 3 services.
       - `depot_inspection` (Maintenance Facility Audit): 2 services.

4. **Microscopic Simulation & Relational Database Results**:
   - `data/trains.db`: 188 services, 920 stops, 188 post-journey dispositions with **0 turnaround violations**.
   - `duarouter`: Compiled **188 out of 188 vehicles (100% routing success)** into `sumo_config/trains.rou.xml`.
   - Full 24-hour SUMO microscopic simulation (`86,400s`):
     - Inserted / Completed: 188 vehicles.
     - Running / Waiting at step 86400: **0**.
     - Average Fleet Speed: 19.58 m/s (~70.5 km/h inclusive of all intermediate dwells and layovers).
     - Average Depart Delay: **0.00s**.
     - Average Waiting Time: **0.60s**.
     - Fatal Errors: **0**.
     - Collisions: **0**.
     - Teleports: **0**.
     - Emergency Stops: **0**.

---

### 12 October 2026 — Flaw 4 Remediation: Full-Day Density Scaling & Network Capacity Optimization

**Objective:** Systematically eliminate network-wide off-peak service deserts, midday schedule gaps, and late-evening drops (Flaw 4) by scaling timetable density across the full 24-hour cycle. Expand the timetable from 188 to **242 scheduled train runs** across the existing 31 physical rakes, eliminate excessive 8–9 hour yard idling periods, achieve balanced fleet utilization, and verify 100% conflict-free routing with 0 errors across 86,400 simulation steps.

#### Phase 13: Full-Day Density Scaling & Network Capacity Overhaul

1. **Full-Day Clockface Cadence Scaling (Expanded from 188 to 242 Scheduled Services)**:
   - **Corridor 1 High-Speed Express (Expanded from 38 to 42 runs)**:
     - Injected evening clockface runs `#12039`/`#12040` (19:00 dep City_1 / 19:35 dep City_4) utilizing `HS-Rake-03`.
     - Injected night clockface runs `#12041`/`#12042` (21:00 dep City_1 / 21:35 dep City_4) utilizing `HS-Rake-06`.
     - Result: Unbroken, continuous hourly express service across the entire operating window from 06:00 to 22:00.
   - **Corridor 1 Local Regional Stopper (Expanded from 34 to 42 runs)**:
     - Injected post-peak transition run `#21035`/`#21036` (09:15 dep City_1 / 09:55 dep City_4) utilizing `REG-C1-05`.
     - Injected midday clockface fill `#21037`/`#21038` (12:15 dep City_1 / 12:55 dep City_4) utilizing `REG-C1-05`.
     - Injected evening clockface fills `#21039`/`#21040` (20:15 dep, `REG-C1-04`) and `#21041`/`#21042` (21:15 dep, `REG-C1-03`).
     - Result: True hourly commuter cadence (:15 EB / :55 WB) from 05:15 to 21:15.
   - **Corridor 2 North–South Regional Spine (Expanded from 38 to 44 runs)**:
     - Injected midday clockface fill `#32039`/`#32040` (10:10 dep City_5 / 10:45 dep City_6) utilizing `REG-C2-04`.
     - Injected evening clockface fill `#32041`/`#32042` (20:10 dep City_5 / 20:45 dep City_6) utilizing `REG-C2-05`.
     - Injected late-night connector `#32043`/`#32044` (22:10 dep City_5 / 22:45 dep City_6) utilizing `REG-C2-02`.
     - Result: Continuous hourly spine operation from 05:10 to 22:10 without multi-hour midday or late-night gaps.
   - **Corridor 3 Northwest Alpine Mountain Line (Expanded from 12 to 18 passenger runs, 22 total)**:
     - Injected midday excursion run `#12775`/`#12776` (11:10 Uphill / 11:40 Downhill) utilizing `ALP-Rake-01`.
     - Injected afternoon panorama run `#12777`/`#12778` (14:10 Uphill / 14:40 Downhill) utilizing `ALP-Rake-01`.
     - Injected twilight return run `#12779`/`#12780` (18:10 Uphill / 18:38 Downhill) utilizing `ALP-Rake-02`.
     - Calibrated downhill departure #12780 to 18:38 (18.1 min turnaround at Town_9), clearing the City_2 junction ahead of mainline moves and eliminating signal hold emergency stops.
   - **Corridor 4 Southern Coastal Arc (Expanded from 26 to 40 passenger runs, 44 total)**:
     - Injected 7 hourly round trips bridging midday and night connectivity (#41027 to #41040) at 10:20, 12:20, 14:20, 15:20, 18:20, 20:20, and 21:20.
     - Result: Continuous hourly clockface (:20 EB / :55 WB) from 06:20 to 21:20 with 30-min rush-hour surges.
   - **Diagonal High-Speed Bypass (Expanded from 10 to 16 runs)**:
     - Injected direct chord services `#15011`/`#15012` (10:25 dep), `#15013`/`#15014` (15:25 dep), and `#15015`/`#15016` (20:25 dep) utilizing `HS-Rake-04`, providing hourly peak relief with irregular off-peak runs.
   - **Trans-Hub Bi-Level Flyover Transfer (Expanded from 16 to 26 runs)**:
     - Injected 5 round trips `#51017` to `#51026` across midday and evening (10:05, 12:05, 15:05, 19:05, 20:05), achieving hourly runs with a gap at 13:05.

2. **Fleet Utilization Balancing & Elimination of Excessive Yard Idling**:
   - Reutilized existing active rolling stock across all 31 rakes, avoiding unnecessary fleet expansion.
   - Reduced most multi-hour yard idling periods into productive layovers (e.g., `REG-C1-05` reduced from 534 min idle to productive 115–174 min layovers; `REG-C4-03` reduced from 483 min idle to 64–124 min turnarounds), while preserving an extended afternoon maintenance layover for `REG-C4-04` (484.1 min between #41016 and #41037).
   - Maintained all consist-scaled turnaround constraints (15.0 min for High-Speed 300, 12.0 min for High-Speed Single, 10.0 min for Regional EMU/DMU).

3. **Turnaround & Disposition Chaining Engine Breakdown**:
   - Total scheduled services: **242**.
   - Intermediate services chained to exact subsequent runs: **211**.
   - Final daily services stabled overnight: **31** (exactly one per rake).
   - Turnaround mode breakdown:
     - `extended_layover`: 110 services
     - `rapid_dual_crew`: 63 services
     - `standard_cab_swap`: 59 services
     - `shunting_and_inspection`: 5 services
     - `container_loading_and_inspection`: 3 services
     - `depot_inspection`: 2 services

4. **Relational Database (`data/trains.db`) Status**:
   - `rolling_stock_types`: 7 records
   - `physical_rakes`: 31 records
   - `train_services`: 242 records
   - `service_stops`: 1,164 records
   - `service_post_disposition`: 242 records
   - `service_operating_days`: 1,446 records

5. **24-Hour Microscopic Simulation & Route Compilation Results (`86,400s`)**:
   - `duarouter`: Compiled **242 out of 242 vehicles (100% routing success)** into `sumo_config/trains.rou.xml`.
   - Full 24-hour SUMO microscopic simulation (`86,400s`):
     - Inserted / Completed: **242 vehicles**.
     - Running / Waiting at step 86400: **0**.
     - Average Fleet Speed: **19.97 m/s (~71.9 km/h)**.
     - Average Depart Delay: **0.00s**.
     - Average Waiting Time: **0.47s**.
     - Emergency Stops: **0**.
     - Collisions: **0**.
     - Teleports: **0**.
     - Deadlocks: **0**.
     - Fatal Errors: **0**.

---

### 12 October 2026 — Flaw 5 Remediation: Dedicated Nocturnal Freight Corridor Wave & Logistics Flow Optimization

**Objective:** Fully remediate Flaw 5 by systematically segregating heavy freight traffic from peak passenger flows, validating the dedicated Nocturnal Freight & Logistics Wave (21:30–05:25), enforcing coordinated passing loop passenger overtakes, standardizing exact calculated turnaround dwell times across all intermediate yard/depot staging procedures, and verifying 100% conflict-free operation across 86,400 simulation steps.

#### Phase 14: Nocturnal Freight Segregation, Passing Loop Holds & Turnaround Calibration

1. **Temporal & Spatial Flow Segregation (Nocturnal Wave 21:30–05:25)**:
   - High-density passenger operations cease after the 21:30–22:45 evening wind-down, clearing mainline tracks for heavy freight operations.
   - 11 of the 14 freight runs operate during the dedicated nocturnal freight wave (21:30–05:25), allowing 2,400 t to 3,800 t heavy freight trains to traverse the network without passenger headway compression or bottleneck conflicts.
   - Cross-Corridor East–West Electric Fast Freight (`#68401` at 23:15 / `#68402` at 01:30) hauls 2,400 t container trains non-stop at 100 km/h across Corridor 1 using 25kV electric power (`electric_trunk_freight`), bypassing all intermediate towns.

2. **Passing Loop Siding Overtakes & Daytime Pathing**:
   - Mountain Bulk Ore trains (`#68101` at 04:30 and `#68103` at 22:30) incorporate a scheduled 720s (12-minute) technical hold on the dedicated passing loop siding (`Town_8_Passing_Loop` / `c3_Town_8_Town_9_loop_siding_fw_0`), safely accommodating passenger overtakes.
   - Daytime freight return runs (`#68302` at 08:30, `#68102` at 11:00, `#68202` at 14:00) operate during wide off-peak headways without impeding commuter flows.
   - Simulation tripinfo logs verify 0.0s waiting time, 0.0s depart delay, and 0 signal holds across all 14 freight services.

3. **Turnaround Dwell Precision & Disposition Calibration**:
   - Replaced static placeholder dwell estimates with exact calculated fractional minutes matching physical schedule timestamps:
     - `#68101` at `Depot_1`: Calibrated from placeholder 240 min to exact **335.0 min** (arr 05:25:00 $\to$ dep 11:00:00).
     - `#68201` at `Depot_3`: Calibrated from placeholder 300 min to exact **505.0 min** (arr 05:35:00 $\to$ dep 14:00:00).
     - `#68301` at `City_6`: Calibrated from placeholder 180 min to exact **230.0 min** (arr 04:40:00 $\to$ dep 08:30:00).
   - Validated multi-day calendar day rotations across midnight for all 4 freight sets (`FRT-Rake-01` to `FRT-Rake-04`), ensuring day-after returns (Mon/Wed/Fri $\to$ Tue/Thu/Sat) match depot availability.

4. **Microscopic Simulation & Route Compilation Results (`86,400s`)**:
   - `duarouter`: Compiled **242 out of 242 vehicles (100% routing success)** into `sumo_config/trains.rou.xml`.
   - Full 24-hour SUMO microscopic simulation (`86,400s`):
     - Inserted / Completed: **242 vehicles** (228 passenger + 14 freight).
     - Running / Waiting at step 86400: **0**.
     - Average Fleet Speed: **19.97 m/s (~71.9 km/h)**.
     - Average Depart Delay: **0.00s**.
     - Average Waiting Time: **0.47s**.
     - Emergency Stops: **0**.
     - Collisions: **0**.
     - Teleports: **0**.
     - Deadlocks: **0**.
     - Fatal Errors: **0**.
