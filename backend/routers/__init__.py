"""
backend/routers package
"""
from .simulation import router as simulation_router
from .websocket import router as websocket_router
from .network import router as network_router
from .timetable import router as timetable_router
from .analytics import router as analytics_router
from .disruption import router as disruption_router
from .overrides import router as overrides_router

__all__ = [
    "simulation_router",
    "websocket_router",
    "network_router",
    "timetable_router",
    "analytics_router",
    "disruption_router",
    "overrides_router"
]
