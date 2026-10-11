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
