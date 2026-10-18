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
import argparse
import xml.etree.ElementTree as ET
import multiprocessing as mp
import numpy as np
from typing import Dict, Any, List, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dispatcher.envs.railway_dispatch_env import RailwayDispatchEnv
from dispatcher.envs.multi_agent_railway_env import MultiAgentRailwayEnv
from dispatcher.agents.baseline_dispatchers import (
    StaticDispatcher,
    FIFODispatcher,
    PriorityGreedyDispatcher
)
from dispatcher.evaluation.evaluate import ModelAgentWrapper
from dispatcher.agents.mappo_agent import MAPPODispatcher
from dispatcher.scenarios.perturbations import PerturbationConfig
from trains.scripts.export_to_sumo import compile_sumo_files

LOGS_DIR = os.path.join(ROOT_DIR, "dispatcher", "logs", "evaluations", "weekly_audits")
MODEL_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "best_model.zip")
MAPPO_MODEL_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "mappo_interlocking.pt")
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
    "Centralized_PPO",
    "Decentralized_MAPPO",
    "Hierarchical_Hybrid"
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


def run_cross_eval_worker(task: Tuple[str, str, str]) -> Dict[str, Any]:
    """
    Worker process running a single dispatcher on a single day for the full 24 hours.
    task: (day, dispatcher_name, disruption_mode)
    """
    day, disp_name, disruption_mode = task
    day_cfg = os.path.join(DAYS_DIR, day, "train_simulation.sumocfg")
    t0 = time.time()

    p_cfg = None
    if disruption_mode == "train_delay":
        p_cfg = PerturbationConfig(
            name="train_delay",
            mode="train_delay",
            trigger_time_sec=27000.0,      # 07:30 AM Morning Peak
            delay_duration_sec=600.0,       # 10 minutes
            seed=42
        )
    elif disruption_mode == "platform_blockage":
        p_cfg = PerturbationConfig(
            name="platform_blockage",
            mode="platform_blockage",
            blocked_lane_id="City_3_EW_plat_1_fw_0",
            trigger_time_sec=27000.0,
            blockage_duration_sec=1800.0,
            seed=42
        )

    is_marl = (disp_name == "Decentralized_MAPPO")
    if is_marl:
        agent = MAPPODispatcher(checkpoint_path=MAPPO_MODEL_PATH, exception_gating=True, smart_interlocking=True)
        env = MultiAgentRailwayEnv(
            sumocfg_path=day_cfg,
            start_time_sec=0.0,
            sim_horizon_sec=SIM_HORIZON_SEC,
            macro_step_sec=MACRO_STEP_SEC,
            perturbation_config=p_cfg,
            gui=False
        )
    else:
        if disp_name == "Static_Baseline":
            agent = StaticDispatcher()
        elif disp_name == "FIFO_Heuristic":
            agent = FIFODispatcher()
        elif disp_name == "Priority_Greedy_Heuristic":
            agent = PriorityGreedyDispatcher()
        elif disp_name in ("Trained_PPO_Dispatcher", "Centralized_PPO"):
            agent = ModelAgentWrapper(MODEL_PATH)
        elif disp_name in ("Hierarchical_Hybrid", "Hierarchical_Hybrid_Ensemble"):
            from dispatcher.agents.hybrid_dispatcher import HierarchicalHybridDispatcher
            agent = HierarchicalHybridDispatcher(MODEL_PATH, MAPPO_MODEL_PATH)
        else:
            raise ValueError(f"Unknown dispatcher: {disp_name}")

        env = RailwayDispatchEnv(
            sumocfg_path=day_cfg,
            start_time_sec=0.0,
            sim_horizon_sec=SIM_HORIZON_SEC,
            macro_step_sec=MACRO_STEP_SEC,
            perturbation_config=p_cfg,
            gui=False
        )

    obs, info = env.reset()
    delays_history = []
    peak_delays_history = []
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
        if is_marl:
            actions_dict = agent.predict(obs, info, deterministic=True)
            for aid, act in actions_dict.items():
                if aid.startswith("station_"):
                    p_act, h_act = int(act[0]), int(act[1])
                    if p_act > 0 or h_act > 0:
                        actions_taken += 1
                    if p_act > 0:
                        plat_switches += 1
                    if h_act > 0:
                        holds_applied += 1
                else:
                    r_act = int(act)
                    if r_act > 0:
                        actions_taken += 1
                        route_diverts += 1
            obs, rewards, term_dict, trunc_dict, info = env.step(actions_dict)
            terminated = term_dict.get("__all__", False)
            truncated = trunc_dict.get("__all__", False)
        else:
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
        peak_delays_history.append(info.get("max_delay_sec", info.get("mean_delay_sec", 0.0)))
        punc_history.append(info.get("punctuality_pct", 100.0))
        active_history.append(info.get("active_trains", 0))
        step += 1

    env.close()
    elapsed = time.time() - t0

    mean_delay = float(np.mean(delays_history)) if delays_history else 0.0
    max_delay = float(np.max(peak_delays_history)) if peak_delays_history else 0.0
    punctuality = float(np.mean(punc_history)) if punc_history else 100.0
    knock_on_events = info.get("knock_on_events", 0)
    peak_active = max(active_history) if active_history else 0

    steps_per_hour = int(3600.0 / MACRO_STEP_SEC)  # 240 steps/hour
    hourly_delays = []
    for h in range(24):
        h_start = h * steps_per_hour
        h_end = min((h + 1) * steps_per_hour, len(delays_history))
        if h_start < len(delays_history):
            hourly_delays.append(round(float(np.mean(delays_history[h_start:h_end])), 2))
        else:
            hourly_delays.append(0.0)

    print(f"[{day} | {disp_name:<26}] 24h Done in {elapsed/60:.2f}m | Delay: {mean_delay:>6.2f}s | Max: {max_delay:>6.1f}s | Punc: {punctuality:>5.1f}% | Knock-ons: {knock_on_events:>6}")

    return {
        "day": day,
        "dispatcher": disp_name,
        "disruption": disruption_mode,
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
        },
        "hourly_delays": hourly_delays
    }



def main():
    parser = argparse.ArgumentParser(description="Full 24-Hour 5-Model Weekly Cross-Comparison Benchmark")
    parser.add_argument("--disruption", type=str, default="none", choices=["none", "train_delay", "platform_blockage"],
                        help="Peak-hour disruption scenario to inject")
    parser.add_argument("--dispatchers", type=str, default=None,
                        help="Comma-separated dispatchers to audit (default: all 5)")
    parser.add_argument("--days", type=str, default=None,
                        help="Comma-separated days to audit (default: all 7 days Mon-Sun)")
    parser.add_argument("--workers", type=int, default=28, help="Number of parallel worker processes")
    parser.add_argument("--output-json", type=str, default=None, help="Custom output JSON path")
    args = parser.parse_args()

    selected_dispatchers = [d.strip() for d in args.dispatchers.split(",")] if args.dispatchers else DISPATCHER_TYPES
    selected_days = [d.strip() for d in args.days.split(",")] if args.days else DAYS

    invalid_days = [d for d in selected_days if d not in DAYS]
    if invalid_days:
        parser.error(f"Invalid days specified: {invalid_days}. Must be a subset of {DAYS}")

    print("=" * 95)
    print("AUTONOMOUS TRAIN DISPATCHER: FULL 24-HOUR 5-MODEL CROSS-COMPARISON BENCHMARK")
    print(f"Operational Horizon: 00:00 to 24:00 (86,400s) | Cadence: {MACRO_STEP_SEC}s (5,760 steps/day)")
    print(f"Days Audited: {', '.join(selected_days)}")
    print(f"Models Audited: {', '.join(selected_dispatchers)}")
    print(f"Disruption Mode: {args.disruption.upper()}")
    print(f"Execution: {len(selected_days) * len(selected_dispatchers)} Parallel Tasks across {args.workers} workers on VM Host")
    print("=" * 95)

    if not os.path.exists(MODEL_PATH):
        print(f"[!] Error: Main model checkpoint not found at {MODEL_PATH}")
        sys.exit(1)

    requires_mappo = any(d in selected_dispatchers for d in ("Decentralized_MAPPO", "Hierarchical_Hybrid", "Hierarchical_Hybrid_Ensemble"))
    if requires_mappo and not os.path.exists(MAPPO_MODEL_PATH):
        print(f"[!] Error: MAPPO model checkpoint not found at {MAPPO_MODEL_PATH}")
        sys.exit(1)

    t0 = time.time()

    # Step 1: Ensure all day configs are ready
    print("\n[*] Verifying isolated configurations...")
    for day in selected_days:
        prepare_day_config(day)

    # Restore master composite schedule in root config
    print("[*] Restoring root master composite schedule (-d all)...")
    compile_sumo_files(mode="rakes", day="all")

    # Step 2: Build task matrix
    tasks = []
    for day in selected_days:
        for disp in selected_dispatchers:
            tasks.append((day, disp, args.disruption))

    worker_count = min(len(tasks), args.workers)
    print(f"\n[*] Launching {len(tasks)} parallel 24-hour simulation runs in worker pool (pool size: {worker_count})...")
    with mp.Pool(processes=worker_count) as pool:
        results = pool.map(run_cross_eval_worker, tasks)

    total_time = time.time() - t0

    # Step 3: Save full JSON report (merging by disruption, day, and dispatcher)
    os.makedirs(LOGS_DIR, exist_ok=True)
    out_json = args.output_json or os.path.join(LOGS_DIR, "cross_comparison_24h.json")
    existing_results = []
    if os.path.exists(out_json):
        try:
            with open(out_json, "r") as f:
                existing_results = json.load(f)
        except Exception:
            pass

    merged_map = {(r.get("disruption", "none"), r["day"], r["dispatcher"]): r for r in existing_results}
    for r in results:
        merged_map[(r.get("disruption", "none"), r["day"], r["dispatcher"])] = r
    final_results = list(merged_map.values())

    with open(out_json, "w") as f:
        json.dump(final_results, f, indent=2)

    print("\n" + "=" * 95)
    print(f"RUNS COMPLETED IN {total_time/60:.2f} MINUTES ({total_time:.1f}s)!")
    print(f"Detailed results saved to: {out_json}")
    print("=" * 95)

    # Keep current audit summary separate from records loaded from the output file.
    # Group results by the requested run and disruption mode, deduplicating by (day, dispatcher).
    unique_run_results = {}
    for r in results:
        if r.get("disruption", "none") == args.disruption:
            key = (r["day"], r["dispatcher"])
            unique_run_results[key] = r
    current_run_results = list(unique_run_results.values())

    day_map = {d: {} for d in selected_days}
    for r in current_run_results:
        if r["day"] in day_map:
            day_map[r["day"]][r["dispatcher"]] = r

    all_audited_dispatchers = [d for d in selected_dispatchers if any(r["dispatcher"] == d for r in current_run_results)]

    # Step 4: Print Cross-Comparison Table for Current Audit Run
    print("\n" + "=" * 115)
    print(f"CURRENT RUN AUDIT SUMMARY (Disruption Mode: {args.disruption.upper()}):")
    print("-" * 115)
    print(f"{'Day':<5} | {'Dispatcher Model':<28} | {'Mean Delay':<11} | {'Max Delay':<10} | {'Punctuality':<12} | {'Knock-ons':<11} | {'Interventions'}")
    print("-" * 115)
    for day in selected_days:
        for disp in all_audited_dispatchers:
            if disp in day_map[day]:
                r = day_map[day][disp]
                print(f"{day:<5} | {disp:<28} | {r['mean_delay_sec']:>7.2f}s   | {r['max_delay_sec']:>7.1f}s  | {r['punctuality_pct']:>8.1f}%   | {r['knock_on_events']:>9}   | {r['actions_taken']:>6}")
        print("-" * 115)

    # Step 5: Print Global Summary for Current Audit Run
    print("\n" + "=" * 105)
    print(f"GLOBAL AUDIT AGGREGATE SUMMARY (Averaged Across Requested Days | Disruption: {args.disruption.upper()}):")
    print("=" * 105)
    print(f"{'Dispatcher Model':<28} | {'Avg Mean Delay':<15} | {'Avg Punctuality':<16} | {'Total Weekly Knock-ons':<24} | {'Delay Reduction'}")
    print("-" * 105)

    model_aggregates = {}
    static_avg_delay = 0.0
    static_baseline_ran = False

    for disp in all_audited_dispatchers:
        disp_results = [r for r in current_run_results if r["dispatcher"] == disp]
        if not disp_results:
            continue
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
            static_baseline_ran = True

    for disp, agg in model_aggregates.items():
        if disp == "Static_Baseline":
            red_str = "Baseline"
        elif static_baseline_ran and static_avg_delay > 0:
            pct_red = ((static_avg_delay - agg["avg_delay"]) / static_avg_delay) * 100.0
            red_str = f"{pct_red:+.1f}%"
        else:
            red_str = "Unavailable"
        print(f"{disp:<28} | {agg['avg_delay']:>10.2f}s    | {agg['avg_punc']:>11.1f}%    | {agg['total_knockons']:>18}     | {red_str}")
    print("=" * 105)


if __name__ == "__main__":
    main()
