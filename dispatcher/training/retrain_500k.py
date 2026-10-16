#!/usr/bin/env python3
"""
retrain_500k.py
Master 500K+ Timesteps Retraining Pipeline for Autonomous Railway Dispatcher.

Addresses all critical flaws:
1. Multi-tier strengthened action penalties (3.5x - 7x) + per-dimension penalties on nominal trains.
2. Verified on-time departure tracking in _refresh_train_states().
3. Deep RL convergence with n_steps=2048, batch_size=256, 8 parallel workers over 500,000 timesteps.
4. Comprehensive multi-wave and multi-calendar generalization:
   - Stage 1: Morning Commuter Peak (100,000 steps)
   - Stage 2: Evening Commuter Peak (100,000 steps)
   - Stage 3: Full 24-Hour Continuous Fleet (200,000 steps)
   - Stage 4: Multi-Calendar Generalization: Monday (50,000 steps) + Saturday (50,000 steps)
   - Stage 5: End-to-End Evaluation & Benchmark Audit
"""

import os
import sys
import time
import argparse
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
    parser = argparse.ArgumentParser(description="Retrain PPO Dispatcher with 500K+ Steps")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel SUMO workers")
    parser.add_argument("--n-steps", type=int, default=2048, help="Rollout steps per worker")
    parser.add_argument("--batch-size", type=int, default=256, help="Minibatch size")
    parser.add_argument("--eval-after", action="store_true", default=True, help="Run benchmarks after training")
    args = parser.parse_args()

    total_t0 = time.time()
    print("=" * 75)
    print("AUTONOMOUS RAILWAY DISPATCHER - 500K+ RETRAINING ORCHESTRATOR")
    print(f"Root:            {ROOT_DIR}")
    print(f"Parallel Workers: {args.workers}")
    print(f"Buffer n_steps:   {args.n_steps} (Total rollout buffer: {args.n_steps * args.workers})")
    print(f"Minibatch Size:   {args.batch_size}")
    print("=" * 75)

    # Ensure master composite schedule is loaded initially
    run_command(
        [PYTHON, "trains/scripts/export_to_sumo.py", "-d", "all"],
        "Restore Master Composite Timetable (242 Services)"
    )

    ckpt_stage1 = os.path.join(MODELS_DIR, "ppo_stage1_morning_peak.zip")
    ckpt_stage2 = os.path.join(MODELS_DIR, "ppo_stage2_evening_peak.zip")
    ckpt_stage3 = os.path.join(MODELS_DIR, "ppo_stage3_full_day.zip")
    ckpt_stage4_mon = os.path.join(MODELS_DIR, "ppo_stage4_monday.zip")
    ckpt_stage4_sat = os.path.join(MODELS_DIR, "ppo_stage4_saturday.zip")
    final_model = os.path.join(MODELS_DIR, "ppo_dispatcher_final.zip")
    best_model = os.path.join(MODELS_DIR, "best_model.zip")

    # -----------------------------------------------------------------
    # Stage 1: Morning Commuter Peak (07:00-09:30) - 100,000 steps
    # -----------------------------------------------------------------
    cmd_s1 = [
        PYTHON, "dispatcher/training/train.py",
        "--wave", "morning_peak",
        "--timesteps", "100000",
        "--workers", str(args.workers),
        "--n-steps", str(args.n_steps),
        "--batch-size", str(args.batch_size),
        "--model-name", "ppo_stage1_morning_peak.zip"
    ]
    run_command(cmd_s1, "Stage 1: Morning Commuter Peak Convergence (100,000 steps)")

    # -----------------------------------------------------------------
    # Stage 2: Evening Commuter Peak (16:00-18:45) - 100,000 steps
    # -----------------------------------------------------------------
    cmd_s2 = [
        PYTHON, "dispatcher/training/train.py",
        "--wave", "evening_peak",
        "--timesteps", "100000",
        "--workers", str(args.workers),
        "--n-steps", str(args.n_steps),
        "--batch-size", str(args.batch_size),
        "--load-model", ckpt_stage1,
        "--model-name", "ppo_stage2_evening_peak.zip"
    ]
    run_command(cmd_s2, "Stage 2: Evening Commuter Peak Convergence (100,000 steps)")

    # -----------------------------------------------------------------
    # Stage 3: Full 24-Hour Continuous Fleet (05:00-23:00) - 200,000 steps
    # -----------------------------------------------------------------
    cmd_s3 = [
        PYTHON, "dispatcher/training/train.py",
        "--wave", "full_day",
        "--timesteps", "200000",
        "--workers", str(args.workers),
        "--n-steps", str(args.n_steps),
        "--batch-size", str(args.batch_size),
        "--load-model", ckpt_stage2,
        "--model-name", "ppo_stage3_full_day.zip"
    ]
    run_command(cmd_s3, "Stage 3: Full 24-Hour Continuous Fleet (200,000 steps)")

    # -----------------------------------------------------------------
    # Stage 4A: Multi-Calendar Generalization - Monday Surges (50,000 steps)
    # -----------------------------------------------------------------
    run_command(
        [PYTHON, "trains/scripts/export_to_sumo.py", "-d", "Mon"],
        "Export Monday Timetable (232 services)"
    )
    cmd_s4a = [
        PYTHON, "dispatcher/training/train.py",
        "--wave", "morning_peak",
        "--timesteps", "50000",
        "--workers", str(args.workers),
        "--n-steps", str(args.n_steps),
        "--batch-size", str(args.batch_size),
        "--load-model", ckpt_stage3,
        "--model-name", "ppo_stage4_monday.zip"
    ]
    run_command(cmd_s4a, "Stage 4A: Monday Commuter Surge Fine-Tuning (50,000 steps)")

    # -----------------------------------------------------------------
    # Stage 4B: Multi-Calendar Generalization - Saturday Leisure Base (50,000 steps)
    # -----------------------------------------------------------------
    run_command(
        [PYTHON, "trains/scripts/export_to_sumo.py", "-d", "Sat"],
        "Export Saturday Timetable (145 services)"
    )
    cmd_s4b = [
        PYTHON, "dispatcher/training/train.py",
        "--wave", "midday_base",
        "--timesteps", "50000",
        "--workers", str(args.workers),
        "--n-steps", str(args.n_steps),
        "--batch-size", str(args.batch_size),
        "--load-model", ckpt_stage4_mon,
        "--model-name", "ppo_stage4_saturday.zip"
    ]
    run_command(cmd_s4b, "Stage 4B: Saturday Leisure Clockface Fine-Tuning (50,000 steps)")

    # -----------------------------------------------------------------
    # Finalize Active Checkpoints
    # -----------------------------------------------------------------
    run_command(
        [PYTHON, "trains/scripts/export_to_sumo.py", "-d", "all"],
        "Restore Master Composite Timetable (242 Services)"
    )

    import shutil
    shutil.copy2(ckpt_stage4_sat, final_model)
    shutil.copy2(ckpt_stage4_sat, best_model)
    print(f"[✓] Deployed final 500K model to {final_model}")
    print(f"[✓] Updated system production best model: {best_model}")

    # -----------------------------------------------------------------
    # Stage 5: Evaluation Benchmark
    # -----------------------------------------------------------------
    if args.eval_after:
        eval_json = os.path.join(EVAL_DIR, "retrained_500k_disruption_benchmark.json")
        cmd_eval = [
            PYTHON, "dispatcher/evaluation/evaluate.py",
            "--model", best_model,
            "--disruption", "train_delay",
            "--start-time", "25200",
            "--horizon", "3600",
            "--output-json", eval_json
        ]
        run_command(cmd_eval, "Stage 5A: Disruption Benchmark Evaluation vs Heuristics")

        cmd_viz = [
            PYTHON, "dispatcher/evaluation/visualizer.py",
            "--json", eval_json,
            "--output-dir", VIZ_DIR
        ]
        run_command(cmd_viz, "Stage 5B: Generate Visual Proof Charts")

    total_time = time.time() - total_t0
    print("\n" + "=" * 75)
    print(f"[★] 500,000-STEP RETRAINING COMPLETED IN {total_time/60:.2f} MINUTES!")
    print(f"[★] Final Model Checkpoint: {final_model}")
    print(f"[★] Production Model:       {best_model}")
    print("=" * 75)


if __name__ == "__main__":
    main()
