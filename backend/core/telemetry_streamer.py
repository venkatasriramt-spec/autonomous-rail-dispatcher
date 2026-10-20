"""
backend/core/telemetry_streamer.py
Manages real-time WebSocket client connections and broadcasts telemetry frames.
"""

import asyncio
import logging
from typing import Set, Dict, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger("telemetry_streamer")


class TelemetryStreamer:
    """Handles WebSocket subscriber lifecycles and broadcasting."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._latest_frame: Optional[Dict[str, Any]] = None
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accepts a new WebSocket connection and sends the latest frame."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Active subscribers: {len(self.active_connections)}")

        if self._latest_frame:
            try:
                await websocket.send_json(self._latest_frame)
            except Exception:
                pass

    async def disconnect(self, websocket: WebSocket):
        """Removes a disconnected WebSocket client."""
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, frame: Dict[str, Any]):
        """Broadcasts a telemetry frame to all connected clients concurrently with timeout."""
        self._latest_frame = frame
        if not self.active_connections:
            return

        async with self._lock:
            subscribers = list(self.active_connections)

        async def _send_to_subscriber(ws: WebSocket):
            try:
                await asyncio.wait_for(ws.send_json(frame), timeout=1.0)
                return None
            except Exception:
                return ws

        results = await asyncio.gather(*[_send_to_subscriber(ws) for ws in subscribers], return_exceptions=False)
        dead_connections = [ws for ws in results if ws is not None]

        if dead_connections:
            async with self._lock:
                for ws in dead_connections:
                    self.active_connections.discard(ws)

    def get_latest_frame(self) -> Optional[Dict[str, Any]]:
        """Returns the most recently broadcast telemetry frame."""
        return self._latest_frame


# Global streamer instance
streamer = TelemetryStreamer()
