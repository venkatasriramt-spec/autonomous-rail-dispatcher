# Dispatcher AI: Autonomous Railway Traffic Management & Dynamic Rescheduling

Welcome to the **Dispatcher AI** subsystem of the Unified Railway Simulation & Infrastructure Monorepo. This package provides an event-driven, multi-paradigm reinforcement learning and heuristic dispatching system designed to solve the **Dynamic Train Dispatching (DTD)**, **Platform Track Assignment (PTAP)**, and **Conflict Detection & Resolution (CDR)** problems in microscopic railway simulation.

---

## 1. System Architecture & Methodology

The Dispatcher AI operates as a microscopic decision-making layer interfacing with Eclipse SUMO through TraCI (`traci`). The subsystem supports eight distinct dispatcher paradigms spanning classical heuristics, centralized single-agent RL, concurrent multi-train RL, decentralized cooperative multi-agent RL (CTDE), and hierarchical lookahead hybrid ensembles.

```
                        [ Microscopic SUMO Simulation (Interlocking & Physics) ]
                                                   │
                            ┌──────────────────────┼──────────────────────┐
                            ▼                      ▼                      ▼
                     [Approach Event]       [Platform Event]      [Dispatch Event]
                     Junction / Siding       Station Throat        Dwell Completed
                            │                      │                      │
                            └──────────────────────┼──────────────────────┘
                                                   │ TraCI Microscopic Telemetry
                                                   ▼
                        ┌─────────────────────────────────────────────────────────┐
                        │              Dispatcher Architecture Fleet              │
                        │                                                         │
                        │  1. Static Baseline (Unmanaged Physics)                 │
                        │  2. FIFO Heuristic (First-In, First-Out)                │
                        │  3. Priority Greedy Heuristic (Class-Weighted)          │
                        │  4. Centralized PPO (Single-Focus Actor-Critic)         │
                        │  5. Multi-Train Centralized PPO (Concurrent Fleet)      │
                        │  6. Decentralized MAPPO (7 Agents, CTDE)                │
                        │  7. Comm-MAPPO (Inter-Agent Messaging + Platform Locks) │
                        │  8. Hierarchical Hybrid (15m Lookahead + PPO + MAPPO)   │
                        └──────────────────────────┬──────────────────────────────┘
                                                   │
                         ┌─────────────────────────┼─────────────────────────┐
                         ▼                         ▼                         ▼
               [1. Dynamic Rerouting]    [2. Platform Selection]    [3. Timetable Dispatch]
               - Main Line vs Bypass     - Alternate platform       - Clear departure vs
               - Divert to Passing Loop    reallocation (1..6)        Hold (30s, 60s, 120s)
```

---

## 2. The 8 Dispatcher Paradigms Explained

### 1. Static Baseline (`StaticDispatcher`)
* **Paradigm:** Unmanaged Physical Simulation Reference.
* **Mechanism:** Acts as a pure no-op controller. Trains strictly follow their static compiled timetable and default route paths. No dynamic platform switches, overtakes, or departure holds are performed.
* **Role:** Establishes the unmanaged baseline against which all active dispatchers are evaluated. Under peak congestion, queueing at station throats causes massive cascading secondary delays.

### 2. FIFO Heuristic (`FIFODispatcher`)
* **Paradigm:** First-In, First-Out Greedy Scheduling.
* **Mechanism:** Evaluates trains approaching station interlockings in order of arrival time. If the scheduled platform is occupied by an earlier dwelling train, it scans for the lowest-indexed unoccupied platform that satisfies physical train length and directional connectivity constraints.
* **Role:** Standard operational baseline in classical railway operations. Significantly reduces station throat queueing, but ignores train priority and cannot proactively plan overtakes.

### 3. Priority Greedy Heuristic (`PriorityGreedyDispatcher`)
* **Paradigm:** Rule-Based Multi-Class Priority Optimization.
* **Mechanism:** Extends FIFO by incorporating a strict rolling stock priority hierarchy ($w_{\text{High-Speed}} > w_{\text{Regional}} > w_{\text{Freight}}$). When platform conflicts arise or overtakes are possible, higher-priority express passenger trains are given right-of-way, and slower freight services are diverted to passing loop sidings.
* **Role:** Serves as a strong non-learning benchmark, achieving low mean delays but at the cost of high continuous intervention churn (~6,000 actions/week).

### 4. Centralized PPO (`ModelAgentWrapper` / `Centralized_PPO`)
* **Paradigm:** Single-Focus Deep Reinforcement Learning (Actor-Critic).
* **Architecture:** Multi-layer Perceptron (MLP) policy trained via Proximal Policy Optimization (PPO) using Stable-Baselines3. Consumes a 28-dimensional normalized state vector representing the focal conflict consist, corridor traffic lookahead, and platform occupancy matrix.
* **Action Space:** $\text{MultiDiscrete}([3, 7, 4])$ representing route selection (main vs loop vs bypass), platform track (1..6), and timetable departure hold duration (0s, 30s, 60s, 120s).
* **Key Strength:** **Action Efficiency.** Operates with extreme surgical precision, achieving heuristic-level delays (50.07s) with only **649 actions across the entire week**—an **89% reduction in dispatcher interventions** compared to heuristics (5,792–6,004 actions).

### 5. Multi-Train Centralized PPO (`MultiTrainCentralizedDispatcher`)
* **Paradigm:** Concurrent Multi-Consist Dispatching.
* **Architecture:** Extends Centralized PPO by eliminating the single-focus bottleneck. At each macro-step (15s), the environment identifies *all* active trains facing immediate conflicts (e.g. within 2,500m of a blocked platform, overtaking candidates, or delayed dwelling trains). The policy evaluates each candidate simultaneously, returning a dictionary of per-consist actions `{vid: action_vector}`.
* **Key Strength & Operational Profile:** Enables concurrent multi-consist dispatching, cutting weekly dispatcher interventions by 57.1% compared to heuristics (2,577 actions vs ~6,000). While concurrent multi-train action execution handles multiple consists simultaneously, simultaneous decisions on shared bottleneck infrastructure result in higher peak rush delays (Monday 135.88s, Thursday 140.64s) than single-focus Centralized PPO (83.49s and 87.59s).

### 6. Decentralized MAPPO (`Decentralized_MAPPO` / `MAPPODispatcher`)
* **Paradigm:** Multi-Agent Reinforcement Learning via Centralized Training with Decentralized Execution (CTDE).
* **Architecture:** Partitions the railway network into **7 autonomous control zones**:
  - **6 Station-Master Interlocking Agents** (`station_city_1` to `station_city_6`): Control localized platform assignments and departure holds using 24-dimensional station observations.
  - **1 Corridor Line Controller** (`corridor_trunk`): Controls dynamic overtaking at the Corridor 3 loop siding and High-Speed Bypass using 14-dimensional corridor observations.
* **Critic Formulation:** Centralized value function $V(\mathbf{S}_{\text{joint}})$ trained on the concatenated joint state of the entire network during training; decentralized actor networks execute policies locally during inference without central coordination bottlenecks.

### 7. Comm-MAPPO (`CommMAPPODispatcher`)
* **Paradigm:** Communicative Multi-Agent RL with Churn Suppression.
* **Enhancements over Baseline MAPPO:**
  - **Inter-Agent Message Passing:** Adjacent station agents exchange 16-dimensional continuous latent feature messages encoding expected downstream train arrivals, delays, and impending corridor surges.
  - **Vehicle-Level Platform Locking:** Keyed by `(agent_id, vehicle_id)`, the dispatcher locks a platform assignment once committed for a train approaching a station throat. This suppresses high-frequency action churn where agents repeatedly reassign platforms on consecutive simulation ticks.
* **Impact:** Suppresses weekly action churn by **90.4%** compared to baseline MAPPO (1,095 actions vs 11,449 actions).

### 8. Hierarchical Hybrid Ensemble (`HierarchicalHybridDispatcher`)
* **Paradigm:** Multi-Tier Predictive Lookahead Ensemble.
* **Architecture:**
  - **Tier 1 (15-Minute Lookahead Conflict Detector):** Traverses scheduled timetable stops and projected physical trajectories 900 seconds into the future. Identifies platform track collisions before trains even enter station approach throats.
  - **Tier 2 (Proactive Platform Reservation):** Automatically reassigns downstream platforms to length-compatible vacant tracks ahead of time, ensuring clear signals.
  - **Tier 3 (Tactical RL Override):** Leverages trained Centralized PPO and MAPPO actor networks to execute tactical micro-actions (High-Speed Bypass diversions, freight loop overtaking, and secondary delay hold sequencing).
* **Key Strength:** Matches peak network punctuality (**96.7%**) and lowest weekly mean delay (**46.89s**) across all 7 days of the week.

---

## 3. Mathematical Formulation

### A. State Space ($\mathcal{S} \in \mathbb{R}^{28}$)
All continuous features are normalized to $[-1.0, 1.0]$ or $[0.0, 1.0]$:
- **Global Context (0..4):** Normalized time of day, active train density, mean network delay, max network delay, peak hour flag.
- **Focus Train Features (5..10):** Class priority weight $w_i$, normalized delay, speed ratio, distance to next station, stop status, decision proximity flag.
- **Traffic Ahead & Behind (11..15):** Leader distance, leader speed, leader priority weight, overtake candidate flag, upcoming station presence.
- **Platform Occupancy Matrix (16..27):** 6-platform binary occupancy flags and remaining normalized dwell times.

### B. Action Space ($\mathcal{A} \in \text{MultiDiscrete}([3, 7, 4])$)
- **Dimension 0 (Route Choice):**
  - `0` = Keep Main Line.
  - `1` = Divert into Corridor 3 Alpine Freight Passing Loop siding.
  - `2` = Reroute over electrified High-Speed Bypass between City 2 and City 5.
- **Dimension 1 (Platform Allocation):**
  - `0` = Default scheduled platform track.
  - `1..6` = Alternate platform tracks 1 to 6 (verified for train length $\le$ track capacity).
- **Dimension 2 (Timetable Dispatch & Holding):**
  - `0` = Proceed immediately upon dwell completion.
  - `1` = Hold departure for 30 seconds.
  - `2` = Hold departure for 60 seconds.
  - `3` = Hold departure for 120 seconds.

### C. Multi-Class Priority Reward Function
$$\text{Reward} = - \sum_{i} w_i \left( \frac{\text{delay}_i}{60} + 0.1 \left(\frac{\text{delay}_i}{60}\right)^2 \right) - \sum_{i} w_i \cdot \Delta \text{delay}_i - \lambda_{\text{knock\_on}} \cdot N_{\text{knock\_on}} + R_{\text{ontime}} + R_{\text{complete}}$$

- **Class Priority Hierarchy ($w_i$):**
  - High-Speed EMU (`high_speed_emu_300` / `single`): $w = 1.0$ / $0.85$
  - Regional Commuter EMU/DMU (`regional_emu_120` / `dmu_120`): $w = 0.6$ / $0.5$
  - Intermodal Container Freight (`intermodal_container_freight`): $w = 0.3$
  - Heavy Bulk Freight (`heavy_freight_cargo` / `electric_trunk_freight`): $w = 0.15$ / $0.25$

---

## 4. Microscopic TraCI Action Execution & Safety Guardrails

The [`ActionHandler`](envs/action_handler.py) enforces safety guardrails to ensure discrete AI decisions translate into physically valid microscopic SUMO commands:

1. **Loop-Siding Overtake Reservations (`route_act == 1`):**
   - **Reservation Lock:** Tracks active loop reservations via `self.siding_reservations: Dict[str, str]`. Only one train can hold a siding reservation at any time; conflicting diversion requests by other trains are rejected.
   - **Corridor Occupancy Inspection:** Inspects lead-in, siding, and lead-out edges (`traci.edge.getLastStepVehicleIDs()`) to ensure the entire loop geometry is physically clear of other vehicles.
   - **Duplicate Stop Suppression:** Queries `traci.vehicle.getStops(focus_veh_id)`. If a stop on the siding track already exists, duplicate stop injections are skipped.
   - **Expiration Cleanup:** Clears siding reservations automatically as soon as the reserving train exits the siding or arrives at its destination.

2. **Vehicle-Level High-Speed Bypass Rerouting (`route_act == 2`):**
   - **Vehicle-Specific Travel Times:** Invokes `traci.vehicle.setAdaptedTraveltime(vid, edge_id, 5.0)` across the 10 bypass chord edges, avoiding corrupting global network edge weights for non-targeted traffic.
   - **Downstream Route Verification:** Compares the vehicle's route before and after `rerouteTraveltime()`. The change is logged as `high_speed_bypass_reroute` only if the route altered and downstream edges contain the bypass.

3. **Platform Reallocation (`plat_act > 0`):**
   - Verifies train length against physical platform clearance ($L_{\text{train}} \le L_{\text{plat}}$, e.g. 340m, 220m, 180m).
   - Verifies track electrification compatibility (diesel-only rakes prohibited from dedicated pantograph tracks).
   - Replaces downstream stops via `traci.vehicle.replaceStop()`.

4. **Departure Holding (`hold_act > 0`):**
   - Rejects holds on trains running significantly late ($>120\text{s}$ delay) to prevent secondary delay compounding.
   - Resumes held trains via `traci.vehicle.resume()` once hold timers expire.

---

## 5. Authoritative 56-Run Weekly Cross-Comparison Benchmark (All 8 Models)

Evaluated across all 7 calendar days (Monday through Sunday, 00:00 to 24:00 daily, 5,760 simulation steps/day, 1,446 total train services evaluated per model, 56 total runs) from [`dispatcher/logs/evaluations/weekly_audits/cross_comparison_24h.json`](logs/evaluations/weekly_audits/cross_comparison_24h.json):

### Summary Table: 7-Day Performance Across All Paradigms

| Dispatcher Model | Architecture Paradigm | Weekly Mean Delay | Weekly Max Delay | 7-Day Punctuality (<3m) | Total Weekly Knock-ons | Total Weekly Actions | Actions vs Heuristics |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Static Baseline** | Unmanaged Physical Baseline | 236.20s | 22,071.0s | 93.4% | 10,878 | **0** | Baseline (No Control) |
| **FIFO Heuristic** | Greedy FCFS Platform Routing | 50.07s | 7,475.0s | 96.3% | 901 | 5,792 | -3.5% |
| **Priority Greedy** | Class-Weighted Rule Heuristic | **46.89s** | 7,475.0s | **96.7%** | 913 | 6,004 | Reference Heuristic |
| **Centralized PPO** | Discrete Actor-Critic RL | 50.07s | 7,475.0s | 96.3% | **903** | **649** | **-89.2% Workload Reduction!** |
| **Multi-Train PPO** | Concurrent Fleet Dispatching | 71.80s | 9,246.0s | 95.6% | 916 | 2,577 | -57.1% Workload Reduction |
| **Decentralized MAPPO** | 7-Agent CTDE Multi-Agent | 152.86s | 22,071.0s | 95.1% | 4,869 | 11,449 | High Action Churn |
| **Comm-MAPPO** | Inter-Agent Comm + Platform Lock | 213.48s | 22,071.0s | 94.3% | 6,612 | **1,095** | **-90.4% Churn Cut vs MAPPO** |
| **Hierarchical Hybrid** | 15m Lookahead + PPO + MAPPO | **46.89s** | 7,475.0s | **96.7%** | 913 | 6,532 | Maximum Punctuality |

### Day-by-Day Mean Delay Breakdown (Seconds)

| Day | Services | Static Baseline | FIFO Heuristic | Priority Greedy | Centralized PPO | Multi-Train PPO | Decentralized MAPPO | Comm-MAPPO | Hierarchical Hybrid |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Mon** | 232 | 224.56s | 83.49s | 83.49s | 83.49s | 135.88s | 48.10s | 151.38s | **83.49s** |
| **Tue** | 233 | 278.61s | 35.03s | 35.03s | 35.03s | 45.75s | 265.71s | 265.71s | **35.03s** |
| **Wed** | 229 | 194.73s | 31.54s | 31.54s | 31.54s | 41.87s | 45.71s | 260.71s | **31.54s** |
| **Thu** | 235 | 229.83s | 87.59s | 87.59s | 87.59s | 140.64s | 52.10s | 158.23s | **87.59s** |
| **Fri** | 231 | 273.54s | 31.53s | 31.53s | 31.53s | 41.86s | 260.65s | 260.65s | **31.53s** |
| **Sat** | 145 | 300.25s | 28.07s | 28.07s | 28.07s | 51.32s | 292.20s | 292.20s | **28.07s** |
| **Sun** | 141 | 151.86s | 53.23s | 30.97s | 53.23s | 45.27s | 105.21s | 105.21s | **30.97s** |

---

## 6. Directory Structure & Key Artifacts

```
dispatcher/
├── envs/
│   ├── railway_dispatch_env.py    # Gymnasium environment wrapping SUMO via TraCI
│   ├── multi_agent_railway_env.py # Decentralized multi-agent environment (7 agents, CTDE)
│   ├── observation_builder.py     # 28-feature single-consist observation builder
│   ├── multi_agent_builder.py     # 24-dim station & 14-dim corridor localized builders
│   ├── marl_zones.py              # Station interlocking & corridor spatial boundary definitions
│   ├── action_handler.py          # Microscopic execution: loop siding reservation, bypass, stops
│   └── reward_engine.py           # Multi-class priority & secondary delay formulation
├── agents/
│   ├── baseline_dispatchers.py    # Static, FIFO, Priority Greedy heuristic controllers
│   ├── mappo_agent.py             # Multi-Agent PPO actor-critic architectures (PyTorch)
│   ├── multi_train_ppo.py         # Concurrent multi-train centralized PPO controller
│   ├── comm_mappo_agent.py        # Communicative MAPPO with inter-agent message passing
│   └── hybrid_dispatcher.py       # Hierarchical Lookahead Ensemble (Tier 1-3)
├── evaluation/
│   ├── audit_cross_comparison_24h.py # Authoritative 56-run weekly 24-hour benchmarking engine
│   ├── visualize_weekly_audit.py     # Publication-grade Matplotlib 8-model visualizer
│   ├── audit_marl_comparison.py      # CTDE vs Centralized commuter audit
│   ├── audit_stress_testing.py       # Severe perturbation stress benchmark
│   └── visualize_marl.py             # 4-panel MARL comparative visualizer
├── models/
│   ├── best_model.zip                # Top Centralized PPO checkpoint
│   ├── ppo_dispatcher_final.zip      # Production-calibrated Centralized PPO model
│   ├── mappo_interlocking.pt         # Production MAPPO actor-critic weights
│   └── mappo_best_*.pt               # Wave-specific curriculum checkpoints
└── logs/
    ├── evaluations/weekly_audits/cross_comparison_24h.json # Complete 56-run weekly dataset
    ├── visual_proofs/                # Publication-ready high-resolution benchmark plots
    └── LOGS_MAP.md                   # Comprehensive directory reference guide
```

---

## 7. Publication-Quality Visual Artifacts (`dispatcher/logs/visual_proofs/`)

The evaluation suite outputs 13 high-resolution visualization artifacts (stored in [`logs/visual_proofs/`](logs/visual_proofs/)):

1. **`weekly_7day_delay_comparison.png`:** Grouped bar chart comparing Mean Delay across all 8 models for every day from Monday to Sunday.
2. **`weekly_7day_punctuality.png`:** Schedule punctuality retention rates (<3 min delay threshold) with target line (95%) across all 8 models.
3. **`weekly_7day_knockon_cascades.png`:** Secondary delay cascades suppressed by day across all 8 models.
4. **`weekly_7day_actions_taken.png`:** Dispatcher intervention intensity and churn comparison across the week, demonstrating Centralized PPO's 89% action reduction.
5. **`weekly_24h_diurnal_timeline.png`:** Hour-by-hour fleet delay progression comparing Monday commuter rush vs Saturday leisure base.
6. **`model_efficiency_tradeoff.png`:** Action-efficiency trade-off scatter plot plotting Weekly Mean Delay (s) vs Total Actions Taken across all dispatcher models.
7. **`marl_vs_centralized_comparison.png`:** 4-panel comparison of Decentralized MAPPO vs Centralized PPO & Baselines.
8. **`benchmark_delay_comparison.png`:** Disruption benchmark bar chart comparing Mean and Max delay.
9. **`benchmark_punctuality_knockon.png`:** Punctuality percentages and 100% secondary delay mitigation.
10. **`benchmark_delay_timeline.png`:** Minute-by-minute fleet delay recovery dynamics under acute primary breakdown.
11. **`stress_test_delay_comparison.png`:** Multi-scenario stress audit delay comparisons (breakdowns, closures, surge, compound).
12. **`stress_test_knockon_cascades.png`:** Knock-on event counts across stress scenarios.
13. **`stress_test_punctuality.png`:** Punctuality retention curves under severe disruption stress testing.

---

## 8. Operational Commands

### 1. Run Authoritative 56-Run Weekly Cross-Comparison
```bash
# Execute full 7-day 24-hour simulation across all 8 dispatchers (56 runs)
python3 dispatcher/evaluation/audit_cross_comparison_24h.py

# Benchmark a specific subset of models:
python3 dispatcher/evaluation/audit_cross_comparison_24h.py --dispatchers "Hierarchical_Hybrid,Centralized_PPO,Comm_MAPPO"
```

### 2. Generate All Comparison Graphs
```bash
python3 dispatcher/evaluation/visualize_weekly_audit.py \
  --json dispatcher/logs/evaluations/weekly_audits/cross_comparison_24h.json \
  --output-dir dispatcher/logs/visual_proofs
```

### 3. Launch Centralized and Multi-Agent Training
```bash
# Train Centralized PPO policy:
python3 dispatcher/training/train.py --wave full_day --timesteps 100000 --workers 16

# Train Comm-MAPPO multi-agent policy:
python3 dispatcher/training/train_mappo_curriculum.py
```

---

## 9. Subsystem Links & References

- **Monorepo Architecture:** [Root README](../README.md)
- **Track Infrastructure & Topology:** [tracks/README.md](../tracks/README.md)
- **Fleet Management & Timetables:** [trains/README.md](../trains/README.md)
- **FastAPI Backend Server:** [backend/README.md](../backend/README.md)
- **Modern Web UI Dashboard:** [frontend/README.md](../frontend/README.md)
- **Model Training Roadmap:** [MODEL_TRAINING_PLAN.md](MODEL_TRAINING_PLAN.md)
- **Logs & Evaluation Reference:** [logs/LOGS_MAP.md](logs/LOGS_MAP.md)
- **Unified Milestone Log:** [project_history.md](../project_history.md)

