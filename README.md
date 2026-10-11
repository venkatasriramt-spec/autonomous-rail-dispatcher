# Train Scheduling & Rolling Stock Management System

This repository provides an automated, realistic railway scheduling, rolling stock rotation, and timetable compilation system. It operates directly on the physical track infrastructure maintained in `/home/venkatasriramt/Desktop/tracks`.

---

## 1. System Architecture

The project separates commercial timetabling and physical vehicle logistics into two interconnected layers:

```
.
├── data/
│   ├── rolling_stock_types.json  # 6 physical train consist models (speed, weight, gauge, power)
│   ├── timetable.json            # 72 scheduled train runs (Train #, names, days of week, stops)
│   ├── rakes_roster.json         # 17 physical trainsets (rakes) and their daily duty cycles
│   └── trains.db                 # Normalized SQLite database for SQL queries
├── scripts/
│   ├── generate_master_timetable.py # Procedural timetable and fleet generator
│   ├── export_to_db.py              # Synchronizes JSON timetable into SQLite database
│   ├── export_to_sumo.py            # Compiles XML trips and routes via duarouter
│   └── verify_simulation.py         # Headless SUMO simulation validator (0 errors/collisions)
├── sumo_config/
│   ├── trains.trips.xml          # Scheduled train trips with platform stops and dwell times
│   ├── trains.rou.xml            # Compiled microscopic edge-by-edge route paths
│   ├── viewsettings.xml         # Dark railway theme for sumo-gui visualizer
│   └── train_simulation.sumocfg  # Master SUMO simulation configuration
└── README.md                     # Comprehensive architecture and operation guide
```

---

## 2. Rolling Stock Fleet (Consist Models)

The rolling stock specifications in `data/rolling_stock_types.json` strictly adhere to the physical engineering limits of the track network:

| Consist Type | Power Supply | Gauge | Max Speed | Carriages | Length | Gross Weight | Role & Allowed Tracks |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`high_speed_emu_300`** | Electric 25kV AC | 1435 mm | **300 km/h** | 16 Cars | 400.0 m | 880 t | Corridor 1 East-West Trunk express runs; stops only at 800m+ City platforms. |
| **`high_speed_emu_single`**| Electric 25kV AC | 1435 mm | **300 km/h** | 8 Cars | 200.0 m | 440 t | High-Speed Diagonal Bypass (`City_2` $\leftrightarrow$ `City_5`). |
| **`regional_emu_120`**   | Electric 15kV / 25kV | 1435 mm | **120 km/h** | 6 Cars | 160.0 m | 240 t | Local stoppers on Corridors 1, 2, 4, and Bi-Level Hub Flyover Transfer. |
| **`regional_dmu_120`**   | Diesel-Electric Hybrid | 1435 mm | **120 km/h** | 4 Cars | 120.0 m | 180 t | Mountain runs on Corridor 3 (`City_2` $\leftrightarrow$ `Town_9`). |
| **`heavy_freight_cargo`**| Diesel Locomotive | 1435 mm | **80 km/h** | 28 Wagons | 420.0 m | 3,800 t | Bulk mineral trains utilizing the Alpine Passing Loop; Coastal cargo. |
| **`intermodal_container`**| Diesel Locomotive | 1435 mm | **80 km/h** | 24 Wagons | 380.0 m | 2,600 t | Logistics transit between `City_5` and `Depot_3` container terminal. |

---

## 3. Master Timetable & Service Breakdown (72 Trains)

The schedule in `data/timetable.json` models 72 distinct train services with explicit day-of-week active flags, stopping patterns, intermediate arrival/departure dwell times, and end-of-run dispositions:

### A. Corridor 1: East–West High-Speed Trunk (`City_1` $\leftrightarrow$ `City_4`)
* **High-Speed Express (16 runs: #12001 to #12016)**:
  * Operates at 300 km/h on slab track.
  * Bypasses intermediate towns (`Town_1`, `Town_2`, `Town_3`) via central through-tracks (`_thru_1`, `_thru_2`) without stopping.
  * Stops only at `City_1`, `City_2`, `City_3_EW`, and `City_4`.
  * **End-of-Run Disposition**: Reverses in terminal pocket tracks (`City_4_pocket_1/2_fw` ending at buffer stops `City_4_buf_1/2`) to form the return service.
* **Regional Local Stoppers (12 runs: #21001 to #21012)**:
  * Operates at 120 km/h.
  * Diverges into platform stopping loops at every intermediate town with 60s dwell times.

### B. Corridor 2: North–South Regional Spine (`City_5` $\leftrightarrow$ `City_6`)
* **Spine InterCity (16 runs: #32001 to #32016)**:
  * Connects `City_5` to `City_6` via the elevated viaduct at `City_3_NS`.
  * **End-of-Run Disposition**: Terminating trains at `City_6` pull into tail tracks `City_6_pocket_1/2_fw` terminating at buffer stops `City_6_buf_1/2`.

### C. Corridor 3: Northwest Alpine Mountain Line (`City_2` $\leftrightarrow$ `Town_9`)
* **Alpine Scenic & Glacier Services (6 runs: #12763 to #12768)**:
  * Runs on specific calendar days: e.g., **#12763 on Monday, Thursday, Sunday**.
  * Climbs from elevation $Z=38\text{ m}$ to $Z=130\text{ m}$.

### D. Corridor 4: Southern Coastal Arc (`City_1` $\leftrightarrow$ `City_6`)
* **Coastal Arc Services (8 runs: #41001 to #41008)**:
  * Sweeps around the southern perimeter servicing `Town_10`, `Town_11`, and `Town_12`.

### E. Diagonal High-Speed Bypass (`City_2` $\leftrightarrow$ `City_5`)
* **Bypass Direct Services (4 runs: #15001 to #15004)**:
  * Direct 300 km/h transit along `bypass_City_2_City_5` without traversing the central hub.

### F. Trans-Hub Bi-Level Flyover Transfer (`City_4` $\leftrightarrow$ `City_6`)
* **Interchange Link (4 runs: #51001 to #51004)**:
  * Cross-corridor link utilizing the 789m, 1.77% gradient flyover ramp (`transfer_City_3_EW_NS`) linking Corridor 1 and Corridor 2.

### G. Heavy Freight & Logistics Services (6 runs: #68101 to #68302)
* **Alpine Mineral Trains (#68101, #68102)**:
  * Uses the **Alpine Passing Loop** between `Town_8` and `Town_9` (`c3_Town_8_Town_9_loop_siding_fw`), holding for 12 minutes on the siding to allow overtaking passenger trains to pass.
* **Logistics Container Trains (#68201, #68202)**:
  * Feeder runs between `City_5` and dead-end pocket tracks at `Depot_3`.
* **Coastal Bulk Cargo (#68301, #68302)**:
  * Freight transit between `Depot_2` yard sidings and `City_6`.

---

## 4. How to Use & Execute

### 1. Regenerate the Timetable & Roster
To recompute the master timetable and rolling stock fleet:
```bash
python3 scripts/generate_master_timetable.py
```

### 2. Export to SQLite Database
To synchronize JSON data into `data/trains.db`:
```bash
python3 scripts/export_to_db.py
```

### 3. Compile SUMO Routes with Duarouter
To compile the microscopic train routes using `duarouter`:
```bash
python3 scripts/export_to_sumo.py
```

### 4. Run Simulation Verification
To verify the entire network simulation in headless mode:
```bash
python3 scripts/verify_simulation.py 30000
```

### 5. Interactive Visual Simulation with SUMO GUI
To watch the trains, signals, crossovers, and overtakes live:
```bash
sumo-gui -c sumo_config/train_simulation.sumocfg
```

---

## 5. Sample SQLite Database Queries

You can query `data/trains.db` using Python or the `sqlite3` CLI:

```sql
-- 1. Find all trains operating on Thursday
SELECT ts.train_number, ts.train_name, ts.origin_station, ts.dest_station, ts.departure_time, rt.name
FROM train_services ts
JOIN service_operating_days sod ON ts.train_number = sod.train_number
JOIN rolling_stock_types rt ON ts.rolling_stock_type = rt.type_id
WHERE sod.day_of_week = 'Thu';

-- 2. Inspect intermediate stopping schedule for Alpine Shuttle 12763
SELECT stop_sequence, station, train_stop_id, arrival_time, departure_time, dwell_sec
FROM service_stops
WHERE train_number = '12763'
ORDER BY stop_sequence;

-- 3. Check turnaround and return duty disposition
SELECT ts.train_number, ts.train_name, spd.action, spd.staging_track, spd.subsequent_service
FROM train_services ts
JOIN service_post_disposition spd ON ts.train_number = spd.train_number
WHERE spd.action = 'turnaround';
```
