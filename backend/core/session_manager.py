"""
backend/core/session_manager.py
Manages isolated user simulation sessions for Model B.
Each user gets their own dedicated SimulationManager, TelemetryStreamer,
and independent simulation state (calendar day, speed, AI model, play/pause state).
"""

import time
import uuid
import logging
import asyncio
import threading
from typing import Dict, Optional, List, Any
from fastapi import Request, Header, Query

from backend.core.sim_manager import SimulationManager
from backend.core.telemetry_streamer import TelemetryStreamer

logger = logging.getLogger("session_manager")


class UserSession:
    """Encapsulates an isolated user's simulation session."""

    def __init__(self, session_id: str, event_loop: Optional[asyncio.AbstractEventLoop] = None):
        self.session_id: str = session_id
        self.created_at: float = time.time()
        self.last_active: float = time.time()

        # Dedicated telemetry streamer and simulation manager for this session
        self.streamer: TelemetryStreamer = TelemetryStreamer()
        self.sim_manager: SimulationManager = SimulationManager(streamer=self.streamer)

        if event_loop and not event_loop.is_closed():
            self.sim_manager.set_event_loop(event_loop)

        # Wire up auto-pause on zero active connections for this session
        self.streamer.set_subscriber_callbacks(
            on_empty=self.sim_manager.auto_pause_simulation,
            on_active=self.sim_manager.auto_resume_simulation
        )
        logger.info(f"Initialized isolated UserSession: {session_id}")

    def touch(self):
        """Updates the session's last activity timestamp."""
        self.last_active = time.time()

    def cleanup(self):
        """Cleanly terminates the simulation worker and releases resources."""
        logger.info(f"Terminating and releasing UserSession: {self.session_id}")
        try:
            self.sim_manager._stop_current_worker()
            if self.sim_manager.env is not None:
                try:
                    self.sim_manager.env.close()
                except Exception:
                    pass
                self.sim_manager.env = None
        except Exception as e:
            logger.warning(f"Error during cleanup of session {self.session_id}: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Returns session status metadata."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "active_subscribers": len(self.streamer.active_connections),
            "sim_status": self.sim_manager.state,
            "sim_day": self.sim_manager.day,
            "sim_model": self.sim_manager.bridge.active_model_name,
            "speed": self.sim_manager.speed_multiplier,
            "sim_time": self.sim_manager.sim_time_sec,
            "auto_paused": self.sim_manager.auto_paused
        }


class SessionManager:
    """Thread-safe registry and lifecycle coordinator for UserSession instances."""

    def __init__(self, idle_timeout_sec: float = 1800.0):
        self._sessions: Dict[str, UserSession] = {}
        self._lock = threading.Lock()
        self.idle_timeout_sec: float = idle_timeout_sec
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._reaper_task: Optional[asyncio.Task] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Binds the main event loop for async WebSocket broadcasts across all sessions."""
        self.event_loop = loop
        with self._lock:
            for session in self._sessions.values():
                session.sim_manager.set_event_loop(loop)

        # Start periodic idle session reaper
        if self._reaper_task is None or self._reaper_task.done():
            self._reaper_task = loop.create_task(self._reaper_loop())

    def get_or_create(self, session_id: Optional[str] = None) -> UserSession:
        """
        Retrieves an existing session by ID, or creates a new isolated session.
        If session_id is None or empty, falls back to the default session.
        """
        sid = (session_id or "").strip()
        if not sid:
            sid = "default"

        with self._lock:
            if sid not in self._sessions:
                session = UserSession(session_id=sid, event_loop=self.event_loop)
                self._sessions[sid] = session
            else:
                session = self._sessions[sid]

            session.touch()
            return session

    def get(self, session_id: str) -> Optional[UserSession]:
        """Retrieves a session if it exists."""
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Lists metadata for all active user sessions."""
        with self._lock:
            return [s.to_dict() for s in self._sessions.values()]

    def cleanup_idle(self, timeout_sec: Optional[float] = None) -> int:
        """
        Reaps sessions that have zero active subscribers and have been idle longer
        than the specified timeout. Protects the 'default' session from deletion.
        """
        threshold = timeout_sec if timeout_sec is not None else self.idle_timeout_sec
        now = time.time()
        to_reap: List[UserSession] = []

        with self._lock:
            for sid, session in list(self._sessions.items()):
                if sid == "default":
                    continue
                has_active_connections = len(session.streamer.active_connections) > 0
                if not has_active_connections and (now - session.last_active > threshold):
                    to_reap.append(session)
                    del self._sessions[sid]

        for s in to_reap:
            s.cleanup()

        if to_reap:
            logger.info(f"Reaped {len(to_reap)} idle user sessions.")
        return len(to_reap)

    def cleanup_all(self):
        """Stops and cleans up all active sessions on server shutdown."""
        with self._lock:
            all_sessions = list(self._sessions.values())
            self._sessions.clear()

        for s in all_sessions:
            s.cleanup()

    async def _reaper_loop(self):
        """Background coroutine that reaps idle sessions every 60 seconds."""
        while True:
            try:
                await asyncio.sleep(60.0)
                self.cleanup_idle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session reaper loop: {e}")


# Master singleton registry
session_manager = SessionManager(idle_timeout_sec=1800.0)


def get_user_session(
    request: Request,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    sessionId: Optional[str] = Query(None)
) -> UserSession:
    """
    FastAPI dependency that resolves the calling client's UserSession.
    Extracts session ID from:
    1. X-Session-ID HTTP header
    2. ?sessionId= query parameter
    3. railway_session_id cookie
    4. Fallback to 'default'
    """
    sid = x_session_id or sessionId or request.cookies.get("railway_session_id")
    return session_manager.get_or_create(sid)
