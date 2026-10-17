# Dispatcher Logs Directory & Mapping Guide

This directory contains all operational training metrics, evaluation JSON reports, and visualization artifacts for the Autonomous Railway Dispatcher RL system.

---

## Directory Structure Overview

```
dispatcher/logs/
├── tensorboard/                      # TensorBoard training logs (PPO_1, PPO_2, ...)
├── evaluations/                      # Structured benchmark & audit JSON results
│   ├── weekly_audits/                # Full 24-hour, 7-day cross-comparison audits
│   ├── calendar_audits/              # Day-specific schedule audits (Mon, Sat, etc.)
│   ├── disruption_benchmarks/        # Disruption stress benchmarks (delays, blockages)
│   ├── marl_audits/                  # Multi-agent MARL vs Centralized benchmark audits
│   └── stress_tests/                 # Severe stress testing (Phases A & B across all days)
├── visual_proofs/                    # High-resolution PNG charts and visual comparisons
└── LOGS_MAP.md                       # This architectural reference map
```

---

## Detailed File & Script Mapping

### 1. Training Runs & TensorBoard Logs (`dispatcher/logs/tensorboard/`)
* **Generating Script:** [`dispatcher/training/train.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/training/train.py) or [`dispatcher/training/retrain_500k.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/training/retrain_500k.py)
* **Contents:** Subdirectories `PPO_1`, `PPO_2`, ..., `PPO_25`, etc.
* **Tracked Metrics:**
  * `train/loss`, `train/value_loss`, `train/policy_gradient_loss`, `train/entropy_loss`
  * `train/approx_kl`, `train/clip_fraction`, `train/explained_variance`
  * `railway/mean_delay_sec`: Rolling average train delay
  * `railway/punctuality_pct`: % of arrivals within 3 minutes of timetable
  * `railway/knock_on_events`: Secondary delay propagation events
  * `railway/intervention_rate_pct`: % of decisions where agent took non-zero action
* **How to View:**
  ```bash
  tensorboard --logdir dispatcher/logs/tensorboard --port 6006
  ```

---

### 2. Full 24-Hour Weekly Audits (`dispatcher/logs/evaluations/weekly_audits/`)

| File Name | Generating Script | CLI Command | Description |
| :--- | :--- | :--- | :--- |
| **`cross_comparison_24h.json`** | [`dispatcher/evaluation/audit_cross_comparison_24h.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/audit_cross_comparison_24h.py) | `python3 dispatcher/evaluation/audit_cross_comparison_24h.py` | Runs 42 parallel 24-hour simulations (7 days × 6 dispatchers: Static Baseline, FIFO Heuristic, Priority Greedy Heuristic, Centralized PPO, Decentralized MAPPO, and Trained PPO Dispatcher). Compares mean delay, max delay, punctuality, knock-ons, and intervention counts across every day of the week. |
| **`cross_comparison_24h_pre_fix.json`** | [`dispatcher/evaluation/audit_cross_comparison_24h.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/audit_cross_comparison_24h.py) | `python3 dispatcher/evaluation/audit_cross_comparison_24h.py` | Historical baseline audit snapshot preserving pre-fix 24-hour evaluation metrics across all 7 days prior to platform reallocation logic centralization and dwell calculation fixes. |
| **`full_day_weekly_audit.json`** | [`dispatcher/evaluation/audit_full_day_parallel.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/audit_full_day_parallel.py) | `python3 dispatcher/evaluation/audit_full_day_parallel.py` | Evaluates 7-day continuous fleet operations under nominal timetable traffic. |

---

### 3. Calendar & Timetable Audits (`dispatcher/logs/evaluations/calendar_audits/`)

| File Name | Generating Script | CLI Command | Description |
| :--- | :--- | :--- | :--- |
| **`weekly_calendar_audit.json`** | [`dispatcher/evaluation/audit_weekly_calendar.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/audit_weekly_calendar.py) | `python3 dispatcher/evaluation/audit_weekly_calendar.py` | 1-hour morning rush evaluation (07:00–08:00) comparing PPO vs Static baseline across all 7 calendar days. |
| **`option1_saturday_eval.json`** | [`dispatcher/training/train_multiday_option1.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/training/train_multiday_option1.py) | `python3 dispatcher/training/train_multiday_option1.py` | Saturday nominal leisure timetable evaluation verifying absence of artificial holds. |
| **`saturday_eval.json`** | [`dispatcher/evaluation/evaluate.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/evaluate.py) | `python3 dispatcher/evaluation/evaluate.py --disruption none` | Saturday baseline timetable audit. |

---

### 4. Disruption Benchmarks (`dispatcher/logs/evaluations/disruption_benchmarks/`)

| File Name | Generating Script | CLI Command | Description |
| :--- | :--- | :--- | :--- |
| **`benchmark_results.json`** | [`dispatcher/evaluation/evaluate.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/evaluate.py) | `python3 dispatcher/evaluation/evaluate.py --model dispatcher/models/best_model.zip --disruption train_delay` | 1-hour morning rush disruption benchmark comparing Static, FIFO, Priority Greedy, and PPO under a 420-second train delay perturbation. |
| **`retrained_500k_disruption_benchmark.json`** | [`dispatcher/training/retrain_500k.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/training/retrain_500k.py) | `python3 dispatcher/training/retrain_500k.py` | Automated post-training verification benchmark produced upon completing the 500,000-step curriculum. |
| **`option1_disruption_eval.json`** | [`dispatcher/training/train_multiday_option1.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/training/train_multiday_option1.py) | `python3 dispatcher/training/train_multiday_option1.py` | Knock-on delay mitigation audit under synthetic delay injection on the 242-run composite fleet. |

---

### 5. Severe Stress Testing (`dispatcher/logs/evaluations/stress_tests/`)

| File Name | Generating Script | CLI Command | Description |
| :--- | :--- | :--- | :--- |
| **`stress_testing_benchmark.json`** | [`dispatcher/evaluation/audit_stress_testing.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/audit_stress_testing.py) | `python3 dispatcher/evaluation/audit_stress_testing.py` | Multi-scenario stress audit comparing models under platform blockages, cascading primary delays, and stochastic delays. |
| **`stress_phase_A_24h.json`** | [`dispatcher/evaluation/audit_stress_24h_all_days.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/audit_stress_24h_all_days.py) | `python3 dispatcher/evaluation/audit_stress_24h_all_days.py --phase A` | 24-hour simulation across all 7 days with persistent peak-hour primary train delay perturbations. |
| **`stress_phase_B_24h.json`** | [`dispatcher/evaluation/audit_stress_24h_all_days.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/audit_stress_24h_all_days.py) | `python3 dispatcher/evaluation/audit_stress_24h_all_days.py --phase B` | 24-hour simulation across all 7 days under major city platform corridor blockages. |

---

### 6. Multi-Agent Audits (`dispatcher/logs/evaluations/marl_audits/`)

| File Name | Generating Script | CLI Command | Description |
| :--- | :--- | :--- | :--- |
| **`marl_vs_centralized_benchmark.json`** | [`dispatcher/evaluation/audit_marl_comparison.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/audit_marl_comparison.py) | `python3 dispatcher/evaluation/audit_marl_comparison.py` | Peak morning commuter comparison benchmarking Decentralized MAPPO (7 agents) vs Centralized PPO vs FIFO vs Static baseline across delays, action counts, and telemetry bandwidth. |

---

### 7. Visual Proofs & Charts (`dispatcher/logs/visual_proofs/`)

This directory contains 11 publication-ready, high-resolution (150-200 DPI) visualization artifacts tracking network performance across disruption benchmarks, stress testing, 7-day 24-hour diurnal timelines, and multi-agent comparisons.

#### Group A: Disruption Benchmark Visual Proofs
* **Generating Script:** [`dispatcher/evaluation/visualizer.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/visualizer.py)
* **Command:** `python3 dispatcher/evaluation/visualizer.py --json dispatcher/logs/evaluations/disruption_benchmarks/benchmark_results.json --output-dir dispatcher/logs/visual_proofs`
* **Artifacts:**
  * **`benchmark_delay_comparison.png`**: High-resolution bar chart comparing Mean Delay and Max Delay across Static, FIFO, Priority Greedy, and Trained PPO Dispatchers.
  * **`benchmark_delay_timeline.png`**: Minute-by-minute delay recovery timeline illustrating secondary delay propagation curves vs. active RL suppression.
  * **`benchmark_punctuality_knockon.png`**: Multi-panel visualization comparing Schedule Punctuality (<3m delay) and Secondary Knock-On delay event suppression (100% elimination).

#### Group B: Peak Morning Disruption Stress-Testing Visual Proofs
* **Generating Script:** [`dispatcher/evaluation/visualize_stress_test.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/visualize_stress_test.py)
* **Command:** `python3 dispatcher/evaluation/visualize_stress_test.py --json dispatcher/logs/evaluations/stress_tests/stress_testing_benchmark.json --output-dir dispatcher/logs/visual_proofs`
* **Artifacts:**
  * **`stress_test_delay_comparison.png`**: Comparative bar chart evaluating Mean Delay across the 4 stress scenarios (10-min Train Breakdown, 30-min Hub Platform Closure, 15% Fleet Dwell Jitter, and Compound Failure).
  * **`stress_test_knockon_cascades.png`**: Comparison of secondary knock-on event counts across disruption scenarios.
  * **`stress_test_punctuality.png`**: Schedule punctuality retention rates (%) under simultaneous rolling-stock and platform failures.

#### Group C: Full 7-Day 24-Hour Diurnal & Calendar Visual Proofs
* **Generating Script:** [`dispatcher/evaluation/visualize_weekly_audit.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/visualize_weekly_audit.py)
* **Command:** `python3 dispatcher/evaluation/visualize_weekly_audit.py --json dispatcher/logs/evaluations/weekly_audits/cross_comparison_24h.json --output-dir dispatcher/logs/visual_proofs`
* **Artifacts:**
  * **`weekly_7day_delay_comparison.png`**: Day-by-day (Monday through Sunday) delay comparison bar chart across all 1,446 services, illustrating PPO's dominance (39.86s global weekly delay vs 46.89s Priority Greedy, 48.34s Centralized PPO, 50.07s FIFO, and 236.20s Static).
  * **`weekly_7day_knockon_cascades.png`**: Day-by-day secondary knock-on conflict counts showing cascade reduction (10,878 Static -> 901 FIFO, 913 Priority Greedy, 918 Centralized PPO, 980 Trained PPO, and 5,645 MAPPO events).
  * **`weekly_7day_punctuality.png`**: Day-by-day schedule punctuality rates across all 7 calendar days (98.0% - 99.5%).
  * **`weekly_24h_diurnal_timeline.png`**: 24-hour continuous timeline (00:00 to 24:00) tracking network-wide delay curves through early morning feeder, morning peak, midday base, evening peak, and nocturnal freight waves.

#### Group D: Multi-Agent MARL vs Centralized PPO Visual Proofs
* **Generating Script:** [`dispatcher/evaluation/visualize_marl.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/visualize_marl.py)
* **Command:** `python3 dispatcher/evaluation/visualize_marl.py`
* **Artifacts:**
  * **`marl_vs_centralized_comparison.png`**: 4-panel publication-grade comparison of Mean Delay, Max Peak Delay, Control Action Interventions (Concurrency), and Telemetry Transmission Bandwidth.


