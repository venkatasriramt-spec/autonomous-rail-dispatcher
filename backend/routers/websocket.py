"""
backend/routers/websocket.py
Real-time WebSocket endpoint streaming simulation telemetry and AI decisions for isolated user sessions (Model B).
"""

import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.core.session_manager import session_manager

router = APIRouter(tags=["WebSocket Telemetry"])
logger = logging.getLogger("websocket_router")


@router.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """
    High-frequency WebSocket endpoint streaming live frames for an isolated user session:
    - Train positions (x, y, angle, speed, delay)
    - Platform occupancies (tracks 1..6)
    - AI actions & decisions
    - Macroscopic KPIs (punctuality, mean delay, knock-ons)
    """
    # Extract session ID from query params, cookies, or fallback
    sid = (
        websocket.query_params.get("sessionId")
        or websocket.query_params.get("session_id")
        or websocket.cookies.get("railway_session_id")
        or "default"
    )

    session = session_manager.get_or_create(sid)
    session.touch()
    streamer = session.streamer

    await streamer.connect(websocket)
    try:
        while True:
            # Keep connection open and receive client heartbeats or control messages
            data = await websocket.receive_text()
            session.touch()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await streamer.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket client error: {e}")
        await streamer.disconnect(websocket)
