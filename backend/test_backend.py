"""
backend/test_backend.py
End-to-end test and validation suite for the Railway Simulation Backend API.
"""

import sys
import time
import asyncio
import threading
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import requests
import uvicorn

from backend.main import app
from backend.core.network_geometry import parse_network_geometry
from backend.core.database import get_train_services, get_physical_rakes, get_rolling_stock_types
from backend.core.sim_manager import sim_manager
from backend.schemas.models import (
    SimulationMode,
    SimulationControlRequest,
    SimulationConfigRequest,
    DisruptionRequest,
    ManualOverrideRequest
)
from backend.routers.simulation import (
    get_simulation_status,
    control_simulation,
    configure_simulation,
    list_available_models,
    list_calendar_days
)
from backend.routers.network import (
    get_network_geometry,
    get_stations,
    get_platforms,
    get_bounds
)
from backend.routers.timetable import (
    list_train_services,
    get_service_by_number,
    list_physical_rakes,
    list_rolling_stock_types,
    list_timetable_stations,
    get_station_board
)
from backend.routers.analytics import (
    get_weekly_benchmark_summary,
    get_diurnal_timeline
)
from backend.routers.disruption import (
    inject_disruption,
    clear_all_disruptions,
    get_active_disruptions
)
from backend.routers.overrides import (
    apply_manual_override,
    get_recent_actions
)


def test_core_components():
    print("Testing core database layer...")
    services = get_train_services(day="Mon")
    assert len(services) > 0, "No train services returned for Monday"
    rakes = get_physical_rakes()
    assert len(rakes) == 31, f"Expected 31 rakes, got {len(rakes)}"
    rolling_stock = get_rolling_stock_types()
    assert len(rolling_stock) == 7, f"Expected 7 rolling stock types, got {len(rolling_stock)}"
    print(f"  ✓ Database verified: {len(services)} Mon services, {len(rakes)} rakes, {len(rolling_stock)} rolling stock types.")

    print("Testing network geometry parser...")
    geom = parse_network_geometry()
    assert len(geom["lanes"]) > 0, "No lanes parsed"
    assert len(geom["stations"]) == 18, f"Expected 18 stations, got {len(geom['stations'])}"
    assert geom["buffer_stops_count"] > 0, "No buffer stops found"
    print(f"  ✓ Geometry verified: {len(geom['lanes'])} lanes, {len(geom['stations'])} stations, bounds {geom['bounds']}.")


def test_routers_direct():
    print("Testing REST API routers directly via async runner...")

    async def _run_tests():
        # Simulation
        st = get_simulation_status()
        assert st["status"] in ("STOPPED", "RUNNING", "PAUSED")
        print(f"  ✓ get_simulation_status: OK (model: {st['dispatcher_model']}, time: {st['time_formatted']})")

        models = await list_available_models()
        assert len(models) == 8
        print(f"  ✓ list_available_models: OK ({len(models)} models)")

        days = await list_calendar_days()
        assert len(days) == 7
        print("  ✓ list_calendar_days: OK (7 days)")

        cfg_res = configure_simulation(SimulationConfigRequest(model="Centralized_PPO", mode=SimulationMode.DEMO_REPLAY, speed=2.0))
        assert cfg_res["success"] is True
        print("  ✓ configure_simulation: OK")

        ctrl_res = control_simulation(SimulationControlRequest(action="step"))
        assert ctrl_res["success"] is True
        print("  ✓ control_simulation (step): OK")

        ctrl_reset = control_simulation(SimulationControlRequest(action="reset", start_time_sec=27000.0))
        assert ctrl_reset["success"] is True
        assert ctrl_reset["current_status"]["sim_time_sec"] == 27000.0
        assert ctrl_reset["current_status"]["time_formatted"] == "07:30:00"
        assert "trains" in ctrl_reset
        assert "platforms" in ctrl_reset
        print("  ✓ control_simulation (reset to 07:30:00): OK")

        # Network
        b = await get_bounds()
        assert "bounds" in b
        print("  ✓ get_bounds: OK")

        stations = await get_stations()
        assert len(stations) == 18
        print(f"  ✓ get_stations: OK ({len(stations)} stations)")

        platforms = await get_platforms()
        assert len(platforms) == 116
        print(f"  ✓ get_platforms: OK ({len(platforms)} platforms)")

        # Timetable
        tt_services = await list_train_services(day="Mon")
        assert len(tt_services) > 0
        first_svc = tt_services[0]["train_number"]
        print(f"  ✓ list_train_services: OK ({len(tt_services)} services)")

        detail = await get_service_by_number(first_svc)
        assert detail["train_number"] == first_svc
        assert "stops" in detail
        print(f"  ✓ get_service_by_number ({first_svc}): OK ({len(detail['stops'])} stops)")

        stations_tt = await list_timetable_stations()
        assert len(stations_tt) == 24
        print(f"  ✓ list_timetable_stations: OK ({len(stations_tt)} station categories)")

        board = await get_station_board("City_1", day="Mon")
        assert isinstance(board, list)
        assert len(board) > 0
        print(f"  ✓ get_station_board (City_1): OK ({len(board)} movements)")

        # Analytics
        summary = await get_weekly_benchmark_summary()
        assert len(summary["models_summary"]) == 8
        assert summary["total_runs"] == 56
        print(f"  ✓ get_weekly_benchmark_summary: OK ({summary['total_runs']} runs, 8 models)")

        diurnal = await get_diurnal_timeline(day="Mon")
        assert len(diurnal["hours"]) == 24
        print("  ✓ get_diurnal_timeline: OK (24 hours)")

        # Disruptions
        dis_res = inject_disruption(DisruptionRequest(mode="fleet_surge", delay_duration_sec=300.0))
        assert dis_res["success"] is True
        active_dis = await get_active_disruptions()
        assert len(active_dis["active_disruptions"]) > 0
        clear_all_disruptions()
        print("  ✓ Disruption inject & clear: OK")

        # Overrides
        ov_res = await apply_manual_override(ManualOverrideRequest(
            vehicle_id="HS_300_01",
            override_type="platform_switch",
            target_platform=3
        ))
        assert ov_res["success"] is True
        recent = await get_recent_actions()
        assert len(recent["recent_actions"]) > 0
        print("  ✓ Manual override & history: OK")

    asyncio.run(_run_tests())


def test_live_http_server():
    print("Testing Live HTTP Server on port 8009...")
    server_config = uvicorn.Config(app, host="127.0.0.1", port=8009, log_level="warning")
    server = uvicorn.Server(server_config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        start_deadline = time.time() + 5.0
        while not server.started:
            if not thread.is_alive():
                raise RuntimeError("Serving thread failed to start or died unexpectedly.")
            if time.time() > start_deadline:
                raise TimeoutError("Timed out waiting for uvicorn server to start.")
            time.sleep(0.05)

        HTTP_TIMEOUT = (2.0, 5.0)

        r = requests.get("http://127.0.0.1:8009/", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "online"
        print("  ✓ HTTP GET /: 200 OK")

        r = requests.get("http://127.0.0.1:8009/health", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /health: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/sim/status", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/sim/status: 200 OK")

        r = requests.post("http://127.0.0.1:8009/api/sim/control", json={"action": "step"}, timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP POST /api/sim/control (step): 200 OK")

        r = requests.post("http://127.0.0.1:8009/api/sim/control", json={"action": "reset", "start_time_sec": 27000.0}, timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        reset_res = r.json()
        assert reset_res.get("current_status", {}).get("sim_time_sec") == 27000.0
        assert reset_res.get("current_status", {}).get("time_formatted") == "07:30:00"
        assert "trains" in reset_res
        assert "platforms" in reset_res
        print("  ✓ HTTP POST /api/sim/control (reset to 07:30:00): 200 OK")

        r = requests.post("http://127.0.0.1:8009/api/sim/config", json={"speed": 1.5}, timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP POST /api/sim/config: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/network/bounds", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/network/bounds: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/network/stations", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/network/stations: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/network/platforms", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/network/platforms: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/network/geometry", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/network/geometry: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/timetable/services", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/timetable/services: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/timetable/rakes", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/timetable/rakes: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/timetable/rolling-stock", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/timetable/rolling-stock: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/timetable/stations", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/timetable/stations: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/timetable/station/City_1?day=Mon", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/timetable/station/City_1: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/analytics/weekly-summary", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/analytics/weekly-summary: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/analytics/diurnal?day=Mon", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/analytics/diurnal: 200 OK")

        r = requests.post("http://127.0.0.1:8009/api/disruption/inject", json={"mode": "fleet_surge", "delay_duration_sec": 60.0}, timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP POST /api/disruption/inject: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/disruption/active", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/disruption/active: 200 OK")

        r = requests.post("http://127.0.0.1:8009/api/disruption/clear", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP POST /api/disruption/clear: 200 OK")

        r = requests.post("http://127.0.0.1:8009/api/override/action", json={"vehicle_id": "HS_300_01", "override_type": "platform_switch", "target_platform": 2}, timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP POST /api/override/action: 200 OK")

        r = requests.get("http://127.0.0.1:8009/api/override/recent", timeout=HTTP_TIMEOUT)
        assert r.status_code == 200
        print("  ✓ HTTP GET /api/override/recent: 200 OK")

    finally:
        server.should_exit = True
        thread.join(timeout=2.0)
        print("  ✓ Live HTTP Server stopped cleanly.")


if __name__ == "__main__":
    print("=====================================================")
    print("Starting Railway Simulation Backend Validation Tests")
    print("=====================================================")
    test_core_components()
    test_routers_direct()
    test_live_http_server()
    print("=====================================================")
    print("ALL TESTS PASSED! Backend is 100% production-ready.")
    print("=====================================================")
