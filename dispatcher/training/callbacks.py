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

        # Periodic logging and evaluation
        if self.n_calls % self.check_freq == 0:
            if self.episode_delays:
                avg_delay = float(np.mean(self.episode_delays[-self.check_freq:]))
                avg_punc = float(np.mean(self.episode_punctualities[-self.check_freq:]))
                tot_knock_on = int(np.sum(self.episode_knock_ons[-self.check_freq:]))

                # Log to TensorBoard
                self.logger.record("railway/mean_delay_sec", avg_delay)
                self.logger.record("railway/punctuality_pct", avg_punc)
                self.logger.record("railway/knock_on_events", tot_knock_on)

                if self.verbose > 0:
                    print(
                        f"Step {self.n_calls:6d} | "
                        f"Mean Delay: {avg_delay:6.1f}s | "
                        f"Punctuality: {avg_punc:5.1f}% | "
                        f"Knock-ons: {tot_knock_on:3d}"
                    )

                # Save best model if delay reduced
                if avg_delay < self.best_mean_delay:
                    self.best_mean_delay = avg_delay
                    best_model_path = os.path.join(self.save_path, "best_model.zip")
                    self.model.save(best_model_path)
                    if self.verbose > 0:
                        print(f"[*] New best model saved with mean delay: {avg_delay:.1f}s -> {best_model_path}")

        return True
