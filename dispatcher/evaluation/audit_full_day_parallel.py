#!/usr/bin/env python3
"""
audit_full_day_parallel.py
Runs a full 24-hour (00:00 to 24:00, 86,400s) microscopic evaluation across ALL 7 DAYS of the week
in parallel using multi-processing across independent SUMO instances.

Guarantees:
- Independent SUMO configs and route files per day in trains/sumo_config/days/{day}
- Zero cross-process socket or route file collisions
- Restores master composite schedule upon completion
- Tracks full-day decision distributions (Route, Platform, Holds, Do-Nothing)
- Compares AI Dispatcher directly against Unmanaged Static Baseline
"""

import os
import sys
import json
import time
import shutil
import xml.etree.ElementTree as ET
import multiprocessing as mp
import numpy as np
from typing import Dict, Any, List

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dispatcher.envs.railway_dispatch_env import RailwayDispatchEnv
from dispatcher.agents.baseline_dispatchers import StaticDispatcher
from dispatcher.evaluation.evaluate import ModelAgentWrapper
from trains.scripts.export_to_sumo import compile_sumo_files

LOGS_DIR = os.path.join(ROOT_DIR, "dispatcher", "logs")
MODEL_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "best_model.zip")
DAYS_DIR = os.path.join(ROOT_DIR, "trains", "sumo_config", "days")

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_SERVICE_COUNTS = {
    "Mon": 232, "Tue": 233, "Wed": 229,
    "Thu": 235, "Fri": 231, "Sat": 145, "Sun": 141
}

SIM_HORIZON_SEC = 86400.0  # Full 24 Hours
MACRO_STEP_SEC = 15.0      # 15-second dispatcher cadence


def prepare_day_config(day: str):
    """Pre-compiles routes for a specific day into an isolated directory."""
    day_folder = os.path.join(DAYS_DIR, day)
    os.makedirs(day_folder, exist_ok=True)

    # 1. Compile day routes in sumo_config
    compile_sumo_files(mode="rakes", day=day)

    src_cfg = os.path.join(ROOT_DIR, "trains", "sumo_config", "train_simulation.sumocfg")
    src_rou = os.path.join(ROOT_DIR, "trains", "sumo_config", "trains_rakes.rou.xml")
    src_view = os.path.join(ROOT_DIR, "trains", "sumo_config", "viewsettings.xml")

    dest_cfg = os.path.join(day_folder, "train_simulation.sumocfg")
    dest_rou = os.path.join(day_folder, "trains_rakes.rou.xml")
    dest_rou_compat = os.path.join(day_folder, "trains.rou.xml")
    dest_view = os.path.join(day_folder, "viewsettings.xml")

    shutil.copy(src_cfg, dest_cfg)
    shutil.copy(src_rou, dest_rou)
    shutil.copy(src_rou, dest_rou_compat)
    if os.path.exists(src_view):
        shutil.copy(src_view, dest_view)

    # 2. Patch relative paths in sumocfg to point back to tracks/network_data
    net_path = os.path.join(ROOT_DIR, "tracks", "network_data", "dense_network.net.xml")
    add_path = os.path.join(ROOT_DIR, "tracks", "network_data", "dense_network.add.xml")

    tree = ET.parse(dest_cfg)
    root = tree.getroot()
    root.find("input/net-file").attrib["value"] = os.path.relpath(net_path, day_folder)
    root.find("input/additional-files").attrib["value"] = os.path.relpath(add_path, day_folder)
    root.find("input/route-files").attrib["value"] = "trains_rakes.rou.xml"
    tree.write(dest_cfg)


def run_single_day_worker(day: str) -> Dict[str, Any]:
    """Worker process that audits a single 24-hour day in an isolated SUMO instance."""
    day_cfg = os.path.join(DAYS_DIR, day, "train_simulation.sumocfg")
    t0 = time.time()
    print(f"[{day}] Starting 24-Hour Simulation (00:00 - 24:00, {DAY_SERVICE_COUNTS.get(day)} services)...")

    # -------------------------------------------------------------
    # 1. Unmanaged Static Baseline (Full 24h)
    # -------------------------------------------------------------
    static_env = RailwayDispatchEnv(
        sumocfg_path=day_cfg,
        start_time_sec=0.0,
        sim_horizon_sec=SIM_HORIZON_SEC,
        macro_step_sec=MACRO_STEP_SEC,
        gui=False
    )
    static_agent = StaticDispatcher()
    obs, info = static_env.reset()
    static_delays = []
    static_step = 0
    terminated = False
    truncated = False

    while not (terminated or truncated):
        action = static_agent.predict(obs, info)
        obs, reward, terminated, truncated, info = static_env.step(action)
        static_delays.append(info.get("mean_delay_sec", 0.0))
        static_step += 1
    static_env.close()

    static_mean_delay = float(np.mean(static_delays)) if static_delays else 0.0
    static_max_delay = float(np.max(static_delays)) if static_delays else 0.0
    static_knock_ons = info.get("knock_on_events", 0)

    # -------------------------------------------------------------
    # 2. Trained AI Dispatcher (Full 24h)
    # -------------------------------------------------------------
    model_wrapper = ModelAgentWrapper(MODEL_PATH)
    ai_env = RailwayDispatchEnv(
        sumocfg_path=day_cfg,
        start_time_sec=0.0,
        sim_horizon_sec=SIM_HORIZON_SEC,
        macro_step_sec=MACRO_STEP_SEC,
        gui=False
    )
    obs, info = ai_env.reset()
    ai_delays = []
    ai_puncs = []
    active_trains_history = []
    ai_step = 0
    terminated = False
    truncated = False

    route_diverts = 0
    plat_switches = 0
    holds_applied = 0
    do_nothing_count = 0

    last_log_time = 0.0
    while not (terminated or truncated):
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
        sim_t = info.get("sim_time", 0.0)
        ai_delays.append(info.get("mean_delay_sec", 0.0))
        ai_puncs.append(info.get("punctuality_pct", 100.0))
        active_trains_history.append(info.get("active_trains", 0))
        ai_step += 1

        # Progress log every 4 simulation hours (14,400s)
        if sim_t - last_log_time >= 14400.0:
            last_log_time = sim_t
            pct = (sim_t / SIM_HORIZON_SEC) * 100.0
            print(f"[{day}] Progress: {pct:.0f}% ({sim_t/3600:.1f}h) | Active: {info.get('active_trains')} | Delay: {info.get('mean_delay_sec', 0.0):.1f}s")

    ai_env.close()
    elapsed = time.time() - t0

    ai_mean_delay = float(np.mean(ai_delays)) if ai_delays else 0.0
    ai_max_delay = float(np.max(ai_delays)) if ai_delays else 0.0
    ai_punctuality = float(np.mean(ai_puncs)) if ai_puncs else 100.0
    ai_knock_ons = info.get("knock_on_events", 0)
    peak_active = max(active_trains_history) if active_trains_history else 0

    total_decisions = ai_step
    print(f"[{day}] COMPLETED in {elapsed/60:.2f} min! Mean Delay: {ai_mean_delay:.2f}s | Punctuality: {ai_punctuality:.1f}% | Knock-ons: {ai_knock_ons}")

    return {
        "day": day,
        "services": DAY_SERVICE_COUNTS.get(day, 0),
        "elapsed_sec": round(elapsed, 1),
        "steps_simulated": ai_step,
        "peak_active_trains": peak_active,
        "decisions": {
            "total_steps": total_decisions,
            "route_diversions": route_diverts,
            "platform_switches": plat_switches,
            "holds": holds_applied,
            "do_nothing": do_nothing_count
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


def main():
    print("=" * 85)
    print("AUTONOMOUS TRAIN DISPATCHER: FULL 24-HOUR WEEKLY CALENDAR PARALLEL AUDIT")
    print(f"Operational Horizon: 00:00 to 24:00 (86,400s) | Cadence: {MACRO_STEP_SEC}s")
    print(f"Execution: 7 Parallel Workers on 32-vCPU Host | Checkpoint: {MODEL_PATH}")
    print("=" * 85)

    if not os.path.exists(MODEL_PATH):
        print(f"[!] Error: Model not found at {MODEL_PATH}")
        sys.exit(1)

    t0 = time.time()

    # Step 1: Pre-compile isolated day configs
    print("\n[*] Pre-compiling isolated 7-day SUMO configs...")
    for day in DAYS:
        print(f"  - Generating {day} config...", end=" ", flush=True)
        prepare_day_config(day)
        print("Done.")

    # Restore master composite schedule in root config
    print("[*] Restoring root master composite schedule (-d all)...")
    compile_sumo_files(mode="rakes", day="all")

    # Step 2: Launch 7 parallel workers
    print("\n[*] Launching 7 parallel workers across VM cores...")
    with mp.Pool(processes=7) as pool:
        results = pool.map(run_single_day_worker, DAYS)

    # Step 3: Save results
    os.makedirs(LOGS_DIR, exist_ok=True)
    out_json = os.path.join(LOGS_DIR, "full_day_weekly_audit.json")
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)

    total_time = time.time() - t0
    print("\n" + "=" * 85)
    print(f"FULL 24-HOUR 7-DAY AUDIT COMPLETE IN {total_time/60:.2f} MINUTES ({total_time:.1f}s)!")
    print(f"Audit report saved to: {out_json}")
    print("=" * 85)

    # Print Comparative Scorecard
    print("\n" + "=" * 95)
    print(f"{'Day':<5} | {'Services':<8} | {'Peak Trn':<8} | {'AI Delay':<10} | {'Static Delay':<12} | {'AI Punc':<9} | {'AI Knock-ons':<13} | {'Static Knock'}")
    print("-" * 95)
    for r in results:
        k = r["ai_kpi"]
        sk = r["static_kpi"]
        print(f"{r['day']:<5} | {r['services']:<8} | {r['peak_active_trains']:<8} | {k['mean_delay_sec']:>7.2f}s   | {sk['mean_delay_sec']:>9.2f}s   | {k['punctuality_pct']:>6.1f}%  | {k['knock_on_events']:>10}    | {sk['knock_on_events']:>10}")
    print("=" * 95)


if __name__ == "__main__":
    main()
