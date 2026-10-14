"""
visualizer.py
Generates publication-quality charts and plots comparing AI Dispatcher vs Baselines
for reports and the final project review.
"""

import os
import json
import argparse
import matplotlib.pyplot as plt
import numpy as np


def plot_benchmark_charts(
    json_path: str,
    output_dir: str = "dispatcher/logs"
):
    """
    Plots comparative delay, punctuality, and timeline charts from benchmark JSON.
    """
    if not os.path.exists(json_path):
        print(f"[!] Results JSON not found: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    dispatchers = list(data.keys())
    mean_delays = [data[d]["mean_delay_sec"] for d in dispatchers]
    max_delays = [data[d]["max_delay_sec"] for d in dispatchers]
    punctualities = [data[d]["punctuality_pct"] for d in dispatchers]
    knock_ons = [data[d]["knock_on_events"] for d in dispatchers]

    # Clean display names
    clean_names = [d.replace("_", " ") for d in dispatchers]
    colors = ["#e74c3c", "#f39c12", "#3498db", "#2ecc71"][:len(dispatchers)]

    # -------------------------------------------------------------
    # 1. Bar Chart: Mean & Max Delay Comparison
    # -------------------------------------------------------------
    fig, ax1 = plt.subplots(figsize=(10, 5.5), dpi=150)
    x = np.arange(len(dispatchers))
    width = 0.35

    rects1 = ax1.bar(x - width/2, mean_delays, width, label='Mean Delay (s)', color=colors, alpha=0.85)
    rects2 = ax1.bar(x + width/2, max_delays, width, label='Max Delay (s)', color=colors, alpha=0.4, hatch="//")

    ax1.set_ylabel('Delay (seconds)', fontsize=12, fontweight='bold')
    ax1.set_title('Railway Dispatcher Performance Under Disruption (Delay Comparison)', fontsize=14, fontweight='bold', pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels(clean_names, fontsize=11, fontweight='semibold')
    ax1.legend(loc='upper right', frameon=True)
    ax1.grid(axis='y', linestyle='--', alpha=0.5)

    # Value labels
    for rect in rects1:
        height = rect.get_height()
        ax1.annotate(f'{height:.1f}s',
                     xy=(rect.get_x() + rect.get_width() / 2, height),
                     xytext=(0, 3), textcoords="offset points",
                     ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()
    bar_path = os.path.join(output_dir, "benchmark_delay_comparison.png")
    plt.savefig(bar_path)
    plt.close()
    print(f"[✓] Saved delay comparison chart: {bar_path}")

    # -------------------------------------------------------------
    # 2. Punctuality & Knock-On Delays
    # -------------------------------------------------------------
    fig, (ax_punc, ax_ko) = plt.subplots(1, 2, figsize=(12, 5), dpi=150)

    # Punctuality
    punc_bars = ax_punc.bar(clean_names, punctualities, color=colors, alpha=0.85, width=0.5)
    ax_punc.set_ylabel('Punctuality Rate (%)', fontsize=11, fontweight='bold')
    ax_punc.set_title('Schedule Punctuality (Arrival <= 3 min)', fontsize=12, fontweight='bold')
    ax_punc.set_ylim(0, 105)
    ax_punc.grid(axis='y', linestyle='--', alpha=0.5)
    for rect in punc_bars:
        h = rect.get_height()
        ax_punc.annotate(f'{h:.1f}%',
                         xy=(rect.get_x() + rect.get_width() / 2, h),
                         xytext=(0, 3), textcoords="offset points",
                         ha='center', va='bottom', fontsize=10, fontweight='bold')

    # Knock-On Delays
    ko_bars = ax_ko.bar(clean_names, knock_ons, color=colors, alpha=0.85, width=0.5)
    ax_ko.set_ylabel('Secondary Conflict Events', fontsize=11, fontweight='bold')
    ax_ko.set_title('Cascading Knock-On Delays Prevented', fontsize=12, fontweight='bold')
    ax_ko.grid(axis='y', linestyle='--', alpha=0.5)
    for rect in ko_bars:
        h = rect.get_height()
        ax_ko.annotate(f'{int(h)}',
                       xy=(rect.get_x() + rect.get_width() / 2, h),
                       xytext=(0, 3), textcoords="offset points",
                       ha='center', va='bottom', fontsize=10, fontweight='bold')

    plt.tight_layout()
    kpi_path = os.path.join(output_dir, "benchmark_punctuality_knockon.png")
    plt.savefig(kpi_path)
    plt.close()
    print(f"[✓] Saved punctuality/knock-on chart: {kpi_path}")

    # -------------------------------------------------------------
    # 3. Dynamic Delay Timeline Progression
    # -------------------------------------------------------------
    has_history = any("delay_history" in data[d] and data[d]["delay_history"] for d in dispatchers)
    if has_history:
        fig, ax = plt.subplots(figsize=(11, 5.5), dpi=150)
        for idx, d in enumerate(dispatchers):
            hist = data[d].get("delay_history", [])
            if hist:
                timeline_mins = np.arange(len(hist)) * 15.0 / 60.0  # 15s step converted to minutes
                ax.plot(timeline_mins, hist, label=clean_names[idx], color=colors[idx], linewidth=2.2)

        ax.set_xlabel('Simulation Elapsed Time (minutes)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Mean Fleet Delay (seconds)', fontsize=11, fontweight='bold')
        ax.set_title('Real-Time Delay Propagation & Recovery Dynamics Under Disruption', fontsize=13, fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend(loc='upper right', frameon=True, fontsize=10)

        plt.tight_layout()
        timeline_path = os.path.join(output_dir, "benchmark_delay_timeline.png")
        plt.savefig(timeline_path)
        plt.close()
        print(f"[✓] Saved delay timeline chart: {timeline_path}")


def main():
    parser = argparse.ArgumentParser(description="Plot benchmark evaluation charts")
    parser.add_argument("--json", type=str, default="dispatcher/logs/benchmark_results.json", help="Path to results JSON")
    parser.add_argument("--output-dir", type=str, default="dispatcher/logs", help="Directory to save charts")
    args = parser.parse_args()

    plot_benchmark_charts(args.json, args.output_dir)


if __name__ == "__main__":
    main()
