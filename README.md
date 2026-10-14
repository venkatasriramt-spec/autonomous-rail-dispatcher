# Train Scheduling & Rolling Stock Management System

This repository provides an automated, realistic railway scheduling, rolling stock rotation, and timetable compilation system. It operates directly on the physical track infrastructure maintained in `/home/venkatasriramt/Desktop/tracks`.

---

## 1. System Architecture

The project separates commercial timetabling and physical vehicle logistics into two interconnected layers:

```
.
├── data/
│   ├── rolling_stock_types.json  # 7 physical train consist models (speed, weight, gauge, power)
│   ├── timetable.json            # 242 scheduled train runs (Train #, names, days of week, stops)
│   ├── rakes_roster.json         # 31 physical trainsets (rakes) and their daily duty cycles
│   └── trains.db                 # Normalized SQLite database for SQL queries
├── scripts/
│   ├── generate_master_timetable.py # Procedural timetable and fleet generator
│   ├── export_to_db.py              # Synchronizes JSON timetable into SQLite database
│   ├── export_to_sumo.py            # Compiles XML trips and routes via duarouter
│   ├── validate_timetable.py        # Validates timetable against physical network (T_min, distances)
│   └── verify_simulation.py         # Headless SUMO simulation validator (0 errors/collisions)
├── sumo_config/
│   ├── trains.trips.xml          # Scheduled train trips with platform stops and dwell times (default export)
│   ├── trains.rou.xml            # Compiled microscopic edge-by-edge route paths (default 242 services)
│   ├── trains.rou.alt.xml        # Alternative compiled route paths
│   ├── trains_rakes.trips.xml    # Continuous physical rakes trips (31 rakes full daily lifecycle)
│   ├── trains_rakes.rou.xml      # Compiled continuous rake routes
│   ├── trains_rakes.rou.alt.xml  # Alternative compiled rake routes
│   ├── trains_services.trips.xml # Discrete service trips XML for slot validation
│   ├── trains_services.rou.xml   # Compiled discrete service routes
│   ├── trains_services.rou.alt.xml # Alternative compiled service routes
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
| **`intermodal_container_freight`**| Diesel Locomotive | 1435 mm | **80 km/h** | 24 Wagons | 380.0 m | 2,600 t | Logistics transit between `City_5` and `Depot_3` container terminal. |
| **`electric_trunk_freight`**| Electric 15kV / 25kV | 1435 mm | **100 km/h** | 24 Wagons | 400.0 m | 2,400 t | Nocturnal trunk express freight across Corridor 1 mainlines (`sumo_vclass="rail_electric"`). |

---

## 3. Master Timetable & Service Breakdown (242 Trains across 31 Rakes)

The schedule in `data/timetable.json` models **242 distinct train services** operating on an integrated clockface cadence (*Taktfahrplan*), featuring heavy morning & evening commuter peak surges (*Spitzenverkehr*), comprehensive full-day midday and evening density scaling, dynamic calibrated station dwells, multi-tier consist turnaround tracking, and a dedicated nocturnal freight wave:

| Time Window | Operational Role | Departures / Hr | Frequency Characteristic |
| :--- | :--- | :---: | :--- |
| **05:00–07:00** | Early Morning Feeder & Awakening | 5–8 runs/hr | Initial positioning & commuter departures |
| **07:00–09:30** | **Morning Commuter Peak (AM Rush)** | **18–23 runs/hr** | **Compressed 15–30 min headways across all corridors** |
| **09:30–15:30** | **Midday Clockface Base & Density Scaling** | **10–14 runs/hr** | **Regular 60-min hourly clockface cadence across all lines** |
| **16:00–18:45** | **Evening Commuter Peak (PM Rush)** | **16–22 runs/hr** | **Compressed 15–30 min headways with peak relief rakes** |
| **19:00–21:30** | **Evening Base & Night-Owl Cadence** | **5–12 runs/hr** | **Continuous hourly clockface & inter-corridor connectivity** |
| **21:30–05:00** | **Nocturnal Freight & Logistics Wave** | **1–3 runs/hr (freight-only)** | Bulk minerals, container feeders, and E-freight express; late-night passenger services (#12029, #12030, #12042, #21042, #32032, #32043, #32044, #41040) listed separately, concluding by 22:45 |

*Note: The 21:30–05:00 cadence rate is freight-only; late-night passenger services (#12029, #12030, #12042, #21042, #32032, #32043, #32044, #41040) are listed separately, concluding between 21:30 and 22:45 at 4–8 runs/hr.*

### A. Corridor 1: East–West High-Speed Trunk (`City_1` $\leftrightarrow$ `City_4`, 28.2 km)
* **High-Speed Express (42 runs)**:
  * Clockface cadence: departs `:00` Eastbound (`City_1` $\to$ `City_4`), `:35` Westbound (`City_4` $\to$ `City_1`, and `:05` during peak surge).
  * Full-day density scaling (weekdays): continuous hourly clockface from 06:00 to 22:00 without evening gaps on weekdays (with base weekend cadence; departures do not provide unbroken hourly service on weekends), supplemented by 30-min weekday peak surges (07:00–09:00 AM peak and 16:00–18:30 PM peak).
  * Speeds up to 300 km/h on slab track, bypassing towns (`Town_1`, `Town_2`, `Town_3`) via central through-tracks (`_thru_1`, `_thru_2`).
  * Dynamic calibrated dwells: 150s peak / 120s off-peak at `City_1`, `City_2`, and `City_4`; 180s peak / 150s off-peak at `City_3_EW` bi-level interchange.
  * Turnaround: 12.6–14.1 min buffer at `City_4` pocket tracks (`City_4_pocket_1_fw`), classified as `rapid_dual_crew` (*Kurzwende*).
* **Regional Local Stoppers (42 runs)**:
  * Clockface cadence: departs `:15` Eastbound, `:55` Westbound (`:25` during peak surge).
  * Full-day density scaling (weekdays): unbroken hourly clockface from 05:15 to 21:15 on weekdays (weekends operate on a reduced base cadence and do not provide unbroken hourly service), with 30-min weekday peak commuter surges (07:15, 07:45, 08:15, 08:45 AM; 16:15, 16:45, 17:15, 17:45, 18:15 PM) deploying peak relief rake `REG-C1-06`.
  * Dynamic calibrated dwells: 60s peak / 45s off-peak at town platform loops; 110s peak / 90s off-peak at cities; 180s peak / 150s off-peak at `City_3_EW`.
  * Turnaround: 8.2–10.1 min turnaround at `City_4_pocket_2_fw` with the 7.0-minute consist minimum.

### B. Corridor 2: North–South Regional Spine (`City_5` $\leftrightarrow$ `City_6`, 23.2 km)
* **Spine InterCity & Commuter (44 runs)**:
  * Clockface cadence: departs `:10` Southbound (`City_5` $\to$ `City_6`), `:45` Northbound (`City_6` $\to$ `City_5`, and `:15` during peak).
  * Full-day density scaling (weekdays): continuous hourly cadence from 05:10 to 22:10 on weekdays (weekends operate on a reduced base schedule without unbroken hourly coverage), compressed to 30-min headways throughout both weekday rush hours (07:10, 07:40, 08:10, 08:40 AM; 16:10, 16:40, 17:10, 17:40, 18:10 PM) utilizing peak relief rake `REG-C2-06`.
  * Dynamic calibrated dwells: 55s peak / 45s off-peak at towns; 110s peak / 90s off-peak at termini; 180s peak / 150s off-peak at `City_3_NS` viaduct interchange.
  * Turnaround: 7.2–8.7 min turnaround at `City_6_pocket_1_fw` (`rapid_dual_crew`).

### C. Corridor 3: Northwest Alpine Mountain Line (`City_2` $\leftrightarrow$ `Town_9`, 9.9 km regional / 14.4 km freight)
* **Alpine Scenic, Glacier, Panorama & Commuter Services (18 passenger runs)**:
  * Multi-day scenic & excursion runs: #12763 (Mon/Thu/Sun), #12765 (Tue/Fri/Sat), #12775 (Daily Shuttle), #12769 (Daily Panorama), #12777 (Daily Express), #12767 (Mon/Thu/Sun), #12779 (Daily Twilight).
  * Weekday commuter surge: #12771 (08:10 AM dep City_2 / 08:38 AM dep Town_9) and #12773 (17:10 PM dep City_2 / 17:38 PM dep Town_9).
  * Clockface cadence: departs `:10` Uphill from `City_2` (synchronized connection from Corridor 1 express), `:40` Downhill from `Town_9` (and `:38` for commuter & twilight shuttles to clear main junction interlocks).
  * Steep gradient mountain operation ($Z=38\text{ m}$ to $Z=130\text{ m}$) with 75s mountain halts.
  * Turnaround: 17.2–19.6 min turnaround at `Town_9_yard_1_fw` (`standard_cab_swap`).

### D. Corridor 4: Southern Coastal Arc (`City_1` $\leftrightarrow$ `City_6`, 29.3 km)
* **Coastal Arc Regional Commuter (40 passenger runs)**:
  * Clockface cadence: departs `:20` Eastbound (`City_1`), `:55` Westbound (`City_6`, and `:25` during peak).
  * Full-day density scaling (weekdays): unbroken hourly clockface from 06:20 to 21:20 on weekdays (weekends operate on a reduced base cadence without unbroken hourly service), compressed to 30-min headway (07:20, 07:50, 08:20, 08:50, 09:20 AM; 16:20, 16:50, 17:20, 17:50 PM) deploying commuter rake `REG-C4-05`.
  * Dynamic calibrated dwells: 60s peak / 45s off-peak at `Town_10`, `Town_11`, and `Town_12`.
  * Turnaround: 7.6–8.7 min turnaround at `City_6_pocket_2_fw`.

### E. Diagonal High-Speed Bypass (`City_2` $\leftrightarrow$ `City_5`, 14.8 km)
* **Bypass Direct Services (16 runs)**:
  * Direct 300 km/h chord transit along `bypass_City_2_City_5` avoiding the central hub.
  * Full-day density scaling: hourly peak relief during rush hours (07:25, 08:25 AM; 17:25, 18:25 PM) with irregular off-peak runs (10:25, 13:25, 15:25, 20:25) using `HS-Rake-04` (`high_speed_emu_single`).
  * Turnaround: 22.1–23.9 min turnaround at `City_5_yard_2_bw` (`standard_cab_swap`).

### F. Trans-Hub Bi-Level Flyover Transfer (`City_4` $\leftrightarrow$ `City_6`, 23.4 km)
* **Interchange Link (26 runs)**:
  * Traverses the 789m, 1.77% gradient flyover ramp (`transfer_City_3_EW_NS`) linking Corridor 1 and Corridor 2.
  * Full-day density scaling: hourly runs throughout the day (07:05, 08:05, 09:05, 10:05, 11:05, 12:05, 14:05, 15:05, 16:05, 17:05, 18:05, 19:05, 20:05) with a gap at 13:05; the 07:05, 09:05, and 16:05–18:05 departures are weekday-only, while the remaining listed departures run daily, including weekends.
  * Multi-level interchange dwell: 210s peak / 180s off-peak at `City_3_EW` / `City_3_NS`.
  * Turnaround: 9.3–9.8 min turnaround at `City_6_pocket_2_fw`.

### G. Heavy Freight & Logistics Services (14 runs: 6 Daytime + 8 Nocturnal Wave)
* **Daytime Freight (6 runs)**:
  * #68101, #68102: Alpine mineral ore trains utilizing the Alpine Passing Loop with a 12-minute scheduled hold (720s dwell) for passenger overtakes.
  * #68201, #68202: Container logistics feeder runs between `City_5` and dead-end pocket tracks at `Depot_3`.
  * #68301, #68302: Coastal bulk cargo between `Depot_2` and `City_6`.
* **Dedicated Nocturnal Freight Wave (8 runs, 21:30–05:25)**:
  * #68103, #68104: Nocturnal mountain bulk ore climb (22:30 Mon/Wed/Fri) and descent (02:00 Tue/Thu/Sat).
  * #68203, #68204: Nocturnal container logistics feeder (23:00 Tue/Thu/Sat) and return (02:30 Wed/Fri/Sun).
  * #68303, #68304: Nocturnal coastal bulk cargo (21:30 Mon/Wed/Fri) and return (01:00 Tue/Thu/Sat).
  * #68401, #68402: Trans-Corridor E-Freight Express (23:15 & 01:30) hauling 2,400 t container trains non-stop at 100 km/h across Corridor 1 using 25kV electric power (`electric_trunk_freight`).

### H. Operating Days & Daily Service Distribution

Train services in `data/timetable.json` declare designated operational calendar days via `service_days` (e.g. `Daily`, `Mon-Fri`, or specific day rotations). The simulation export script `scripts/export_to_sumo.py` filters services by day:

| Operating Day | Scheduled Services | Operational Breakdown |
| :--- | :--- | :--- |
| **Monday** | **232** | Daily baseline (136) + Mon-Fri commuter surges (88) + Mon/Wed/Fri (4) + Mon/Thu/Sun (4) |
| **Tuesday** | **233** | Daily baseline (136) + Mon-Fri commuter surges (88) + Tue/Thu/Sat (7) + Tue/Fri/Sat (2) |
| **Wednesday** | **229** | Daily baseline (136) + Mon-Fri commuter surges (88) + Mon/Wed/Fri (4) + Wed/Fri/Sun (1) |
| **Thursday** | **235** | Daily baseline (136) + Mon-Fri commuter surges (88) + Tue/Thu/Sat (7) + Mon/Thu/Sun (4) |
| **Friday** | **231** | Daily baseline (136) + Mon-Fri commuter surges (88) + Mon/Wed/Fri (4) + Tue/Fri/Sat (2) + Wed/Fri/Sun (1) |
| **Saturday** | **145** | Daily baseline (136) + Tue/Thu/Sat (7) + Tue/Fri/Sat (2) *(no weekday commuter peaks)* |
| **Sunday** | **141** | Daily baseline (136) + Mon/Thu/Sun (4) + Wed/Fri/Sun (1) *(no weekday commuter peaks)* |
| **Composite (All)** | **242** | Full weekly pool of unique train runs across all operating schedules |

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

### 3. Compile SUMO Routes with Duarouter (Dual-Mode)
To compile microscopic train routes using `duarouter`, either for continuous physical rakes (the 31-train fleet with full daily lifecycles) or discrete commercial service trips:
```bash
# Continuous Physical Rakes Mode (Default: 31 physical trainsets with stabling & pocket turnarounds):
python3 scripts/export_to_sumo.py --mode rakes

# Discrete Services Mode (242 independent commercial timetable runs):
python3 scripts/export_to_sumo.py --mode services

# Dual-Mode Export (Compiles both formats simultaneously):
python3 scripts/export_to_sumo.py --mode both

# Day-specific export (filters timetable by operating day):
python3 scripts/export_to_sumo.py --day Mon      # Monday
python3 scripts/export_to_sumo.py --day Sat      # Saturday
```

### 4. Validate Timetable Feasibility, Distances & Rake Lifecycles
To audit all scheduled services against the physical track network, verifying that theoretical lower bounds ($T_{\text{planned}} \ge T_{\min}$), route lengths ($|\text{declared} - \text{route\_len}| \le 0.05\text{ km}$), and continuous rake rotation duty cycles are strictly satisfied:
```bash
# Auto-detects mode from active route file:
python3 scripts/validate_timetable.py

# Explicitly audit both discrete services and continuous rakes:
python3 scripts/validate_timetable.py --mode both
```

### 5. Run Simulation Verification
To verify the entire network simulation in headless mode (auto-detects rakes vs services mode):
```bash
# Standard 24-hour verification on currently exported configuration:
python3 scripts/verify_simulation.py 86400  # Full 24-hour verification

# Quick 7-hour verification:
python3 scripts/verify_simulation.py 26000

# Automated sweep verifying all 7 operating days:
python3 scripts/verify_simulation.py --all-days 86400
```

### 6. Interactive Visual Simulation with SUMO GUI
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
