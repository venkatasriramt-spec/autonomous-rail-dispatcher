"""
train.py
Trains the autonomous reinforcement learning railway dispatcher using PPO (Stable-Baselines3).
Optimized for multi-core CPU execution.
"""

import os
import sys
import argparse
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

# Add repository root to python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dispatcher.envs.railway_dispatch_env import RailwayDispatchEnv
from dispatcher.scenarios.perturbations import PerturbationConfig
from dispatcher.training.callbacks import RailwayMetricsCallback


def make_env(
    rank: int,
    seed: int = 42,
    disruption_mode: str = "none",
    start_time: float = 21600.0,
    horizon: float = 7200.0
):
    def _init():
        p_cfg = None
        if disruption_mode == "train_delay":
            p_cfg = PerturbationConfig(
                name="train_delay",
                mode="train_delay",
                trigger_time_sec=start_time + 300.0,
                delay_duration_sec=420.0,
                seed=seed + rank
            )
        elif disruption_mode == "platform_blockage":
            p_cfg = PerturbationConfig(
                name="platform_blockage",
                mode="platform_blockage",
                blocked_lane_id="City_3_EW_plat_1_fw_0",
                trigger_time_sec=start_time + 300.0,
                blockage_duration_sec=1200.0,
                seed=seed + rank
            )
        elif disruption_mode == "stochastic":
            p_cfg = PerturbationConfig(
                name="stochastic",
                mode="stochastic",
                stochastic_rate=0.08,
                seed=seed + rank
            )

        env = RailwayDispatchEnv(
            start_time_sec=start_time,
            sim_horizon_sec=horizon,
            macro_step_sec=15.0,
            perturbation_config=p_cfg,
            gui=False,
            seed=seed + rank
        )
        return env
    return _init


def main():
    parser = argparse.ArgumentParser(description="Train PPO Railway Dispatcher Agent")
    parser.add_argument("--timesteps", type=int, default=5000, help="Total training timesteps")
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel environment workers")
    parser.add_argument("--disruption", type=str, default="none", choices=["none", "train_delay", "platform_blockage", "stochastic"])
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate")
    parser.add_argument("--save-dir", type=str, default=os.path.join(ROOT_DIR, "dispatcher", "models"))
    parser.add_argument("--log-dir", type=str, default=os.path.join(ROOT_DIR, "dispatcher", "logs"))
    parser.add_argument("--start-time", type=float, default=21600.0, help="Simulation start time in seconds")
    parser.add_argument("--horizon", type=float, default=7200.0, help="Simulation horizon in seconds per episode")
    args = parser.parse_args()

    os.makedirs(args.save_dir, exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)

    print("=" * 70)
    print("RAILWAY TRAFFIC MANAGEMENT SYSTEM - RL DISPATCHER TRAINING")
    print("=" * 70)
    print(f"Target Timesteps:     {args.timesteps}")
    print(f"Parallel Workers:     {args.workers}")
    print(f"Disruption Scenario:  {args.disruption}")
    print(f"Learning Rate:        {args.lr}")
    print(f"Operational Window:   {args.start_time:.0f}s to {args.start_time + args.horizon:.0f}s ({(args.horizon)/3600:.1f} hours)")
    print(f"PyTorch Device:       {'cpu'} ({torch.get_num_threads()} threads)")
    print("-" * 70)

    # Initialize vectorized environment
    env_fns = [
        make_env(
            rank=i,
            seed=42 + i,
            disruption_mode=args.disruption,
            start_time=args.start_time,
            horizon=args.horizon
        )
        for i in range(args.workers)
    ]

    if args.workers == 1:
        vec_env = DummyVecEnv(env_fns)
    else:
        vec_env = SubprocVecEnv(env_fns)

    # PPO Architecture: 2-layer MLP [128, 128] for CPU efficiency
    policy_kwargs = dict(
        net_arch=dict(pi=[128, 128], vf=[128, 128]),
        activation_fn=torch.nn.Tanh
    )

    model = PPO(
        policy="MlpPolicy",
        env=vec_env,
        learning_rate=args.lr,
        n_steps=256,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        policy_kwargs=policy_kwargs,
        tensorboard_log=args.log_dir,
        verbose=1
    )

    callback = RailwayMetricsCallback(
        check_freq=100,
        save_path=args.save_dir,
        verbose=1
    )

    print("[*] Commencing training rollouts...")
    try:
        model.learn(total_timesteps=args.timesteps, callback=callback)
    except KeyboardInterrupt:
        print("[!] Training interrupted by user.")
    finally:
        final_path = os.path.join(args.save_dir, "ppo_dispatcher_final.zip")
        model.save(final_path)
        print(f"[✓] Final model checkpoint saved to: {final_path}")
        vec_env.close()


if __name__ == "__main__":
    main()
