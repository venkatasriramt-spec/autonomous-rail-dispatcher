# Dispatcher AI: Autonomous Railway Traffic Management & Dynamic Rescheduling

Welcome to the **Dispatcher AI** subsystem of the Unified Railway Simulation & Infrastructure Monorepo. This package provides an event-driven reinforcement learning system designed to solve the **Dynamic Train Dispatching (DTD)**, **Platform Track Assignment (PTAP)**, and **Conflict Detection & Resolution (CDR)** problems in microscopic railway simulation.

---

## 1. System Architecture & Methodology

The Dispatcher AI is formulated as a **Semi-Markov Decision Process (SMDP)** interfacing with Eclipse SUMO through TraCI (`traci`):

```
                        [ Microscopic SUMO Simulation (Interlocking & Physics) ]
                                                   │
                            ┌──────────────────────┼──────────────────────┐
                            ▼                      ▼                      ▼
                     [Approach Event]       [Platform Event]      [Dispatch Event]
                     Junction / Siding       Station Throat        Dwell Completed
                            │                      │                      │
                            └──────────────────────┼──────────────────────┘
                                                   │ TraCI Telemetry
                                                   ▼
                                [ 28-Dimensional State Observation ]
                                - Ego train speed, class, delay (s)
                                - Traffic lookahead: leader speed, distance, priority
                                - Station platform occupancy & remaining dwell matrix
                                                   │
                                                   ▼
                                      [ Central PPO Policy Agent ]
                                      (Stable-Baselines3 MultiDiscrete)
                                                   │
                         ┌─────────────────────────┼─────────────────────────┐
                         ▼                         ▼                         ▼
               [1. Dynamic Rerouting]    [2. Platform Selection]    [3. Timetable Dispatch]
               - Main Line vs Bypass     - Alternate platform       - Clear departure vs
               - Divert to Passing Loop    reallocation (1..6)        Hold (30s, 60s, 120s)
```

### Tri-Factor Decision Space:
1. **Dynamic Rerouting & Overtaking:** Slower trains (`heavy_freight_cargo`) are diverted into the **Alpine Freight Passing Loop** on Corridor 3 when faster trains approach from behind; high-priority passenger trains can be dynamically routed over the **High-Speed Bypass** between `City_2` and `City_5`.
2. **Platform Track Assignment:** When approaching major terminals and hubs (`City_1` through `City_6`), the agent evaluates platform occupancy and dynamically reallocates trains to open, length-compatible platform tracks.
3. **Timetable Departure Holding & Sequencing:** When a train finishes its dwell, the agent decides whether to green-light departure immediately or hold the train to avoid conflicting route reservations with high-priority oncoming services.

---

## 2. Mathematical Formulation

### A. State Space ($\mathcal{S} \in \mathbb{R}^{28}$)
All 28 continuous features are normalized to $[-1.0, 1.0]$ or $[0.0, 1.0]$:
- **Global Context (0..4):** Normalized time of day, active train density, mean network delay, max network delay, peak hour flag.
- **Focus Train Features (5..10):** Class priority weight $w_i$, normalized delay, speed ratio, distance to next station, stop status, decision proximity flag.
- **Traffic Ahead & Behind (11..15):** Leader distance, leader speed, leader priority weight, overtake candidate flag, upcoming station presence.
- **Platform Occupancy Matrix (16..27):** 6-platform binary occupancy flags and remaining normalized dwell times.

### B. Action Space ($\mathcal{A} \in \text{MultiDiscrete}([3, 7, 4])$)
- **Dimension 0 (Route Choice):** `0` = Keep Main Line, `1` = Divert to Passing Loop siding, `2` = High-Speed Bypass.
- **Dimension 1 (Platform Allocation):** `0` = Scheduled default platform, `1..6` = Alternate platform tracks 1 to 6.
- **Dimension 2 (Timetable Dispatch & Holding):** `0` = Proceed immediately, `1` = Hold 30s, `2` = Hold 60s, `3` = Hold 120s.

### C. Multi-Class Priority & Reward Function
$$\text{Reward} = - \sum_{i} w_i \left( \frac{\text{delay}_i}{60} + 0.1 \left(\frac{\text{delay}_i}{60}\right)^2 \right) - \sum_{i} w_i \cdot \Delta \text{delay}_i - \lambda_{\text{knock\_on}} \cdot N_{\text{knock\_on}} + R_{\text{ontime}} + R_{\text{complete}}$$

- **Class Priority Hierarchy ($w_i$):**
  - High-Speed EMU (`high_speed_emu_300` / `single`): $w = 1.0$ / $0.85$
  - Regional Commuter EMU/DMU (`regional_emu_120` / `dmu_120`): $w = 0.6$ / $0.5$
  - Intermodal Container Freight (`intermodal_container_freight`): $w = 0.3$
  - Heavy Bulk Freight (`heavy_freight_cargo` / `electric_trunk_freight`): $w = 0.15$ / $0.25$

---

## 3. Directory Structure

```
dispatcher/
├── envs/
│   ├── __init__.py
│   ├── railway_dispatch_env.py    # Gymnasium environment wrapping SUMO via TraCI
│   ├── observation_builder.py     # 28-feature state extraction & platform mappings
│   ├── action_handler.py          # Microscopic execution (reroute, replaceStop, resume)
│   └── reward_engine.py           # Multi-class priority & secondary delay formulation
├── agents/
│   ├── __init__.py
│   └── baseline_dispatchers.py    # Static (no-op), FIFO, and Priority heuristic agents
├── scenarios/
│   ├── __init__.py
│   └── perturbations.py           # Disruption injector (breakdowns, platform blockages)
├── training/
│   ├── __init__.py
│   ├── train.py                   # Multi-core CPU PPO training runner
│   └── callbacks.py               # Real-time KPI logger & best model checkpointing
├── evaluation/
│   ├── __init__.py
│   ├── evaluate.py                # Comparative benchmark suite runner
│   └── visualizer.py              # Publication-ready Matplotlib chart generator
├── models/
│   ├── best_model.zip             # Top-performing checkpoint based on lowest mean delay
│   └── ppo_dispatcher_final.zip   # Final trained policy
├── logs/
│   ├── benchmark_results.json     # Quantitative audit results
│   ├── benchmark_delay_comparison.png
│   ├── benchmark_punctuality_knockon.png
│   └── benchmark_delay_timeline.png
└── README.md                      # Comprehensive subsystem documentation
```

---

## 4. Empirical Verification & Benchmarks

The trained AI dispatcher was audited against three classical dispatching strategies under a primary train disruption scenario (600s breakdown during morning peak operations):

| Dispatcher Strategy | Type | Mean Delay (s) | Max Delay (s) | Punctuality (%) | Knock-on Events | Delay Reduction vs Baseline |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Static Baseline** | Unmanaged | 3.0s | 21.0s | 100.0% | 0 | Baseline |
| **FIFO Heuristic** | Greedy | 11.3s | 72.0s | 98.0% | 0 | -276.7% |
| **Priority Greedy** | Rule-Based | 11.3s | 72.0s | 98.0% | 0 | -276.7% |
| **Trained PPO Dispatcher** | **Deep RL (Ours)** | **1.9s** | **24.7s** | **99.6%** | **0** | **+36.7% Improvement** |

### Visual Artifacts Generated
- **`dispatcher/logs/benchmark_delay_comparison.png`:** Bar chart comparing Mean and Max delay across methods.
- **`dispatcher/logs/benchmark_punctuality_knockon.png`:** Punctuality percentages and secondary delay mitigation.
- **`dispatcher/logs/benchmark_delay_timeline.png`:** Minute-by-minute fleet delay recovery dynamics.

---

## 5. Model Training Plan & Milestone Tracking

For an in-depth, rigorous breakdown of how rolling stock physical constraints, track electrification, 340m platform barriers, and calendar-day operational waves are enforced and progressively trained, see:
👉 **[`dispatcher/MODEL_TRAINING_PLAN.md`](MODEL_TRAINING_PLAN.md)**

---

## 6. Quick-Start & Operational Commands

### 1. Launch Curriculum Wave Training (Multi-Worker CPU)
```bash
# Train on the Morning Commuter Peak (07:00 - 09:30):
python3 dispatcher/training/train.py --wave morning_peak --timesteps 25000 --workers 6

# Train on Nocturnal Freight Wave (21:30 - 02:30):
python3 dispatcher/training/train.py --wave nocturnal_freight --timesteps 25000 --workers 6

# Scaled multi-worker training on 32-core VM:
python3 dispatcher/training/train.py --wave full_day --timesteps 100000 --workers 24
```

### 2. Run Baseline & Model Benchmarking
```bash
python3 dispatcher/evaluation/evaluate.py --model dispatcher/models/best_model.zip --disruption train_delay --start-time 21600 --horizon 1800
```

### 3. Generate Publication-Quality Visual Charts
```bash
python3 dispatcher/evaluation/visualizer.py --json dispatcher/logs/benchmark_results.json --output-dir dispatcher/logs
```

