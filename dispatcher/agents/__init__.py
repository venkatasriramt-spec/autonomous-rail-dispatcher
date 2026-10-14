"""
agents module
"""
from .baseline_dispatchers import (
    BaseDispatcher,
    StaticDispatcher,
    FIFODispatcher,
    PriorityGreedyDispatcher
)

__all__ = [
    "BaseDispatcher",
    "StaticDispatcher",
    "FIFODispatcher",
    "PriorityGreedyDispatcher"
]
