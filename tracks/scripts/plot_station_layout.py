import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EDG_FILE = os.path.join(SCRIPT_DIR, '..', 'network_data', 'dense_network.edg.xml')
NOD_FILE = os.path.join(SCRIPT_DIR, '..', 'network_data', 'dense_network.nod.xml')
ADD_FILE = os.path.join(SCRIPT_DIR, '..', 'network_data', 'dense_network.add.xml')
OUTPUT_IMG = os.path.join(SCRIPT_DIR, 'station_4track_layout.png')

tree = ET.parse(EDG_FILE)
root = tree.getroot()

fig, ax = plt.subplots(figsize=(14, 6), dpi=200)
fig.patch.set_facecolor('#090d16')
ax.set_facecolor('#0b1120')

# We focus on Town_1 (centered at x=-8800, y=1800, angle=8.0 deg)
target_stn = 'Town_1'

for edge in root.findall('edge'):
    eid = edge.get('id', '')
    if target_stn not in eid and 'c1_' not in eid: continue
    shape = edge.get('shape')
    if not shape: continue
    pts = [list(map(float, p.split(','))) for p in shape.split()]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    
    # Check if edge is in vicinity of Town_1 (-9600 to -8000, 1600 to 2000)
    if any(-9600 <= p[0] <= -8000 and 1500 <= p[1] <= 2100 for p in pts):
        if f'{target_stn}_thru' in eid:
            color = '#00f0ff' # bright cyan through tracks
            lw = 2.8
            label = 'Center Express Through-Tracks (300 km/h, No Stop)' if eid == f'{target_stn}_thru_1_fw' else None
        elif f'{target_stn}_plat' in eid:
            color = '#facc15' # yellow platform loops
            lw = 2.8
            label = 'Outer Platform Loops (50 km/h, Passenger Stops)' if eid == f'{target_stn}_plat_1_fw' else None
        elif f'{target_stn}_yard' in eid:
            color = '#fb923c' # orange siding
            lw = 2.0
            label = 'Service / Freight Siding (20 km/h)' if eid == f'{target_stn}_yard_1_fw' else None
        elif 'c1_' in eid:
            color = '#38bdf8' # approach mainline
            lw = 1.6
            alpha = 0.7
            label = 'High-Speed Approach Mainline (300 km/h)' if 'Town_1_fw_b2' in eid or 'City_2_fw_b0' in eid else None
        else:
            continue
        ax.plot(xs, ys, color=color, linewidth=lw, alpha=0.95, label=label)

# Throat nodes
nod_tree = ET.parse(NOD_FILE)
for node in nod_tree.findall('node'):
    nid = node.get('id', '')
    if target_stn in nid and 'Throat' in nid:
        x, y = float(node.get('x')), float(node.get('y'))
        ax.scatter([x], [y], color='#f43f5e', s=50, zorder=5)
        offset_y = 35 if 'Throat1' in nid else -40
        ax.text(x, y + offset_y, f'{nid}\n(Interlocking Switch)', color='#ffffff', fontsize=8, fontweight='bold', ha='center', va='center', zorder=6,
                 bbox=dict(boxstyle='round,pad=0.25', facecolor='#1e293b', edgecolor='#f43f5e', alpha=0.9))

# Station center label
ax.text(-8800, 1800 + 45, f'{target_stn} Station Center\n(4-Track High-Speed Layout)', color='#ffffff', fontsize=9, fontweight='bold', ha='center', va='center', zorder=6,
        bbox=dict(boxstyle='round,pad=0.3', facecolor='#0f172a', edgecolor='#38bdf8', alpha=0.9))

ax.set_xlim(-9400, -8200)
ax.set_ylim(1680, 1920)
ax.set_title(f'Modern 4-Track Station Layout ({target_stn}): Center 300 km/h Through-Tracks + Platform Loops', color='#f8fafc', fontsize=12, pad=12)
ax.set_xlabel('X Coordinate [m]', color='#94a3b8', fontsize=9)
ax.set_ylabel('Y Coordinate [m]', color='#94a3b8', fontsize=9)
ax.grid(True, color='#1e293b', linestyle='--', alpha=0.6)
ax.tick_params(colors='#64748b', labelsize=8)
for spine in ax.spines.values(): spine.set_color('#334155')
ax.legend(loc='lower right', facecolor='#1e293b', edgecolor='#475569', labelcolor='#ffffff', fontsize=8)

plt.subplots_adjust(left=0.07, right=0.96, top=0.92, bottom=0.12)
plt.savefig(OUTPUT_IMG, facecolor='#090d16', edgecolor='none')
plt.close()
print(f'Successfully rendered 4-track station layout to: {OUTPUT_IMG}')
