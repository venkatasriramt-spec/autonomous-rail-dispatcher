#!/usr/bin/env python3
"""
audit_marl_comparison.py
Empirical performance comparison between:
1. Centralized Single-Agent PPO (Monolithic Dispatcher)
2. Decentralized Multi-Agent MAPPO (7 Decentralized Interlocking Controllers)
3. Static Baseline (Unmanaged timetable)
4. FIFO Heuristic Dispatcher

Evaluated over the morning commuter peak hour (06:00 to 07:00 AM, 240 steps at 15.0s resolution).
Measures:
- Mean Delay and Punctuality Percentage (< 3 min) (excluding zero-train steps); Max Delay includes all steps
- Secondary Knock-On Delays
- Control Actions Executed
- Telemetry Transmission Overhead (KB)
"""

import os
import sys
import json
import time
import logging
import numpy as np
from typing import Dict, Any, List, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dispatcher.envs.railway_dispatch_env import RailwayDispatchEnv
from dispatcher.envs.multi_agent_railway_env import MultiAgentRailwayEnv
from dispatcher.agents.baseline_dispatchers import StaticDispatcher, FIFODispatcher
from dispatcher.agents.mappo_agent import MAPPODispatcher
from dispatcher.evaluation.evaluate import ModelAgentWrapper

MODEL_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "best_model.zip")
MAPPO_CHECKPOINT_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "mappo_interlocking.pt")
SUMOCFG_PATH = os.path.join(ROOT_DIR, "trains", "sumo_config", "train_simulation.sumocfg")
OUTPUT_LOGS_DIR = os.path.join(ROOT_DIR, "dispatcher", "logs", "evaluations", "marl_audits")

START_TIME_SEC = 21600.0   # 06:00 AM
HORIZON_SEC = 3600.0       # 1 Hour
MACRO_STEP_SEC = 15.0      # 240 steps


def evaluate_single_agent(agent_type: str) -> Dict[str, Any]:
    """Runs single-agent evaluation (PPO, FIFO, or Static). Only mean delay and punctuality exclude zero-train steps; max delay includes all steps."""
    t0 = time.time()
    if agent_type == "Centralized_PPO":
        agent = ModelAgentWrapper(MODEL_PATH, exception_gating=True, smart_interlocking=True)
    elif agent_type == "FIFO_Heuristic":
        agent = FIFODispatcher()
    else:
        agent = StaticDispatcher()

    env = RailwayDispatchEnv(
        sumocfg_path=SUMOCFG_PATH,
        start_time_sec=START_TIME_SEC,
        sim_horizon_sec=HORIZON_SEC,
        macro_step_sec=MACRO_STEP_SEC,
        gui=False
    )

    obs, info = env.reset()
    delays_hist = []
    max_delays_hist = []
    punc_hist = []
    actions_count = 0
    total_bytes_transmitted = 0

    terminated = False
    truncated = False
    step = 0

    while not (terminated or truncated):
        action = agent.predict(obs, info)
        r, p, h = int(action[0]), int(action[1]), int(action[2])
        if r > 0 or p > 0 or h > 0:
            actions_count += 1

        # Centralized agent transmits full 28 float32 observation vector (112 bytes)
        total_bytes_transmitted += 28 * 4

        obs, reward, terminated, truncated, info = env.step(action)
        active = info.get("active_trains", 0)
        if active > 0:
            delays_hist.append(info.get("mean_delay_sec", 0.0))
            punc_hist.append(info.get("punctuality_pct", 100.0))
        max_delays_hist.append(info.get("max_delay_sec", 0.0))
        step += 1

    knock_ons = info.get("knock_on_events", 0)
    env.close()
    elapsed = time.time() - t0

    return {
        "model": agent_type,
        "paradigm": "Centralized Single-Agent",
        "elapsed_sec": round(elapsed, 1),
        "steps": step,
        "mean_delay_sec": round(float(np.mean(delays_hist)), 2) if delays_hist else 0.0,
        "max_delay_sec": round(float(np.max(max_delays_hist)), 1) if max_delays_hist else 0.0,
        "punctuality_pct": round(float(np.mean(punc_hist)), 1) if punc_hist else 100.0,
        "knock_on_events": knock_ons,
        "actions_taken": actions_count,
        "telemetry_kb": round(total_bytes_transmitted / 1024.0, 2)
    }


def evaluate_multi_agent_mappo(checkpoint_path: Optional[str] = MAPPO_CHECKPOINT_PATH) -> Dict[str, Any]:
    """Runs decentralized MAPPO multi-agent evaluation. Only mean delay and punctuality exclude zero-train steps; max delay includes all steps."""
    t0 = time.time()
    env = MultiAgentRailwayEnv(
        sumocfg_path=SUMOCFG_PATH,
        start_time_sec=START_TIME_SEC,
        sim_horizon_sec=HORIZON_SEC,
        macro_step_sec=MACRO_STEP_SEC,
        gui=False
    )

    if checkpoint_path and os.path.exists(checkpoint_path):
        dispatcher = MAPPODispatcher(checkpoint_path=checkpoint_path, exception_gating=True, smart_interlocking=True)
        model_name = "Decentralized_MAPPO"
        paradigm = "Multi-Agent CTDE (7 Interlocking Agents)"
    else:
        # Untrained baseline
        logging.warning("MAPPO checkpoint missing at '%s'; audit will use an untrained policy.", checkpoint_path)
        dispatcher = MAPPODispatcher(checkpoint_path=None, exception_gating=True, smart_interlocking=True)
        model_name = "Decentralized_MAPPO_Untrained"
        paradigm = "Multi-Agent CTDE (7 Interlocking Agents, Untrained)"

    obs_dict, info = env.reset()

    delays_hist = []
    max_delays_hist = []
    punc_hist = []
    actions_count = 0
    total_bytes_transmitted = 0

    terminated_all = False
    truncated_all = False
    step = 0

    while not (terminated_all or truncated_all):
        actions_dict = dispatcher.predict(obs_dict, info=info)

        # Count actions and calculate decentralized bandwidth:
        for aid, act in actions_dict.items():
            if aid.startswith("station_"):
                if int(act[0]) > 0 or int(act[1]) > 0:
                    actions_count += 1
            else:
                if int(act) > 0:
                    actions_count += 1
            obs_elems = int(np.prod(obs_dict[aid].shape)) if aid in obs_dict else 0
            total_bytes_transmitted += obs_elems * 4

        obs_dict, rewards, terminated, truncated, info = env.step(actions_dict)
        active = info.get("active_trains", 0)
        if active > 0:
            delays_hist.append(info.get("mean_delay_sec", 0.0))
            punc_hist.append(info.get("punctuality_pct", 100.0))
        max_delays_hist.append(info.get("max_delay_sec", 0.0))

        terminated_all = terminated.get("__all__", False)
        truncated_all = truncated.get("__all__", False)
        step += 1

    knock_ons = info.get("knock_on_events", 0)
    env.close()
    elapsed = time.time() - t0

    return {
        "model": model_name,
        "paradigm": paradigm,
        "elapsed_sec": round(elapsed, 1),
        "steps": step,
        "mean_delay_sec": round(float(np.mean(delays_hist)), 2) if delays_hist else 0.0,
        "max_delay_sec": round(float(np.max(max_delays_hist)), 1) if max_delays_hist else 0.0,
        "punctuality_pct": round(float(np.mean(punc_hist)), 1) if punc_hist else 100.0,
        "knock_on_events": knock_ons,
        "actions_taken": actions_count,
        "telemetry_kb": round(total_bytes_transmitted / 1024.0, 2)
    }


def main():
    print("=" * 115)
    print("FRONTIER 3: MULTI-AGENT REINFORCEMENT LEARNING (MARL) EMPIRICAL BENCHMARK")
    print("Architecture: Centralized Training with Decentralized Execution (CTDE)")
    print("Agents: 6 Station-Master Interlocking Agents + 1 Corridor Block Agent")
    print(f"Horizon: 06:00 to 07:00 AM (Peak Commuter Window) | Cadence: {MACRO_STEP_SEC}s (240 steps)")
    print("=" * 115)

    os.makedirs(OUTPUT_LOGS_DIR, exist_ok=True)
    results = []

    # 1. Centralized Single-Agent Baseline
    print("\n[*] Evaluating Centralized Single-Agent PPO...")
    res_ppo = evaluate_single_agent("Centralized_PPO")
    results.append(res_ppo)
    print(f"    PPO Done in {res_ppo['elapsed_sec']}s | Delay: {res_ppo['mean_delay_sec']}s | Punc: {res_ppo['punctuality_pct']}% | Actions: {res_ppo['actions_taken']}")

    # 2. Decentralized Multi-Agent MAPPO
    print("\n[*] Evaluating Decentralized Multi-Agent MAPPO (7 Agents)...")
    res_mappo = evaluate_multi_agent_mappo()
    results.append(res_mappo)
    print(f"    MAPPO Done in {res_mappo['elapsed_sec']}s | Delay: {res_mappo['mean_delay_sec']}s | Punc: {res_mappo['punctuality_pct']}% | Actions: {res_mappo['actions_taken']}")

    # 3. Static & FIFO Baselines for reference
    print("\n[*] Evaluating Static Baseline...")
    res_stat = evaluate_single_agent("Static_Baseline")
    results.append(res_stat)

    print("\n[*] Evaluating FIFO Heuristic...")
    res_fifo = evaluate_single_agent("FIFO_Heuristic")
    results.append(res_fifo)

    # Save Results
    out_json = os.path.join(OUTPUT_LOGS_DIR, "marl_vs_centralized_benchmark.json")
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)

    # Print Summary Table
    print("\n" + "=" * 135)
    print(f"{'Dispatcher Model':<30} | {'Paradigm':<42} | {'Mean Delay':<11} | {'Max Delay':<10} | {'Punctuality':<12} | {'Actions':<8} | {'Bandwidth'}")
    print("-" * 135)
    for r in results:
        print(
            f"{r['model']:<30} | {r['paradigm']:<42} | {r['mean_delay_sec']:>9.2f}s | "
            f"{r['max_delay_sec']:>8.1f}s | {r['punctuality_pct']:>10.1f}% | {r['actions_taken']:>8} | {r['telemetry_kb']:>6.1f} KB"
        )
    print("=" * 135)
    print(f"\n[✓] MARL benchmark data saved to: {out_json}")


if __name__ == "__main__":
    main()
