"""
backend/core/telemetry_streamer.py
Manages real-time WebSocket client connections and broadcasts telemetry frames.
Supports automatic pausing when all browser subscribers disconnect to conserve CPU.
"""

import asyncio
import logging
from typing import Set, Dict, Any, Optional, Callable
from fastapi import WebSocket

logger = logging.getLogger("telemetry_streamer")


class TelemetryStreamer:
    """Handles WebSocket subscriber lifecycles and broadcasting."""

    def __init__(self, debounce_sec: float = 3.0):
        self.active_connections: Set[WebSocket] = set()
        self._latest_frame: Optional[Dict[str, Any]] = None
        self._lock = asyncio.Lock()
        self.debounce_sec: float = debounce_sec
        self._empty_timer_task: Optional[asyncio.Task] = None
        self._on_empty_callback: Optional[Callable[[], Any]] = None
        self._on_active_callback: Optional[Callable[[], Any]] = None

    def set_subscriber_callbacks(
        self,
        on_empty: Optional[Callable[[], Any]] = None,
        on_active: Optional[Callable[[], Any]] = None
    ):
        """Registers callbacks for when all clients disconnect and when a client connects."""
        self._on_empty_callback = on_empty
        self._on_active_callback = on_active

    async def connect(self, websocket: WebSocket):
        """Accepts a new WebSocket connection and sends the latest frame."""
        await websocket.accept()

        # Cancel any pending auto-pause timer since an active viewer has connected
        if self._empty_timer_task and not self._empty_timer_task.done():
            self._empty_timer_task.cancel()
            self._empty_timer_task = None
            logger.info("Cancelled pending auto-pause timer due to active client connection.")

        first_client = False
        async with self._lock:
            if len(self.active_connections) == 0:
                first_client = True
            self.active_connections.add(websocket)

        logger.info(f"WebSocket client connected. Active subscribers: {len(self.active_connections)}")

        if first_client and self._on_active_callback:
            try:
                self._on_active_callback()
            except Exception as e:
                logger.error(f"Error executing on_active_callback: {e}")

        if self._latest_frame:
            try:
                await websocket.send_json(self._latest_frame)
            except Exception:
                pass

    async def disconnect(self, websocket: WebSocket):
        """Removes a disconnected WebSocket client."""
        async with self._lock:
            self.active_connections.discard(websocket)
            remaining = len(self.active_connections)
        logger.info(f"WebSocket client disconnected. Remaining: {remaining}")

        if remaining == 0:
            self._schedule_empty_check()

    def _schedule_empty_check(self):
        """Schedules a debounced check to pause simulation if no clients reconnect."""
        if self._empty_timer_task and not self._empty_timer_task.done():
            self._empty_timer_task.cancel()
        try:
            loop = asyncio.get_running_loop()
            self._empty_timer_task = loop.create_task(self._empty_grace_period())
        except RuntimeError:
            pass

    async def _empty_grace_period(self):
        """Waits for the debounce duration, then triggers on_empty_callback if still 0 clients."""
        try:
            await asyncio.sleep(self.debounce_sec)
            async with self._lock:
                is_empty = (len(self.active_connections) == 0)
            if is_empty:
                logger.info(
                    f"No active WebSocket clients for {self.debounce_sec}s. "
                    "Triggering subscriber empty callback."
                )
                if self._on_empty_callback:
                    try:
                        self._on_empty_callback()
                    except Exception as e:
                        logger.error(f"Error executing on_empty_callback: {e}")
        except asyncio.CancelledError:
            pass

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
                remaining = len(self.active_connections)
            for ws in dead_connections:
                try:
                    await ws.close(code=1011)
                except Exception:
                    pass
            if remaining == 0:
                self._schedule_empty_check()

    def get_latest_frame(self) -> Optional[Dict[str, Any]]:
        """Returns the most recently broadcast telemetry frame."""
        return self._latest_frame


# Global streamer instance
streamer = TelemetryStreamer()

