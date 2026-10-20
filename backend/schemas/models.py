"""
backend/schemas/models.py
Pydantic schemas for request bodies, responses, and real-time telemetry frames.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field


class SimulationState(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


class SimulationMode(str, Enum):
    LIVE_SUMO = "LIVE_SUMO"
    DEMO_REPLAY = "DEMO_REPLAY"


class TrainTelemetry(BaseModel):
    id: str
    x: float
    y: float
    angle: float
    speed_kmh: float
    speed_ms: float
    max_speed_kmh: float
    delay_sec: float
    vtype: str
    priority: float
    length_m: float
    road_id: str
    lane_pos: float
    upcoming_station: Optional[str] = None
    scheduled_platform: Optional[str] = None
    is_at_stop: bool = False
    bypass_divert: bool = False


class PlatformTelemetry(BaseModel):
    platform_id: str
    station_name: str
    track: str
    direction: str
    is_occupied: bool
    occupying_train_id: Optional[str] = None
    dwell_rem_sec: float = 0.0


class DispatcherActionEvent(BaseModel):
    timestamp_sec: float
    time_formatted: str
    vehicle_id: str
    action_type: str
    details: str
    dispatcher_model: str


class FleetKPIs(BaseModel):
    sim_time_sec: float
    time_formatted: str
    active_trains_count: int
    mean_delay_sec: float
    max_delay_sec: float
    punctuality_pct: float
    total_knock_on_events: int
    total_actions_taken: int
    collisions: int = 0
    teleports: int = 0


class TelemetryFrame(BaseModel):
    kpis: FleetKPIs
    trains: List[TrainTelemetry]
    platforms: List[PlatformTelemetry]
    recent_actions: List[DispatcherActionEvent]
    sim_status: SimulationState
    dispatcher_model: str
    calendar_day: str
    speed_multiplier: float
    mode: SimulationMode


# Request Models
class SimulationControlRequest(BaseModel):
    action: Literal["play", "pause", "step", "reset"] = Field(..., description="'play', 'pause', 'step', or 'reset'")
    speed: Optional[float] = Field(None, gt=0, description="Playback speed multiplier (e.g. 1.0, 5.0, 10.0)")


class SimulationConfigRequest(BaseModel):
    day: Optional[str] = Field(None, description="Calendar day: Mon, Tue, Wed, Thu, Fri, Sat, Sun")
    model: Optional[str] = Field(None, description="Dispatcher model name")
    mode: Optional[SimulationMode] = Field(None, description="LIVE_SUMO or DEMO_REPLAY")
    start_time_sec: Optional[float] = Field(None, ge=0.0, lt=86400.0, description="Start time in seconds from 00:00 (e.g. 21600 for 06:00)")
    speed: Optional[float] = Field(None, gt=0, description="Simulation speed multiplier")


class DisruptionRequest(BaseModel):
    mode: str = Field(..., description="'train_delay', 'platform_blockage', 'fleet_surge', or 'compound_failure'")
    vehicle_id: Optional[str] = Field(None, description="Target vehicle ID for mechanical stall")
    platform_id: Optional[str] = Field(None, description="Platform lane ID to shut down (e.g. City_3_EW_plat_1_fw_0)")
    delay_duration_sec: Optional[float] = Field(600.0, description="Duration of stall or platform closure in seconds")


class ManualOverrideRequest(BaseModel):
    vehicle_id: str = Field(..., description="Target train consist ID")
    override_type: str = Field(..., description="'platform_switch', 'departure_hold', 'bypass_divert', or 'release_hold'")
    target_platform: Optional[int] = Field(None, description="Platform track index (1 to 6)")
    hold_duration_sec: Optional[float] = Field(None, description="Hold duration in seconds (30, 60, 120)")


# Response Models
class SimulationStatusResponse(BaseModel):
    status: SimulationState
    mode: SimulationMode
    calendar_day: str
    dispatcher_model: str
    sim_time_sec: float
    time_formatted: str
    speed_multiplier: float
    active_trains_count: int
    mean_delay_sec: float
    punctuality_pct: float
    total_actions_taken: int
    active_disruptions: List[str]


class TrackLaneGeometry(BaseModel):
    edge_id: str
    lane_id: str
    category: str
    speed_kmh: float
    length_m: float
    allow: str
    coordinates: List[List[float]]


class StationMetadata(BaseModel):
    station_name: str
    display_name: str
    x: float
    y: float
    platform_count: int
    platforms: List[Dict[str, Any]]


class NetworkGeometryResponse(BaseModel):
    bounds: List[float]  # [min_x, min_y, max_x, max_y]
    lanes: List[TrackLaneGeometry]
    stations: List[StationMetadata]
    signals_count: int
    buffer_stops_count: int
    net_file: Optional[str] = None
    add_file: Optional[str] = None
