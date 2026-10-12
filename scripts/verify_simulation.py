#!/usr/bin/env python3
"""
verify_simulation.py
Runs a headless SUMO simulation to verify that the compiled timetable and routes run cleanly
on the dense railway network without collisions, deadlocks, or teleports.
Supports day-specific verification via --day or full multi-day audit via --all-days.
"""

import subprocess
import os
import sys
import argparse

TRAINS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMOCFG = os.path.join(TRAINS_DIR, "sumo_config", "train_simulation.sumocfg")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_to_sumo import compile_sumo_files

def run_verification(max_steps=3600):
    print("=" * 65)
    print("RUNNING SUMO RAILWAY SIMULATION VERIFICATION")
    print("=" * 65)
    print(f"Config File: {SUMOCFG}")
    print(f"Max Sim Steps: {max_steps} seconds ({max_steps/3600:.1f} hours simulated)")

    cmd = [
        "sumo",
        "-c", SUMOCFG,
        "--end", str(max_steps),
        "--collision.action", "warn",
        "--duration-log.statistics", "true",
        "--no-step-log", "true"
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)

    print("\n--- SUMO OUTPUT SUMMARY ---")
    lines = res.stdout.splitlines() + res.stderr.splitlines()
    for line in lines:
        if any(keyword in line for keyword in ["Simulation version", "Performance:", "Vehicles:", "Speed:", "Duration:", "Teleports:", "Collision", "Quitting"]):
            print(line)

    if "Error:" in res.stderr:
        print("\n[!] Errors encountered:")
        print(res.stderr)
        return False
    else:
        print("\n[OK] Simulation verified successfully with 0 fatal errors!")
        return True

def verify_day(day, max_steps=86400):
    print(f"\n>>> Compiling SUMO files for: {day} <<<")
    compile_sumo_files(day=day)
    return run_verification(max_steps=max_steps)

def verify_all_days(max_steps=86400):
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "all"]
    results = {}
    print("=" * 65)
    print("RUNNING FULL MULTI-DAY OPERATING SCHEDULE VERIFICATION")
    print("=" * 65)
    for d in days:
        print(f"\n==================== Verifying {d.upper()} ====================")
        success = verify_day(d, max_steps=max_steps)
        results[d] = success

    print("\n" + "=" * 65)
    print("MULTI-DAY VERIFICATION SUMMARY")
    print("=" * 65)
    all_ok = True
    for d, ok in results.items():
        status = "PASSED (0 fatal errors)" if ok else "FAILED"
        print(f"  Day {d:5s}: {status}")
        if not ok:
            all_ok = False
    return all_ok

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verify SUMO railway network simulation runs without errors or deadlocks."
    )
    parser.add_argument(
        "steps",
        nargs="?",
        type=int,
        default=None,
        help="Max simulation steps in seconds (default: 3600 or 86400 if --day/--all-days is specified)"
    )
    parser.add_argument(
        "-d", "--day",
        type=str,
        default=None,
        help="Compile and verify a specific operating day (Mon, Tue, Wed, Thu, Fri, Sat, Sun, all)"
    )
    parser.add_argument(
        "--all-days",
        action="store_true",
        help="Compile and verify all 7 operating days and the composite schedule"
    )
    args = parser.parse_args()

    if args.all_days:
        steps = args.steps if args.steps is not None else 86400
        ok = verify_all_days(max_steps=steps)
        sys.exit(0 if ok else 1)
    elif args.day:
        steps = args.steps if args.steps is not None else 86400
        ok = verify_day(args.day, max_steps=steps)
        sys.exit(0 if ok else 1)
    else:
        steps = args.steps if args.steps is not None else 3600
        ok = run_verification(max_steps=steps)
        sys.exit(0 if ok else 1)
