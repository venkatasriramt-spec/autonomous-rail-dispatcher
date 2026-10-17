#!/usr/bin/env python3
"""
audit_stress_testing.py
Microscopic stress-testing benchmark comparing:
1. Static_Baseline
2. FIFO_Heuristic
3. Priority_Greedy_Heuristic
4. Trained_PPO_Dispatcher

Under 4 Unplanned Network Disruption Scenarios during Peak Morning Operations (06:00 to 09:00, 10,800s):
- Scenario A: Train Breakdown (train_delay - 600s mechanical incident)
- Scenario B: Platform Closure (platform_blockage - 1,800s hub platform shutdown)
- Scenario C: Fleet Delay Surge (stochastic - random boarding delays across 15% of fleet)
- Scenario D: Compound Failure (compound - concurrent platform closure AND train breakdown)

All 16 runs execute concurrently in a parallel multiprocessing worker pool.
"""

import os
import sys
import json
import time
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

LOGS_DIR = os.path.join(ROOT_DIR, "dispatcher", "logs", "evaluations", "stress_tests")
MODEL_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "best_model.zip")
MAPPO_MODEL_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "mappo_interlocking.pt")
SUMOCFG_PATH = os.path.join(ROOT_DIR, "trains", "sumo_config", "train_simulation.sumocfg")

DISPATCHER_TYPES = [
    "Static_Baseline",
    "FIFO_Heuristic",
    "Priority_Greedy_Heuristic",
    "Centralized_PPO",
    "Decentralized_MAPPO"
]

SCENARIOS = [
    {
        "id": "train_delay",
        "name": "Train Breakdown (600s Incident)",
        "config": PerturbationConfig(
            name="train_delay",
            mode="train_delay",
            trigger_time_sec=22200.0,      # 06:10 AM (active mainline traffic)
            delay_duration_sec=600.0,       # 10 minutes
            seed=42
        )
    },
    {
        "id": "platform_blockage",
        "name": "Platform Closure (1800s Hub Shutdown)",
        "config": PerturbationConfig(
            name="platform_blockage",
            mode="platform_blockage",
            blocked_lane_id="City_3_EW_plat_1_fw_0",
            trigger_time_sec=22200.0,      # 06:10 AM
            blockage_duration_sec=1800.0,  # 30 minutes
            seed=42
        )
    },
    {
        "id": "stochastic",
        "name": "Fleet Surge (15% Stochastic Dwell)",
        "config": PerturbationConfig(
            name="stochastic",
            mode="stochastic",
            stochastic_rate=0.15,
            seed=42
        )
    },
    {
        "id": "compound",
        "name": "Compound Failure (Breakdown + Blockage)",
        "config": PerturbationConfig(
            name="compound",
            mode="compound",
            blocked_lane_id="City_3_EW_plat_1_fw_0",
            trigger_time_sec=22200.0,      # 06:10 AM
            delay_duration_sec=600.0,       # 10 min train breakdown
            blockage_duration_sec=1800.0,  # 30 min platform shutdown
            seed=42
        )
    }
]

START_TIME_SEC = 21600.0  # 06:00 AM (Morning Commuter Peak)
HORIZON_SEC = 7200.0      # 2 Hours (06:00 to 08:00 AM)
MACRO_STEP_SEC = 15.0     # 480 macro-steps


def run_stress_test_worker(task: Tuple[str, str, int]) -> Dict[str, Any]:
    """
    Worker executing one model under one disruption scenario.
    task: (scenario_id, dispatcher_name, scenario_index)
    """
    scen_id, disp_name, scen_idx = task
    scenario = SCENARIOS[scen_idx]
    p_cfg = scenario["config"]

    t0 = time.time()

    is_marl = (disp_name == "Decentralized_MAPPO")
    if is_marl:
        agent = MAPPODispatcher(checkpoint_path=MAPPO_MODEL_PATH, exception_gating=True, smart_interlocking=True)
        env = MultiAgentRailwayEnv(
            sumocfg_path=SUMOCFG_PATH,
            start_time_sec=START_TIME_SEC,
            sim_horizon_sec=HORIZON_SEC,
            macro_step_sec=MACRO_STEP_SEC,
            perturbation_config=p_cfg,
            gui=False,
            seed=42
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
        else:
            raise ValueError(f"Unknown dispatcher: {disp_name}")

        env = RailwayDispatchEnv(
            sumocfg_path=SUMOCFG_PATH,
            start_time_sec=START_TIME_SEC,
            sim_horizon_sec=HORIZON_SEC,
            macro_step_sec=MACRO_STEP_SEC,
            perturbation_config=p_cfg,
            gui=False,
            seed=42
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

    applied_disruptions = list(env.disruption_manager.applied_disruptions)
    env.close()
    elapsed = time.time() - t0

    mean_delay = float(np.mean(delays_history)) if delays_history else 0.0
    max_delay = float(np.max(peak_delays_history)) if peak_delays_history else 0.0
    punctuality = float(np.mean(punc_history)) if punc_history else 100.0
    knock_on_events = info.get("knock_on_events", 0)
    peak_active = max(active_history) if active_history else 0

    print(
        f"[{scenario['name'][:22]:<22} | {disp_name:<26}] "
        f"Done in {elapsed:.1f}s | Delay: {mean_delay:>6.2f}s | Max: {max_delay:>6.1f}s | "
        f"Punc: {punctuality:>5.1f}% | Knock-ons: {knock_on_events:>5} | Actions: {actions_taken:>4}",
        flush=True
    )


    return {
        "scenario_id": scen_id,
        "scenario_name": scenario["name"],
        "dispatcher": disp_name,
        "elapsed_sec": round(elapsed, 1),
        "steps_simulated": step,
        "peak_active_trains": peak_active,
        "mean_delay_sec": round(mean_delay, 2),
        "max_delay_sec": round(max_delay, 1),
        "punctuality_pct": round(punctuality, 1),
        "knock_on_events": knock_on_events,
        "actions_taken": actions_taken,
        "applied_disruptions": applied_disruptions,
        "action_breakdown": {
            "route_diversions": route_diverts,
            "platform_switches": plat_switches,
            "holds": holds_applied
        }
    }


def main():
    print("=" * 105)
    print("AUTONOMOUS TRAIN DISPATCHER: NETWORK STRESS-TESTING & DISRUPTION BENCHMARK")
    print(f"Time Horizon: 06:00 to 09:00 AM (10,800s Peak Window) | Cadence: {MACRO_STEP_SEC}s (720 steps)")
    print(f"Disruption Scenarios Audited: {len(SCENARIOS)} | Dispatcher Models Audited: {len(DISPATCHER_TYPES)} | Parallel Runs: {len(SCENARIOS) * len(DISPATCHER_TYPES)}")
    print("=" * 105)

    if not os.path.exists(MODEL_PATH):
        print(f"[!] Error: Model checkpoint not found at {MODEL_PATH}")
        sys.exit(1)

    if "Decentralized_MAPPO" in DISPATCHER_TYPES and not os.path.exists(MAPPO_MODEL_PATH):
        print(f"[!] Error: MAPPO model checkpoint not found at {MAPPO_MODEL_PATH}")
        sys.exit(1)

    # Ensure master schedule is compiled
    compile_sumo_files(mode="rakes", day="all")

    tasks = []
    for s_idx, scen in enumerate(SCENARIOS):
        for disp in DISPATCHER_TYPES:
            tasks.append((scen["id"], disp, s_idx))

    t0 = time.time()
    print(f"\n[*] Launching {len(tasks)} parallel disruption simulations across worker pool...\n")
    with mp.Pool(processes=min(len(tasks), 20)) as pool:
        results = pool.map(run_stress_test_worker, tasks)

    total_time = time.time() - t0

    os.makedirs(LOGS_DIR, exist_ok=True)
    out_json = os.path.join(LOGS_DIR, "stress_testing_benchmark.json")
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 105)
    print(f"ALL {len(tasks)} STRESS-TEST RUNS COMPLETED IN {total_time:.1f}s ({total_time/60:.2f} min)!")
    print(f"Detailed results saved to: {out_json}")
    print("=" * 105)

    # Group by Scenario
    scen_map = {s["id"]: {} for s in SCENARIOS}
    for r in results:
        scen_map[r["scenario_id"]][r["dispatcher"]] = r

    print("\n" + "=" * 125)
    print(f"{'Disruption Scenario':<36} | {'Dispatcher Model':<26} | {'Mean Delay':<11} | {'Max Delay':<10} | {'Punc %':<8} | {'Knock-ons':<10} | {'Actions'}")
    print("-" * 125)
    for s in SCENARIOS:
        s_id = s["id"]
        for disp in DISPATCHER_TYPES:
            r = scen_map[s_id][disp]
            print(
                f"{s['name']:<36} | {disp:<26} | {r['mean_delay_sec']:>9.2f}s | "
                f"{r['max_delay_sec']:>8.1f}s | {r['punctuality_pct']:>6.1f}% | "
                f"{r['knock_on_events']:>9} | {r['actions_taken']:>6}"
            )
        print("-" * 125)


if __name__ == "__main__":
    main()
