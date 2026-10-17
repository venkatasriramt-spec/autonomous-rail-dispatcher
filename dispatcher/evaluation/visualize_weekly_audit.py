"""
visualize_weekly_audit.py
Generates comprehensive 7-day multi-model evaluation charts from cross_comparison_24h.json:
1. 7-Day Mean & Max Delay Grouped Bar Chart
2. 7-Day Knock-On Cascades Suppressed
3. 7-Day Schedule Punctuality Comparison
4. 24-Hour Diurnal Fleet Delay Timeline (00:00 to 24:00)
"""

import os
import json
import argparse
import matplotlib.pyplot as plt
import numpy as np

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
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


def plot_weekly_charts(json_path: str, output_dir: str):
    if not os.path.exists(json_path):
        print(f"[!] Error: JSON not found at {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    # Organize data: day_map[day][disp] = record
    day_map = {d: {} for d in DAYS}
    for item in data:
        disp_key = item["dispatcher"]
        if disp_key == "Trained_PPO_Dispatcher":
            disp_key = "Centralized_PPO"
        day_map[item["day"]][disp_key] = item

    active_dispatchers = [d for d in DISPATCHERS if any(d in day_map[d_day] for d_day in DAYS)]
    if not active_dispatchers:
        active_dispatchers = DISPATCHERS

    x = np.arange(len(DAYS))
    n_bars = len(active_dispatchers)
    width = 0.82 / max(1, n_bars)

    # -------------------------------------------------------------
    # 1. 7-Day Mean Delay Grouped Bar Chart
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(13, 6), dpi=150)

    for i, disp in enumerate(active_dispatchers):
        offsets = x + (i - (n_bars - 1) / 2) * width
        delays = [day_map[d].get(disp, {}).get("mean_delay_sec", 0.0) for d in DAYS]
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
            if h > 0.05:
                ax.annotate(f"{h:.1f}s",
                            xy=(rect.get_x() + rect.get_width() / 2, h),
                            xytext=(0, 2), textcoords="offset points",
                            ha='center', va='bottom', fontsize=7.0, fontweight='bold')

    ax.set_ylabel("Mean Delay per Consist (seconds)", fontsize=12, fontweight="bold")
    ax.set_title("Autonomous Train Dispatcher: 7-Day Full 24-Hour Mean Delay Benchmark", fontsize=13, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{d}\n({data[0].get('services', '')} svc)" if d == "Mon" else d for d in DAYS], fontsize=10, fontweight="semibold")
    ax.legend(loc="upper right", frameon=True, fontsize=9.5)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    chart1_path = os.path.join(output_dir, "weekly_7day_delay_comparison.png")
    plt.savefig(chart1_path)
    plt.close()
    print(f"[✓] Saved 7-day delay chart: {chart1_path}")

    # -------------------------------------------------------------
    # 2. 7-Day Secondary Knock-On Cascades Suppressed
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(13, 6), dpi=150)
    for i, disp in enumerate(active_dispatchers):
        offsets = x + (i - (n_bars - 1) / 2) * width
        knockons = [day_map[d].get(disp, {}).get("knock_on_events", 0) for d in DAYS]
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
            if h > 0:
                ax.annotate(f"{int(h)}",
                            xy=(rect.get_x() + rect.get_width() / 2, h),
                            xytext=(0, 2), textcoords="offset points",
                            ha='center', va='bottom', fontsize=7.0, fontweight='bold')

    ax.set_ylabel("Secondary Knock-On Delay Events", fontsize=12, fontweight="bold")
    ax.set_title("Cascading Secondary Conflicts Suppressed Across All 7 Days (24 Hours)", fontsize=13, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(DAYS, fontsize=10, fontweight="semibold")
    ax.legend(loc="upper right", frameon=True, fontsize=9.5)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    chart2_path = os.path.join(output_dir, "weekly_7day_knockon_cascades.png")
    plt.savefig(chart2_path)
    plt.close()
    print(f"[✓] Saved 7-day knock-on chart: {chart2_path}")

    # -------------------------------------------------------------
    # 3. 7-Day Schedule Punctuality Comparison
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(13, 6), dpi=150)
    for i, disp in enumerate(active_dispatchers):
        offsets = x + (i - (n_bars - 1) / 2) * width
        puncs = [day_map[d].get(disp, {}).get("punctuality_pct", 100.0) for d in DAYS]
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
                        ha='center', va='bottom', fontsize=7.0, fontweight='bold')

    ax.set_ylabel("Punctuality Rate (<3 min delay) %", fontsize=12, fontweight="bold")
    ax.set_title("Schedule Punctuality Retention Across All 7 Days of the Week", fontsize=13, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(DAYS, fontsize=10, fontweight="semibold")
    ax.set_ylim(85, 103)
    ax.legend(loc="lower right", frameon=True, fontsize=9.5)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    chart3_path = os.path.join(output_dir, "weekly_7day_punctuality.png")
    plt.savefig(chart3_path)
    plt.close()
    print(f"[✓] Saved 7-day punctuality chart: {chart3_path}")

    # -------------------------------------------------------------
    # 4. 24-Hour Diurnal Hourly Profile (Monday vs Saturday)
    # -------------------------------------------------------------
    has_hourly = any("hourly_delays" in item and item["hourly_delays"] for item in data)
    if has_hourly:
        fig, (ax_mon, ax_sat) = plt.subplots(1, 2, figsize=(15, 5.5), dpi=150)
        hours = np.arange(24)

        for disp in active_dispatchers:
            mon_item = day_map["Mon"].get(disp, {})
            sat_item = day_map["Sat"].get(disp, {})
            if "hourly_delays" in mon_item and mon_item["hourly_delays"]:
                ax_mon.plot(hours, mon_item["hourly_delays"], label=DISPLAY_NAMES.get(disp, disp), color=COLORS.get(disp, "#7f8c8d"), linewidth=2.0)
            if "hourly_delays" in sat_item and sat_item["hourly_delays"]:
                ax_sat.plot(hours, sat_item["hourly_delays"], label=DISPLAY_NAMES.get(disp, disp), color=COLORS.get(disp, "#7f8c8d"), linewidth=2.0)


        ax_mon.set_xlabel("Hour of the Day (00:00 - 24:00)", fontsize=10, fontweight="bold")
        ax_mon.set_ylabel("Mean Delay (seconds)", fontsize=10, fontweight="bold")
        ax_mon.set_title("Monday Commuter Surge: 24-Hour Hourly Delay Progression", fontsize=11, fontweight="bold")
        ax_mon.set_xticks(range(0, 24, 2))
        ax_mon.grid(True, linestyle="--", alpha=0.5)
        ax_mon.legend(loc="upper right", frameon=True, fontsize=9)

        ax_sat.set_xlabel("Hour of the Day (00:00 - 24:00)", fontsize=10, fontweight="bold")
        ax_sat.set_ylabel("Mean Delay (seconds)", fontsize=10, fontweight="bold")
        ax_sat.set_title("Saturday Leisure Base: 24-Hour Hourly Delay Progression", fontsize=11, fontweight="bold")
        ax_sat.set_xticks(range(0, 24, 2))
        ax_sat.grid(True, linestyle="--", alpha=0.5)
        ax_sat.legend(loc="upper right", frameon=True, fontsize=9)

        plt.tight_layout()
        chart4_path = os.path.join(output_dir, "weekly_24h_diurnal_timeline.png")
        plt.savefig(chart4_path)
        plt.close()
        print(f"[✓] Saved 24h diurnal timeline: {chart4_path}")


def main():
    parser = argparse.ArgumentParser(description="Plot weekly 24-hour audit charts")
    parser.add_argument("--json", type=str, default="dispatcher/logs/evaluations/weekly_audits/cross_comparison_24h.json",
                        help="Path to cross_comparison_24h.json")
    parser.add_argument("--output-dir", type=str, default="dispatcher/logs/visual_proofs",
                        help="Directory to save charts")
    args = parser.parse_args()

    plot_weekly_charts(args.json, args.output_dir)


if __name__ == "__main__":
    main()
