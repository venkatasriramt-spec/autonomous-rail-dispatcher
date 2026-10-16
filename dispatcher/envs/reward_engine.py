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
        delay_weight: float = 0.05,
        delay_delta_weight: float = 0.08,
        secondary_delay_weight: float = 0.15,
        ontime_bonus: float = 1.0,
        completion_bonus: float = 5.0,
        unnecessary_stop_penalty: float = 0.5,
        action_penalty_weight: float = 0.4
    ):
        self.delay_weight = delay_weight
        self.delay_delta_weight = delay_delta_weight
        self.secondary_delay_weight = secondary_delay_weight
        self.ontime_bonus = ontime_bonus
        self.completion_bonus = completion_bonus
        self.unnecessary_stop_penalty = unnecessary_stop_penalty
        self.action_penalty_weight = action_penalty_weight

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
        knock_on_events: int,
        focus_veh_id: Any = None,
        action: Any = None
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

        # 5. Intervention Cost & Dynamic Conflict Resolution
        if focus_veh_id and action is not None and focus_veh_id in train_states:
            focus_state = train_states[focus_veh_id]
            route_act = int(action[0]) if len(action) > 0 else 0
            plat_act = int(action[1]) if len(action) > 1 else 0
            hold_act = int(action[2]) if len(action) > 2 else 0

            leader_dist = focus_state.get("leader_dist", 3000.0)
            leader_id = focus_state.get("leader_id", None)
            has_close_leader = (leader_id is not None and leader_dist < 2000.0)
            is_overtake_candidate = focus_state.get("is_overtake_candidate", False)
            delay_sec = focus_state.get("delay_sec", 0.0)
            dist_to_stop = focus_state.get("dist_to_next_stop", 9999.0)
            is_at_stop = focus_state.get("is_at_stop", False)
            plat_occupied = focus_state.get("scheduled_platform_occupied", False)
            approaching_station = (dist_to_stop < 2500.0 and dist_to_stop > 400.0 and not is_at_stop)

            # Train is truly nominal: On-schedule, clear track ahead, scheduled platform is free
            is_nominal = (delay_sec < 60.0 and not has_close_leader and not is_overtake_candidate and not plat_occupied)

            # A. Platform Switch Evaluation:
            if plat_act > 0:
                if plat_occupied and approaching_station:
                    # SMART INTERVENTION: Active conflict resolution!
                    # Reassigning away from an occupied platform avoids a massive mainline blockage
                    total_reward += 1.5
                elif is_at_stop or dist_to_stop > 2500.0 or dist_to_stop < 400.0 or is_nominal:
                    # Frivolous platform change
                    total_reward -= self.action_penalty_weight * 1.0

            # B. Route Divert Evaluation:
            if route_act > 0:
                if is_overtake_candidate:
                    # Smart overtakes/sidings
                    total_reward += 1.0
                elif is_nominal or not has_close_leader:
                    total_reward -= self.action_penalty_weight * 1.0

            # C. Hold Action Evaluation:
            if hold_act > 0:
                if has_close_leader:
                    # Regulating hold to allow spacing
                    total_reward += 0.2
                else:
                    # Unnecessary delay insertion
                    total_reward -= self.action_penalty_weight * (1.0 if hold_act == 1 else 2.0)

            # D. Timetable Adherence Bonus vs Conflict Neglect:
            if route_act == 0 and plat_act == 0 and hold_act == 0:
                if is_nominal:
                    # Reward smooth timetable flow
                    total_reward += 0.1
                elif plat_occupied and approaching_station:
                    # Neglect penalty: heading straight into an occupied platform without intervening!
                    total_reward -= 0.5

        return float(total_reward)
