#!/usr/bin/env python3
"""
train_and_benchmark_all.py
Master Orchestrator for Sequential Retraining and Full 7-Day Microscopic Evaluation:
1. Retrain Decentralized MAPPO 4-Wave Diurnal Curriculum on the bug-fixed environment.
2. Fine-tune Centralized PPO Policy on the corrected RewardEngine and interlocking dynamics.
3. Execute the Full 24-Hour 7-Day Microscopic Benchmark across all 5 models.
4. Generate the comparative delta report against the pre-fix baseline.
"""

import os
import sys
import time
import json
import subprocess
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

PYTHON = sys.executable
MODELS_DIR = os.path.join(ROOT_DIR, "dispatcher", "models")
LOGS_DIR = os.path.join(ROOT_DIR, "dispatcher", "logs", "evaluations", "weekly_audits")
PRE_FIX_JSON = os.path.join(LOGS_DIR, "cross_comparison_24h_pre_fix.json")
POST_FIX_JSON = os.path.join(LOGS_DIR, "cross_comparison_24h.json")


def run_stage(cmd: list, title: str) -> float:
    print("\n" + "=" * 95)
    print(f"[*] STARTING: {title}")
    print(f"[*] CMD: {' '.join(cmd)}")
    print("=" * 95)
    t0 = time.time()
    res = subprocess.run(cmd, cwd=ROOT_DIR)
    elapsed = time.time() - t0
    if res.returncode != 0:
        print(f"[!] STAGE FAILED: {title} (Exit code: {res.returncode}, Elapsed: {elapsed:.1f}s)")
        sys.exit(res.returncode)
    print(f"[✓] COMPLETED: {title} ({elapsed/60:.2f} min / {elapsed:.1f}s)")
    return elapsed


def compare_and_report():
    print("\n" + "=" * 105)
    print("PRE-FIX VS POST-RETRAINING COMPARATIVE AUDIT REPORT (ALL 7 DAYS, 24 HOURS)")
    print("=" * 105)

    if not os.path.exists(POST_FIX_JSON):
        print(f"[!] Error: {POST_FIX_JSON} not found. Comparison aborted.")
        return

    with open(POST_FIX_JSON, "r") as f:
        post_data = json.load(f)

    pre_data = []
    if os.path.exists(PRE_FIX_JSON):
        with open(PRE_FIX_JSON, "r") as f:
            pre_data = json.load(f)

    models = [
        "Static_Baseline",
        "FIFO_Heuristic",
        "Priority_Greedy_Heuristic",
        "Centralized_PPO",
        "Multi_Train_Centralized_PPO",
        "Decentralized_MAPPO",
        "Comm_MAPPO",
        "Hierarchical_Hybrid"
    ]

    print(f"{'Dispatcher Model':<28} | {'Avg Delay':<16} | {'Avg Punctuality':<16} | {'Weekly Knock-ons':<20} | {'Weekly Actions'}")
    print("-" * 105)

    for m in models:
        post_sub = [r for r in post_data if r["dispatcher"] == m]
        if not post_sub:
            continue

        post_del = float(np.mean([r["mean_delay_sec"] for r in post_sub]))
        post_punc = float(np.mean([r["punctuality_pct"] for r in post_sub]))
        post_ko = sum(r["knock_on_events"] for r in post_sub)
        post_acts = sum(r["actions_taken"] for r in post_sub)

        pre_sub = [r for r in pre_data if r["dispatcher"] == m]
        if pre_sub:
            pre_del = float(np.mean([r["mean_delay_sec"] for r in pre_sub]))
            pre_punc = float(np.mean([r["punctuality_pct"] for r in pre_sub]))
            pre_ko = sum(r["knock_on_events"] for r in pre_sub)
            pre_acts = sum(r["actions_taken"] for r in pre_sub)

            del_diff = post_del - pre_del
            punc_diff = post_punc - pre_punc
            ko_diff = post_ko - pre_ko
            act_diff = post_acts - pre_acts

            print(f"{m:<28} | {post_del:>6.2f}s ({del_diff:+5.2f}s) | {post_punc:>5.1f}% ({punc_diff:+4.1f}%) | {post_ko:>7} ({ko_diff:+7})  | {post_acts:>6} ({act_diff:+6})")
        else:
            print(f"{m:<28} | {post_del:>6.2f}s           | {post_punc:>5.1f}%           | {post_ko:>7}            | {post_acts:>6}")

    print("=" * 105)


def main():
    total_t0 = time.time()
    print("=" * 95)
    print("AUTONOMOUS RAILWAY DISPATCHER: MASTER RETRAINING & EVALUATION PIPELINE")
    print("Sequential Stages:")
    print("  Stage 1: Retrain Decentralized MAPPO Diurnal Curriculum (16 workers)")
    print("  Stage 2: Fine-Tune Centralized PPO Policy on Corrected Dynamics (16 workers)")
    print("  Stage 3: Full 24-Hour 7-Day 5-Model Microscopic Benchmark (28 workers)")
    print("  Stage 4: Automated Pre-Fix vs Post-Retraining Comparative Report")
    print("=" * 95)

    # Stage 1: Retrain MAPPO Curriculum across 6 Diurnal Waves (including Midday Glacier Wave)
    cmd_mappo = [
        PYTHON, "dispatcher/training/train_mappo_curriculum.py",
        "--workers", "24",
        "--steps-per-phase", "6144",
        "--full-day-steps", "12288"
    ]
    t1 = run_stage(cmd_mappo, "Stage 1: Decentralized MAPPO 6-Wave Curriculum Retraining (24 workers)")

    # Stage 2A: Deep Fine-Tune Centralized PPO on Monday Alpine Mountain Pass & Shuttle Wave (150k steps)
    best_ppo = os.path.join(MODELS_DIR, "best_model.zip")
    cmd_ppo_alpine = [
        PYTHON, "dispatcher/training/train.py",
        "--wave", "alpine_shuttle",
        "--timesteps", "147456",
        "--workers", "24",
        "--n-steps", "1024",
        "--batch-size", "256",
        "--load-model", best_ppo,
        "--model-name", "best_model.zip"
    ]
    t2a = run_stage(cmd_ppo_alpine, "Stage 2A: Centralized PPO Deep Alpine Fine-Tuning 150k steps (24 workers)")

    # Stage 2B: Fine-Tune Centralized PPO on Tuesday Midday Glacier Wave
    cmd_ppo_glacier = [
        PYTHON, "dispatcher/training/train.py",
        "--wave", "glacier_express",
        "--timesteps", "49152",
        "--workers", "24",
        "--n-steps", "1024",
        "--batch-size", "256",
        "--load-model", best_ppo,
        "--model-name", "best_model.zip"
    ]
    t2b = run_stage(cmd_ppo_glacier, "Stage 2B: Centralized PPO Midday Glacier Fine-Tuning (24 workers)")

    # Stage 2C: Consolidate Centralized PPO on Morning Peak
    cmd_ppo_peak = [
        PYTHON, "dispatcher/training/train.py",
        "--wave", "morning_peak",
        "--timesteps", "49152",
        "--workers", "24",
        "--n-steps", "1024",
        "--batch-size", "256",
        "--load-model", best_ppo,
        "--model-name", "best_model.zip"
    ]
    t2c = run_stage(cmd_ppo_peak, "Stage 2C: Centralized PPO Morning Peak Consolidation (24 workers)")

    # Invalidate any pre-existing post-fix results so a stale file cannot satisfy the check
    if os.path.exists(POST_FIX_JSON):
        try:
            os.remove(POST_FIX_JSON)
            print(f"[*] Cleared previous {os.path.basename(POST_FIX_JSON)} to ensure fresh evaluation results.")
        except OSError as e:
            print(f"\n[!] Error: Failed to remove pre-existing {POST_FIX_JSON}: {e}. Stopping pipeline to prevent stale results.")
            sys.exit(1)

    # Stage 3: Full 7-Day 24-Hour Benchmark
    cmd_bench = [
        PYTHON, "dispatcher/evaluation/audit_cross_comparison_24h.py",
        "--workers", "28"
    ]
    t3 = run_stage(cmd_bench, "Stage 3: Full 24-Hour 7-Day 5-Model Cross-Comparison Benchmark")

    # Stage 4: Comparative Report (proceed only if Stage 3 successfully produced POST_FIX_JSON in current run)
    if os.path.exists(POST_FIX_JSON):
        compare_and_report()
    else:
        print(f"\n[!] Error: Stage 3 completed but {POST_FIX_JSON} was not generated during this run.")
        sys.exit(1)

    total_elapsed = time.time() - total_t0
    print(f"\n[✓] ALL STAGES COMPLETED SUCCESSFULLY IN {total_elapsed/60:.2f} MINUTES ({total_elapsed:.1f}s)!")


if __name__ == "__main__":
    main()
