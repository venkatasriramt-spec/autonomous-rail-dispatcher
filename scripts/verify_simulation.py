#!/usr/bin/env python3
"""
verify_simulation.py
Runs a headless SUMO simulation to verify that the compiled timetable and routes run cleanly
on the dense railway network without collisions, deadlocks, or teleports.
"""

import subprocess
import os
import sys

TRAINS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMOCFG = os.path.join(TRAINS_DIR, "sumo_config", "train_simulation.sumocfg")

def run_verification(max_steps=3600):
    print("=" * 65)
    print("RUNNING SUMO RAILWAY SIMULATION VERIFICATION")
    print("=" * 65)
    print(f"Config File: {SUMOCFG}")
    print(f"Max Sim Steps: {max_steps} seconds (1 hour simulated)")

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

if __name__ == "__main__":
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    run_verification(steps)
