"""
evaluate.py
Executes comprehensive benchmarking to empirically prove the AI dispatcher's effectiveness
over Static, FIFO, and Priority heuristics under disruption scenarios.
"""

import os
import sys
import json
import argparse
import numpy as np
from typing import Dict, Any, List, Optional
from stable_baselines3 import PPO

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dispatcher.envs.railway_dispatch_env import RailwayDispatchEnv
from dispatcher.scenarios.perturbations import PerturbationConfig
from dispatcher.agents.baseline_dispatchers import (
    BaseDispatcher,
    StaticDispatcher,
    FIFODispatcher,
    PriorityGreedyDispatcher
)


class ModelAgentWrapper(BaseDispatcher):
    def __init__(self, model_path: str, name: str = "Trained_PPO_Dispatcher", exception_gating: bool = True):
        super().__init__(name=name)
        self.model = PPO.load(model_path)
        self.exception_gating = exception_gating

    def predict(self, observation: np.ndarray, info: Optional[Dict[str, Any]] = None) -> np.ndarray:
        obs_1d = observation.flatten()

        # Frontier 1: Dispatch-by-Exception Gating
        # In real-world rail operations, trains run on scheduled nominal routes by default.
        # The AI dispatcher intervenes only when an active physical exception is detected.
        if self.exception_gating and len(obs_1d) >= 28:
            has_network_delay = obs_1d[2] > 0.033         # Fleet mean delay > 60s
            has_train_delay = obs_1d[6] > 0.033           # Focus train delay > 60s
            is_dwelling = obs_1d[9] > 0.5                 # Focus train currently berthed at a stop
            is_leader_close = obs_1d[11] < 0.50           # Leader consist within 1500m
            is_overtake_candidate = obs_1d[14] > 0.50     # Slower train ahead to overtake
            is_station_approach = obs_1d[15] > 0.50       # Approaching a scheduled station
            has_platform_conflict = np.any(obs_1d[16:28:2] > 0.5) if is_station_approach else False

            # If the consist is on-time with clear track ahead and no conflict, leave on nominal schedule
            if not (has_network_delay or has_train_delay or is_dwelling or is_leader_close or is_overtake_candidate or has_platform_conflict):
                return np.array([0, 0, 0])

        action, _ = self.model.predict(observation, deterministic=True)
        return action


def evaluate_single_run(
    dispatcher: BaseDispatcher,
    env: RailwayDispatchEnv,
    max_steps: int = 500
) -> Dict[str, Any]:
    """
    Runs an evaluation episode with the specified dispatcher.
    """
    obs, info = env.reset()
    delays_history = []
    punc_history = []
    active_history = []
    actions_taken = 0
    total_reward = 0.0

    step = 0
    terminated = False
    truncated = False

    while not (terminated or truncated) and step < max_steps:
        action = dispatcher.predict(obs, info)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward

        delays_history.append(info.get("mean_delay_sec", 0.0))
        punc_history.append(info.get("punctuality_pct", 100.0))
        active_history.append(info.get("active_trains", 0))
        if any(int(a) > 0 for a in action):
            actions_taken += 1

        step += 1

    env.close()

    mean_delay = float(np.mean(delays_history)) if delays_history else 0.0
    max_delay = float(np.max(delays_history)) if delays_history else 0.0
    punctuality = float(np.mean(punc_history)) if punc_history else 100.0
    knock_on_events = info.get("knock_on_events", 0)

    return {
        "dispatcher": dispatcher.name,
        "mean_delay_sec": mean_delay,
        "max_delay_sec": max_delay,
        "punctuality_pct": punctuality,
        "knock_on_events": knock_on_events,
        "actions_taken": actions_taken,
        "total_reward": total_reward,
        "delay_history": delays_history,
        "step_count": step
    }


evaluate_dispatcher = evaluate_single_run


def run_benchmark_suite(
    model_path: Optional[str] = None,
    disruption_mode: str = "train_delay",
    start_time: float = 21600.0,
    horizon: float = 5400.0,  # 1.5 hours
    seed: int = 42
) -> Dict[str, Any]:
    """
    Runs comparative benchmark across Static, FIFO, Priority, and AI dispatchers.
    """
    print("=" * 80)
    print("AUTONOMOUS TRAIN DISPATCHER BENCHMARK & VERIFICATION AUDIT")
    print("=" * 80)
    print(f"Scenario:             {disruption_mode.upper()}")
    print(f"Operational Window:   {start_time:.0f}s to {start_time + horizon:.0f}s ({(horizon)/3600:.1f} hours)")
    print(f"Model Checkpoint:     {model_path or 'None (Baselines Only)'}")
    print("-" * 80)

    dispatchers: List[BaseDispatcher] = [
        StaticDispatcher(),
        FIFODispatcher(),
        PriorityGreedyDispatcher()
    ]

    if model_path and os.path.exists(model_path):
        dispatchers.append(ModelAgentWrapper(model_path))

    results = {}

    for agent in dispatchers:
        print(f"[*] Auditing {agent.name:<28} ...", end="", flush=True)

        p_cfg = None
        if disruption_mode == "train_delay":
            p_cfg = PerturbationConfig(
                name="train_delay",
                mode="train_delay",
                trigger_time_sec=start_time + 300.0,
                delay_duration_sec=600.0,
                seed=seed
            )
        elif disruption_mode == "platform_blockage":
            p_cfg = PerturbationConfig(
                name="platform_blockage",
                mode="platform_blockage",
                blocked_lane_id="City_3_EW_plat_1_fw_0",
                trigger_time_sec=start_time + 300.0,
                blockage_duration_sec=1800.0,
                seed=seed
            )

        env = RailwayDispatchEnv(
            start_time_sec=start_time,
            sim_horizon_sec=horizon,
            macro_step_sec=15.0,
            perturbation_config=p_cfg,
            gui=False,
            seed=seed
        )

        metrics = evaluate_single_run(agent, env)
        results[agent.name] = metrics
        print(
            f" DONE! Mean Delay: {metrics['mean_delay_sec']:6.1f}s | "
            f"Punctuality: {metrics['punctuality_pct']:5.1f}% | "
            f"Knock-ons: {metrics['knock_on_events']:2d}"
        )

    # Print Summary Table
    print("\n" + "=" * 80)
    print(f"{'Dispatcher':<26} | {'Mean Delay':<12} | {'Max Delay':<12} | {'Punctuality':<12} | {'Knock-ons':<10}")
    print("-" * 80)
    for name, m in results.items():
        print(
            f"{name:<26} | "
            f"{m['mean_delay_sec']:>10.1f}s | "
            f"{m['max_delay_sec']:>10.1f}s | "
            f"{m['punctuality_pct']:>10.1f}% | "
            f"{m['knock_on_events']:>10d}"
        )
    print("=" * 80)

    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate and benchmark train dispatchers")
    parser.add_argument("--model", type=str, default=None, help="Path to trained PPO model zip")
    parser.add_argument("--disruption", type=str, default="train_delay", choices=["none", "train_delay", "platform_blockage"])
    parser.add_argument("--start-time", type=float, default=21600.0)
    parser.add_argument("--horizon", type=float, default=5400.0)
    parser.add_argument("--output-json", type=str, default=os.path.join(ROOT_DIR, "dispatcher", "logs", "evaluations", "disruption_benchmarks", "benchmark_results.json"))
    args = parser.parse_args()

    results = run_benchmark_suite(
        model_path=args.model,
        disruption_mode=args.disruption,
        start_time=args.start_time,
        horizon=args.horizon
    )

    # Save results to JSON
    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    serializable = {}
    for k, v in results.items():
        serializable[k] = {
            "mean_delay_sec": v["mean_delay_sec"],
            "max_delay_sec": v["max_delay_sec"],
            "punctuality_pct": v["punctuality_pct"],
            "knock_on_events": v["knock_on_events"],
            "actions_taken": v["actions_taken"],
            "total_reward": v["total_reward"],
            "delay_history": v["delay_history"]
        }
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)
    print(f"\n[✓] Benchmark results saved to: {args.output_json}")


if __name__ == "__main__":
    main()
