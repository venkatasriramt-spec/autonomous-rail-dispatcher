"""
visualize_marl.py
Generates a comprehensive 4-panel comparison visualization for Frontier 3:
Multi-Agent Reinforcement Learning (MARL / MAPPO) vs Centralized PPO & Baselines.

Metrics visualized:
1. Mean Network Delay (seconds)
2. Peak / Max Network Delay (seconds)
3. Dispatcher Action Interventions (Decentralized Interlockings vs Centralized Bottleneck)
4. Telemetry Transmission Bandwidth (KB)
"""

import os
import json
import matplotlib.pyplot as plt
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JSON_PATH = os.path.join(ROOT_DIR, "dispatcher", "logs", "evaluations", "marl_audits", "marl_vs_centralized_benchmark.json")
OUTPUT_DIR = os.path.join(ROOT_DIR, "dispatcher", "logs", "visual_proofs")
OUTPUT_IMAGE = os.path.join(OUTPUT_DIR, "marl_vs_centralized_comparison.png")

COLORS = {
    "Static_Baseline": "#e74c3c",                # Crimson
    "FIFO_Heuristic": "#f39c12",                 # Amber
    "Centralized_PPO": "#3498db",                # Sky Blue
    "Decentralized_MAPPO": "#2ecc71",             # Emerald Green
    "Decentralized_MAPPO_Untrained": "#2ecc71"   # Emerald Green
}

LABELS = {
    "Static_Baseline": "Static (Default)",
    "FIFO_Heuristic": "FIFO Heuristic",
    "Centralized_PPO": "Centralized PPO\n(Monolithic Agent)",
    "Decentralized_MAPPO": "Decentralized MAPPO\n(7 Interlocking Agents)",
    "Decentralized_MAPPO_Untrained": "Decentralized MAPPO\n(7 Agents, Untrained)"
}


def main():
    if not os.path.exists(JSON_PATH):
        print(f"[!] Benchmark file not found: {JSON_PATH}")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Reorder models for logical progression
    order = ["Static_Baseline", "FIFO_Heuristic", "Centralized_PPO", "Decentralized_MAPPO", "Decentralized_MAPPO_Untrained"]
    entry_map = {item["model"]: item for item in data}
    records = [entry_map[m] for m in order if m in entry_map]


    models = [r["model"] for r in records]
    labels = [LABELS.get(m, m) for m in models]
    colors = [COLORS.get(m, "#95a5a6") for m in models]

    mean_delays = [r["mean_delay_sec"] for r in records]
    max_delays = [r["max_delay_sec"] for r in records]
    actions = [r["actions_taken"] for r in records]
    bandwidth = [r["telemetry_kb"] for r in records]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Frontier 3: Multi-Agent Reinforcement Learning (MAPPO) vs Centralized Dispatching\nPeak Commuter Horizon (06:00 - 07:00 AM, 240 Steps)", fontsize=15, fontweight="bold", y=0.98)

    x = np.arange(len(models))

    # Panel 1: Mean Network Delay
    ax1 = axes[0, 0]
    bars1 = ax1.bar(x, mean_delays, color=colors, width=0.55, edgecolor="black", linewidth=1.1)
    ax1.set_title("Mean Network Delay (s) - Lower is Better", fontsize=12, fontweight="bold", pad=10)
    ax1.set_ylabel("Seconds per Train", fontsize=11)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=9)
    ax1.grid(axis="y", linestyle="--", alpha=0.6)
    for bar in bars1:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., h + 0.03, f"{h:.2f}s", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax1.set_ylim(0, max(mean_delays) * 1.25)

    # Panel 2: Max Peak Delay
    ax2 = axes[0, 1]
    bars2 = ax2.bar(x, max_delays, color=colors, width=0.55, edgecolor="black", linewidth=1.1)
    ax2.set_title("Peak Max Delay (s) - Lower is Better", fontsize=12, fontweight="bold", pad=10)
    ax2.set_ylabel("Max Delayed Train (s)", fontsize=11)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=9)
    ax2.grid(axis="y", linestyle="--", alpha=0.6)
    for bar in bars2:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., h + 0.5, f"{h:.1f}s", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax2.set_ylim(0, max(max_delays) * 1.25)

    # Panel 3: Action Interventions
    ax3 = axes[1, 0]
    bars3 = ax3.bar(x, actions, color=colors, width=0.55, edgecolor="black", linewidth=1.1)
    ax3.set_title("Intervention Actions Taken (Concurrency Capacity)", fontsize=12, fontweight="bold", pad=10)
    ax3.set_ylabel("Total Control Actions Executed", fontsize=11)
    ax3.set_xticks(x)
    ax3.set_xticklabels(labels, fontsize=9)
    ax3.grid(axis="y", linestyle="--", alpha=0.6)
    for bar in bars3:
        h = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., h + 3.0, f"{int(h)}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax3.set_ylim(0, max(actions) * 1.2)

    # Panel 4: Telemetry Bandwidth
    ax4 = axes[1, 1]
    bars4 = ax4.bar(x, bandwidth, color=colors, width=0.55, edgecolor="black", linewidth=1.1)
    ax4.set_title("State Telemetry Transmitted (KB)", fontsize=12, fontweight="bold", pad=10)
    ax4.set_ylabel("Total Observation Bandwidth (KB)", fontsize=11)
    ax4.set_xticks(x)
    ax4.set_xticklabels(labels, fontsize=9)
    ax4.grid(axis="y", linestyle="--", alpha=0.6)
    for bar in bars4:
        h = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., h + 3.0, f"{h:.1f} KB", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax4.set_ylim(0, max(bandwidth) * 1.2)

    plt.tight_layout()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    plt.savefig(OUTPUT_IMAGE, dpi=200)
    plt.close()
    print(f"[✓] Successfully generated MARL comparison chart: {OUTPUT_IMAGE}")


if __name__ == "__main__":
    main()
