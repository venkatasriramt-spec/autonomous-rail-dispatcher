#!/usr/bin/env python3
"""
train_mappo_curriculum.py
Master Multi-Agent PPO (MAPPO) Curriculum Training Orchestrator.
Executes multi-wave diurnal curriculum phases sequentially across high-core CPU hardware:
  - Phase 1: Nocturnal Freight Wave (21:30 - 02:30) - Alpine passing loops & mixed freight-passenger speeds
  - Phase 2: Evening Commuter Peak (16:00 - 18:45) - High-density reverse commuter flows
  - Phase 3: Sunday Staging & Platform Calibration (08:00 - 12:00) - Weekend buffer staging & platform 1 rules
  - Phase 4: Full-Day Continuous Fleet (05:00 - 23:00) - Full 24-hour diurnal consolidation (242 runs / 31 rakes)
"""

import os
import sys
import time
import subprocess
import argparse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

MODELS_DIR = os.path.join(ROOT_DIR, "dispatcher", "models")
os.makedirs(MODELS_DIR, exist_ok=True)

PYTHON = sys.executable
BASE_MODEL = os.path.join(MODELS_DIR, "mappo_interlocking.pt")
BEST_MODEL = os.path.join(MODELS_DIR, "mappo_best.pt")


def run_phase(cmd: list, desc: str) -> float:
    print("\n" + "=" * 90)
    print(f"[*] STARTING CURRICULUM PHASE: {desc}")
    print(f"[*] COMMAND: {' '.join(cmd)}")
    print("=" * 90)
    t0 = time.time()
    res = subprocess.run(cmd, cwd=ROOT_DIR)
    elapsed = time.time() - t0
    if res.returncode != 0:
        print(f"[!] FAILED: {desc} (Exit code: {res.returncode}, Time: {elapsed:.1f}s)")
        sys.exit(res.returncode)
    print(f"[✓] COMPLETED: {desc} (Elapsed: {elapsed:.1f}s / {elapsed/60:.2f} min)")
    return elapsed


def main():
    parser = argparse.ArgumentParser(description="Multi-Wave MAPPO Curriculum Training Orchestrator")
    parser.add_argument("--workers", type=int, default=16, help="Number of parallel SUMO workers (utilizing 32 CPU cores)")
    parser.add_argument("--steps-per-phase", type=int, default=10240, help="Timesteps per intermediate curriculum wave")
    parser.add_argument("--full-day-steps", type=int, default=15360, help="Timesteps for full-day consolidation wave")
    parser.add_argument("--start-phase", type=int, default=1, choices=[1, 2, 3, 4], help="Starting curriculum phase (1..4)")
    args = parser.parse_args()

    total_t0 = time.time()
    print("=" * 90)
    print("AUTONOMOUS RAILWAY DISPATCHER: MAPPO MULTI-WAVE DIURNAL CURRICULUM")
    print(f"Root: {ROOT_DIR}")
    print(f"Hardware: 32 CPU Cores | Parallel Workers: {args.workers}")
    print(f"Steps per Wave: {args.steps_per_phase} | Full Day Steps: {args.full_day_steps}")
    print(f"Initial Weights: {BASE_MODEL if os.path.exists(BASE_MODEL) else 'Random Init'}")
    print("=" * 90)

    # -------------------------------------------------------------
    # Phase 1: Nocturnal Freight Wave (21:30 - 02:30)
    # -------------------------------------------------------------
    if args.start_phase <= 1:
        cmd_p1 = [
            PYTHON, "dispatcher/training/train_mappo.py",
            "--wave", "nocturnal_freight",
            "--timesteps", str(args.steps_per_phase),
            "--workers", str(args.workers),
            "--save-path", BASE_MODEL,
            "--best-path", os.path.join(MODELS_DIR, "mappo_best_nocturnal_freight.pt")
        ]
        if os.path.exists(BASE_MODEL):
            cmd_p1.extend(["--load-checkpoint", BASE_MODEL])
        run_phase(cmd_p1, "Phase 1: Nocturnal Freight & Logistics Wave (21:30-02:30, Alpine Overtakes)")

    # -------------------------------------------------------------
    # Phase 2: Evening Commuter Peak (16:00 - 18:45)
    # -------------------------------------------------------------
    if args.start_phase <= 2:
        cmd_p2 = [
            PYTHON, "dispatcher/training/train_mappo.py",
            "--wave", "evening_peak",
            "--timesteps", str(args.steps_per_phase),
            "--workers", str(args.workers),
            "--load-checkpoint", BASE_MODEL,
            "--save-path", BASE_MODEL,
            "--best-path", os.path.join(MODELS_DIR, "mappo_best_evening_peak.pt")
        ]
        run_phase(cmd_p2, "Phase 2: Evening Commuter Peak Wave (16:00-18:45, High-Density Reverse Commute)")

    # -------------------------------------------------------------
    # Phase 3: Sunday Staging & Platform Calibration (08:00 - 12:00)
    # -------------------------------------------------------------
    if args.start_phase <= 3:
        cmd_p3 = [
            PYTHON, "dispatcher/training/train_mappo.py",
            "--wave", "sunday_staging",
            "--day", "Sun",
            "--timesteps", str(args.steps_per_phase),
            "--workers", str(args.workers),
            "--load-checkpoint", BASE_MODEL,
            "--save-path", BASE_MODEL,
            "--best-path", os.path.join(MODELS_DIR, "mappo_best_sunday_staging.pt")
        ]
        run_phase(cmd_p3, "Phase 3: Sunday Platform Staging & Turnaround Calibration (08:00-12:00, Platform 1 Buffer)")

    # -------------------------------------------------------------
    # Phase 4: Full-Day Continuous Fleet (05:00 - 23:00)
    # -------------------------------------------------------------
    if args.start_phase <= 4:
        cmd_p4 = [
            PYTHON, "dispatcher/training/train_mappo.py",
            "--wave", "full_day",
            "--timesteps", str(args.full_day_steps),
            "--workers", str(args.workers),
            "--load-checkpoint", BASE_MODEL,
            "--save-path", BASE_MODEL,
            "--best-path", os.path.join(MODELS_DIR, "mappo_best_full_day.pt")
        ]
        run_phase(cmd_p4, "Phase 4: Full 24-Hour Continuous Fleet Synthesis (05:00-23:00, 242 Runs / 31 Rakes)")

    total_elapsed = time.time() - total_t0
    print("\n" + "=" * 90)
    print(f"[✓] MAPPO MULTI-WAVE CURRICULUM TRAINING COMPLETE IN {total_elapsed:.1f}s ({total_elapsed/60:.2f} min)!")
    print(f"[✓] Final Consolidated Checkpoint: {BASE_MODEL}")
    print(f"[✓] Best Validation Model:         {BEST_MODEL}")
    print("=" * 90)


if __name__ == "__main__":
    main()
