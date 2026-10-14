import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(SCRIPT_DIR, '..', 'network_data', 'dense_network.net.xml')
OUTPUT_IMG = os.path.join(SCRIPT_DIR, 'current_network_preview.png')

tree = ET.parse(NET_FILE)
root = tree.getroot()

fig, ax = plt.subplots(figsize=(18, 18), dpi=200)
ax.set_facecolor('#090d16')

# Plot edges
for edge in root.findall('edge'):
    if edge.get('function') == 'internal': continue
    eid = edge.get('id', '')
    for lane in edge.findall('lane'):
        shape = lane.get('shape')
        if not shape: continue
        pts = [list(map(float, p.split(','))) for p in shape.split()]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        
        if 'pocket' in eid:
            color = '#f43f5e' # rose terminal pocket track
            lw = 3.2
            alpha = 1.0
            zorder = 5
        elif 'siding' in eid or 'lead' in eid:
            color = '#a3e635' # lime alpine freight passing loop
            lw = 3.2
            alpha = 1.0
            zorder = 5
        elif 'xov1' in eid or 'xov2' in eid:
            color = '#f59e0b' # vibrant amber crossover turnout
            lw = 3.0
            alpha = 1.0
            zorder = 4
        elif 'thru' in eid:
            color = '#00f0ff' # bright cyan express through-track
            lw = 2.2
            alpha = 1.0
            zorder = 3
        elif 'plat' in eid:
            color = '#facc15' # yellow station platform loop
            lw = 2.4
            alpha = 1.0
            zorder = 3
        elif 'yard' in eid:
            color = '#fb923c' # orange yard siding
            lw = 1.8
            alpha = 0.9
            zorder = 2
        elif 'c1_' in eid or 'bypass' in eid:
            color = '#38bdf8' # cyan high speed trunk
            lw = 1.6
            alpha = 0.85
            zorder = 2
        elif 'c2_' in eid or 'c3_' in eid:
            color = '#4ade80' # green regional trunk
            lw = 1.4
            alpha = 0.85
            zorder = 2
        else:
            color = '#c084fc' # purple transfer / depot spurs
            lw = 1.2
            alpha = 0.8
            zorder = 2
            
        ax.plot(xs, ys, color=color, linewidth=lw, alpha=alpha, zorder=zorder)

# Plot junction nodes & labels
for n in root.findall('junction'):
    jid = n.get('id', '')
    x, y = float(n.get('x')), float(n.get('y'))
    if 'buf' in jid:
        ax.scatter([x], [y], color='#e11d48', s=45, marker='s', edgecolor='#ffffff', linewidth=1, zorder=6)
    elif 'swA' in jid or 'swB' in jid:
        ax.scatter([x], [y], color='#ec4899', s=55, marker='D', edgecolor='#ffffff', linewidth=1.2, zorder=6)
    elif 'xov' in jid and ('1A' in jid or '2B' in jid or '2C' in jid or '1D' in jid):
        ax.scatter([x], [y], color='#f59e0b', s=25, marker='D', zorder=5)
    elif 'Throat' in jid or ('City' in jid and 'signal' not in jid and ':' not in jid) or ('Town' in jid and 'signal' not in jid and ':' not in jid) or ('Depot' in jid and 'signal' not in jid and ':' not in jid):
        if 'Throat1' in jid:
            stn_name = jid.replace('_Throat1', '')
            ax.scatter([x], [y], color='#f43f5e', s=35, zorder=5)
            ax.text(x, y + 250, stn_name, color='#ffffff', fontsize=8, fontweight='bold', ha='center', va='bottom', zorder=6,
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#1e293b', edgecolor='#475569', alpha=0.85))

# Legend
legend_elements = [
    Line2D([0], [0], color='#38bdf8', lw=2, label='High-Speed Mainline (300 km/h)'),
    Line2D([0], [0], color='#4ade80', lw=2, label='Regional Mainline (120 km/h)'),
    Line2D([0], [0], color='#00f0ff', lw=2.5, label='Station Express Through-Tracks (300/120 km/h)'),
    Line2D([0], [0], color='#facc15', lw=2.5, label='Station Platform Tracks (Platform Edge)'),
    Line2D([0], [0], color='#fb923c', lw=2, label='Freight Yard Sidings & Depot Loops'),
    Line2D([0], [0], color='#f59e0b', lw=3, label='Universal Crossover Interlockings (100 km/h)'),
    Line2D([0], [0], color='#a3e635', lw=3, label='Alpine Freight Passing Loop (Überholgleis, 60 km/h)'),
    Line2D([0], [0], color='#f43f5e', lw=3, label='Terminal Turn-Around Pocket Tracks (50 km/h)'),
    Line2D([0], [0], marker='s', color='w', markerfacecolor='#e11d48', markersize=8, label='Dead-End Buffer Stops (Kopfmachen)', linestyle='None'),
    Line2D([0], [0], color='#c084fc', lw=1.5, label='Logistics Depot Spurs & Hub Transfer'),
]
ax.legend(handles=legend_elements, loc='upper left', facecolor='#0f172a', edgecolor='#334155',
          labelcolor='#e2e8f0', fontsize=9, framealpha=0.9)

ax.set_title('Complete Realistic Railway Network Infrastructure\n[Graduated Block Signaling | Universal Crossovers | Alpine Überholgleis | Terminal Buffer Stops]',
             color='#f8fafc', fontsize=15, fontweight='bold', pad=15)
ax.set_aspect('equal', 'box')
ax.grid(True, color='#1e293b', linestyle='--', alpha=0.6)
ax.tick_params(colors='#64748b', labelsize=8)
for spine in ax.spines.values(): spine.set_color('#334155')

plt.tight_layout()
plt.savefig(OUTPUT_IMG, facecolor='#090d16', edgecolor='none')
print(f'Successfully rendered network to: {OUTPUT_IMG}')
