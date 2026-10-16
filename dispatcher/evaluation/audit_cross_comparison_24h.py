#!/usr/bin/env python3
"""
audit_cross_comparison_24h.py
Runs a full 24-hour (00:00 to 24:00, 86,400s) microscopic evaluation across ALL 7 DAYS of the week,
cross-comparing all four dispatcher models:
1. Static_Baseline (Unmanaged timetable reference)
2. FIFO_Heuristic (Greedy platform reallocation)
3. Priority_Greedy_Heuristic (Rule-based class priority right-of-way)
4. Trained_PPO_Dispatcher (Main Deep RL Policy)

Executes 28 parallel worker runs across the 32-core VM for maximum speed.
"""

import os
import sys
import json
import time
import shutil
import xml.etree.ElementTree as ET
import multiprocessing as mp
import numpy as np
from typing import Dict, Any, List, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dispatcher.envs.railway_dispatch_env import RailwayDispatchEnv
from dispatcher.agents.baseline_dispatchers import (
    StaticDispatcher,
    FIFODispatcher,
    PriorityGreedyDispatcher
)
from dispatcher.evaluation.evaluate import ModelAgentWrapper
from trains.scripts.export_to_sumo import compile_sumo_files

LOGS_DIR = os.path.join(ROOT_DIR, "dispatcher", "logs", "evaluations", "weekly_audits")
MODEL_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "best_model.zip")
DAYS_DIR = os.path.join(ROOT_DIR, "trains", "sumo_config", "days")

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_SERVICE_COUNTS = {
    "Mon": 232, "Tue": 233, "Wed": 229,
    "Thu": 235, "Fri": 231, "Sat": 145, "Sun": 141
}

DISPATCHER_TYPES = [
    "Static_Baseline",
    "FIFO_Heuristic",
    "Priority_Greedy_Heuristic",
    "Trained_PPO_Dispatcher"
]

SIM_HORIZON_SEC = 86400.0  # Full 24 Hours
MACRO_STEP_SEC = 15.0      # 15-second dispatcher interval


def prepare_day_config(day: str):
    """Ensures each day has its isolated SUMO config and routes."""
    day_folder = os.path.join(DAYS_DIR, day)
    os.makedirs(day_folder, exist_ok=True)

    cfg_file = os.path.join(day_folder, "train_simulation.sumocfg")
    rou_file = os.path.join(day_folder, "trains_rakes.rou.xml")

    # If already prepared and valid, skip re-export
    if os.path.exists(cfg_file) and os.path.exists(rou_file):
        return

    compile_sumo_files(mode="rakes", day=day)
    src_cfg = os.path.join(ROOT_DIR, "trains", "sumo_config", "train_simulation.sumocfg")
    src_rou = os.path.join(ROOT_DIR, "trains", "sumo_config", "trains_rakes.rou.xml")
    src_view = os.path.join(ROOT_DIR, "trains", "sumo_config", "viewsettings.xml")

    shutil.copy(src_cfg, cfg_file)
    shutil.copy(src_rou, rou_file)
    shutil.copy(src_rou, os.path.join(day_folder, "trains.rou.xml"))
    if os.path.exists(src_view):
        shutil.copy(src_view, os.path.join(day_folder, "viewsettings.xml"))

    net_path = os.path.join(ROOT_DIR, "tracks", "network_data", "dense_network.net.xml")
    add_path = os.path.join(ROOT_DIR, "tracks", "network_data", "dense_network.add.xml")

    tree = ET.parse(cfg_file)
    root = tree.getroot()
    root.find("input/net-file").attrib["value"] = os.path.relpath(net_path, day_folder)
    root.find("input/additional-files").attrib["value"] = os.path.relpath(add_path, day_folder)
    root.find("input/route-files").attrib["value"] = "trains_rakes.rou.xml"
    tree.write(cfg_file)


def run_cross_eval_worker(task: Tuple[str, str]) -> Dict[str, Any]:
    """
    Worker process running a single dispatcher on a single day for the full 24 hours.
    task: (day, dispatcher_name)
    """
    day, disp_name = task
    day_cfg = os.path.join(DAYS_DIR, day, "train_simulation.sumocfg")
    t0 = time.time()

    # Instantiate dispatcher
    if disp_name == "Static_Baseline":
        agent = StaticDispatcher()
    elif disp_name == "FIFO_Heuristic":
        agent = FIFODispatcher()
    elif disp_name == "Priority_Greedy_Heuristic":
        agent = PriorityGreedyDispatcher()
    elif disp_name == "Trained_PPO_Dispatcher":
        agent = ModelAgentWrapper(MODEL_PATH)
    else:
        raise ValueError(f"Unknown dispatcher: {disp_name}")

    env = RailwayDispatchEnv(
        sumocfg_path=day_cfg,
        start_time_sec=0.0,
        sim_horizon_sec=SIM_HORIZON_SEC,
        macro_step_sec=MACRO_STEP_SEC,
        gui=False
    )

    obs, info = env.reset()
    delays_history = []
    punc_history = []
    active_history = []
    step = 0
    actions_taken = 0
    route_diverts = 0
    plat_switches = 0
    holds_applied = 0
    terminated = False
    truncated = False

    while not (terminated or truncated):
        action = agent.predict(obs, info)
        r_act, p_act, h_act = int(action[0]), int(action[1]), int(action[2])

        if r_act > 0 or p_act > 0 or h_act > 0:
            actions_taken += 1
        if r_act > 0:
            route_diverts += 1
        if p_act > 0:
            plat_switches += 1
        if h_act > 0:
            holds_applied += 1

        obs, reward, terminated, truncated, info = env.step(action)
        delays_history.append(info.get("mean_delay_sec", 0.0))
        punc_history.append(info.get("punctuality_pct", 100.0))
        active_history.append(info.get("active_trains", 0))
        step += 1

    env.close()
    elapsed = time.time() - t0

    mean_delay = float(np.mean(delays_history)) if delays_history else 0.0
    max_delay = float(np.max(delays_history)) if delays_history else 0.0
    punctuality = float(np.mean(punc_history)) if punc_history else 100.0
    knock_on_events = info.get("knock_on_events", 0)
    peak_active = max(active_history) if active_history else 0

    print(f"[{day} | {disp_name:<25}] 24h Done in {elapsed/60:.2f}m | Delay: {mean_delay:>6.2f}s | Punc: {punctuality:>5.1f}% | Knock-ons: {knock_on_events:>6}")

    return {
        "day": day,
        "dispatcher": disp_name,
        "services": DAY_SERVICE_COUNTS.get(day, 0),
        "elapsed_sec": round(elapsed, 1),
        "steps_simulated": step,
        "peak_active_trains": peak_active,
        "mean_delay_sec": round(mean_delay, 2),
        "max_delay_sec": round(max_delay, 1),
        "punctuality_pct": round(punctuality, 1),
        "knock_on_events": knock_on_events,
        "actions_taken": actions_taken,
        "action_breakdown": {
            "route_diversions": route_diverts,
            "platform_switches": plat_switches,
            "holds": holds_applied
        }
    }


def main():
    print("=" * 95)
    print("AUTONOMOUS TRAIN DISPATCHER: FULL 24-HOUR 4-MODEL CROSS-COMPARISON BENCHMARK")
    print(f"Operational Horizon: 00:00 to 24:00 (86,400s) | Cadence: {MACRO_STEP_SEC}s (5,760 steps/day)")
    print(f"Models Audited: Static_Baseline, FIFO_Heuristic, Priority_Greedy, Trained_PPO_Dispatcher")
    print(f"Execution: 28 Parallel Tasks across 32 vCPUs on VM Host")
    print("=" * 95)

    if not os.path.exists(MODEL_PATH):
        print(f"[!] Error: Main model checkpoint not found at {MODEL_PATH}")
        sys.exit(1)

    t0 = time.time()

    # Step 1: Ensure all day configs are ready
    print("\n[*] Verifying 7-day isolated configurations...")
    for day in DAYS:
        prepare_day_config(day)

    # Restore master composite schedule in root config
    print("[*] Restoring root master composite schedule (-d all)...")
    compile_sumo_files(mode="rakes", day="all")

    # Step 2: Build task matrix (7 days x 4 dispatchers = 28 runs)
    tasks = []
    for day in DAYS:
        for disp in DISPATCHER_TYPES:
            tasks.append((day, disp))

    print(f"\n[*] Launching 28 parallel 24-hour simulation runs in worker pool...")
    with mp.Pool(processes=28) as pool:
        results = pool.map(run_cross_eval_worker, tasks)

    total_time = time.time() - t0

    # Step 3: Save full JSON report
    os.makedirs(LOGS_DIR, exist_ok=True)
    out_json = os.path.join(LOGS_DIR, "cross_comparison_24h.json")
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 95)
    print(f"ALL 28 RUNS COMPLETED IN {total_time/60:.2f} MINUTES ({total_time:.1f}s)!")
    print(f"Detailed results saved to: {out_json}")
    print("=" * 95)

    # Organize results by Day
    day_map = {d: {} for d in DAYS}
    for r in results:
        day_map[r["day"]][r["dispatcher"]] = r

    # Step 4: Print Full Weekly Cross-Comparison Table
    print("\n" + "=" * 115)
    print(f"{'Day':<5} | {'Dispatcher Model':<26} | {'Mean Delay':<11} | {'Max Delay':<10} | {'Punctuality':<12} | {'Knock-ons':<11} | {'Interventions'}")
    print("-" * 115)
    for day in DAYS:
        for disp in DISPATCHER_TYPES:
            r = day_map[day][disp]
            print(f"{day:<5} | {disp:<26} | {r['mean_delay_sec']:>7.2f}s   | {r['max_delay_sec']:>7.1f}s  | {r['punctuality_pct']:>8.1f}%   | {r['knock_on_events']:>9}   | {r['actions_taken']:>6}")
        print("-" * 115)

    # Step 5: Print Global Weekly Summary
    print("\n" + "=" * 95)
    print("GLOBAL WEEKLY AGGREGATE SUMMARY (Averaged Across All 7 Days of the Week):")
    print("=" * 95)
    print(f"{'Dispatcher Model':<28} | {'Avg Mean Delay':<15} | {'Avg Punctuality':<16} | {'Total Weekly Knock-ons':<24} | {'Delay Reduction'}")
    print("-" * 95)

    model_aggregates = {}
    static_avg_delay = 0.0

    for disp in DISPATCHER_TYPES:
        disp_results = [r for r in results if r["dispatcher"] == disp]
        avg_mean_del = float(np.mean([r["mean_delay_sec"] for r in disp_results]))
        avg_punc = float(np.mean([r["punctuality_pct"] for r in disp_results]))
        tot_knockons = sum(r["knock_on_events"] for r in disp_results)
        model_aggregates[disp] = {
            "avg_delay": avg_mean_del,
            "avg_punc": avg_punc,
            "total_knockons": tot_knockons
        }
        if disp == "Static_Baseline":
            static_avg_delay = avg_mean_del

    for disp in DISPATCHER_TYPES:
        agg = model_aggregates[disp]
        red_str = "Baseline"
        if disp != "Static_Baseline" and static_avg_delay > 0:
            pct_red = ((static_avg_delay - agg["avg_delay"]) / static_avg_delay) * 100.0
            red_str = f"{pct_red:+.1f}%"
        print(f"{disp:<28} | {agg['avg_delay']:>10.2f}s    | {agg['avg_punc']:>11.1f}%    | {agg['total_knockons']:>18}     | {red_str}")
    print("=" * 95)


if __name__ == "__main__":
    main()
