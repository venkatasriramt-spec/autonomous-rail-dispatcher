#!/usr/bin/env python3
"""
train_curriculum.py
Master Autonomous Curriculum Training & Evaluation Orchestrator.
Executes all curriculum phases sequentially without manual intervention:
  - Phase 1A: Nocturnal Freight Wave (Already completed: ppo_nocturnal_freight.zip)
  - Phase 1B: Morning Commuter Peak (07:00-09:30)
  - Phase 2:  Multi-Day / Evening Commuter Peak (16:00-18:45)
  - Phase 3:  Full 24-Hour Continuous Fleet (05:00-23:00, 242 runs / 31 rakes)
  - Phase 4:  Comprehensive Disruption Stress Benchmark & Proof Generation
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
EVAL_DIR = os.path.join(LOGS_DIR, "evaluations", "disruption_benchmarks")
VIZ_DIR = os.path.join(LOGS_DIR, "visual_proofs")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(EVAL_DIR, exist_ok=True)
os.makedirs(VIZ_DIR, exist_ok=True)

PYTHON = sys.executable

def run_command(cmd, desc):
    print("\n" + "=" * 75)
    print(f"[*] STARTING: {desc}")
    print(f"[*] COMMAND:  {' '.join(cmd)}")
    print("=" * 75)
    t0 = time.time()
    res = subprocess.run(cmd, cwd=ROOT_DIR)
    elapsed = time.time() - t0
    if res.returncode != 0:
        print(f"[!] FAILED: {desc} (Exit code: {res.returncode}, Time: {elapsed:.1f}s)")
        sys.exit(res.returncode)
    print(f"[✓] COMPLETED: {desc} (Elapsed: {elapsed/60:.2f} min)")
    return elapsed

def main():
    total_t0 = time.time()
    print("=" * 75)
    print("AUTONOMOUS RAILWAY DISPATCHER - MASTER CURRICULUM PIPELINE")
    print(f"Subsystem Root: {ROOT_DIR}")
    print(f"PyTorch / CPU:  32 Cores | Vectorized SUMO Workers: 8")
    print("=" * 75)

    # -------------------------------------------------------------
    # Phase 1B: Morning Commuter Peak (07:00 - 09:30)
    # -------------------------------------------------------------
    ckpt_1b = os.path.join(MODELS_DIR, "ppo_commuter_peak.zip")
    if os.path.exists(ckpt_1b):
        print(f"[✓] Phase 1B already completed ({ckpt_1b}) - Reusing checkpoint.")
    else:
        cmd_1b = [
            PYTHON, "dispatcher/training/train.py",
            "--wave", "morning_peak",
            "--timesteps", "12000",
            "--workers", "8",
            "--load-model", os.path.join(MODELS_DIR, "ppo_nocturnal_freight.zip"),
            "--model-name", "ppo_commuter_peak.zip"
        ]
        run_command(cmd_1b, "Phase 1B: Morning Commuter Peak Wave (07:00-09:30)")

    # -------------------------------------------------------------
    # Phase 2: Evening Commuter Peak & Calendar Shifts (16:00 - 18:45)
    # -------------------------------------------------------------
    ckpt_2 = os.path.join(MODELS_DIR, "ppo_evening_peak.zip")
    if os.path.exists(ckpt_2):
        print(f"[✓] Phase 2 already completed ({ckpt_2}) - Reusing checkpoint.")
    else:
        cmd_2 = [
            PYTHON, "dispatcher/training/train.py",
            "--wave", "evening_peak",
            "--timesteps", "12000",
            "--workers", "8",
            "--load-model", os.path.join(MODELS_DIR, "ppo_commuter_peak.zip"),
            "--model-name", "ppo_evening_peak.zip"
        ]
        run_command(cmd_2, "Phase 2: Evening Commuter Peak Wave (16:00-18:45)")

    # -------------------------------------------------------------
    # Phase 3: Full 24-Hour Continuous Fleet (05:00 - 23:00)
    # -------------------------------------------------------------
    cmd_3 = [
        PYTHON, "dispatcher/training/train.py",
        "--wave", "full_day",
        "--timesteps", "16000",
        "--workers", "8",
        "--load-model", os.path.join(MODELS_DIR, "ppo_evening_peak.zip"),
        "--model-name", "ppo_full_day.zip"
    ]
    run_command(cmd_3, "Phase 3: Full 24-Hour Continuous Fleet (242 Services / 31 Rakes)")

    # -------------------------------------------------------------
    # Phase 4: Disruption Stress Benchmark & Evaluation Proof
    # -------------------------------------------------------------
    best_model = os.path.join(MODELS_DIR, "best_model.zip")
    eval_json = os.path.join(EVAL_DIR, "benchmark_results.json")
    cmd_4_eval = [
        PYTHON, "dispatcher/evaluation/evaluate.py",
        "--model", best_model,
        "--disruption", "train_delay",
        "--start-time", "25200",
        "--horizon", "3600",
        "--output-json", eval_json
    ]
    run_command(cmd_4_eval, "Phase 4A: Disruption Benchmark Evaluation vs Heuristics")

    # Generate Publication-Quality Visual Proof Charts
    cmd_4_viz = [
        PYTHON, "dispatcher/evaluation/visualizer.py",
        "--json", eval_json,
        "--output-dir", VIZ_DIR
    ]
    run_command(cmd_4_viz, "Phase 4B: Publication Visual Charts Generation")

    total_elapsed = time.time() - total_t0
    print("\n" + "=" * 75)
    print(f"[★] ALL CURRICULUM PHASES COMPLETED SUCCESSFULLY IN {total_elapsed/60:.2f} MINUTES!")
    print(f"[★] Production Checkpoint: {best_model}")
    print(f"[★] Evaluation Report:     {eval_json}")
    print(f"[★] Visual Charts:         {VIZ_DIR}/")
    print("=" * 75)

if __name__ == "__main__":
    main()
