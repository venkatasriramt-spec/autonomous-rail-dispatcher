# Project History

A chronological log of how the train scheduling, rolling stock rotation, and timetable compilation system evolved, from initial concept to the current programmatic data pipeline.

---

### 11 October 2026 — Project Initialization, Rolling Stock Modeling, and Master Scheduling Pipeline

**Objective:** Build an autonomous, realistic train scheduling and fleet management system in `/home/venkatasriramt/Desktop/trains` that operates directly on top of the physical track infrastructure from `/home/venkatasriramt/Desktop/network`.

#### Phase 1: Separation of Concerns & Repository Architecture
- Established `/home/venkatasriramt/Desktop/trains` as the dedicated downstream repository for rolling stock, timetables, train rotation, and simulation execution.
- Linked directly against the track graph (`dense_network.net.xml`) and platform additions (`dense_network.add.xml`) in `/home/venkatasriramt/Desktop/network/network_data/`.
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
