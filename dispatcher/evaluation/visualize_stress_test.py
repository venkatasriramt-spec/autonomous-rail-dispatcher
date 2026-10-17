"""
visualize_stress_test.py
Generates comparative bar charts from stress_testing_benchmark.json:
1. Mean Delay across 4 disruption scenarios (Train Breakdown, Platform Closure, Fleet Surge, Compound)
2. Knock-On Delay Events Prevented
3. Punctuality Retention (%)
"""

import os
import json
import argparse
import matplotlib.pyplot as plt
import numpy as np

SCENARIO_NAMES = {
    "train_delay": "Train Breakdown\n(10-min Mainline)",
    "platform_blockage": "Platform Closure\n(30-min Hub Shut)",
    "stochastic": "Fleet Surge\n(15% Dwell Jitter)",
    "compound": "Compound Failure\n(Breakdown + Blockage)"
}
SCENARIO_ORDER = ["train_delay", "platform_blockage", "stochastic", "compound"]

DISPATCHERS = [
    "Static_Baseline",
    "FIFO_Heuristic",
    "Priority_Greedy_Heuristic",
    "Centralized_PPO",
    "Decentralized_MAPPO"
]
DISPLAY_NAMES = {
    "Static_Baseline": "Static (Default)",
    "FIFO_Heuristic": "FIFO Heuristic",
    "Priority_Greedy_Heuristic": "Priority Greedy",
    "Centralized_PPO": "Centralized PPO (AI)",
    "Trained_PPO_Dispatcher": "Centralized PPO (AI)",
    "Decentralized_MAPPO": "Decentralized MAPPO (7 Agents)"
}
COLORS = {
    "Static_Baseline": "#e74c3c",           # Crimson
    "FIFO_Heuristic": "#f39c12",            # Amber
    "Priority_Greedy_Heuristic": "#3498db", # Sky Blue
    "Centralized_PPO": "#2980b9",           # Royal Blue
    "Trained_PPO_Dispatcher": "#2980b9",
    "Decentralized_MAPPO": "#2ecc71"         # Emerald Green
}


def plot_stress_charts(json_path: str, output_dir: str):
    if not os.path.exists(json_path):
        print(f"[!] Error: JSON not found at {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    # Organize: scen_map[scen_id][disp] = record
    scen_map = {s: {} for s in SCENARIO_ORDER}
    for item in data:
        s_id = item.get("scenario_id")
        disp_key = item["dispatcher"]
        if disp_key == "Trained_PPO_Dispatcher":
            disp_key = "Centralized_PPO"
        if s_id in scen_map:
            scen_map[s_id][disp_key] = item

    active_dispatchers = [d for d in DISPATCHERS if any(d in scen_map[s] for s in SCENARIO_ORDER)]
    if not active_dispatchers:
        active_dispatchers = DISPATCHERS

    x = np.arange(len(SCENARIO_ORDER))
    n_bars = len(active_dispatchers)
    width = 0.82 / max(1, n_bars)

    # -------------------------------------------------------------
    # 1. Mean Delay Comparison Across Disruption Scenarios
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 5.5), dpi=150)
    for i, disp in enumerate(active_dispatchers):
        offsets = x + (i - (n_bars - 1) / 2) * width
        delays = [scen_map[s].get(disp, {}).get("mean_delay_sec", 0.0) for s in SCENARIO_ORDER]
        rects = ax.bar(
            offsets, delays, width,
            label=DISPLAY_NAMES.get(disp, disp),
            color=COLORS.get(disp, "#7f8c8d"),
            alpha=0.9,
            edgecolor="black",
            linewidth=0.5
        )
        for rect in rects:
            h = rect.get_height()
            ax.annotate(f"{h:.1f}s",
                        xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 2), textcoords="offset points",
                        ha='center', va='bottom', fontsize=7.5, fontweight='bold')

    ax.set_ylabel("Mean Delay per Consist (seconds)", fontsize=11, fontweight="bold")
    ax.set_title("Stress-Testing Benchmark: Delay Under Extreme Disruption Scenarios", fontsize=12, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_NAMES[s] for s in SCENARIO_ORDER], fontsize=10, fontweight="semibold")
    ax.legend(loc="upper left", frameon=True, fontsize=9.5)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    chart1_path = os.path.join(output_dir, "stress_test_delay_comparison.png")
    plt.savefig(chart1_path)
    plt.close()
    print(f"[✓] Saved stress delay chart: {chart1_path}")

    # -------------------------------------------------------------
    # 2. Knock-On Delay Cascades Suppressed
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 5.5), dpi=150)
    for i, disp in enumerate(active_dispatchers):
        offsets = x + (i - (n_bars - 1) / 2) * width
        knockons = [scen_map[s].get(disp, {}).get("knock_on_events", 0) for s in SCENARIO_ORDER]
        rects = ax.bar(
            offsets, knockons, width,
            label=DISPLAY_NAMES.get(disp, disp),
            color=COLORS.get(disp, "#7f8c8d"),
            alpha=0.9,
            edgecolor="black",
            linewidth=0.5
        )
        for rect in rects:
            h = rect.get_height()
            ax.annotate(f"{int(h)}",
                        xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 2), textcoords="offset points",
                        ha='center', va='bottom', fontsize=7.5, fontweight='bold')

    ax.set_ylabel("Secondary Knock-On Conflicts", fontsize=11, fontweight="bold")
    ax.set_title("Cascading Secondary Conflicts Under Disruption Scenarios", fontsize=12, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_NAMES[s] for s in SCENARIO_ORDER], fontsize=10, fontweight="semibold")
    ax.legend(loc="upper right", frameon=True, fontsize=9.5)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    chart2_path = os.path.join(output_dir, "stress_test_knockon_cascades.png")
    plt.savefig(chart2_path)
    plt.close()
    print(f"[✓] Saved stress knock-on chart: {chart2_path}")

    # -------------------------------------------------------------
    # 3. Schedule Punctuality Retention (%)
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 5.5), dpi=150)
    for i, disp in enumerate(active_dispatchers):
        offsets = x + (i - (n_bars - 1) / 2) * width
        puncs = [scen_map[s].get(disp, {}).get("punctuality_pct", 100.0) for s in SCENARIO_ORDER]
        rects = ax.bar(
            offsets, puncs, width,
            label=DISPLAY_NAMES.get(disp, disp),
            color=COLORS.get(disp, "#7f8c8d"),
            alpha=0.9,
            edgecolor="black",
            linewidth=0.5
        )
        for rect in rects:
            h = rect.get_height()
            ax.annotate(f"{h:.1f}%",
                        xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 2), textcoords="offset points",
                        ha='center', va='bottom', fontsize=7.5, fontweight='bold')

    ax.set_ylabel("Punctuality Rate (<3 min delay) %", fontsize=11, fontweight="bold")
    ax.set_title("Punctuality Retention Under Active Disruption", fontsize=12, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_NAMES[s] for s in SCENARIO_ORDER], fontsize=10, fontweight="semibold")
    ax.set_ylim(85, 103)
    ax.legend(loc="lower left", frameon=True, fontsize=9.5)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    chart3_path = os.path.join(output_dir, "stress_test_punctuality.png")
    plt.savefig(chart3_path)
    plt.close()
    print(f"[✓] Saved stress punctuality chart: {chart3_path}")


def main():
    parser = argparse.ArgumentParser(description="Plot stress test benchmark charts")
    parser.add_argument("--json", type=str,
                        default="dispatcher/logs/evaluations/stress_tests/stress_testing_benchmark.json",
                        help="Path to stress_testing_benchmark.json")
    parser.add_argument("--output-dir", type=str, default="dispatcher/logs/visual_proofs",
                        help="Directory to save charts")
    args = parser.parse_args()

    plot_stress_charts(args.json, args.output_dir)


if __name__ == "__main__":
    main()
