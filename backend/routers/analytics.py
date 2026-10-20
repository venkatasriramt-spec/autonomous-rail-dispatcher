"""
backend/routers/analytics.py
Endpoints for authoritative 56-run benchmark datasets, diurnal curves, and stress audits.
"""

import os
import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException

from backend.config import (
    WEEKLY_BENCHMARK_JSON,
    DISRUPTION_BENCHMARK_JSON,
    STRESS_BENCHMARK_JSON
)

router = APIRouter(prefix="/api/analytics", tags=["Benchmark & Analytics"])


@router.get("/weekly-summary")
async def get_weekly_benchmark_summary():
    """
    Returns the authoritative 56-run 7-day 24-hour weekly cross-comparison dataset
    comparing all 8 dispatcher paradigms.
    """
    if not os.path.exists(WEEKLY_BENCHMARK_JSON):
        raise HTTPException(status_code=404, detail="Weekly benchmark results file not found.")

    with open(WEEKLY_BENCHMARK_JSON, "r") as f:
        records: List[Dict[str, Any]] = json.load(f)

    # Compute model-level weekly aggregations
    models_summary: Dict[str, Dict[str, Any]] = {}
    for r in records:
        disp = r.get("dispatcher", "Unknown")
        if disp not in models_summary:
            models_summary[disp] = {
                "dispatcher": disp,
                "days_evaluated": 0,
                "total_services": 0,
                "delays": [],
                "max_delays": [],
                "puncts": [],
                "knock_ons": 0,
                "actions": 0,
                "by_day": {}
            }

        s = models_summary[disp]
        s["days_evaluated"] += 1
        s["total_services"] += r.get("services", 0)
        s["delays"].append(r.get("mean_delay_sec", 0.0))
        s["max_delays"].append(r.get("max_delay_sec", 0.0))
        s["puncts"].append(r.get("punctuality_pct", 100.0))
        s["knock_ons"] += r.get("knock_on_events", 0)
        s["actions"] += r.get("actions_taken", 0)
        s["by_day"][r.get("day")] = {
            "mean_delay_sec": r.get("mean_delay_sec"),
            "max_delay_sec": r.get("max_delay_sec"),
            "punctuality_pct": r.get("punctuality_pct"),
            "knock_on_events": r.get("knock_on_events"),
            "actions_taken": r.get("actions_taken")
        }

    summary_list = []
    for disp, s in models_summary.items():
        avg_delay = float(sum(s["delays"]) / max(1, len(s["delays"])))
        avg_punc = float(sum(s["puncts"]) / max(1, len(s["puncts"])))
        max_del = float(max(s["max_delays"])) if s["max_delays"] else 0.0

        summary_list.append({
            "dispatcher": disp,
            "weekly_mean_delay_sec": round(avg_delay, 2),
            "weekly_max_delay_sec": round(max_del, 1),
            "weekly_punctuality_pct": round(avg_punc, 2),
            "total_weekly_knock_ons": s["knock_ons"],
            "total_weekly_actions": s["actions"],
            "days_evaluated": s["days_evaluated"],
            "by_day": s["by_day"]
        })

    summary_list.sort(key=lambda x: x["weekly_mean_delay_sec"])

    return {
        "total_runs": len(records),
        "models_summary": summary_list,
        "raw_records": records
    }


@router.get("/diurnal")
async def get_diurnal_timeline(day: str = "Mon"):
    """Returns 24-hour hour-by-hour fleet delay progression comparing dispatchers."""
    if not os.path.exists(WEEKLY_BENCHMARK_JSON):
        raise HTTPException(status_code=404, detail="Weekly benchmark results file not found.")

    with open(WEEKLY_BENCHMARK_JSON, "r") as f:
        records: List[Dict[str, Any]] = json.load(f)

    day_records = [r for r in records if r.get("day", "").lower() == day.lower()]
    hourly_comparison: Dict[str, List[float]] = {}
    for r in day_records:
        disp = r.get("dispatcher")
        hourly = r.get("hourly_delays", [])
        if disp and hourly:
            hourly_comparison[disp] = hourly

    return {
        "day": day,
        "hours": list(range(24)),
        "hourly_delays_by_model": hourly_comparison
    }


@router.get("/stress-test")
async def get_stress_test_results():
    """Returns multi-scenario stress benchmark results (breakdowns, closures, surge, compound)."""
    if not os.path.exists(STRESS_BENCHMARK_JSON):
        raise HTTPException(status_code=404, detail="Stress testing results not found.")

    with open(STRESS_BENCHMARK_JSON, "r") as f:
        data = json.load(f)
    return data


@router.get("/disruption")
async def get_disruption_benchmark():
    """Returns peak disruption recovery results comparing RL to classical heuristics."""
    if not os.path.exists(DISRUPTION_BENCHMARK_JSON):
        raise HTTPException(status_code=404, detail="Disruption benchmark results not found.")

    with open(DISRUPTION_BENCHMARK_JSON, "r") as f:
        data = json.load(f)
    return data
