import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import os
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(SCRIPT_DIR, '..', 'network_data', 'dense_network.net.xml')
OUTPUT_IMG = os.path.join(SCRIPT_DIR, 'alpine_passing_loop.png')

tree = ET.parse(NET_FILE)
root = tree.getroot()

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), dpi=200, gridspec_kw={'height_ratios': [2.5, 1]})
fig.patch.set_facecolor('#090d16')
ax1.set_facecolor('#090d16')
ax2.set_facecolor('#090d16')

# 1. 2D Plan View
for edge in root.findall('edge'):
    if edge.get('function') == 'internal': continue
    eid = edge.get('id', '')
    if 'c3_Town_8_Town_9' not in eid: continue
    
    for lane in edge.findall('lane'):
        shape = lane.get('shape')
        if not shape: continue
        pts = [list(map(float, p.split(','))) for p in shape.split()]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        
        if 'siding' in eid or 'lead' in eid:
            color = '#a3e635'  # Electric lime for freight passing loop siding
            lw = 3.5
            ls = '-'
            label = 'Freight Passing Siding (60 km/h, 12,000 t)' if 'siding_fw' in eid else ""
            zorder = 5
        elif 'T1' in eid:
            color = '#38bdf8'  # Bright Sky Blue for Track 1 mainline
            lw = 2.2
            ls = '-'
            label = 'Mainline Track 1 (Uphill, 120 km/h)' if 'T1_mid_fw' in eid else ""
            zorder = 3
        elif 'T2' in eid:
            color = '#f59e0b'  # Amber for Track 2 mainline
            lw = 2.2
            ls = '-'
            label = 'Mainline Track 2 (Downhill, 120 km/h)' if 'T2_fw_b0' in eid else ""
            zorder = 3
        else:
            color = '#94a3b8'
            lw = 1.5
            ls = ':'
            label = ""
            zorder = 2
            
        ax1.plot(xs, ys, color=color, linewidth=lw, linestyle=ls, label=label if label else None, zorder=zorder)

# Plot Junctions and Signals in Loop Area
for junction in root.findall('junction'):
    jid = junction.get('id', '')
    if 'c3_Town_8_Town_9' not in jid and jid not in ['Town_8_Throat2', 'Town_9_Throat1']: continue
    x, y = float(junction.get('x')), float(junction.get('y'))
    
    if 'swA' in jid or 'swB' in jid:
        ax1.scatter([x], [y], color='#ec4899', s=90, marker='D', edgecolor='#ffffff', linewidth=1.5, zorder=6)
        label_text = "Entry Turnout (swA)\nR=1,000m / 60 km/h" if 'swA' in jid else "Exit Turnout (swB)\nR=1,000m / 60 km/h"
        ax1.annotate(label_text, (x, y), textcoords="offset points", xytext=(-20, 25 if 'swA' in jid else -35),
                     fontsize=9, fontweight='bold', color='#fbcfe8',
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='#831843', edgecolor='#f472b6', alpha=0.9),
                     arrowprops=dict(arrowstyle="->", color='#f472b6', lw=1.2), zorder=7)
    elif 'sid_' in jid:
        ax1.scatter([x], [y], color='#a3e635', s=60, marker='o', edgecolor='#ffffff', linewidth=1.2, zorder=6)
        lbl = "Siding Signal A" if 'sid_A' in jid else "Siding Signal B"
        ax1.text(x - 40, y + 25, lbl, fontsize=8, color='#d9f99d', fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='#14532d', edgecolor='#84cc16', alpha=0.85), zorder=7)
    elif 'sig' in jid:
        ax1.scatter([x], [y], color='#06b6d4', s=35, marker='s', edgecolor='#ffffff', linewidth=1, zorder=5)

ax1.set_title('Corridor 3: Alpine Freight Passing Loop (Überholgleis) [1,200m Siding, 16.67 m/s, 12,000t Capacity]',
              color='#f8fafc', fontsize=13, fontweight='bold', pad=12)
ax1.set_xlabel('X Coordinate (m)', color='#94a3b8', fontsize=9)
ax1.set_ylabel('Y Coordinate (m)', color='#94a3b8', fontsize=9)
ax1.grid(True, color='#1e293b', linestyle='--', alpha=0.7)
ax1.tick_params(colors='#64748b', labelsize=8)
for spine in ax1.spines.values(): spine.set_color('#334155')
ax1.legend(loc='lower right', facecolor='#0f172a', edgecolor='#334155', labelcolor='#e2e8f0', fontsize=9)

# 2. Elevation Gradient Profile
# Town 8 (z=80m) to Town 9 (z=130m)
s_vals = np.linspace(0, 4242, 200) # hypot(-7500 - (-10500), 5200 - 8200) = sqrt(3000^2 + 3000^2) = 4242.6m
z_vals = 80.0 + (130.0 - 80.0) * (s_vals / 4242.0)

ax2.plot(s_vals, z_vals, color='#38bdf8', lw=2.5, label='Mainline Grade (+11.8‰ / 1.18%)')
# Passing loop section: s_mid = 2121m, L_loop = 1200m -> [1521m, 2721m]
s_loop_start = 2121.0 - 600.0
s_loop_end = 2121.0 + 600.0
ax2.axvspan(s_loop_start, s_loop_end, color='#a3e635', alpha=0.15, label='1,200m Freight Passing Loop Envelope')
ax2.scatter([s_loop_start, s_loop_end], [80.0 + 50.0*(s_loop_start/4242.0), 80.0 + 50.0*(s_loop_end/4242.0)],
            color='#ec4899', s=70, marker='D', zorder=5)

ax2.set_title('Mountain Grade Profile: Town_8 (El. 80m) → Überholgleis → Town_9 (El. 130m)',
              color='#f8fafc', fontsize=11, fontweight='bold', pad=8)
ax2.set_xlabel('Chainage along Corridor (m)', color='#94a3b8', fontsize=9)
ax2.set_ylabel('Elevation Z (m)', color='#94a3b8', fontsize=9)
ax2.grid(True, color='#1e293b', linestyle='--', alpha=0.7)
ax2.tick_params(colors='#64748b', labelsize=8)
for spine in ax2.spines.values(): spine.set_color('#334155')
ax2.legend(loc='upper left', facecolor='#0f172a', edgecolor='#334155', labelcolor='#e2e8f0', fontsize=8)

plt.tight_layout()
plt.savefig(OUTPUT_IMG, facecolor='#090d16', edgecolor='none')
print(f"Alpine passing loop rendering saved to {OUTPUT_IMG}")
