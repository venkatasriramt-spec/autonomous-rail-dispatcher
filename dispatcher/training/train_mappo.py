"""
train_mappo.py
High-Performance Multi-Agent Proximal Policy Optimization (MAPPO) Training Pipeline
for Autonomous Railway Dispatching.

Optimized for high-core CPU hardware (e.g. 32 cores) using vectorized multi-worker
environment rollouts and Centralized Training with Decentralized Execution (CTDE).

Architecture:
- 6 Decentralized Station Actors: MultiDiscrete([7, 4])
- 1 Decentralized Corridor Actor: Discrete(3)
- 1 Centralized Critic: Evaluates joint state S_joint (158-dim) across all 7 zones
- Multiprocessing Worker Pool: Parallel SUMO simulation instances communicating via Pipes
"""

import os
import sys
import time
import argparse
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import multiprocessing as mp
from typing import Dict, Any, List, Tuple, Optional

# Add root directory to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dispatcher.envs.marl_zones import (
    MARL_AGENT_IDS,
    STATION_AGENT_NAMES,
    STATION_OBS_DIM,
    CORRIDOR_OBS_DIM,
    TOTAL_JOINT_OBS_DIM
)
from dispatcher.envs.multi_agent_railway_env import MultiAgentRailwayEnv
from dispatcher.agents.mappo_agent import (
    StationActor,
    CorridorActor,
    CentralizedCritic,
    MAPPODispatcher
)

SUMOCFG_PATH = os.path.join(ROOT_DIR, "trains", "sumo_config", "train_simulation.sumocfg")
DEFAULT_MODEL_DIR = os.path.join(ROOT_DIR, "dispatcher", "models")
DEFAULT_CHECKPOINT = os.path.join(DEFAULT_MODEL_DIR, "mappo_interlocking.pt")
DEFAULT_BEST_MODEL = os.path.join(DEFAULT_MODEL_DIR, "mappo_best.pt")

WAVE_CONFIGS = {
    "morning_peak": {"start_time": 25200.0, "horizon": 9000.0, "desc": "07:00-09:30 Morning Commuter Rush (18-23 runs/hr)"},
    "evening_peak": {"start_time": 57600.0, "horizon": 9900.0, "desc": "16:00-18:45 Evening Commuter Rush (16-22 runs/hr)"},
    "midday_base": {"start_time": 34200.0, "horizon": 14400.0, "desc": "09:30-13:30 Midday Clockface Cadence (10-14 runs/hr)"},
    "nocturnal_freight": {"start_time": 77400.0, "horizon": 18000.0, "desc": "21:30-02:30 Nocturnal Freight & Logistics Wave"},
    "alpine_shuttle": {"start_time": 25200.0, "horizon": 10800.0, "desc": "07:00-10:00 Alpine Mountain Pass & Shuttle Wave", "day": "Mon"},
    "glacier_express": {"start_time": 36000.0, "horizon": 10800.0, "desc": "10:00-13:00 Alpine Glacier Express & Midday Freight Wave", "day": "Tue"},
    "sunday_staging": {"start_time": 28800.0, "horizon": 14400.0, "desc": "08:00-12:00 Sunday Platform Staging Wave", "day": "Sun"},
    "early_morning": {"start_time": 18000.0, "horizon": 7200.0, "desc": "05:00-07:00 Early Morning Feeder & Awakening"},
    "full_day": {"start_time": 18000.0, "horizon": 64800.0, "desc": "05:00-23:00 Full Continuous Fleet (242 runs)"},
}


# ==============================================================================
# 1. Parallel Environment Worker (Process-Level TraCI Encapsulation)
# ==============================================================================

import traceback

def env_worker_loop(remote, worker_id: int, sumocfg_path: Optional[str], start_time: float, horizon: float, seed: int):
    """
    Independent worker process managing a single headless SUMO multi-agent environment.
    Communicates with the central trainer via a bidirectional Pipe.
    """
    worker_port = 12500 + worker_id * 10
    cfg = sumocfg_path if sumocfg_path else SUMOCFG_PATH
    if not os.path.exists(cfg):
        raise FileNotFoundError(f"Worker {worker_id}: SUMO configuration not found at {cfg}")
    try:
        env = MultiAgentRailwayEnv(
            sumocfg_path=cfg,
            start_time_sec=start_time,
            sim_horizon_sec=horizon,
            macro_step_sec=15.0,
            cooperation_factor=0.5,
            gui=False,
            seed=None,
            port=worker_port
        )

        while True:
            cmd, data = remote.recv()

            if cmd == "reset":
                ep_seed = seed + worker_id * 100 + int(data or 0)
                obs_dict, info = env.reset(seed=ep_seed)
                remote.send((obs_dict, info))

            elif cmd == "step":
                action_dict = data
                obs_dict, reward_dict, term_dict, trunc_dict, info = env.step(action_dict)
                done = term_dict.get("__all__", False) or trunc_dict.get("__all__", False)
                if done:
                    # Auto-reset upon completion
                    obs_dict, info = env.reset()
                remote.send((obs_dict, reward_dict, done, info))

            elif cmd == "close":
                env.close()
                remote.close()
                break

            else:
                raise ValueError(f"Unknown command: {cmd}")

    except Exception as e:
        traceback.print_exc()
        remote.send(("error", str(e)))
        remote.close()



class ParallelMultiAgentEnv:
    """Manages a pool of parallel worker processes running MultiAgentRailwayEnv instances."""
    def __init__(self, num_workers: int, start_time: float, horizon: float, sumocfg_path: Optional[str] = None, base_seed: int = 42):
        self.num_workers = num_workers
        self.remotes, self.work_remotes = zip(*[mp.Pipe() for _ in range(num_workers)])
        self.processes = []

        for w_idx in range(num_workers):
            p = mp.Process(
                target=env_worker_loop,
                args=(self.work_remotes[w_idx], w_idx, sumocfg_path, start_time, horizon, base_seed),
                daemon=True
            )
            p.start()
            self.processes.append(p)
            self.work_remotes[w_idx].close()

    def reset(self, episode_counts: Optional[List[int]] = None) -> Tuple[List[Dict[str, np.ndarray]], List[Dict[str, Any]]]:
        for idx, remote in enumerate(self.remotes):
            ep_val = episode_counts[idx] if episode_counts else 0
            remote.send(("reset", ep_val))
        results = [remote.recv() for remote in self.remotes]
        obs_list, info_list = zip(*results)
        return list(obs_list), list(info_list)

    def step(self, actions_list: List[Dict[str, Any]]) -> Tuple[List[Dict[str, np.ndarray]], List[Dict[str, float]], List[bool], List[Dict[str, Any]]]:
        for remote, act in zip(self.remotes, actions_list):
            remote.send(("step", act))
        results = [remote.recv() for remote in self.remotes]
        obs_list, rewards_list, dones_list, infos_list = zip(*results)
        return list(obs_list), list(rewards_list), list(dones_list), list(infos_list)

    def close(self):
        for remote in self.remotes:
            try:
                remote.send(("close", None))
            except Exception:
                pass
        for p in self.processes:
            p.join(timeout=2.0)


# ==============================================================================
# 2. Rollout Buffer for Centralized Training with Decentralized Execution
# ==============================================================================

class MAPPORolloutBuffer:
    """
    Stores multi-worker rollouts across all 7 decentralized actors and the centralized critic.
    Computes Generalized Advantage Estimation (GAE) per agent.
    """
    def __init__(self, num_steps: int, num_workers: int, gamma: float = 0.99, gae_lambda: float = 0.95):
        self.num_steps = num_steps
        self.num_workers = num_workers
        self.gamma = gamma
        self.gae_lambda = gae_lambda

        # Joint critic observations: [T, W, 158]
        self.joint_obs = np.zeros((num_steps, num_workers, TOTAL_JOINT_OBS_DIM), dtype=np.float32)
        self.values = np.zeros((num_steps, num_workers), dtype=np.float32)
        self.dones = np.zeros((num_steps, num_workers), dtype=np.bool_)

        # Decentralized Actor buffers
        self.actor_obs: Dict[str, np.ndarray] = {}
        self.actor_actions: Dict[str, np.ndarray] = {}
        self.actor_log_probs: Dict[str, np.ndarray] = {}
        self.actor_rewards: Dict[str, np.ndarray] = {}
        self.actor_advantages: Dict[str, np.ndarray] = {}
        self.actor_returns: Dict[str, np.ndarray] = {}

        for aid in MARL_AGENT_IDS:
            obs_dim = STATION_OBS_DIM if aid.startswith("station_") else CORRIDOR_OBS_DIM
            act_dim = 2 if aid.startswith("station_") else 1
            self.actor_obs[aid] = np.zeros((num_steps, num_workers, obs_dim), dtype=np.float32)
            self.actor_actions[aid] = np.zeros((num_steps, num_workers, act_dim) if act_dim > 1 else (num_steps, num_workers), dtype=np.int64)
            self.actor_log_probs[aid] = np.zeros((num_steps, num_workers), dtype=np.float32)
            self.actor_rewards[aid] = np.zeros((num_steps, num_workers), dtype=np.float32)
            self.actor_advantages[aid] = np.zeros((num_steps, num_workers), dtype=np.float32)
            self.actor_returns[aid] = np.zeros((num_steps, num_workers), dtype=np.float32)

        self.step_idx = 0

    def insert(
        self,
        joint_obs: np.ndarray,
        values: np.ndarray,
        dones: np.ndarray,
        actor_obs: Dict[str, np.ndarray],
        actor_actions: Dict[str, np.ndarray],
        actor_log_probs: Dict[str, np.ndarray],
        actor_rewards: Dict[str, np.ndarray]
    ):
        t = self.step_idx
        self.joint_obs[t] = joint_obs
        self.values[t] = values
        self.dones[t] = dones

        for aid in MARL_AGENT_IDS:
            self.actor_obs[aid][t] = actor_obs[aid]
            self.actor_actions[aid][t] = actor_actions[aid]
            self.actor_log_probs[aid][t] = actor_log_probs[aid]
            self.actor_rewards[aid][t] = actor_rewards[aid]

        self.step_idx += 1

    def compute_gae(self, last_values: np.ndarray):
        """Computes Generalized Advantage Estimation across all agents."""
        for aid in MARL_AGENT_IDS:
            last_adv = np.zeros(self.num_workers, dtype=np.float32)
            for t in reversed(range(self.num_steps)):
                next_val = last_values if t == self.num_steps - 1 else self.values[t + 1]
                next_non_terminal = 1.0 - self.dones[t].astype(np.float32)
                delta = self.actor_rewards[aid][t] + self.gamma * next_val * next_non_terminal - self.values[t]
                self.actor_advantages[aid][t] = delta + self.gamma * self.gae_lambda * next_non_terminal * last_adv
                last_adv = self.actor_advantages[aid][t]

            self.actor_returns[aid] = self.actor_advantages[aid] + self.values


# ==============================================================================
# 3. MAPPO Multi-Agent Trainer
# ==============================================================================

class MAPPOTrainer:
    """Centralized Training with Decentralized Execution Trainer for Autonomous Dispatching."""
    def __init__(
        self,
        dispatcher: MAPPODispatcher,
        lr_actor: float = 3e-4,
        lr_critic: float = 1e-3,
        clip_eps: float = 0.2,
        entropy_coef: float = 0.01,
        val_coef: float = 0.5,
        max_grad_norm: float = 0.5
    ):
        self.dispatcher = dispatcher
        self.clip_eps = clip_eps
        self.entropy_coef = entropy_coef
        self.val_coef = val_coef
        self.max_grad_norm = max_grad_norm

        # Actor Optimizers
        self.actor_optimizers: Dict[str, optim.Optimizer] = {
            aid: optim.Adam(self.dispatcher.actors[aid].parameters(), lr=lr_actor)
            for aid in MARL_AGENT_IDS
        }

        # Centralized Critic Optimizer
        self.critic_optimizer = optim.Adam(self.dispatcher.critic.parameters(), lr=lr_critic)

    def train_step(self, buffer: MAPPORolloutBuffer, num_epochs: int = 4, batch_size: int = 64) -> Dict[str, float]:
        """Performs PPO mini-batch updates across actors and centralized critic."""
        num_samples = buffer.num_steps * buffer.num_workers
        indices = np.arange(num_samples)

        critic_losses = []
        actor_losses = {aid: [] for aid in MARL_AGENT_IDS}

        flat_joint_obs = buffer.joint_obs.reshape(-1, TOTAL_JOINT_OBS_DIM)
        flat_values = buffer.values.reshape(-1)

        # Average returns across agents for centralized value target
        stacked_returns = np.stack([buffer.actor_returns[aid].reshape(-1) for aid in MARL_AGENT_IDS], axis=0)
        mean_flat_returns = np.mean(stacked_returns, axis=0)

        for _ in range(num_epochs):
            np.random.shuffle(indices)

            for start in range(0, num_samples, batch_size):
                end = start + batch_size
                mb_idx = indices[start:end]

                # --- 1. Centralized Critic Update ---
                mb_joint_obs = torch.as_tensor(flat_joint_obs[mb_idx], dtype=torch.float32)
                mb_target_val = torch.as_tensor(mean_flat_returns[mb_idx], dtype=torch.float32)

                val_pred = self.dispatcher.critic.evaluate_state(mb_joint_obs)
                critic_loss = nn.functional.mse_loss(val_pred, mb_target_val)

                self.critic_optimizer.zero_grad()
                critic_loss.backward()
                nn.utils.clip_grad_norm_(self.dispatcher.critic.parameters(), self.max_grad_norm)
                self.critic_optimizer.step()
                critic_losses.append(critic_loss.item())

                # --- 2. Decentralized Actors Update ---
                for aid in MARL_AGENT_IDS:
                    actor = self.dispatcher.actors[aid]
                    opt = self.actor_optimizers[aid]

                    flat_obs = buffer.actor_obs[aid].reshape(-1, buffer.actor_obs[aid].shape[-1])
                    flat_act = buffer.actor_actions[aid].reshape(-1, buffer.actor_actions[aid].shape[-1]) if aid.startswith("station_") else buffer.actor_actions[aid].reshape(-1)
                    flat_old_log_probs = buffer.actor_log_probs[aid].reshape(-1)
                    flat_adv = buffer.actor_advantages[aid].reshape(-1)

                    mb_obs = torch.as_tensor(flat_obs[mb_idx], dtype=torch.float32)
                    mb_act = torch.as_tensor(flat_act[mb_idx], dtype=torch.int64)
                    mb_old_lp = torch.as_tensor(flat_old_log_probs[mb_idx], dtype=torch.float32)
                    mb_adv = torch.as_tensor(flat_adv[mb_idx], dtype=torch.float32)

                    # Normalize advantages
                    mb_adv = (mb_adv - mb_adv.mean()) / (mb_adv.std() + 1e-8)

                    new_log_prob, entropy = actor.evaluate_actions(mb_obs, mb_act)
                    ratio = torch.exp(new_log_prob - mb_old_lp)

                    surr1 = ratio * mb_adv
                    surr2 = torch.clamp(ratio, 1.0 - self.clip_eps, 1.0 + self.clip_eps) * mb_adv
                    policy_loss = - torch.min(surr1, surr2).mean()
                    ent_loss = - self.entropy_coef * entropy.mean()

                    actor_loss = policy_loss + ent_loss

                    opt.zero_grad()
                    actor_loss.backward()
                    nn.utils.clip_grad_norm_(actor.parameters(), self.max_grad_norm)
                    opt.step()
                    actor_losses[aid].append(actor_loss.item())

        mean_actor_loss = float(np.mean([np.mean(losses) for losses in actor_losses.values() if losses]))
        return {
            "critic_loss": float(np.mean(critic_losses)),
            "actor_loss": mean_actor_loss
        }


# ==============================================================================
# 4. Main Training Orchestrator
# ==============================================================================

def train_mappo(
    total_timesteps: int = 50000,
    num_workers: int = 8,
    rollout_steps: int = 64,
    start_time: float = 21600.0,
    horizon: float = 7200.0,
    sumocfg_path: Optional[str] = None,
    wave_name: Optional[str] = None,
    save_path: str = DEFAULT_CHECKPOINT,
    best_model_path: str = DEFAULT_BEST_MODEL,
    load_checkpoint: Optional[str] = None
):
    print("=" * 115)
    print("AUTONOMOUS RAILWAY DISPATCHER: MULTI-AGENT PPO (MAPPO) CTDE TRAINING")
    print(f"Workers: {num_workers} parallel CPU processes | Rollout Steps/Worker: {rollout_steps}")
    print(f"Total Target Timesteps: {total_timesteps} | Batch Concurrency: {num_workers * rollout_steps} steps/iter")
    wave_info = f"Wave: {wave_name} | " if wave_name else ""
    print(f"{wave_info}Operational Horizon: {start_time/3600:.1f}h to {(start_time+horizon)/3600:.1f}h")
    if sumocfg_path:
        print(f"SUMO Config: {sumocfg_path}")
    if load_checkpoint:
        print(f"Resuming weights from checkpoint: {load_checkpoint}")
    print("=" * 115)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # Validate SUMO configuration before spawning workers
    cfg_to_use = sumocfg_path if sumocfg_path else SUMOCFG_PATH
    if not os.path.exists(cfg_to_use):
        raise FileNotFoundError(f"SUMO configuration not found at: {cfg_to_use}")

    # Initialize MAPPODispatcher
    dispatcher = MAPPODispatcher(checkpoint_path=load_checkpoint, exception_gating=False, smart_interlocking=False)
    trainer = MAPPOTrainer(dispatcher=dispatcher, lr_actor=3e-4, lr_critic=1e-3)

    print(f"[*] Initializing {num_workers} parallel environment workers...")
    env_pool = ParallelMultiAgentEnv(
        num_workers=num_workers,
        start_time=start_time,
        horizon=horizon,
        sumocfg_path=cfg_to_use,
        base_seed=42
    )

    buffer = MAPPORolloutBuffer(
        num_steps=rollout_steps,
        num_workers=num_workers,
        gamma=0.99,
        gae_lambda=0.95
    )

    obs_list, infos_list = env_pool.reset()
    total_steps = 0
    iteration = 0
    best_mean_delay = float("inf")
    t0 = time.time()

    try:
        while total_steps < total_timesteps:
            iteration += 1
            iter_start = time.time()
            buffer.step_idx = 0

            # -------------------------------------------------------------
            # A. Collect Rollout across All Parallel Workers
            # -------------------------------------------------------------
            for step_in_iter in range(rollout_steps):
                # Construct joint observations and local agent observation arrays
                joint_obs_batch = np.zeros((num_workers, TOTAL_JOINT_OBS_DIM), dtype=np.float32)
                actor_obs_batch = {
                    aid: np.zeros((num_workers, STATION_OBS_DIM if aid.startswith("station_") else CORRIDOR_OBS_DIM), dtype=np.float32)
                    for aid in MARL_AGENT_IDS
                }

                for w_idx in range(num_workers):
                    obs_dict = obs_list[w_idx]
                    joint_features = []
                    for aid in MARL_AGENT_IDS:
                        o = obs_dict.get(aid, np.zeros(STATION_OBS_DIM if aid.startswith("station_") else CORRIDOR_OBS_DIM))
                        actor_obs_batch[aid][w_idx] = o
                        joint_features.append(o)
                    joint_obs_batch[w_idx] = np.concatenate(joint_features)

                # Centralized Critic evaluation
                with torch.no_grad():
                    t_joint = torch.as_tensor(joint_obs_batch, dtype=torch.float32)
                    values = dispatcher.critic.evaluate_state(t_joint).cpu().numpy()

                # Decentralized Actors action sampling
                actor_actions_batch = {}
                actor_log_probs_batch = {}
                actions_to_send = [{} for _ in range(num_workers)]

                with torch.no_grad():
                    for aid in MARL_AGENT_IDS:
                        t_obs = torch.as_tensor(actor_obs_batch[aid], dtype=torch.float32)
                        acts, lps = dispatcher.actors[aid].get_action_and_log_prob(t_obs, deterministic=False)
                        actor_actions_batch[aid] = acts.cpu().numpy()
                        actor_log_probs_batch[aid] = lps.cpu().numpy()

                        for w_idx in range(num_workers):
                            actions_to_send[w_idx][aid] = actor_actions_batch[aid][w_idx]

                # Step parallel environments
                next_obs_list, rewards_list, dones_list, infos_list = env_pool.step(actions_to_send)

                # Format rewards
                actor_rewards_batch = {aid: np.zeros(num_workers, dtype=np.float32) for aid in MARL_AGENT_IDS}
                for w_idx in range(num_workers):
                    for aid in MARL_AGENT_IDS:
                        actor_rewards_batch[aid][w_idx] = rewards_list[w_idx].get(aid, 0.0)

                # Store transition
                buffer.insert(
                    joint_obs=joint_obs_batch,
                    values=values,
                    dones=np.array(dones_list, dtype=np.bool_),
                    actor_obs=actor_obs_batch,
                    actor_actions=actor_actions_batch,
                    actor_log_probs=actor_log_probs_batch,
                    actor_rewards=actor_rewards_batch
                )

                obs_list = next_obs_list
                total_steps += num_workers

            # -------------------------------------------------------------
            # B. Compute GAE and Update Policies
            # -------------------------------------------------------------
            # Compute last values for GAE bootstrap
            joint_obs_last = np.zeros((num_workers, TOTAL_JOINT_OBS_DIM), dtype=np.float32)
            for w_idx in range(num_workers):
                joint_features = [obs_list[w_idx].get(aid, np.zeros(STATION_OBS_DIM if aid.startswith("station_") else CORRIDOR_OBS_DIM)) for aid in MARL_AGENT_IDS]
                joint_obs_last[w_idx] = np.concatenate(joint_features)

            with torch.no_grad():
                t_joint_last = torch.as_tensor(joint_obs_last, dtype=torch.float32)
                last_vals = dispatcher.critic.evaluate_state(t_joint_last).cpu().numpy()

            buffer.compute_gae(last_vals)

            # Perform PPO optimization
            loss_dict = trainer.train_step(buffer, num_epochs=4, batch_size=64)

            # Metrics
            iter_duration = time.time() - iter_start
            sps = (num_workers * rollout_steps) / iter_duration
            mean_delay = float(np.mean([info.get("mean_delay_sec", 0.0) for info in infos_list]))
            mean_punc = float(np.mean([info.get("punctuality_pct", 100.0) for info in infos_list]))
            mean_reward = float(np.mean(buffer.joint_obs)) # proxy

            print(
                f"[Iter {iteration:>3}] Steps: {total_steps:>6}/{total_timesteps} | "
                f"SPS: {sps:>5.1f} | Actor Loss: {loss_dict['actor_loss']:>7.4f} | "
                f"Critic Loss: {loss_dict['critic_loss']:>7.4f} | Mean Delay: {mean_delay:>5.2f}s | "
                f"Punc: {mean_punc:>5.1f}%"
            )

            # Save periodic checkpoint
            dispatcher.save(save_path)

            if mean_delay < best_mean_delay:
                best_mean_delay = mean_delay
                dispatcher.save(best_model_path)

    finally:
        print("\n[*] Shutting down environment workers cleanly...")
        env_pool.close()

    total_time = time.time() - t0
    print("=" * 115)
    print(f"[✓] MAPPO TRAINING COMPLETED IN {total_time:.1f}s ({total_time/60:.2f} min)!")
    print(f"[✓] Saved Final Checkpoint: {save_path}")
    print(f"[✓] Saved Best Model: {best_model_path}")
    print("=" * 115)


def main():
    parser = argparse.ArgumentParser(description="Train Multi-Agent PPO (MAPPO) Railway Dispatcher")
    parser.add_argument("--timesteps", type=int, default=15000, help="Total training timesteps across all workers")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel SUMO workers (utilizing 32 CPU cores)")
    parser.add_argument("--rollout-steps", type=int, default=64, help="Rollout steps per worker per iteration")
    parser.add_argument("--wave", type=str, default=None, choices=list(WAVE_CONFIGS.keys()) + ["custom"],
                        help="Operational wave preset for curriculum training")
    parser.add_argument("--day", type=str, default=None, choices=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                        help="Calendar day to simulate (Mon..Sun)")
    parser.add_argument("--sumocfg-path", type=str, default=None, help="Custom SUMO configuration path")
    parser.add_argument("--start-time", type=float, default=21600.0, help="Simulation start time (default: 06:00 AM)")
    parser.add_argument("--horizon", type=float, default=7200.0, help="Simulation horizon in seconds (default: 2 hours)")
    parser.add_argument("--save-path", type=str, default=DEFAULT_CHECKPOINT, help="Output path for model checkpoint")
    parser.add_argument("--best-path", type=str, default=DEFAULT_BEST_MODEL, help="Output path for best model checkpoint")
    parser.add_argument("--load-checkpoint", type=str, default=None, help="Resume training from an existing checkpoint")
    args = parser.parse_args()

    start_time = args.start_time
    horizon = args.horizon
    day = args.day
    wave_name = args.wave

    if args.wave and args.wave != "custom":
        cfg = WAVE_CONFIGS[args.wave]
        start_time = cfg["start_time"]
        horizon = cfg["horizon"]
        if "day" in cfg and not day:
            day = cfg["day"]

    cfg_path = args.sumocfg_path
    if not cfg_path and day:
        candidate_cfg = os.path.join(ROOT_DIR, "trains", "sumo_config", "days", day, "train_simulation.sumocfg")
        if os.path.exists(candidate_cfg):
            cfg_path = candidate_cfg
        else:
            raise FileNotFoundError(f"Day-specific SUMO configuration for '{day}' not found at: {candidate_cfg}")

    train_mappo(
        total_timesteps=args.timesteps,
        num_workers=args.workers,
        rollout_steps=args.rollout_steps,
        start_time=start_time,
        horizon=horizon,
        sumocfg_path=cfg_path,
        wave_name=wave_name,
        save_path=args.save_path,
        best_model_path=args.best_path,
        load_checkpoint=args.load_checkpoint
    )


if __name__ == "__main__":
    main()
