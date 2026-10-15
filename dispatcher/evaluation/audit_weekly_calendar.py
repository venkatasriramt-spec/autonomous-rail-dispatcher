#!/usr/bin/env python3
"""
audit_weekly_calendar.py
Audits the trained AI dispatcher against every day of the week (Mon, Tue, Wed, Thu, Fri, Sat, Sun)
to analyze how its decision-making changes between heavy weekday commuter traffic and weekend clockface traffic.
"""

import os
import sys
import json
import time
import subprocess
import numpy as np
from typing import Dict, Any, List

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dispatcher.envs.railway_dispatch_env import RailwayDispatchEnv
from dispatcher.agents.baseline_dispatchers import StaticDispatcher
from dispatcher.evaluation.evaluate import ModelAgentWrapper

LOGS_DIR = os.path.join(ROOT_DIR, "dispatcher", "logs")
MODEL_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "best_model.zip")
PYTHON = sys.executable

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

DAY_SERVICE_COUNTS = {
    "Mon": 232,
    "Tue": 233,
    "Wed": 229,
    "Thu": 235,
    "Fri": 231,
    "Sat": 145,
    "Sun": 141
}

def export_day(day: str):
    cmd = [PYTHON, "trains/scripts/export_to_sumo.py", "-d", day]
    res = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to export schedule for {day}: {res.stderr}")

def evaluate_day(day: str, model_wrapper: ModelAgentWrapper, horizon_sec: float = 3600.0, start_time_sec: float = 25200.0) -> Dict[str, Any]:
    print(f"\n[*] Auditing {day} ({DAY_SERVICE_COUNTS.get(day, '?')} services) | Window: {start_time_sec:.0f}s - {start_time_sec+horizon_sec:.0f}s...")
    export_day(day)

    # 1. Evaluate Static Baseline
    static_env = RailwayDispatchEnv(
        start_time_sec=start_time_sec,
        sim_horizon_sec=horizon_sec,
        macro_step_sec=15.0,
        gui=False
    )
    static_agent = StaticDispatcher()
    obs, info = static_env.reset()
    static_delays = []
    static_step = 0
    terminated = False
    truncated = False

    while not (terminated or truncated) and static_step < 300:
        action = static_agent.predict(obs, info)
        obs, reward, terminated, truncated, info = static_env.step(action)
        static_delays.append(info.get("mean_delay_sec", 0.0))
        static_step += 1
    static_env.close()

    static_mean_delay = float(np.mean(static_delays)) if static_delays else 0.0
    static_max_delay = float(np.max(static_delays)) if static_delays else 0.0
    static_knock_ons = info.get("knock_on_events", 0)

    # 2. Evaluate Trained AI Dispatcher
    ai_env = RailwayDispatchEnv(
        start_time_sec=start_time_sec,
        sim_horizon_sec=horizon_sec,
        macro_step_sec=15.0,
        gui=False
    )
    obs, info = ai_env.reset()
    ai_delays = []
    ai_puncs = []
    ai_step = 0
    terminated = False
    truncated = False

    route_diverts = 0
    plat_switches = 0
    holds_applied = 0
    do_nothing_count = 0

    while not (terminated or truncated) and ai_step < 300:
        action = model_wrapper.predict(obs, info)
        route_act, plat_act, hold_act = int(action[0]), int(action[1]), int(action[2])

        if route_act > 0:
            route_diverts += 1
        if plat_act > 0:
            plat_switches += 1
        if hold_act > 0:
            holds_applied += 1
        if route_act == 0 and plat_act == 0 and hold_act == 0:
            do_nothing_count += 1

        obs, reward, terminated, truncated, info = ai_env.step(action)
        ai_delays.append(info.get("mean_delay_sec", 0.0))
        ai_puncs.append(info.get("punctuality_pct", 100.0))
        ai_step += 1
    ai_env.close()

    ai_mean_delay = float(np.mean(ai_delays)) if ai_delays else 0.0
    ai_max_delay = float(np.max(ai_delays)) if ai_delays else 0.0
    ai_punctuality = float(np.mean(ai_puncs)) if ai_puncs else 100.0
    ai_knock_ons = info.get("knock_on_events", 0)

    total_decisions = ai_step
    action_rate = ((route_diverts + plat_switches + holds_applied) / max(1, total_decisions)) * 100.0

    result = {
        "day": day,
        "services": DAY_SERVICE_COUNTS.get(day, 0),
        "steps_simulated": ai_step,
        "decisions": {
            "total": total_decisions,
            "route_diversions": route_diverts,
            "platform_switches": plat_switches,
            "holds": holds_applied,
            "do_nothing": do_nothing_count,
            "intervention_rate_pct": round(action_rate, 1)
        },
        "ai_kpi": {
            "mean_delay_sec": round(ai_mean_delay, 2),
            "max_delay_sec": round(ai_max_delay, 1),
            "punctuality_pct": round(ai_punctuality, 1),
            "knock_on_events": ai_knock_ons
        },
        "static_kpi": {
            "mean_delay_sec": round(static_mean_delay, 2),
            "max_delay_sec": round(static_max_delay, 1),
            "knock_on_events": static_knock_ons
        }
    }

    print(f"  [✓] {day} Done! AI Mean Delay: {ai_mean_delay:.2f}s | Punc: {ai_punctuality:.1f}% | Holds: {holds_applied} | Plat: {plat_switches} | DoNothing: {do_nothing_count}")
    return result

def main():
    print("=" * 80)
    print("AUTONOMOUS TRAIN DISPATCHER: FULL WEEKLY CALENDAR DECISION AUDIT")
    print(f"Model Checkpoint: {MODEL_PATH}")
    print("Window: Morning Peak (07:00 to 08:00, 25,200s - 28,800s)")
    print("=" * 80)

    if not os.path.exists(MODEL_PATH):
        print(f"[!] Error: Model not found at {MODEL_PATH}")
        sys.exit(1)

    t0 = time.time()
    model_wrapper = ModelAgentWrapper(MODEL_PATH)

    weekly_results = []
    for day in DAYS:
        res = evaluate_day(day, model_wrapper)
        weekly_results.append(res)

    # Restore master composite schedule
    print("\n[*] Restoring master composite schedule (-d all)...")
    export_day("all")

    # Save JSON report
    os.makedirs(LOGS_DIR, exist_ok=True)
    out_json = os.path.join(LOGS_DIR, "weekly_calendar_audit.json")
    with open(out_json, "w") as f:
        json.dump(weekly_results, f, indent=2)

    total_time = time.time() - t0
    print("\n" + "=" * 80)
    print(f"FULL WEEKLY AUDIT COMPLETE IN {total_time:.1f}s ({total_time/60:.2f} min)")
    print(f"Results saved to: {out_json}")
    print("=" * 80)

    # Print summary table
    print("\n" + "=" * 90)
    print(f"{'Day':<6} | {'Services':<8} | {'Interventions':<14} | {'Holds':<6} | {'Plat':<5} | {'DoNothing':<10} | {'Mean Delay':<11} | {'Punctuality':<11} | {'Knock-ons'}")
    print("-" * 90)
    for r in weekly_results:
        d = r["decisions"]
        k = r["ai_kpi"]
        interventions_str = f"{d['intervention_rate_pct']}% ({d['route_diversions']+d['platform_switches']+d['holds']}/{d['total']})"
        print(f"{r['day']:<6} | {r['services']:<8} | {interventions_str:<14} | {d['holds']:<6} | {d['platform_switches']:<5} | {d['do_nothing']:<10} | {k['mean_delay_sec']:>6.2f}s     | {k['punctuality_pct']:>6.1f}%     | {k['knock_on_events']}")
    print("=" * 90)

if __name__ == "__main__":
    main()
