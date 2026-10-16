"""
perturbations.py
Injects controlled, realistic railway disruptions and primary delays into SUMO/TraCI.
Used for training robust RL dispatchers and stress-testing baselines.
"""

import random
from typing import Dict, List, Optional, Any


class PerturbationConfig:
    def __init__(
        self,
        name: str = "nominal",
        mode: str = "none",  # "none", "train_delay", "platform_blockage", "stochastic", "compound", "scheduled"
        target_train_id: Optional[str] = None,
        trigger_time_sec: float = 0.0,
        delay_duration_sec: float = 0.0,
        blocked_lane_id: Optional[str] = None,
        blockage_duration_sec: float = 0.0,
        stochastic_rate: float = 0.0,
        events: Optional[List[Dict[str, Any]]] = None,
        seed: Optional[int] = 42
    ):
        self.name = name
        self.mode = mode
        self.target_train_id = target_train_id
        self.trigger_time_sec = trigger_time_sec
        self.delay_duration_sec = delay_duration_sec
        self.blocked_lane_id = blocked_lane_id
        self.blockage_duration_sec = blockage_duration_sec
        self.stochastic_rate = stochastic_rate
        self.events = events or []
        self.seed = seed


class DisruptionManager:
    """
    Manages runtime disruption triggers in SUMO via TraCI.
    Supports both legacy single disruptions and multi-wave 24-hour scheduled disruption suites.
    """

    def __init__(self, config: Optional[PerturbationConfig] = None):
        self.config = config or PerturbationConfig(name="nominal", mode="none")
        self.rng = random.Random(self.config.seed)
        self.applied_disruptions: List[Dict[str, Any]] = []
        self.primary_delayed_trains: Dict[str, float] = {}
        self.pending_events: List[Dict[str, Any]] = list(self.config.events or [])

    def reset(self, config: Optional[PerturbationConfig] = None):
        if config:
            self.config = config
        self.rng = random.Random(self.config.seed)
        self.applied_disruptions.clear()
        self.primary_delayed_trains.clear()
        self.pending_events = [dict(ev) for ev in (self.config.events or [])]

    def step(self, sim_time: float, traci_module: Any):
        """
        Evaluate and inject disruptions at the given simulation time.
        """
        # 0. Check and execute multi-wave scheduled events
        if self.pending_events:
            remaining_events = []
            for ev in self.pending_events:
                ev_time = ev.get("trigger_time", 0.0)
                if sim_time >= ev_time:
                    ev_type = ev.get("type", "")
                    if ev_type == "platform_blockage":
                        lane_id = ev["lane_id"]
                        try:
                            orig_speed = traci_module.lane.getMaxSpeed(lane_id)
                            traci_module.lane.setMaxSpeed(lane_id, 0.0)
                            self.applied_disruptions.append({
                                "type": "platform_blockage",
                                "name": ev.get("name", "Platform Blockage"),
                                "lane_id": lane_id,
                                "orig_speed": orig_speed,
                                "start_time": sim_time,
                                "duration": ev.get("duration", 1800.0)
                            })
                        except Exception:
                            remaining_events.append(ev)
                    elif ev_type == "train_delay":
                        active_vehs = traci_module.vehicle.getIDList()
                        pattern = ev.get("target_pattern", "")
                        target_id = ev.get("target_id")
                        if not target_id or target_id not in active_vehs:
                            mainline_vehs = [
                                v for v in active_vehs
                                if not any(x in traci_module.vehicle.getRoadID(v) for x in ("_yard_", "_pocket_", "_buf_", ":"))
                            ]
                            if pattern:
                                candidates = [v for v in mainline_vehs if pattern in v]
                            else:
                                candidates = mainline_vehs
                            target_id = candidates[0] if candidates else (mainline_vehs[0] if mainline_vehs else (active_vehs[0] if active_vehs else None))

                        if target_id and target_id in active_vehs:
                            road_id = traci_module.vehicle.getRoadID(target_id)
                            if road_id and not road_id.startswith(":") and "_pocket_" not in road_id and "_yard_" not in road_id:
                                lane_pos = traci_module.vehicle.getLanePosition(target_id)
                                lane_id = traci_module.vehicle.getLaneID(target_id)
                                try:
                                    lane_len = traci_module.lane.getLength(lane_id)
                                except Exception:
                                    lane_len = 1000.0
                                pos = min(lane_pos + 10.0, max(1.0, lane_len - 15.0))
                                dur = ev.get("duration", 600.0)
                                try:
                                    traci_module.vehicle.setStop(
                                        target_id,
                                        edgeID=road_id,
                                        pos=pos,
                                        laneIndex=0,
                                        duration=dur,
                                        flags=0
                                    )
                                    self.primary_delayed_trains[target_id] = dur
                                    self.applied_disruptions.append({
                                        "type": "train_delay",
                                        "name": ev.get("name", "Train Breakdown"),
                                        "train_id": target_id,
                                        "time": sim_time,
                                        "duration": dur,
                                        "edge": road_id
                                    })
                                except Exception:
                                    remaining_events.append(ev)
                            else:
                                remaining_events.append(ev)
                        else:
                            remaining_events.append(ev)
                else:
                    remaining_events.append(ev)
            self.pending_events = remaining_events

        if self.config.mode == "none" and not self.config.events:
            return

        # 1. Targeted single-train breakdown / dwell extension
        if self.config.mode in ("train_delay", "compound"):
            if (
                len(self.primary_delayed_trains) == 0
                and sim_time >= self.config.trigger_time_sec
            ):
                active_vehs = traci_module.vehicle.getIDList()
                target_id = self.config.target_train_id
                # If target is specified or pick an active train running on a mainline corridor
                if not target_id or target_id not in active_vehs:
                    mainline_vehs = [
                        v for v in active_vehs
                        if not any(x in traci_module.vehicle.getRoadID(v) for x in ("_yard_", "_pocket_", "_buf_", ":"))
                    ]
                    candidates = [v for v in mainline_vehs if "REG-" in v or "FRT-" in v or "IC-" in v]
                    target_id = candidates[0] if candidates else (mainline_vehs[0] if mainline_vehs else (active_vehs[0] if active_vehs else None))

                if target_id and target_id in active_vehs:
                    road_id = traci_module.vehicle.getRoadID(target_id)
                    # Wait if train is currently inside an internal junction or yard pocket
                    if road_id and not road_id.startswith(":") and "_pocket_" not in road_id and "_yard_" not in road_id:
                        lane_pos = traci_module.vehicle.getLanePosition(target_id)
                        lane_id = traci_module.vehicle.getLaneID(target_id)
                        try:
                            lane_len = traci_module.lane.getLength(lane_id)
                        except Exception:
                            lane_len = 1000.0
                        pos = min(lane_pos + 10.0, max(1.0, lane_len - 15.0))
                        try:
                            # Extend stop / force dwell
                            traci_module.vehicle.setStop(
                                target_id,
                                edgeID=road_id,
                                pos=pos,
                                laneIndex=0,
                                duration=self.config.delay_duration_sec,
                                flags=0
                            )
                            self.primary_delayed_trains[target_id] = self.config.delay_duration_sec
                            self.applied_disruptions.append({
                                "type": "train_delay",
                                "train_id": target_id,
                                "time": sim_time,
                                "duration": self.config.delay_duration_sec,
                                "edge": road_id
                            })
                        except Exception:
                            pass

        # 2. Platform Blockage
        if self.config.mode in ("platform_blockage", "compound"):
            has_plat_disruption = any(d.get("type") == "platform_blockage" for d in self.applied_disruptions)
            if (
                self.config.blocked_lane_id
                and not has_plat_disruption
                and sim_time >= self.config.trigger_time_sec
            ):
                lane_id = self.config.blocked_lane_id
                try:
                    orig_speed = traci_module.lane.getMaxSpeed(lane_id)
                    # Setting speed to 0.0 prevents entry/traversal without breaking network topology or routing
                    traci_module.lane.setMaxSpeed(lane_id, 0.0)
                    self.applied_disruptions.append({
                        "type": "platform_blockage",
                        "lane_id": lane_id,
                        "orig_speed": orig_speed,
                        "start_time": sim_time,
                        "duration": self.config.blockage_duration_sec
                    })
                except Exception:
                    pass

            # Re-open if duration elapsed
            for d in self.applied_disruptions:
                if d.get("type") == "platform_blockage" and not d.get("reopened"):
                    if sim_time >= d["start_time"] + d["duration"]:
                        try:
                            orig_speed = d.get("orig_speed", 13.89)
                            traci_module.lane.setMaxSpeed(d["lane_id"], orig_speed)
                            d["reopened"] = True
                        except Exception:
                            pass

        # 3. Stochastic Delays (Realistic random station dwell extensions)
        elif self.config.mode == "stochastic":
            active_vehs = traci_module.vehicle.getIDList()
            for v in active_vehs:
                if v not in self.primary_delayed_trains and self.rng.random() < self.config.stochastic_rate:
                    # Inject 120s to 450s random delay
                    delay = self.rng.randint(120, 450)
                    road_id = traci_module.vehicle.getRoadID(v)
                    try:
                        traci_module.vehicle.slowDown(v, 0.0, 10.0)
                        self.primary_delayed_trains[v] = delay
                        self.applied_disruptions.append({
                            "type": "stochastic_delay",
                            "train_id": v,
                            "time": sim_time,
                            "duration": delay,
                            "edge": road_id
                        })
                    except Exception:
                        pass
