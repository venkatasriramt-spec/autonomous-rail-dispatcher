"""
visualize_weekly_audit.py
Generates comprehensive 7-day multi-model evaluation charts from cross_comparison_24h.json:
1. 7-Day Mean Delay Grouped Bar Chart
2. 7-Day Secondary Knock-On Cascades Suppressed
3. 7-Day Schedule Punctuality Comparison (with 95% threshold)
4. 7-Day Total Dispatcher Actions Taken & Churn Analysis
5. 24-Hour Diurnal Fleet Delay Timeline (Monday Surge vs Saturday Leisure)
6. Dispatcher Action-Efficiency Trade-off (Delay vs Interventions)
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
    "Multi_Train_Centralized_PPO",
    "Decentralized_MAPPO",
    "Comm_MAPPO",
    "Hierarchical_Hybrid"
]

DISPLAY_NAMES = {
    "Static_Baseline": "Static (Default)",
    "FIFO_Heuristic": "FIFO Heuristic",
    "Priority_Greedy_Heuristic": "Priority Greedy",
    "Centralized_PPO": "Centralized PPO (AI)",
    "Trained_PPO_Dispatcher": "Centralized PPO (AI)",
    "Multi_Train_Centralized_PPO": "Multi-Train PPO (AI)",
    "Multi_Train_PPO": "Multi-Train PPO (AI)",
    "Decentralized_MAPPO": "Decentralized MAPPO",
    "Comm_MAPPO": "Comm-MAPPO (7 Agents)",
    "Hierarchical_Hybrid": "Hierarchical Hybrid (Ensemble)",
    "Hierarchical_Hybrid_Ensemble": "Hierarchical Hybrid (Ensemble)"
}

COLORS = {
    "Static_Baseline": "#e74c3c",           # Crimson
    "FIFO_Heuristic": "#f39c12",            # Amber
    "Priority_Greedy_Heuristic": "#d35400", # Rust / Deep Orange
    "Centralized_PPO": "#2980b9",           # Royal Blue
    "Trained_PPO_Dispatcher": "#2980b9",
    "Multi_Train_Centralized_PPO": "#8e44ad", # Purple
    "Multi_Train_PPO": "#8e44ad",
    "Decentralized_MAPPO": "#95a5a6",         # Slate Gray
    "Comm_MAPPO": "#16a085",                # Teal / Dark Mint
    "Hierarchical_Hybrid": "#27ae60",       # Emerald Green
    "Hierarchical_Hybrid_Ensemble": "#27ae60"
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
        elif disp_key == "Multi_Train_PPO":
            disp_key = "Multi_Train_Centralized_PPO"
        elif disp_key == "Hierarchical_Hybrid_Ensemble":
            disp_key = "Hierarchical_Hybrid"
        day_map[item["day"]][disp_key] = item

    active_dispatchers = [d for d in DISPATCHERS if any(d in day_map[d_day] for d_day in DAYS)]
    if not active_dispatchers:
        active_dispatchers = DISPATCHERS

    x = np.arange(len(DAYS))
    n_bars = len(active_dispatchers)
    width = 0.86 / max(1, n_bars)

    # -------------------------------------------------------------
    # 1. 7-Day Mean Delay Grouped Bar Chart
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(16, 7), dpi=160)

    for i, disp in enumerate(active_dispatchers):
        offsets = x + (i - (n_bars - 1) / 2) * width
        delays = [day_map[d].get(disp, {}).get("mean_delay_sec", 0.0) for d in DAYS]
        rects = ax.bar(
            offsets, delays, width,
            label=DISPLAY_NAMES.get(disp, disp),
            color=COLORS.get(disp, "#7f8c8d"),
            alpha=0.92,
            edgecolor="black",
            linewidth=0.5
        )
        for rect in rects:
            h = rect.get_height()
            if h > 1.0:
                ax.annotate(f"{h:.1f}s",
                            xy=(rect.get_x() + rect.get_width() / 2, h),
                            xytext=(0, 2), textcoords="offset points",
                            ha='center', va='bottom', fontsize=6.2, fontweight='bold', rotation=90)

    ax.set_ylabel("Mean Delay per Consist (seconds)", fontsize=12, fontweight="bold")
    ax.set_title("Autonomous Railway Dispatcher: 7-Day Full 24-Hour Mean Delay Benchmark (All Models)", fontsize=13, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(DAYS, fontsize=11, fontweight="semibold")
    ax.legend(loc="upper right", frameon=True, fontsize=9.0, ncol=2)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    chart1_path = os.path.join(output_dir, "weekly_7day_delay_comparison.png")
    plt.savefig(chart1_path)
    plt.close()
    print(f"[✓] Saved 7-day delay chart: {chart1_path}")

    # -------------------------------------------------------------
    # 2. 7-Day Secondary Knock-On Cascades Suppressed
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(16, 7), dpi=160)
    for i, disp in enumerate(active_dispatchers):
        offsets = x + (i - (n_bars - 1) / 2) * width
        knockons = [day_map[d].get(disp, {}).get("knock_on_events", 0) for d in DAYS]
        rects = ax.bar(
            offsets, knockons, width,
            label=DISPLAY_NAMES.get(disp, disp),
            color=COLORS.get(disp, "#7f8c8d"),
            alpha=0.92,
            edgecolor="black",
            linewidth=0.5
        )
        for rect in rects:
            h = rect.get_height()
            if h > 10:
                ax.annotate(f"{int(h)}",
                            xy=(rect.get_x() + rect.get_width() / 2, h),
                            xytext=(0, 2), textcoords="offset points",
                            ha='center', va='bottom', fontsize=6.2, fontweight='bold', rotation=90)

    ax.set_ylabel("Secondary Knock-On Delay Events", fontsize=12, fontweight="bold")
    ax.set_title("Cascading Secondary Conflicts Suppressed Across All 7 Days (24 Hours)", fontsize=13, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(DAYS, fontsize=11, fontweight="semibold")
    ax.legend(loc="upper right", frameon=True, fontsize=9.0, ncol=2)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    chart2_path = os.path.join(output_dir, "weekly_7day_knockon_cascades.png")
    plt.savefig(chart2_path)
    plt.close()
    print(f"[✓] Saved 7-day knock-on chart: {chart2_path}")

    # -------------------------------------------------------------
    # 3. 7-Day Schedule Punctuality Comparison (with 95% target line)
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(16, 7), dpi=160)
    for i, disp in enumerate(active_dispatchers):
        offsets = x + (i - (n_bars - 1) / 2) * width
        puncs = [day_map[d].get(disp, {}).get("punctuality_pct", 100.0) for d in DAYS]
        rects = ax.bar(
            offsets, puncs, width,
            label=DISPLAY_NAMES.get(disp, disp),
            color=COLORS.get(disp, "#7f8c8d"),
            alpha=0.92,
            edgecolor="black",
            linewidth=0.5
        )
        for rect in rects:
            h = rect.get_height()
            if h > 80:
                ax.annotate(f"{h:.1f}%",
                            xy=(rect.get_x() + rect.get_width() / 2, h),
                            xytext=(0, 2), textcoords="offset points",
                            ha='center', va='bottom', fontsize=5.8, fontweight='bold', rotation=90)

    ax.axhline(95.0, color="#c0392b", linestyle="--", linewidth=1.5, label="Target Punctuality Threshold (95%)")
    ax.set_ylabel("Punctuality Rate (<3 min delay) %", fontsize=12, fontweight="bold")
    ax.set_title("Schedule Punctuality Retention Across All 7 Days of the Week", fontsize=13, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(DAYS, fontsize=11, fontweight="semibold")
    ax.set_ylim(85, 102)
    ax.legend(loc="lower right", frameon=True, fontsize=9.0, ncol=2)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    chart3_path = os.path.join(output_dir, "weekly_7day_punctuality.png")
    plt.savefig(chart3_path)
    plt.close()
    print(f"[✓] Saved 7-day punctuality chart: {chart3_path}")

    # -------------------------------------------------------------
    # 4. 7-Day Total Dispatcher Actions Taken & Churn Analysis
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(16, 7), dpi=160)
    for i, disp in enumerate(active_dispatchers):
        offsets = x + (i - (n_bars - 1) / 2) * width
        acts = [day_map[d].get(disp, {}).get("actions_taken", 0) for d in DAYS]
        rects = ax.bar(
            offsets, acts, width,
            label=DISPLAY_NAMES.get(disp, disp),
            color=COLORS.get(disp, "#7f8c8d"),
            alpha=0.92,
            edgecolor="black",
            linewidth=0.5
        )
        for rect in rects:
            h = rect.get_height()
            if h > 10:
                ax.annotate(f"{int(h)}",
                            xy=(rect.get_x() + rect.get_width() / 2, h),
                            xytext=(0, 2), textcoords="offset points",
                            ha='center', va='bottom', fontsize=6.0, fontweight='bold', rotation=90)

    ax.set_ylabel("Total Actions / Interventions Applied", fontsize=12, fontweight="bold")
    ax.set_title("Dispatcher Action Intensity & Churn Analysis Across All 7 Days", fontsize=13, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(DAYS, fontsize=11, fontweight="semibold")
    ax.legend(loc="upper right", frameon=True, fontsize=9.0, ncol=2)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    chart4_path = os.path.join(output_dir, "weekly_7day_actions_taken.png")
    plt.savefig(chart4_path)
    plt.close()
    print(f"[✓] Saved 7-day actions chart: {chart4_path}")

    # -------------------------------------------------------------
    # 5. 24-Hour Diurnal Hourly Profile (Monday Surge vs Saturday Leisure)
    # -------------------------------------------------------------
    has_hourly = any("hourly_delays" in item and item["hourly_delays"] for item in data)
    if has_hourly:
        fig, (ax_mon, ax_sat) = plt.subplots(1, 2, figsize=(17, 6.0), dpi=160)
        hours = np.arange(24)

        for disp in active_dispatchers:
            mon_item = day_map["Mon"].get(disp, {})
            sat_item = day_map["Sat"].get(disp, {})
            if "hourly_delays" in mon_item and mon_item["hourly_delays"]:
                ax_mon.plot(hours, mon_item["hourly_delays"], label=DISPLAY_NAMES.get(disp, disp),
                            color=COLORS.get(disp, "#7f8c8d"), linewidth=2.0, marker='o', markersize=3.0)
            if "hourly_delays" in sat_item and sat_item["hourly_delays"]:
                ax_sat.plot(hours, sat_item["hourly_delays"], label=DISPLAY_NAMES.get(disp, disp),
                            color=COLORS.get(disp, "#7f8c8d"), linewidth=2.0, marker='o', markersize=3.0)

        ax_mon.set_xlabel("Hour of the Day (00:00 - 24:00)", fontsize=10, fontweight="bold")
        ax_mon.set_ylabel("Mean Delay (seconds)", fontsize=10, fontweight="bold")
        ax_mon.set_title("Monday Commuter Surge: 24-Hour Hourly Delay Progression", fontsize=11, fontweight="bold")
        ax_mon.set_xticks(range(0, 24, 2))
        ax_mon.grid(True, linestyle="--", alpha=0.5)
        ax_mon.legend(loc="upper right", frameon=True, fontsize=8.0)

        ax_sat.set_xlabel("Hour of the Day (00:00 - 24:00)", fontsize=10, fontweight="bold")
        ax_sat.set_ylabel("Mean Delay (seconds)", fontsize=10, fontweight="bold")
        ax_sat.set_title("Saturday Leisure Base: 24-Hour Hourly Delay Progression", fontsize=11, fontweight="bold")
        ax_sat.set_xticks(range(0, 24, 2))
        ax_sat.grid(True, linestyle="--", alpha=0.5)
        ax_sat.legend(loc="upper right", frameon=True, fontsize=8.0)

        plt.tight_layout()
        chart5_path = os.path.join(output_dir, "weekly_24h_diurnal_timeline.png")
        plt.savefig(chart5_path)
        plt.close()
        print(f"[✓] Saved 24h diurnal timeline: {chart5_path}")

    # -------------------------------------------------------------
    # 6. Action-Efficiency Trade-off (Mean Delay vs Actions)
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(11, 7), dpi=160)

    label_offsets = {
        "Static_Baseline": (14, -6),
        "Comm_MAPPO": (14, 4),
        "Centralized_PPO": (14, 6),
        "Multi_Train_Centralized_PPO": (14, 8),
        "FIFO_Heuristic": (-130, 16),
        "Priority_Greedy_Heuristic": (-80, -28),
        "Hierarchical_Hybrid": (14, 12),
        "Decentralized_MAPPO": (-150, -18)
    }

    for disp in active_dispatchers:
        items = [day_map[d].get(disp, {}) for d in DAYS if disp in day_map[d]]
        if not items:
            continue
        avg_delay = np.mean([it.get("mean_delay_sec", 0.0) for it in items])
        total_actions = sum(it.get("actions_taken", 0) for it in items)
        avg_punc = np.mean([it.get("punctuality_pct", 100.0) for it in items])

        ax.scatter(total_actions, avg_delay, s=200, color=COLORS.get(disp, "#7f8c8d"),
                   edgecolors="black", linewidth=1.2, alpha=0.92, zorder=5)

        offset_xy = label_offsets.get(disp, (10, 8))
        ax.annotate(
            f"{DISPLAY_NAMES.get(disp, disp)}\n({avg_delay:.1f}s, {int(total_actions)} acts, {avg_punc:.1f}%)",
            xy=(total_actions, avg_delay),
            xytext=offset_xy,
            textcoords="offset points",
            fontsize=8.5,
            fontweight="semibold",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#bdc3c7", alpha=0.8)
        )

    ax.set_xlabel("Weekly Dispatcher Actions Taken (Interventions)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Weekly Average Mean Delay per Consist (seconds)", fontsize=11, fontweight="bold")
    ax.set_title("Dispatcher Action-Efficiency Trade-off: Delay vs Intervention Intensity", fontsize=12, fontweight="bold", pad=12)
    ax.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    chart6_path = os.path.join(output_dir, "model_efficiency_tradeoff.png")
    plt.savefig(chart6_path)
    plt.close()
    print(f"[✓] Saved efficiency tradeoff chart: {chart6_path}")


def main():
    parser = argparse.ArgumentParser(description="Plot weekly 24-hour audit charts for all dispatchers")
    parser.add_argument("--json", type=str, default="dispatcher/logs/evaluations/weekly_audits/cross_comparison_24h.json",
                        help="Path to cross_comparison_24h.json")
    parser.add_argument("--output-dir", type=str, default="dispatcher/logs/visual_proofs",
                        help="Directory to save charts")
    args = parser.parse_args()

    plot_weekly_charts(args.json, args.output_dir)


if __name__ == "__main__":
    main()
