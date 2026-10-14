import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(SCRIPT_DIR, '..', 'network_data', 'dense_network.net.xml')
OUTPUT_IMG = os.path.join(SCRIPT_DIR, 'terminal_pocket_tracks.png')

tree = ET.parse(NET_FILE)
root = tree.getroot()

fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(3, 2, figsize=(16, 20), dpi=200)
fig.patch.set_facecolor('#090d16')
axes = [ax1, ax2, ax3, ax4, ax5, ax6]
for ax in axes: ax.set_facecolor('#090d16')

terminals = [
    ('City_1', ax1, 'City_1: Western High-Speed Terminus (3 Pockets [580m] & 18 Stabling Yards)', -13000, 1000, 800, True),
    ('City_4', ax2, 'City_4: Eastern High-Speed Terminus (2 Pockets [550m] & 6 Stabling Yards)', 14200, 0, 800, False),
    ('City_5', ax3, 'City_5: Northern Regional Terminus (2 Pockets [580m] & 8 Stabling Yards)', 4200, 12500, 800, True),
    ('City_6', ax4, 'City_6: Southern Regional Terminus (2 Pockets [550m] & 4 Stabling Yards)', 6500, -10000, 800, False),
    ('Depot_1', ax5, 'Depot_1: Mountain Alpine Freight Staging (4x 600m Pockets)', -13500, 11200, 700, False),
    ('Depot_4', ax6, 'Depot_4: Electrified High-Speed EMU Depot (4x 600m Pockets)', 6500, 1000, 700, False)
]

for stn_id, ax, title, cx, cy, span, west_throat in terminals:
    all_xs = []
    all_ys = []
    # Edges
    for edge in root.findall('edge'):
        if edge.get('function') == 'internal': continue
        eid = edge.get('id', '')
        if stn_id not in eid: continue
        
        for lane in edge.findall('lane'):
            shape = lane.get('shape')
            if not shape: continue
            pts = [list(map(float, p.split(','))) for p in shape.split()]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            all_xs.extend(xs)
            all_ys.extend(ys)
            
            if 'pocket' in eid:
                color = '#f43f5e'  # Rose red for pocket tail tracks
                lw = 3.2
                label = 'Reversal Pocket Track' if ('pocket_1_fw' in eid) else ""
                zorder = 5
            elif 'plat' in eid:
                color = '#facc15'  # Yellow station platform tracks
                lw = 2.4
                label = 'Platform Track' if ('plat_1_fw' in eid) else ""
                zorder = 4
            elif 'yard' in eid:
                color = '#fb923c'  # Orange yard tracks
                lw = 2.0
                label = 'Staging Yard Track' if ('yard_1_fw' in eid) else ""
                zorder = 3
            else:
                color = '#38bdf8'  # Mainline approach
                lw = 1.8
                label = 'Mainline Throat' if ('c1_' in eid or 'c2_' in eid or 'c3_' in eid) else ""
                zorder = 2
                
            ax.plot(xs, ys, color=color, linewidth=lw, label=label if label else None, zorder=zorder)
            
    # Junctions
    for junction in root.findall('junction'):
        jid = junction.get('id', '')
        if stn_id not in jid: continue
        jx, jy = float(junction.get('x')), float(junction.get('y'))
        all_xs.append(jx)
        all_ys.append(jy)
        
        if 'buf' in jid:
            # Buffer stop dead-end marker
            ax.scatter([jx], [jy], color='#e11d48', s=110, marker='s', edgecolor='#ffffff', linewidth=1.5, zorder=7)
            b_num = jid.split('_')[-1]
            ax.annotate(f"Buffer #{b_num}\n(Reversal Point)", (jx, jy), textcoords="offset points", xytext=(12, -8),
                        fontsize=7.5, fontweight='bold', color='#fecdd3',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='#881337', edgecolor='#f43f5e', alpha=0.9),
                        arrowprops=dict(arrowstyle="->", color='#f43f5e', lw=1), zorder=8)
        elif 'Throat' in jid:
            ax.scatter([jx], [jy], color='#a855f7', s=80, marker='D', edgecolor='#ffffff', linewidth=1.2, zorder=6)
            t_lbl = "Throat 1" if 'Throat1' in jid else "Throat 2"
            ax.text(jx, jy + 25, t_lbl, fontsize=8, color='#e9d5ff', fontweight='bold', ha='center',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#581c87', edgecolor='#a855f7', alpha=0.85), zorder=8)

    ax.set_title(title, color='#f8fafc', fontsize=10, fontweight='bold', pad=8)
    ax.set_xlabel('X Coordinate (m)', color='#94a3b8', fontsize=8)
    ax.set_ylabel('Y Coordinate (m)', color='#94a3b8', fontsize=8)
    if all_xs and all_ys:
        min_x, max_x = min(all_xs), max(all_xs)
        min_y, max_y = min(all_ys), max(all_ys)
        x_pad = max(60.0, (max_x - min_x) * 0.08)
        y_pad = max(60.0, (max_y - min_y) * 0.12)
        ax.set_xlim(min_x - x_pad, max_x + x_pad)
        ax.set_ylim(min_y - y_pad, max_y + y_pad)
    ax.set_aspect('equal', 'box')
    ax.grid(True, color='#1e293b', linestyle='--', alpha=0.7)
    ax.tick_params(colors='#64748b', labelsize=8)
    for spine in ax.spines.values(): spine.set_color('#334155')
    ax.legend(loc='upper left', facecolor='#0f172a', edgecolor='#334155', labelcolor='#e2e8f0', fontsize=7.5)

plt.subplots_adjust(left=0.06, right=0.96, top=0.94, bottom=0.06, hspace=0.3, wspace=0.25)
plt.savefig(OUTPUT_IMG, facecolor='#090d16', edgecolor='none')
print(f"Terminal pocket tracks rendering saved to {OUTPUT_IMG}")
