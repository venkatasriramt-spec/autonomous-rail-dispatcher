#!/usr/bin/env python3
"""
train_multiday_option1.py
Option 1: Multi-Calendar Day Generalization & "Do-Nothing" Timetable Bias Training.

Executes:
1. Export Monday schedule (232 services, weekday commuter surges).
2. Fine-tune PPO policy on Monday with intervention penalty active (10,000 steps).
3. Export Saturday schedule (145 services, free-flowing weekend clockface).
4. Fine-tune PPO policy on Saturday with intervention penalty active (8,000 steps).
5. Audit Saturday performance (demonstrating elimination of artificial holds).
6. Restore master composite schedule (242 services).
7. Audit disruption response (demonstrating knock-on delay suppression).
8. Generate publication visual proof charts.
"""

import os
import sys
import time
import subprocess

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

MODELS_DIR = os.path.join(ROOT_DIR, "dispatcher", "models")
LOGS_DIR = os.path.join(ROOT_DIR, "dispatcher", "logs")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

PYTHON = sys.executable

def run_step(cmd, desc):
    print("\n" + "=" * 75)
    print(f"[*] STEP: {desc}")
    print(f"[*] CMD:  {' '.join(cmd)}")
    print("=" * 75)
    t0 = time.time()
    res = subprocess.run(cmd, cwd=ROOT_DIR)
    elapsed = time.time() - t0
    if res.returncode != 0:
        print(f"[!] FAILED: {desc} (Exit code: {res.returncode}, Elapsed: {elapsed:.1f}s)")
        sys.exit(res.returncode)
    print(f"[✓] COMPLETED: {desc} ({elapsed/60:.2f} min)")
    return elapsed

def main():
    total_t0 = time.time()
    best_model = os.path.join(MODELS_DIR, "best_model.zip")
    mon_model = os.path.join(MODELS_DIR, "ppo_monday_surge.zip")
    sat_model = os.path.join(MODELS_DIR, "ppo_saturday_base.zip")

    print("=" * 75)
    print("OPTION 1: MULTI-CALENDAR DAY GENERALIZATION & DO-NOTHING BIAS TRAINING")
    print(f"Root: {ROOT_DIR}")
    print(f"Base Checkpoint: {best_model}")
    print("=" * 75)

    # -------------------------------------------------------------
    # 1. Export Monday (232 services, weekday commuter surges)
    # -------------------------------------------------------------
    run_step(
        [PYTHON, "trains/scripts/export_to_sumo.py", "-d", "Mon"],
        "Export Monday Schedule (232 services)"
    )

    # -------------------------------------------------------------
    # 2. Train on Monday Commuter Schedule (10,000 steps)
    # -------------------------------------------------------------
    run_step(
        [
            PYTHON, "dispatcher/training/train.py",
            "--wave", "morning_peak",
            "--timesteps", "10000",
            "--workers", "8",
            "--load-model", best_model,
            "--model-name", "ppo_monday_surge.zip"
        ],
        "Train on Monday Schedule (10,000 steps with Intervention Penalty)"
    )

    # -------------------------------------------------------------
    # 3. Export Saturday (145 services, free-flowing weekend base)
    # -------------------------------------------------------------
    run_step(
        [PYTHON, "trains/scripts/export_to_sumo.py", "-d", "Sat"],
        "Export Saturday Schedule (145 services)"
    )

    # -------------------------------------------------------------
    # 4. Train on Saturday Leisure Schedule (8,000 steps)
    # -------------------------------------------------------------
    run_step(
        [
            PYTHON, "dispatcher/training/train.py",
            "--wave", "midday_base",
            "--timesteps", "8000",
            "--workers", "8",
            "--load-model", mon_model,
            "--model-name", "ppo_saturday_base.zip"
        ],
        "Train on Saturday Schedule (8,000 steps - Learning Do-Nothing / Timetable Adherence)"
    )

    # -------------------------------------------------------------
    # 5. Audit Saturday Nominal Performance (Verify 0 unnecessary holds)
    # -------------------------------------------------------------
    sat_audit_json = os.path.join(LOGS_DIR, "option1_saturday_eval.json")
    run_step(
        [
            PYTHON, "dispatcher/evaluation/evaluate.py",
            "--model", sat_model,
            "--disruption", "none",
            "--start-time", "25200",
            "--horizon", "3600",
            "--output", sat_audit_json
        ],
        "Audit Saturday Performance (Verify Elimination of Artificial Delays)"
    )

    # -------------------------------------------------------------
    # 6. Restore Master Composite Schedule (242 services)
    # -------------------------------------------------------------
    run_step(
        [PYTHON, "trains/scripts/export_to_sumo.py", "-d", "all"],
        "Restore Master Composite Schedule (242 services)"
    )

    # -------------------------------------------------------------
    # 7. Audit Disruption Response on Composite Fleet
    # -------------------------------------------------------------
    comp_audit_json = os.path.join(LOGS_DIR, "option1_disruption_eval.json")
    run_step(
        [
            PYTHON, "dispatcher/evaluation/evaluate.py",
            "--model", sat_model,
            "--disruption", "train_delay",
            "--start-time", "25200",
            "--horizon", "3600",
            "--output", comp_audit_json
        ],
        "Audit Disruption Response (Verify Knock-on Delay Mitigation)"
    )

    # -------------------------------------------------------------
    # 8. Generate Visual Proof Charts
    # -------------------------------------------------------------
    run_step(
        [
            PYTHON, "dispatcher/evaluation/visualizer.py",
            "--json", comp_audit_json,
            "--output-dir", LOGS_DIR
        ],
        "Generate Visual Proof Charts for Option 1"
    )

    total_time = time.time() - total_t0
    print("\n" + "=" * 75)
    print(f"[★] OPTION 1 MULTI-DAY TRAINING COMPLETE IN {total_time/60:.2f} MINUTES!")
    print(f"[★] Monday Checkpoint:   {mon_model}")
    print(f"[★] Saturday Checkpoint: {sat_model}")
    print(f"[★] Production Model:    {best_model}")
    print(f"[★] Saturday Audit:      {sat_audit_json}")
    print(f"[★] Disruption Audit:    {comp_audit_json}")
    print("=" * 75)

if __name__ == "__main__":
    main()
