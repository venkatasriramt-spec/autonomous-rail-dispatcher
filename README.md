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

## 3. Master Timetable & Service Breakdown (188 Trains across 31 Rakes)

The schedule in `data/timetable.json` models **188 distinct train services** operating on an integrated clockface cadence (*Taktfahrplan*), featuring heavy morning & evening commuter peak surges (*Spitzenverkehr*), calibrated station dwells, turnaround disposition tracking, and a dedicated nocturnal freight wave:

| Time Window | Operational Role | Departures / Hr | Frequency Characteristic |
| :--- | :--- | :---: | :--- |
| **05:00–07:00** | Early Morning Feeder & Awakening | 5–8 runs/hr | Initial positioning & commuter departures |
| **07:00–09:30** | **Morning Commuter Peak (AM Rush)** | **18–23 runs/hr** | **Compressed 15–30 min headways across all corridors** |
| **10:00–15:30** | Midday Clockface Base (Off-Peak) | 4–6 runs/hr | Standard 60–120 min cadence |
| **16:00–18:45** | **Evening Commuter Peak (PM Rush)** | **16–22 runs/hr** | **Compressed 15–30 min headways with peak relief rakes** |
| **19:00–21:30** | Evening Base & InterCity Return | 3–6 runs/hr | 60–120 min cadence |
| **21:30–05:00** | **Nocturnal Freight & Logistics Wave** | 1–3 runs/hr | Bulk minerals, container feeders, and E-freight express |

### A. Corridor 1: East–West High-Speed Trunk (`City_1` $\leftrightarrow$ `City_4`, 27.4 km)
* **High-Speed Express (38 runs)**:
  * Clockface cadence: departs `:00` Eastbound (`City_1` $\to$ `City_4`), `:35` Westbound (`City_4` $\to$ `City_1`, and `:05` during peak surge).
  * Peak headway surge: compressed to 30-min frequency during 07:00–09:00 (AM peak) and 16:00–18:30 (PM peak).
  * Speeds up to 300 km/h on slab track, bypassing towns (`Town_1`, `Town_2`, `Town_3`) via central through-tracks (`_thru_1`, `_thru_2`).
  * Calibrated dwells: 120s at `City_1`, `City_2`, and `City_4`; 150s at `City_3_EW` bi-level interchange.
* **Regional Local Stoppers (34 runs)**:
  * Clockface cadence: departs `:15` Eastbound, `:55` Westbound (`:25` during peak surge).
  * Peak commuter surge: compressed to 30-min headways (07:15, 07:45, 08:15, 08:45 AM; 16:15, 16:45, 17:15, 17:45, 18:15 PM) utilizing dedicated peak relief rake `REG-C1-06`.
  * Stops at all intermediate town platform loops (`_plat_1`, `_plat_2`) with 45s dwell times.

### B. Corridor 2: North–South Regional Spine (`City_5` $\leftrightarrow$ `City_6`, 22.6 km)
* **Spine InterCity & Commuter (38 runs)**:
  * Clockface cadence: departs `:10` Southbound (`City_5` $\to$ `City_6`), `:45` Northbound (`City_6` $\to$ `City_5`).
  * Peak headway surge: compressed to 30-min headway throughout both rush hours (07:10, 07:40, 08:10, 08:40 AM; 16:10, 16:40, 17:10, 17:40, 18:10 PM) utilizing peak relief rake `REG-C2-06`.
  * Connects across the elevated viaduct level at `City_3_NS` (150s dwell).

### C. Corridor 3: Northwest Alpine Mountain Line (`City_2` $\leftrightarrow$ `Town_9`, 12.9 km)
* **Alpine Scenic, Glacier, Panorama & Commuter Services (12 runs)**:
  * Multi-day scenic runs: #12763 (Mon/Thu/Sun), #12765 (Tue/Fri/Sat), #12769 (Daily Panorama), #12767 (Mon/Thu/Sun).
  * Weekday commuter surge: #12771 (08:10 AM) and #12773 (17:10 PM) providing daily mountain resident connectivity.
  * Clockface cadence: departs `:10` Uphill from `City_2` (synchronized connection from Corridor 1 express), `:40` Downhill from `Town_9`.
  * Climbs through steep gradients ($Z=38\text{ m}$ to $Z=130\text{ m}$) with 75s mountain halts.

### D. Corridor 4: Southern Coastal Arc (`City_1` $\leftrightarrow$ `City_6`, 27.4 km)
* **Coastal Arc Regional Commuter (26 runs)**:
  * Clockface cadence: departs `:20` Eastbound (`City_1`), `:55` Westbound (`City_6`).
  * Peak headway surge: compressed to 30-min headway (07:20, 07:50, 08:20, 08:50, 09:20 AM; 16:20, 16:50, 17:20, 17:50 PM) deploying dedicated commuter rake `REG-C4-05`.
  * Servicing `Town_10`, `Town_11`, and `Town_12` with 45s dwells.

### E. Diagonal High-Speed Bypass (`City_2` $\leftrightarrow$ `City_5`, 13.3 km)
* **Bypass Direct Services (10 runs)**:
  * Direct 300 km/h chord transit along `bypass_City_2_City_5` avoiding the central hub.
  * Peak headway surge: half-hourly commuter relief during rush hours (07:25, 08:25 AM; 17:25, 18:25 PM) using `HS-Rake-04`.

### F. Trans-Hub Bi-Level Flyover Transfer (`City_4` $\leftrightarrow$ `City_6`, 21.5 km)
* **Interchange Link (16 runs)**:
  * Traverses the 789m, 1.77% gradient flyover ramp (`transfer_City_3_EW_NS`) linking Corridor 1 and Corridor 2.
  * Peak headway surge: hourly rush-hour connection (07:05, 08:05, 09:05 AM; 16:05, 17:05, 18:05 PM) vs 3-hour off-peak cadence.

### G. Heavy Freight & Logistics Services (14 runs: 6 Daytime + 8 Nocturnal Wave)
* **Daytime Freight (6 runs)**:
  * #68101, #68102: Alpine mineral ore trains utilizing the Alpine Passing Loop with a 12-minute scheduled hold for passenger overtakes.
  * #68201, #68202: Container logistics feeder runs between `City_5` and dead-end pocket tracks at `Depot_3`.
  * #68301, #68302: Coastal bulk cargo between `Depot_2` and `City_6`.
* **Dedicated Nocturnal Freight Wave (8 runs, 21:30–05:25)**:
  * #68103, #68104: Nocturnal mountain bulk ore climb (22:30 Mon/Wed/Fri) and descent (02:00 Tue/Thu/Sat).
  * #68203, #68204: Nocturnal container logistics feeder (23:00 Tue/Thu/Sat) and return (02:30 Wed/Fri/Sun).
  * #68303, #68304: Nocturnal coastal bulk cargo (21:30 Mon/Wed/Fri) and return (01:00 Tue/Thu/Sat).
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
