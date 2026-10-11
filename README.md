# Train Scheduling & Rolling Stock Management System

This repository provides an automated, realistic railway scheduling, rolling stock rotation, and timetable compilation system. It operates directly on the physical track infrastructure maintained in `/home/venkatasriramt/Desktop/tracks`.

---

## 1. System Architecture

The project separates commercial timetabling and physical vehicle logistics into two interconnected layers:

```
.
├── data/
│   ├── rolling_stock_types.json  # 7 physical train consist models (speed, weight, gauge, power)
│   ├── timetable.json            # 152 scheduled train runs (Train #, names, days of week, stops)
│   ├── rakes_roster.json         # 28 physical trainsets (rakes) and their daily duty cycles
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
| **`electric_trunk_freight`**| Electric 15kV / 25kV | 1435 mm | **100 km/h** | 24 Wagons | 400.0 m | 2,400 t | Nocturnal trunk express freight across Corridor 1 mainlines (`sumo_vclass="rail_electric"`). |

---

## 3. Master Timetable & Service Breakdown (152 Trains across 28 Rakes)

The schedule in `data/timetable.json` models 152 distinct train services operating on a coordinated clockface cadence (*Taktfahrplan*), with morning/evening peak surges, calibrated station dwells, turnaround disposition tracking, and a dedicated nocturnal freight wave:

### A. Corridor 1: East–West High-Speed Trunk (`City_1` $\leftrightarrow$ `City_4`, 27.4 km)
* **High-Speed Express (38 runs)**:
  * Clockface cadence: departs `:00` Eastbound (`City_1` $\to$ `City_4`), `:35` Westbound (`City_4` $\to$ `City_1`, and `:05` during peak surge).
  * Peak headway surge: compressed to 30-min frequency during 07:00–09:00 (AM peak) and 16:00–18:30 (PM peak).
  * Speeds up to 300 km/h on slab track, bypassing towns (`Town_1`, `Town_2`, `Town_3`) via central through-tracks (`_thru_1`, `_thru_2`).
  * Calibrated dwells: 120s at `City_1`, `City_2`, and `City_4`; 150s at `City_3_EW` bi-level interchange.
* **Regional Local Stoppers (28 runs)**:
  * Clockface cadence: departs `:15` Eastbound, `:55` Westbound (`:25` during peak surge).
  * Stops at all intermediate town platform loops (`_plat_1`, `_plat_2`) with 45s dwell times.

### B. Corridor 2: North–South Regional Spine (`City_5` $\leftrightarrow$ `City_6`, 22.6 km)
* **Spine InterCity (32 runs)**:
  * Clockface cadence: departs `:10` Southbound (`City_5` $\to$ `City_6`), `:45` Northbound (`City_6` $\to$ `City_5`).
  * Peak headway surge: compressed to 30-min headway during commuter rush hours (e.g. 07:40 $\to$ 08:15 return).
  * Connects across the elevated viaduct level at `City_3_NS` (150s dwell).

### C. Corridor 3: Northwest Alpine Mountain Line (`City_2` $\leftrightarrow$ `Town_9`, 12.9 km)
* **Alpine Scenic, Glacier & Panorama Services (8 runs)**:
  * Operating on specific days and daily: #12763 (Mon/Thu/Sun), #12765 (Tue/Fri/Sat), #12769 (Daily Panorama), #12767 (Mon/Thu/Sun).
  * Clockface cadence: departs `:10` Uphill from `City_2` (synchronized connection from Corridor 1 express), `:40` Downhill from `Town_9`.
  * Climbs through steep gradients ($Z=38\text{ m}$ to $Z=130\text{ m}$) with 75s mountain halts.

### D. Corridor 4: Southern Coastal Arc (`City_1` $\leftrightarrow$ `City_6`, 27.4 km)
* **Coastal Arc Regional (18 runs)**:
  * Clockface cadence: departs `:20` Eastbound (`City_1`), `:55` Westbound (`City_6`).
  * Servicing `Town_10`, `Town_11`, and `Town_12` with 45s dwells and peak surges at 08:20 and 17:20.

### E. Diagonal High-Speed Bypass (`City_2` $\leftrightarrow$ `City_5`, 13.3 km)
* **Bypass Direct Services (6 runs)**:
  * Direct 300 km/h chord transit along `bypass_City_2_City_5` avoiding the central hub.
  * Cadence: departs `:25` Northeast, `:55` Southwest.

### F. Trans-Hub Bi-Level Flyover Transfer (`City_4` $\leftrightarrow$ `City_6`, 21.5 km)
* **Interchange Link (8 runs)**:
  * Traverses the 789m, 1.77% gradient flyover ramp (`transfer_City_3_EW_NS`) linking Corridor 1 and Corridor 2.
  * Cadence: departs `:05` East-to-South, `:35` South-to-East with 180s bi-level interchange dwells.

### G. Heavy Freight & Logistics Services (14 runs: 6 Daytime + 8 Nocturnal Wave)
* **Daytime Freight (6 runs)**:
  * #68101, #68102: Alpine mineral ore trains utilizing the Alpine Passing Loop with a 12-minute scheduled hold for passenger overtakes.
  * #68201, #68202: Container logistics feeder runs between `City_5` and dead-end pocket tracks at `Depot_3`.
  * #68301, #68302: Coastal bulk cargo between `Depot_2` and `City_6`.
* **Dedicated Nocturnal Freight Wave (8 runs, 21:30–05:25)**:
  * #68103, #68104: Nocturnal mountain bulk ore climb (22:30) and descent (02:00) during empty passenger windows.
  * #68203, #68204: Nocturnal container logistics feeder (23:00) and return (02:30).
  * #68303, #68304: Nocturnal coastal bulk cargo (21:30) and return (01:00).
  * #68401, #68402: Trans-Corridor E-Freight Express (23:15 & 01:30) hauling 2,400 t container trains non-stop at 100 km/h across Corridor 1 using 25kV electric power (`electric_trunk_freight`).

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
