import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(SCRIPT_DIR, '..', 'network_data', 'dense_network.net.xml')
OUTPUT_IMG = os.path.join(SCRIPT_DIR, 'current_network_preview.png')

tree = ET.parse(NET_FILE)
root = tree.getroot()

fig, ax = plt.subplots(figsize=(16, 16), dpi=200)
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
        
        if 'thru' in eid:
            color = '#00f0ff' # bright cyan express through-track
            lw = 2.2
            alpha = 1.0
        elif 'plat' in eid:
            color = '#facc15' # yellow station platform loop
            lw = 2.4
            alpha = 1.0
        elif 'yard' in eid:
            color = '#fb923c' # orange yard siding
            lw = 1.8
            alpha = 0.9
        elif 'c1_' in eid or 'bypass' in eid:
            color = '#38bdf8' # cyan high speed trunk
            lw = 1.6
            alpha = 0.85
        elif 'c2_' in eid or 'c3_' in eid:
            color = '#4ade80' # green regional trunk
            lw = 1.4
            alpha = 0.85
        else:
            color = '#c084fc' # purple loop / depot spurs
            lw = 1.2
            alpha = 0.8
            
        ax.plot(xs, ys, color=color, linewidth=lw, alpha=alpha)

# Plot junction nodes & labels
for n in root.findall('junction'):
    jid = n.get('id', '')
    if 'Throat' in jid or ('City' in jid and 'signal' not in jid and ':' not in jid) or ('Town' in jid and 'signal' not in jid and ':' not in jid) or ('Depot' in jid and 'signal' not in jid and ':' not in jid):
        x, y = float(n.get('x')), float(n.get('y'))
        if 'Throat1' in jid:
            stn_name = jid.replace('_Throat1', '')
            ax.scatter([x], [y], color='#f43f5e', s=25, zorder=5)
            ax.text(x, y + 250, stn_name, color='#ffffff', fontsize=8, fontweight='bold', ha='center', va='bottom', zorder=6,
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#1e293b', edgecolor='#475569', alpha=0.85))

ax.set_title('Current Railway Network Topology & Geometry', color='#f8fafc', fontsize=16, pad=15)
ax.set_aspect('equal', 'box')
ax.grid(True, color='#1e293b', linestyle='--', alpha=0.6)
ax.tick_params(colors='#64748b', labelsize=8)
for spine in ax.spines.values(): spine.set_color('#334155')

plt.tight_layout()
plt.savefig(OUTPUT_IMG, facecolor='#090d16', edgecolor='none')
print(f'Successfully rendered network to: {OUTPUT_IMG}')
