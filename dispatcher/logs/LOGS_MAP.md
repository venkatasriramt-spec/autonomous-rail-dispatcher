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
│   └── stress_tests/                 # Severe stress testing (Phases A & B across all days)
├── visual_proofs/                    # High-resolution PNG charts and visual comparisons
└── LOGS_MAP.md                       # This architectural reference map
```

---

## Detailed File & Script Mapping

### 1. Training Runs & TensorBoard Logs (`dispatcher/logs/tensorboard/`)
* **Generating Script:** [`dispatcher/training/train.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/training/train.py) or [`dispatcher/training/retrain_500k.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/training/retrain_500k.py)
* **Contents:** Subdirectories `PPO_1`, `PPO_2`, ..., `PPO_18`, etc.
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
| **`cross_comparison_24h.json`** | [`dispatcher/evaluation/audit_cross_comparison_24h.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/audit_cross_comparison_24h.py) | `python3 dispatcher/evaluation/audit_cross_comparison_24h.py` | Runs 28 parallel 24-hour simulations (7 days × 4 dispatchers: Static, FIFO, Priority Greedy, PPO). Compares mean delay, max delay, punctuality, knock-ons, and intervention counts across every day of the week. |
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

### 6. Visual Proofs & Charts (`dispatcher/logs/visual_proofs/`)

* **Generating Script:** [`dispatcher/evaluation/visualizer.py`](file:///home/venkatasriramt/Desktop/railway-simulation/dispatcher/evaluation/visualizer.py)
* **CLI Command:**
  ```bash
  python3 dispatcher/evaluation/visualizer.py --json dispatcher/logs/evaluations/disruption_benchmarks/benchmark_results.json --output-dir dispatcher/logs/visual_proofs
  ```
* **Artifacts:**
  * **`benchmark_delay_comparison.png`**: High-resolution bar chart comparing Mean and Max Delays across all 4 dispatchers.
  * **`benchmark_delay_timeline.png`**: Minute-by-minute delay recovery timeline showing delay propagation vs. mitigation curves.
  * **`benchmark_punctuality_knockon.png`**: Multi-panel visualization of Punctuality % and Knock-on Event counts.
