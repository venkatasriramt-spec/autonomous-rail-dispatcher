"""
callbacks.py
Custom Stable-Baselines3 callbacks for tracking railway dispatching KPIs during training:
- Mean and Max Delay (seconds)
- Punctuality Percentage (% arrivals <= 3 min)
- Knock-On Delay Events
- Automated Best Model Checkpointing
"""

import os
import numpy as np
from stable_baselines3.common.callbacks import BaseCallback


class RailwayMetricsCallback(BaseCallback):
    def __init__(
        self,
        check_freq: int = 100,
        save_path: str = "dispatcher/models",
        verbose: int = 1
    ):
        super().__init__(verbose)
        self.check_freq = check_freq
        self.save_path = save_path
        os.makedirs(save_path, exist_ok=True)
        self.best_mean_delay = float("inf")
        self.best_reward = float("-inf")
        self.episode_delays = []
        self.episode_punctualities = []
        self.episode_knock_ons = []
        self.episode_nonzeros = []
        self.episode_plat_acts = []
        self.episode_route_acts = []
        self.episode_hold_acts = []

        self.enable_watchdog = True
        self.consecutive_stagnations = 0

    def _on_step(self) -> bool:
        # Extract info dict from current step
        infos = self.locals.get("infos", [])
        for info in infos:
            if "mean_delay_sec" in info:
                self.episode_delays.append(info["mean_delay_sec"])
            if "punctuality_pct" in info:
                self.episode_punctualities.append(info["punctuality_pct"])
            if "knock_on_events" in info:
                self.episode_knock_ons.append(info["knock_on_events"])
            if "action_nonzero" in info:
                self.episode_nonzeros.append(1.0 if info["action_nonzero"] else 0.0)
            if "action_plat" in info:
                self.episode_plat_acts.append(1 if info["action_plat"] else 0)
            if "action_route" in info:
                self.episode_route_acts.append(1 if info["action_route"] else 0)
            if "action_hold" in info:
                self.episode_hold_acts.append(1 if info["action_hold"] else 0)

        # Periodic logging and evaluation
        if self.n_calls % self.check_freq == 0:
            if self.episode_delays:
                recent_slice = -self.check_freq * len(infos) if infos else -self.check_freq
                avg_delay = float(np.mean(self.episode_delays[recent_slice:]))
                avg_punc = float(np.mean(self.episode_punctualities[recent_slice:]))
                tot_knock_on = int(np.mean(self.episode_knock_ons[recent_slice:])) if self.episode_knock_ons else 0

                interv_pct = float(np.mean(self.episode_nonzeros[recent_slice:])) * 100.0 if self.episode_nonzeros else 0.0
                tot_plat = int(np.sum(self.episode_plat_acts[recent_slice:])) if self.episode_plat_acts else 0
                tot_route = int(np.sum(self.episode_route_acts[recent_slice:])) if self.episode_route_acts else 0
                tot_hold = int(np.sum(self.episode_hold_acts[recent_slice:])) if self.episode_hold_acts else 0

                # Log to TensorBoard
                self.logger.record("railway/mean_delay_sec", avg_delay)
                self.logger.record("railway/punctuality_pct", avg_punc)
                self.logger.record("railway/knock_on_events", tot_knock_on)
                self.logger.record("railway/intervention_rate_pct", interv_pct)

                if self.verbose > 0:
                    print(
                        f"Step {self.n_calls:6d} | "
                        f"Delay: {avg_delay:6.1f}s | "
                        f"Punc: {avg_punc:5.1f}% | "
                        f"Knock-ons: {tot_knock_on:4d} | "
                        f"Interv: {interv_pct:4.1f}% (Plat: {tot_plat:3d}, Route: {tot_route:2d}, Hold: {tot_hold:2d})"
                    )

                # Save best model if delay reduced and policy is taking active, controlled interventions
                if avg_delay < self.best_mean_delay:
                    self.best_mean_delay = avg_delay
                    best_model_path = os.path.join(self.save_path, "best_model.zip")
                    self.model.save(best_model_path)
                    if self.verbose > 0:
                        print(f"[*] New best model saved with mean delay: {avg_delay:.1f}s -> {best_model_path}")

                # Automated Early-Stopping Watchdog
                if self.enable_watchdog and self.num_timesteps >= 49152:  # After 3 PPO iterations
                    # Check 1: 100% Passive Collapse (Policy learned to do nothing)
                    if interv_pct == 0.0:
                        self.consecutive_stagnations += 1
                        print(f"[!] WATCHDOG: Policy collapsed to 0% interventions ({self.consecutive_stagnations}/3)")
                    # Check 2: Severe Gridlock Degradation (Delay > 350s or Punctuality < 70%)
                    elif avg_delay > 350.0 or avg_punc < 70.0:
                        self.consecutive_stagnations += 1
                        print(f"[!] WATCHDOG: Severe gridlock degradation (Delay: {avg_delay:.1f}s, Punc: {avg_punc:.1f}%, {self.consecutive_stagnations}/3)")
                    else:
                        self.consecutive_stagnations = 0

                    if self.consecutive_stagnations >= 3:
                        print(f"\n[🛑 WATCHDOG HALT] Early stopping triggered: policy is learning pathological behavior. Halting training.")
                        return False

        return True
