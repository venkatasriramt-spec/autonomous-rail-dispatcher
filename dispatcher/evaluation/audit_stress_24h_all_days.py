#!/usr/bin/env python3
"""
audit_stress_24h_all_days.py
Runs full 24-hour (00:00 to 24:00, 86,400s) stress-testing evaluations across ALL 7 DAYS of the week,
cross-comparing all 4 dispatcher models:
1. Static_Baseline (Unmanaged timetable reference)
2. FIFO_Heuristic (First-in, first-out platform reassignment)
3. Priority_Greedy_Heuristic (Rule-based class priority right-of-way)
4. Trained_PPO_Dispatcher (Main Deep Reinforcement Learning Agent)

Under 2 Rigorous 24-Hour Multi-Wave Stress Phases:
- Phase A: 24-Hour Multi-Wave Platform Blockages
    Wave 1 (07:30 - 08:15, 2700s): City_3_EW_plat_1_fw_0 (Morning Peak Hub Closure)
    Wave 2 (13:00 - 14:00, 3600s): City_2_plat_1_fw_0 (Midday Hub Maintenance)
    Wave 3 (17:30 - 18:30, 3600s): City_3_EW_plat_1_bw_0 (Evening Return Rush Closure)

- Phase B: 24-Hour Multi-Wave Rolling Stock Breakdowns
    Wave 1 (07:45, 600s): Morning Commuter Peak Regional Rake Breakdown (REG-)
    Wave 2 (13:30, 600s): Midday Freight Heavy Rake Stall (FRT-)
    Wave 3 (18:00, 600s): Evening Commuter Return Rush Emergency Brake Lock (REG-)

Execution: 28 Parallel Tasks per Phase across the 32-core VM host.
"""

import os
import sys
import json
import time
import argparse
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
from dispatcher.scenarios.perturbations import PerturbationConfig
from trains.scripts.export_to_sumo import compile_sumo_files

LOGS_DIR = os.path.join(ROOT_DIR, "dispatcher", "logs")
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
MACRO_STEP_SEC = 15.0      # 15.0s decision cadence (5,760 steps/day)


def get_phase_config(phase: str) -> PerturbationConfig:
    """Constructs the multi-wave perturbation schedule for Phase A or Phase B."""
    if phase.upper() == "A":
        return PerturbationConfig(
            name="Phase_A_24h_Platform_Blockages",
            mode="scheduled",
            events=[
                {
                    "type": "platform_blockage",
                    "name": "Morning Peak Interchange Hub Closure",
                    "lane_id": "City_3_EW_plat_1_fw_0",
                    "trigger_time": 27000.0,       # 07:30 AM
                    "duration": 2700.0             # 45 minutes (until 08:15 AM)
                },
                {
                    "type": "platform_blockage",
                    "name": "Midday City 2 Platform Maintenance",
                    "lane_id": "City_2_plat_1_fw_0",
                    "trigger_time": 46800.0,       # 13:00 PM
                    "duration": 3600.0             # 60 minutes (until 14:00 PM)
                },
                {
                    "type": "platform_blockage",
                    "name": "Evening Peak Return Hub Closure",
                    "lane_id": "City_3_EW_plat_1_bw_0",
                    "trigger_time": 63000.0,       # 17:30 PM
                    "duration": 3600.0             # 60 minutes (until 18:30 PM)
                }
            ],
            seed=42
        )
    elif phase.upper() == "B":
        return PerturbationConfig(
            name="Phase_B_24h_Train_Breakdowns",
            mode="scheduled",
            events=[
                {
                    "type": "train_delay",
                    "name": "Morning Commuter Peak Rake Breakdown",
                    "trigger_time": 27900.0,       # 07:45 AM
                    "duration": 600.0,             # 10 minutes
                    "target_pattern": "REG-"
                },
                {
                    "type": "train_delay",
                    "name": "Midday Freight Heavy Rake Stall",
                    "trigger_time": 48600.0,       # 13:30 PM
                    "duration": 600.0,             # 10 minutes
                    "target_pattern": "FRT-"
                },
                {
                    "type": "train_delay",
                    "name": "Evening Commuter Return Rush Emergency Brake Lock",
                    "trigger_time": 64800.0,       # 18:00 PM
                    "duration": 600.0,             # 10 minutes
                    "target_pattern": "REG-"
                }
            ],
            seed=42
        )
    else:
        raise ValueError(f"Unknown phase: {phase}")


def run_stress_eval_worker(task: Tuple[str, str, str]) -> Dict[str, Any]:
    """
    Worker executing a single dispatcher on a single day under 24-hour multi-wave disruption.
    task: (day, dispatcher_name, phase)
    """
    day, disp_name, phase = task
    day_cfg = os.path.join(DAYS_DIR, day, "train_simulation.sumocfg")
    p_cfg = get_phase_config(phase)
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
        perturbation_config=p_cfg,
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

    applied_disruptions = list(env.disruption_manager.applied_disruptions)
    collisions = info.get("collisions", 0)
    teleports = info.get("teleports", 0)
    knock_on_events = info.get("knock_on_events", 0)
    env.close()

    elapsed = time.time() - t0
    mean_delay = float(np.mean(delays_history)) if delays_history else 0.0
    max_delay = float(np.max(delays_history)) if delays_history else 0.0
    punctuality = float(np.mean(punc_history)) if punc_history else 100.0
    peak_active = max(active_history) if active_history else 0

    print(
        f"[{phase} | {day} | {disp_name:<25}] "
        f"24h Done in {elapsed/60:.2f}m | Delay: {mean_delay:>6.2f}s | Max: {max_delay:>6.1f}s | "
        f"Punc: {punctuality:>5.1f}% | Knock-ons: {knock_on_events:>6} | Collisions: {collisions}",
        flush=True
    )

    return {
        "phase": phase,
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
        "collisions": collisions,
        "teleports": teleports,
        "actions_taken": actions_taken,
        "action_breakdown": {
            "route_diversions": route_diverts,
            "platform_switches": plat_switches,
            "holds": holds_applied
        },
        "applied_disruptions_count": len(applied_disruptions),
        "applied_disruptions": applied_disruptions
    }


def execute_phase(phase: str) -> List[Dict[str, Any]]:
    phase_title = "PHASE A: 24-HOUR MULTI-WAVE PLATFORM BLOCKAGES" if phase == "A" else "PHASE B: 24-HOUR MULTI-WAVE TRAIN BREAKDOWNS"
    print("\n" + "=" * 115)
    print(f"STARTING {phase_title}")
    print(f"Horizon: 00:00 to 24:00 (86,400s) | Days: 7 | Models: 4 | Parallel Tasks: 28")
    print("=" * 115)

    tasks = [(day, disp, phase) for day in DAYS for disp in DISPATCHER_TYPES]
    t0 = time.time()

    print(f"[*] Launching 28 parallel 24-hour workers for Phase {phase} across 32 vCPUs...")
    with mp.Pool(processes=28) as pool:
        results = pool.map(run_stress_eval_worker, tasks)

    total_time = time.time() - t0
    os.makedirs(LOGS_DIR, exist_ok=True)
    out_json = os.path.join(LOGS_DIR, f"stress_phase_{phase}_24h.json")
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 115)
    print(f"PHASE {phase} COMPLETED IN {total_time/60:.2f} MINUTES ({total_time:.1f}s)!")
    print(f"Results saved to: {out_json}")
    print("=" * 115)

    # Print Full Scorecard
    day_map = {d: {} for d in DAYS}
    for r in results:
        day_map[r["day"]][r["dispatcher"]] = r

    print("\n" + "=" * 135)
    print(f"{'Day':<5} | {'Dispatcher Model':<26} | {'Mean Delay':<11} | {'Max Delay':<10} | {'Punctuality':<12} | {'Knock-ons':<11} | {'Collisions':<11} | {'Interventions'}")
    print("-" * 135)
    for day in DAYS:
        for disp in DISPATCHER_TYPES:
            r = day_map[day][disp]
            print(
                f"{day:<5} | {disp:<26} | {r['mean_delay_sec']:>9.2f}s | {r['max_delay_sec']:>8.1f}s | "
                f"{r['punctuality_pct']:>10.1f}% | {r['knock_on_events']:>11} | {r['collisions']:>11} | {r['actions_taken']:>13}"
            )
        print("-" * 135)

    # Global Aggregate
    print("\n" + "=" * 115)
    print(f"GLOBAL WEEKLY AGGREGATE SUMMARY (PHASE {phase} - 24-HOUR HORIZON):")
    print("=" * 115)
    print(f"{'Dispatcher Model':<26} | {'Avg Mean Delay':<15} | {'Avg Punctuality':<16} | {'Weekly Knock-ons':<17} | {'Total Collisions'}")
    print("-" * 115)
    for disp in DISPATCHER_TYPES:
        model_results = [r for r in results if r["dispatcher"] == disp]
        avg_delay = np.mean([r["mean_delay_sec"] for r in model_results])
        avg_punc = np.mean([r["punctuality_pct"] for r in model_results])
        tot_knock = sum([r["knock_on_events"] for r in model_results])
        tot_col = sum([r["collisions"] for r in model_results])
        print(f"{disp:<26} | {avg_delay:>13.2f}s | {avg_punc:>14.1f}% | {tot_knock:>17} | {tot_col:>16}")
    print("=" * 115)

    return results


def main():
    parser = argparse.ArgumentParser(description="24-Hour 7-Day Stress-Testing Benchmark")
    parser.add_argument("--phase", type=str, default="all", choices=["A", "B", "all"], help="Stress phase to execute")
    args = parser.parse_args()

    print("=" * 115)
    print("AUTONOMOUS TRAIN DISPATCHER: 24-HOUR 7-DAY INTENSIFIED STRESS-TEST BENCHMARK")
    print(f"Target Policy: {MODEL_PATH}")
    print("=" * 115)

    if not os.path.exists(MODEL_PATH):
        print(f"[!] Error: Model not found at {MODEL_PATH}")
        sys.exit(1)

    t_start = time.time()

    if args.phase in ("A", "all"):
        execute_phase("A")

    if args.phase in ("B", "all"):
        execute_phase("B")

    # Restore master composite config
    compile_sumo_files(mode="rakes", day="all")
    print(f"\n[★] Complete 24-Hour 7-Day Stress-Testing Suite finalized in {(time.time() - t_start)/60:.2f} minutes.")


if __name__ == "__main__":
    main()
