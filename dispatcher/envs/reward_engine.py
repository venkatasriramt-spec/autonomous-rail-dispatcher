"""
reward_engine.py
Calculates domain-specific, priority-weighted railway dispatching rewards.
Rewards punctuality, delay reduction, and smooth traffic flow while penalizing
knock-on delays, platform congestion, and unnecessary stops.
"""

from typing import Dict, Any, List


class RewardEngine:
    def __init__(
        self,
        delay_weight: float = 0.01,
        delay_delta_weight: float = 0.05,
        secondary_delay_weight: float = 0.1,
        ontime_bonus: float = 1.0,
        completion_bonus: float = 5.0,
        unnecessary_stop_penalty: float = 0.5
    ):
        self.delay_weight = delay_weight
        self.delay_delta_weight = delay_delta_weight
        self.secondary_delay_weight = secondary_delay_weight
        self.ontime_bonus = ontime_bonus
        self.completion_bonus = completion_bonus
        self.unnecessary_stop_penalty = unnecessary_stop_penalty

        # Priority weights based on passenger capacity and class importance
        self.priority_weights = {
            "high_speed_emu_300": 1.0,
            "high_speed_emu_single": 0.85,
            "regional_emu_120": 0.6,
            "regional_dmu_120": 0.5,
            "intermodal_container_freight": 0.3,
            "electric_trunk_freight": 0.25,
            "heavy_freight_cargo": 0.15
        }
        self.prev_delays: Dict[str, float] = {}

    def get_priority_weight(self, vtype: str) -> float:
        for prefix, weight in self.priority_weights.items():
            if prefix in vtype:
                return weight
        if "HS-" in vtype or "high_speed" in vtype:
            return 1.0
        elif "REG-" in vtype or "regional" in vtype or "ALP-" in vtype:
            return 0.6
        elif "FRT-" in vtype or "freight" in vtype:
            return 0.2
        return 0.5

    def reset(self):
        self.prev_delays.clear()

    def compute_reward(
        self,
        train_states: Dict[str, Dict[str, Any]],
        departed_ontime: List[str],
        completed_trains: List[str],
        knock_on_events: int
    ) -> float:
        """
        Compute total reward for the step.
        """
        total_reward = 0.0

        # 1. Delay penalties
        for vid, state in train_states.items():
            delay = state.get("delay_sec", 0.0)
            vtype = state.get("vtype", "")
            weight = self.get_priority_weight(vtype)

            # Absolute delay penalty (linear + soft quadratic for severe delays)
            delay_norm = delay / 60.0  # delay in minutes
            penalty = weight * (delay_norm + 0.1 * (delay_norm ** 2))
            total_reward -= self.delay_weight * penalty

            # Delay delta (reward for recovering delay, penalize for worsening)
            prev_delay = self.prev_delays.get(vid, delay)
            delta = delay - prev_delay
            total_reward -= self.delay_delta_weight * weight * (delta / 60.0)
            self.prev_delays[vid] = delay

            # Penalty for stopping unexpectedly on mainline
            if state.get("speed", 10.0) < 0.1 and not state.get("is_at_scheduled_stop", False):
                total_reward -= self.unnecessary_stop_penalty * weight

        # 2. Knock-on / Secondary delay penalty
        if knock_on_events > 0:
            total_reward -= self.secondary_delay_weight * knock_on_events

        # 3. On-time departure bonus
        for vid in departed_ontime:
            total_reward += self.ontime_bonus

        # 4. Service completion bonus
        for vid in completed_trains:
            total_reward += self.completion_bonus

        return float(total_reward)
