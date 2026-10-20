"""
backend/core/sim_manager.py
Thread-safe master simulation manager orchestrating SUMO/TraCI, AI dispatchers,
telemetry capture, and WebSocket broadcasting.
"""

import os
import sys
import time
import math
import shutil
import random
import logging
import threading
import asyncio
from typing import Dict, Any, List, Optional

from backend.config import (
    ROOT_DIR,
    DAYS_DIR,
    DEFAULT_SUMOCFG,
    DEFAULT_MACRO_STEP_SEC,
    DEFAULT_SIM_SPEED,
    TELEMETRY_BROADCAST_HZ,
    CALENDAR_DAYS,
    DISPATCHER_MODELS,
    PPO_MODEL_PATH,
    MAPPO_MODEL_PATH
)
from backend.schemas.models import (
    SimulationState,
    SimulationMode,
    TrainTelemetry,
    PlatformTelemetry,
    DispatcherActionEvent,
    FleetKPIs,
    TelemetryFrame
)
from backend.core.dispatcher_bridge import DispatcherBridge
from backend.core.network_geometry import parse_network_geometry
from backend.core.telemetry_streamer import streamer

logger = logging.getLogger("sim_manager")

# Ensure SUMO tools
if "SUMO_HOME" in os.environ:
    sumo_tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    if sumo_tools not in sys.path:
        sys.path.append(sumo_tools)
elif os.path.exists("/usr/share/sumo/tools"):
    if "/usr/share/sumo/tools" not in sys.path:
        sys.path.append("/usr/share/sumo/tools")

try:
    import traci
except ImportError:
    traci = None


def format_sim_time(sim_sec: float) -> str:
    """Formats simulation seconds into HH:MM:SS."""
    total_sec = int(sim_sec) % 86400
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


class SimulationManager:
    """Coordinates the railway simulation lifecycle, AI dispatching, and streaming."""

    def __init__(self):
        self.state: SimulationState = SimulationState.STOPPED
        self.mode: SimulationMode = SimulationMode.LIVE_SUMO
        self.day: str = "Mon"
        self.sim_time_sec: float = 21600.0  # Default 06:00 AM (morning start)
        self.start_time_sec: float = 21600.0
        self.speed_multiplier: float = DEFAULT_SIM_SPEED
        self.macro_step_sec: float = DEFAULT_MACRO_STEP_SEC

        self.bridge: DispatcherBridge = DispatcherBridge(default_model="Centralized_PPO")
        self.env: Any = None
        self.geometry = parse_network_geometry()

        # Telemetry state
        self.trains_cache: List[Dict[str, Any]] = []
        self.platforms_cache: List[Dict[str, Any]] = []
        self.recent_actions: List[Dict[str, Any]] = []
        self.active_disruptions: List[str] = []
        self._applied_perturbations: List[Dict[str, Any]] = []
        self._demo_overrides: Dict[str, Dict[str, Any]] = {}
        self.total_actions_count: int = 0
        self.total_knock_ons: int = 0

        # Concurrency primitives
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.Lock()
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Sets the main asyncio loop for thread-safe WebSocket broadcasts."""
        self.event_loop = loop

    def get_status(self) -> Dict[str, Any]:
        """Returns the current simulation status and metrics."""
        with self._lock:
            active_count = len(self.trains_cache)
            delays = [t.get("delay_sec", 0.0) for t in self.trains_cache]
            mean_delay = float(sum(delays) / max(1, len(delays))) if delays else 0.0
            ontime = sum(1 for d in delays if d <= 180.0)
            punctuality = (ontime / max(1, len(delays))) * 100.0 if delays else 100.0

            return {
                "status": self.state,
                "mode": self.mode,
                "calendar_day": self.day,
                "dispatcher_model": self.bridge.active_model_name,
                "sim_time_sec": self.sim_time_sec,
                "time_formatted": format_sim_time(self.sim_time_sec),
                "speed_multiplier": self.speed_multiplier,
                "active_trains_count": active_count,
                "mean_delay_sec": round(mean_delay, 1),
                "punctuality_pct": round(punctuality, 1),
                "total_actions_taken": self.total_actions_count,
                "active_disruptions": list(self.active_disruptions)
            }

    def _get_sumocfg_path(self, day: str) -> str:
        """Finds or builds the isolated day config."""
        day_folder = DAYS_DIR / day
        cfg_file = day_folder / "train_simulation.sumocfg"
        if cfg_file.exists():
            return str(cfg_file)
        return str(DEFAULT_SUMOCFG)

    def play(self) -> bool:
        """Starts or resumes simulation execution."""
        with self._lock:
            if self.state == SimulationState.RUNNING:
                return True

            if self.state == SimulationState.PAUSED:
                self.state = SimulationState.RUNNING
                self._pause_event.clear()
                logger.info("Simulation resumed.")
                return True

            if self._thread and self._thread.is_alive():
                logger.warning("Cannot start simulation: previous worker thread is still alive.")
                return False

            # Start fresh from STOPPED
            self.state = SimulationState.RUNNING
            self._stop_event.clear()
            self._pause_event.clear()
            self._thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._thread.start()
            logger.info(f"Simulation started in mode {self.mode} on {self.day}.")
            return True

    def pause(self) -> bool:
        """Pauses simulation execution."""
        with self._lock:
            if self.state == SimulationState.RUNNING:
                self.state = SimulationState.PAUSED
                self._pause_event.set()
                logger.info("Simulation paused.")
                return True
            return False

    def step(self) -> bool:
        """Advances simulation by one macro-step (15s) while paused."""
        if self.state != SimulationState.PAUSED and self.state != SimulationState.STOPPED:
            self.pause()

        with self._lock:
            self._advance_one_macro_step()
            self._broadcast_frame()
            return True

    def reset(self, start_time_sec: Optional[float] = None) -> bool:
        """Stops and resets simulation state."""
        self._stop_current_worker()

        with self._lock:
            self.state = SimulationState.STOPPED
            if start_time_sec is not None:
                self.start_time_sec = start_time_sec
            self.sim_time_sec = self.start_time_sec
            self.trains_cache.clear()
            self.platforms_cache.clear()
            self.recent_actions.clear()
            self.active_disruptions.clear()
            self._applied_perturbations.clear()
            self._demo_overrides.clear()
            self.total_actions_count = 0
            self.total_knock_ons = 0

            if self.env:
                try:
                    self.env.close()
                except Exception:
                    pass
                self.env = None

            logger.info("Simulation reset.")
            self._broadcast_frame()
            return True

    def configure(
        self,
        day: Optional[str] = None,
        model: Optional[str] = None,
        mode: Optional[SimulationMode] = None,
        speed: Optional[float] = None,
        start_time_sec: Optional[float] = None
    ) -> Dict[str, Any]:
        """Applies configuration updates."""
        need_reset = False

        if day and day in CALENDAR_DAYS and day != self.day:
            self.day = day
            need_reset = True

        if mode and mode != self.mode:
            self.mode = mode
            need_reset = True

        if start_time_sec is not None and start_time_sec != self.start_time_sec:
            self.start_time_sec = start_time_sec
            need_reset = True

        if speed is not None and speed > 0:
            self.speed_multiplier = speed

        if model and model in DISPATCHER_MODELS:
            current_is_marl = self.bridge.is_marl_model()
            incoming_is_marl = self.bridge.is_marl_model(model)
            if incoming_is_marl != current_is_marl:
                self._stop_current_worker()
                need_reset = True
            with self._lock:
                self.bridge.load_model(model)

        if need_reset:
            self.reset(self.start_time_sec)

        return self.get_status()

    def _stop_current_worker(self):
        """Signals the worker thread to terminate cleanly."""
        self._stop_event.set()
        self._pause_event.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            if self._thread.is_alive():
                logger.warning("Worker thread did not terminate within timeout.")
                return
        self._thread = None

    def _init_env(self):
        """Initializes the RailwayDispatchEnv or MultiAgentRailwayEnv."""
        if self.mode != SimulationMode.LIVE_SUMO:
            return

        cfg_path = self._get_sumocfg_path(self.day)
        try:
            if self.bridge.is_marl_model():
                from dispatcher.envs.multi_agent_railway_env import MultiAgentRailwayEnv
                self.env = MultiAgentRailwayEnv(
                    sumocfg_path=cfg_path,
                    start_time_sec=self.start_time_sec,
                    sim_horizon_sec=86400.0,
                    macro_step_sec=self.macro_step_sec,
                    gui=False
                )
            else:
                from dispatcher.envs.railway_dispatch_env import RailwayDispatchEnv
                self.env = RailwayDispatchEnv(
                    sumocfg_path=cfg_path,
                    start_time_sec=self.start_time_sec,
                    sim_horizon_sec=86400.0,
                    macro_step_sec=self.macro_step_sec,
                    gui=False
                )

            obs, info = self.env.reset()
            self.env.last_obs = obs
            self.sim_time_sec = info.get("sim_time", self.start_time_sec)
            logger.info(f"Environment initialized at sim time {self.sim_time_sec}s")
        except Exception as e:
            logger.error(f"Error initializing SUMO environment: {e}. Switching to DEMO_REPLAY.")
            self.mode = SimulationMode.DEMO_REPLAY
            self.env = None

    def _worker_loop(self):
        """Background thread executing simulation steps and broadcasting frames."""
        try:
            self._init_env()
            last_broadcast = time.time()
            broadcast_interval = 1.0 / TELEMETRY_BROADCAST_HZ

            while not self._stop_event.is_set():
                if self._pause_event.is_set():
                    time.sleep(0.1)
                    continue

                step_start = time.time()
                with self._lock:
                    self._advance_one_macro_step()

                # Broadcast frame at target rate
                now = time.time()
                if now - last_broadcast >= broadcast_interval:
                    self._broadcast_frame()
                    last_broadcast = now

                # Sleep to match playback speed multiplier
                step_duration = time.time() - step_start
                simulated_seconds = self.macro_step_sec
                real_time_budget = simulated_seconds / max(0.1, self.speed_multiplier)
                sleep_needed = max(0.01, real_time_budget - step_duration)
                time.sleep(min(sleep_needed, 0.5))
        finally:
            with self._lock:
                if self.env is not None:
                    try:
                        self.env.close()
                    except Exception as e:
                        logger.warning(f"Error closing environment on worker exit: {e}")
                    self.env = None

    def _advance_one_macro_step(self):
        """Advances 15 simulation seconds, querying the AI dispatcher."""
        if self.mode == SimulationMode.LIVE_SUMO and self.env is not None:
            self._step_live_sumo()
        else:
            self._step_demo_replay()

    def _step_live_sumo(self):
        """Steps microscopic SUMO environment with active AI dispatcher."""
        try:
            is_marl = self.bridge.is_marl_model()
            obs = getattr(self.env, "last_obs", None)
            info = getattr(self.env, "_get_info", lambda: {})() if hasattr(self.env, "_get_info") else {}

            action = self.bridge.predict(obs, info)

            if is_marl:
                obs, rewards, terms, truncs, info = self.env.step(action)
                self.env.last_obs = obs
                agent_actions = info.get("agent_actions", {})
                for aid, res in agent_actions.items():
                    if isinstance(res, dict):
                        for ch in res.get("changes", []):
                            self._record_action_event(ch)
            else:
                action_handler = getattr(self.env, "action_handler", None)
                prev_len = len(action_handler.action_history) if action_handler else 0
                obs, reward, term, trunc, info = self.env.step(action)
                self.env.last_obs = obs
                if action_handler:
                    new_entries = action_handler.action_history[prev_len:]
                    for entry in new_entries:
                        for ch in entry.get("changes", []):
                            self._record_action_event(ch)

            self.sim_time_sec = info.get("sim_time", self.sim_time_sec + self.macro_step_sec)
            self.total_knock_ons = info.get("knock_on_events", self.total_knock_ons)

            # Capture vehicle telemetry from TraCI
            self._extract_live_trains()
            self._extract_live_platforms()

        except Exception as e:
            logger.error(f"Error stepping live SUMO: {e}. Falling back to DEMO_REPLAY.")
            self.mode = SimulationMode.DEMO_REPLAY
            self._step_demo_replay()

    def _extract_live_trains(self):
        """Extracts spatial train telemetry via TraCI."""
        if traci is None:
            return
        trains = []
        try:
            active_ids = traci.vehicle.getIDList()
            train_states = getattr(self.env, "train_states", {})

            for vid in active_ids:
                try:
                    pos = traci.vehicle.getPosition(vid)
                    angle = traci.vehicle.getAngle(vid)
                    speed_ms = traci.vehicle.getSpeed(vid)
                    vtype = traci.vehicle.getTypeID(vid)
                    road_id = traci.vehicle.getRoadID(vid)
                    lane_pos = traci.vehicle.getLanePosition(vid)
                    length = traci.vehicle.getLength(vid)
                    is_at_stop = traci.vehicle.isStopped(vid)

                    state = train_states.get(vid, {})
                    delay = state.get("delay_sec", 0.0)
                    prio = state.get("priority", 0.5)
                    upcoming = state.get("upcoming_station")
                    sched_plat = state.get("scheduled_platform_edge")

                    trains.append({
                        "id": vid,
                        "x": round(float(pos[0]), 2),
                        "y": round(float(pos[1]), 2),
                        "angle": round(float(angle), 1),
                        "speed_kmh": round(float(speed_ms * 3.6), 1),
                        "speed_ms": round(float(speed_ms), 2),
                        "max_speed_kmh": round(float(traci.vehicle.getMaxSpeed(vid) * 3.6), 1),
                        "delay_sec": round(float(delay), 1),
                        "vtype": vtype,
                        "priority": float(prio),
                        "length_m": round(float(length), 1),
                        "road_id": road_id,
                        "lane_pos": round(float(lane_pos), 1),
                        "upcoming_station": upcoming,
                        "scheduled_platform": sched_plat,
                        "is_at_stop": bool(is_at_stop)
                    })
                except Exception:
                    pass
        except Exception:
            pass

        self.trains_cache = trains

    def _extract_live_platforms(self):
        """Extracts platform occupancy states from TraCI."""
        if traci is None:
            return
        platforms_out = []
        for st in self.geometry.get("stations", []):
            st_name = st["station_name"]
            for plat in st.get("platforms", []):
                pid = plat["platform_id"]
                lane = plat["lane"]
                occupied = False
                train_id = None
                try:
                    vehs = traci.lane.getLastStepVehicleIDs(f"{lane}_0" if not lane.endswith("_0") else lane)
                    if vehs:
                        occupied = True
                        train_id = vehs[0]
                except Exception:
                    pass

                platforms_out.append({
                    "platform_id": pid,
                    "station_name": st_name,
                    "track": plat.get("track", "p1"),
                    "direction": plat.get("direction", "fw"),
                    "is_occupied": occupied,
                    "occupying_train_id": train_id,
                    "dwell_rem_sec": 45.0 if occupied else 0.0
                })
        self.platforms_cache = platforms_out

    def _step_demo_replay(self):
        """Simulates realistic train movement along track vectors when headless SUMO is offline."""
        self.sim_time_sec += self.macro_step_sec
        lanes = self.geometry.get("lanes", [])
        if not lanes:
            return

        # Generate ~15-25 active trains distributed across key trunk corridors
        demo_train_types = [
            ("HS_300_", "high_speed_emu_300", 300, 1.0, 400.0),
            ("REG_120_", "regional_emu_120", 160, 0.6, 160.0),
            ("FRT_Hvy_", "heavy_freight_cargo", 80, 0.15, 420.0),
            ("XFER_01_", "regional_dmu_120", 140, 0.5, 120.0)
        ]

        t = self.sim_time_sec
        active_demo = []
        for i in range(22):
            prefix, vtype, max_kmh, prio, length = demo_train_types[i % len(demo_train_types)]
            vid = f"{prefix}{i+1:02d}"

            # Pick a lane based on train index
            lane_idx = (i * 35) % len(lanes)
            lane = lanes[lane_idx]
            coords = lane.get("coordinates", [])
            if not coords or len(coords) < 2:
                continue

            # Compute parametric progress along polyline
            speed_fraction = (t * 0.002 * (max_kmh / 120.0) + (i * 0.15)) % 1.0
            pt_idx = int(speed_fraction * (len(coords) - 1))
            pt = coords[pt_idx]
            next_pt = coords[min(len(coords) - 1, pt_idx + 1)]

            dx = next_pt[0] - pt[0]
            dy = next_pt[1] - pt[1]
            angle = (math.degrees(math.atan2(dx, dy)) + 360) % 360

            delay = max(0.0, math.sin(t * 0.01 + i) * 25.0)

            train_entry = {
                "id": vid,
                "x": round(pt[0], 2),
                "y": round(pt[1], 2),
                "angle": round(angle, 1),
                "speed_kmh": round(max_kmh * 0.85, 1),
                "speed_ms": round((max_kmh * 0.85) / 3.6, 2),
                "max_speed_kmh": float(max_kmh),
                "delay_sec": round(delay, 1),
                "vtype": vtype,
                "priority": prio,
                "length_m": length,
                "road_id": lane.get("edge_id", ""),
                "lane_pos": 100.0,
                "upcoming_station": f"City_{(i % 6) + 1}",
                "scheduled_platform": f"City_{(i % 6) + 1}_plat_1_fw",
                "is_at_stop": (i % 7 == 0),
                "bypass_divert": False
            }
            if vid in self._demo_overrides:
                for k, v in self._demo_overrides[vid].items():
                    train_entry[k] = v
            active_demo.append(train_entry)

        self.trains_cache = active_demo

        # Simulate platform occupancies
        mock_plats = []
        for st in self.geometry.get("stations", [])[:6]:
            st_name = st["station_name"]
            for p in st.get("platforms", [])[:4]:
                occ = random.random() < 0.25
                mock_plats.append({
                    "platform_id": p["platform_id"],
                    "station_name": st_name,
                    "track": p.get("track", "p1"),
                    "direction": p.get("direction", "fw"),
                    "is_occupied": occ,
                    "occupying_train_id": f"REG_{random.randint(10, 99)}" if occ else None,
                    "dwell_rem_sec": random.randint(10, 60) if occ else 0.0
                })
        self.platforms_cache = mock_plats

        # Occasionally add an AI decision event for demo realism
        if int(t) % 60 == 0:
            self._record_action_event({
                "type": "platform_reassigned",
                "vid": f"REG_120_{(int(t)//60) % 10 + 1:02d}",
                "target_platform": f"Track {(int(t)//60) % 6 + 1}",
                "station": "City_3",
                "reason": "Proactive conflict avoidance: Plat 1 dwelling"
            })

    def _record_action_event(self, change: Dict[str, Any]):
        """Records an AI or manual dispatcher intervention event."""
        self.total_actions_count += 1
        ch_type = change.get("type", "dispatch_decision")
        vid = change.get("vid", "fleet")

        if ch_type == "platform_reassigned":
            details = f"Reassigned to {change.get('target_platform', 'Alt Track')} at {change.get('station', 'Hub')}"
        elif ch_type == "diverted_to_passing_loop":
            details = "Diverted into Alpine Passing Loop siding for high-speed overtake"
        elif ch_type == "high_speed_bypass_reroute":
            details = "Rerouted via electrified High-Speed Bypass chord (City 2 -> City 5)"
        elif ch_type == "departure_held":
            details = f"Departure held for {change.get('hold_duration', 30)}s to prevent headway conflict"
        else:
            details = str(change)

        event = {
            "timestamp_sec": self.sim_time_sec,
            "time_formatted": format_sim_time(self.sim_time_sec),
            "vehicle_id": vid,
            "action_type": ch_type,
            "details": details,
            "dispatcher_model": self.bridge.active_model_name
        }

        self.recent_actions.insert(0, event)
        if len(self.recent_actions) > 50:
            self.recent_actions.pop()

    def inject_disruption(self, mode: str, vehicle_id: Optional[str] = None, platform_id: Optional[str] = None, duration: float = 600.0) -> bool:
        """Injects a physical disruption into the running simulation under lock."""
        with self._lock:
            desc = f"{mode}: duration {duration}s"
            if vehicle_id:
                desc += f" on {vehicle_id}"
            if platform_id:
                desc += f" on {platform_id}"

            # If live SUMO, apply direct TraCI perturbation and record for rollback
            if self.mode == SimulationMode.LIVE_SUMO and traci is not None:
                try:
                    if mode == "train_delay" and vehicle_id:
                        traci.vehicle.setSpeed(vehicle_id, 0.0)
                        self._applied_perturbations.append({"type": "vehicle_speed", "vid": vehicle_id})
                    elif mode == "platform_blockage" and platform_id:
                        resolved_lane = platform_id
                        if self.geometry and "stations" in self.geometry:
                            for st in self.geometry["stations"]:
                                for plat in st.get("platforms", []):
                                    if plat.get("platform_id") == platform_id:
                                        resolved_lane = plat.get("lane", platform_id)
                                        break
                        traci.lane.setDisallowed(resolved_lane, ["all"])
                        self._applied_perturbations.append({"type": "lane_disallow", "lane": resolved_lane})
                except Exception as e:
                    logger.error(f"Failed to inject TraCI disruption: {e}")
                    return False

            self.active_disruptions.append(desc)
            logger.info(f"Disruption injected: {desc}")

            self._record_action_event({
                "type": "disruption_injected",
                "vid": vehicle_id or "infrastructure",
                "details": desc
            })
            return True

    def clear_disruptions(self) -> bool:
        """Clears all active perturbations and restores TraCI state under lock."""
        with self._lock:
            if self.mode == SimulationMode.LIVE_SUMO and traci is not None:
                for p in self._applied_perturbations:
                    try:
                        if p.get("type") == "vehicle_speed":
                            traci.vehicle.setSpeed(p["vid"], -1.0)
                        elif p.get("type") == "lane_disallow":
                            traci.lane.setDisallowed(p["lane"], [])
                    except Exception as e:
                        logger.warning(f"Error restoring perturbation {p}: {e}")

            self._applied_perturbations.clear()
            self.active_disruptions.clear()
            self._record_action_event({
                "type": "disruptions_cleared",
                "vid": "infrastructure",
                "details": "All active disruptions cleared."
            })
            return True

    def manual_override(self, vehicle_id: str, override_type: str, target_platform: Optional[int] = None, hold_duration: Optional[float] = None) -> bool:
        """Applies a human-in-the-loop dispatcher override under lock."""
        with self._lock:
            applied = False
            details = f"Operator Override: {override_type}"

            if self.mode == SimulationMode.LIVE_SUMO and self.env is not None and traci is not None:
                try:
                    active_ids = traci.vehicle.getIDList()
                    if vehicle_id not in active_ids:
                        logger.warning(f"Manual override failed: vehicle {vehicle_id} not active.")
                        return False

                    action_handler = getattr(self.env, "action_handler", None)
                    train_states = getattr(self.env, "train_states", {})

                    if override_type == "platform_switch":
                        plat_idx = int(target_platform) if target_platform is not None else 1
                        details += f" -> Track {plat_idx}"
                        if action_handler:
                            res = action_handler.apply_action(
                                focus_veh_id=vehicle_id,
                                action=[0, plat_idx, 0],
                                train_states=train_states,
                                sim_time=self.sim_time_sec,
                                traci_module=traci
                            )
                            changes = res.get("changes", [])
                            applied = bool(changes) and not any(ch.get("type") == "action_rejected" for ch in changes)
                        else:
                            applied = True

                    elif override_type == "departure_hold":
                        dur = float(hold_duration) if hold_duration is not None else 30.0
                        details += f" -> Hold {dur}s"
                        if action_handler:
                            hold_act = 1 if dur <= 30 else (2 if dur <= 60 else 3)
                            res = action_handler.apply_action(
                                focus_veh_id=vehicle_id,
                                action=[0, 0, hold_act],
                                train_states=train_states,
                                sim_time=self.sim_time_sec,
                                traci_module=traci
                            )
                            changes = res.get("changes", [])
                            applied = bool(changes) and not any(ch.get("type") == "action_rejected" for ch in changes)
                        else:
                            applied = True

                    elif override_type == "bypass_divert":
                        details += " -> High-Speed Bypass Reroute"
                        if action_handler:
                            res = action_handler.apply_action(
                                focus_veh_id=vehicle_id,
                                action=[2, 0, 0],
                                train_states=train_states,
                                sim_time=self.sim_time_sec,
                                traci_module=traci
                            )
                            changes = res.get("changes", [])
                            applied = bool(changes) and not any(ch.get("type") == "action_rejected" for ch in changes)
                        else:
                            applied = True

                    elif override_type == "release_hold":
                        details += " -> Resume Departure"
                        traci.vehicle.resume(vehicle_id)
                        if action_handler and vehicle_id in action_handler.train_hold_seconds:
                            action_handler.train_hold_seconds[vehicle_id] = 0.0
                        applied = True

                    else:
                        logger.warning(f"Unknown override type: {override_type}")
                        return False

                except Exception as e:
                    logger.error(f"Error executing manual override: {e}")
                    return False

            elif self.mode == SimulationMode.DEMO_REPLAY:
                train_match = next((t for t in self.trains_cache if t["id"] == vehicle_id), None)
                if not train_match:
                    logger.warning(f"Manual override failed: {vehicle_id} not in demo trains.")
                    return False

                if vehicle_id not in self._demo_overrides:
                    self._demo_overrides[vehicle_id] = {}

                if override_type == "platform_switch":
                    plat_str = f"Track {target_platform or 1}"
                    details += f" -> {plat_str}"
                    self._demo_overrides[vehicle_id]["scheduled_platform"] = plat_str
                    train_match["scheduled_platform"] = plat_str
                    applied = True
                elif override_type == "departure_hold":
                    details += f" -> Hold {hold_duration or 30}s"
                    self._demo_overrides[vehicle_id]["is_at_stop"] = True
                    train_match["is_at_stop"] = True
                    applied = True
                elif override_type == "release_hold":
                    details += " -> Resume Departure"
                    self._demo_overrides[vehicle_id]["is_at_stop"] = False
                    train_match["is_at_stop"] = False
                    applied = True
                elif override_type == "bypass_divert":
                    details += " -> High-Speed Bypass Reroute"
                    self._demo_overrides[vehicle_id]["bypass_divert"] = True
                    train_match["bypass_divert"] = True
                    applied = True
                else:
                    return False
            else:
                return False

            if applied:
                self._record_action_event({
                    "type": f"manual_{override_type}",
                    "vid": vehicle_id,
                    "details": details
                })
                return True

            return False

    def _broadcast_frame(self):
        """Assembles and broadcasts the current telemetry frame over WebSocket."""
        if self.event_loop is None:
            return

        delays = [t.get("delay_sec", 0.0) for t in self.trains_cache]
        mean_delay = float(sum(delays) / max(1, len(delays))) if delays else 0.0
        max_delay = float(max(delays)) if delays else 0.0
        ontime = sum(1 for d in delays if d <= 180.0)
        punctuality = (ontime / max(1, len(delays))) * 100.0 if delays else 100.0

        frame = {
            "kpis": {
                "sim_time_sec": self.sim_time_sec,
                "time_formatted": format_sim_time(self.sim_time_sec),
                "active_trains_count": len(self.trains_cache),
                "mean_delay_sec": round(mean_delay, 1),
                "max_delay_sec": round(max_delay, 1),
                "punctuality_pct": round(punctuality, 1),
                "total_knock_on_events": self.total_knock_ons,
                "total_actions_taken": self.total_actions_count,
                "collisions": 0,
                "teleports": 0
            },
            "trains": self.trains_cache,
            "platforms": self.platforms_cache,
            "recent_actions": self.recent_actions[:15],
            "sim_status": self.state,
            "dispatcher_model": self.bridge.active_model_name,
            "calendar_day": self.day,
            "speed_multiplier": self.speed_multiplier,
            "mode": self.mode
        }

        try:
            asyncio.run_coroutine_threadsafe(streamer.broadcast(frame), self.event_loop)
        except Exception:
            pass


# Global singleton instance
sim_manager = SimulationManager()
