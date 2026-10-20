"""
backend/routers/websocket.py
Real-time WebSocket endpoint streaming simulation telemetry and AI decisions.
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.core.telemetry_streamer import streamer

router = APIRouter(tags=["WebSocket Telemetry"])
logger = logging.getLogger("websocket_router")


@router.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """
    High-frequency WebSocket endpoint streaming live frames:
    - Train positions (x, y, angle, speed, delay)
    - Platform occupancies (tracks 1..6)
    - AI actions & decisions
    - Macroscopic KPIs (punctuality, mean delay, knock-ons)
    """
    await streamer.connect(websocket)
    try:
        while True:
            # Keep connection open and receive client heartbeats or control messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await streamer.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket client error: {e}")
        await streamer.disconnect(websocket)
