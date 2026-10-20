"""
backend/routers/network.py
Endpoints for track network geometry, station layouts, and platform data.
"""

from typing import Dict, Any, List
from fastapi import APIRouter
from backend.core.network_geometry import parse_network_geometry
from backend.schemas.models import NetworkGeometryResponse

router = APIRouter(prefix="/api/network", tags=["Network Infrastructure"])


@router.get("/geometry", response_model=NetworkGeometryResponse)
async def get_network_geometry():
    """Returns the complete 2D vector geometry for all track segments and stations."""
    return parse_network_geometry()


@router.get("/stations")
async def get_stations():
    """Returns all 18 stations with centroid coordinates and platform listings."""
    geom = parse_network_geometry()
    return geom.get("stations", [])


@router.get("/platforms")
async def get_platforms():
    """Returns all 116 microscopic platform tracks with physical lengths and lanes."""
    geom = parse_network_geometry()
    all_platforms = []
    for st in geom.get("stations", []):
        all_platforms.extend(st.get("platforms", []))
    return all_platforms


@router.get("/bounds")
async def get_bounds():
    """Returns the coordinate bounding box [min_x, min_y, max_x, max_y] of the network."""
    geom = parse_network_geometry()
    return {"bounds": geom.get("bounds", [0, 0, 30000, 30000])}
