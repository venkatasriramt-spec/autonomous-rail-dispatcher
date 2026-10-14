import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EDG_FILE = os.path.join(SCRIPT_DIR, '..', 'network_data', 'dense_network.edg.xml')
NOD_FILE = os.path.join(SCRIPT_DIR, '..', 'network_data', 'dense_network.nod.xml')
OUTPUT_IMG = os.path.join(SCRIPT_DIR, 'city3_bilevel_hub.png')

tree = ET.parse(EDG_FILE)
root = tree.getroot()

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 10), dpi=180)
fig.patch.set_facecolor('#090d16')
ax1.set_facecolor('#0b1120')
ax2.set_facecolor('#0b1120')

# 1. 2D Plan View of City_3 Bi-Level Hub
for edge in root.findall('edge'):
    eid = edge.get('id', '')
    shape = edge.get('shape')
    if not shape: continue
    pts = [list(map(float, p.split(','))) for p in shape.split()]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    
    if any(4200 <= p[0] <= 6200 and 500 <= p[1] <= 2500 for p in pts):
        if 'City_3_EW_plat' in eid:
            ax1.plot(xs, ys, color='#38bdf8', linewidth=2.8, alpha=0.95, label='Lower Level Platforms (EW, Z=12m)' if eid == 'City_3_EW_plat_1_fw' else None)
        elif 'City_3_EW_yard' in eid:
            ax1.plot(xs, ys, color='#0284c7', linewidth=1.8, alpha=0.9, label='Lower Level Yard Tracks (EW, Z=12m)' if eid == 'City_3_EW_yard_5_fw' else None)
        elif 'City_3_NS_plat' in eid:
            ax1.plot(xs, ys, color='#f43f5e', linewidth=2.8, alpha=0.95, label='Upper Viaduct Platforms (NS, Z=26m)' if eid == 'City_3_NS_plat_1_fw' else None)
        elif 'City_3_NS_yard' in eid:
            ax1.plot(xs, ys, color='#e11d48', linewidth=1.8, alpha=0.9, label='Upper Viaduct Yard Track (NS, Z=26m)' if eid == 'City_3_NS_yard_5_fw' else None)
        elif 'transfer_City_3_EW_NS' in eid:
            ax1.plot(xs, ys, color='#facc15', linewidth=2.2, linestyle='-', alpha=0.95, label='Flyover Connector Ramp (12m -> 26m)' if eid == 'transfer_City_3_EW_NS_fw' else None)
        elif 'c1_' in eid or 'spur_' in eid:
            ax1.plot(xs, ys, color='#60a5fa', linewidth=1.2, alpha=0.6)
        elif 'c2_' in eid:
            ax1.plot(xs, ys, color='#fb7185', linewidth=1.2, alpha=0.6)

# Main throat markers
nod_tree = ET.parse(NOD_FILE)
for node in nod_tree.findall('node'):
    nid = node.get('id', '')
    if nid in ['City_3_EW_Throat1', 'City_3_EW_Throat2', 'City_3_NS_Throat1', 'City_3_NS_Throat2']:
        x, y = float(node.get('x')), float(node.get('y'))
        z = float(node.get('z', 0))
        color = '#38bdf8' if 'EW' in nid else '#f43f5e'
        ax1.scatter([x], [y], color=color, s=45, zorder=5)
        offset_y = 50 if 'Throat1' in nid else -65
        ax1.text(x, y + offset_y, f'{nid} (Z={z:.0f}m)', color='#ffffff', fontsize=7.5, fontweight='bold', ha='center', va='center', zorder=6,
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='#1e293b', edgecolor=color, alpha=0.9))

ax1.set_xlim(4300, 6100)
ax1.set_ylim(600, 2400)
ax1.set_title('City_3 Bi-Level Hub: Plan View (Grade-Separated Crossing & Flyover Ramp)', color='#f8fafc', fontsize=12, pad=10)
ax1.set_xlabel('X Coordinate [m]', color='#94a3b8', fontsize=9)
ax1.set_ylabel('Y Coordinate [m]', color='#94a3b8', fontsize=9)
ax1.grid(True, color='#1e293b', linestyle='--', alpha=0.6)
ax1.tick_params(colors='#64748b', labelsize=8)
for spine in ax1.spines.values(): spine.set_color('#334155')
ax1.legend(loc='lower left', facecolor='#1e293b', edgecolor='#475569', labelcolor='#ffffff', fontsize=7.5)

# 2. Elevation Profile
c1_pts = []
for eid in ['c1_Town_2_City_3_EW_fw_b0', 'c1_Town_2_City_3_EW_fw_b1', 'c1_Town_2_City_3_EW_fw_b2', 'City_3_EW_plat_1_fw', 'c1_City_3_EW_Town_3_fw_b0', 'c1_City_3_EW_Town_3_fw_b1', 'c1_City_3_EW_Town_3_fw_b2']:
    e = root.find(f".//edge[@id='{eid}']")
    if e is not None and e.get('shape'):
        pts = [list(map(float, p.split(','))) for p in e.get('shape').split()]
        c1_pts.extend(pts)

c2_pts = []
for eid in ['c2_Town_5_City_3_NS_fw_b0', 'c2_Town_5_City_3_NS_fw_b1', 'City_3_NS_plat_1_fw', 'c2_City_3_NS_Town_6_fw_b0', 'c2_City_3_NS_Town_6_fw_b1']:
    e = root.find(f".//edge[@id='{eid}']")
    if e is not None and e.get('shape'):
        pts = [list(map(float, p.split(','))) for p in e.get('shape').split()]
        c2_pts.extend(pts)

ramp_e = root.find(".//edge[@id='transfer_City_3_EW_NS_fw']")
ramp_pts = [list(map(float, p.split(','))) for p in ramp_e.get('shape').split()] if ramp_e is not None else []

if c1_pts:
    c1_x = [p[0] for p in c1_pts]
    c1_z = [p[2] for p in c1_pts]
    ax2.plot(c1_x, c1_z, color='#38bdf8', linewidth=2.5, label='East-West Trunk (Lower Level, Z=12m)')

if c2_pts:
    c2_x = [p[0] for p in c2_pts]
    c2_z = [p[2] for p in c2_pts]
    ax2.plot(c2_x, c2_z, color='#f43f5e', linewidth=2.5, label='North-South Viaduct (Upper Level, Z=26m)')

if ramp_pts:
    ramp_x = [p[0] for p in ramp_pts]
    ramp_z = [p[2] for p in ramp_pts]
    ax2.plot(ramp_x, ramp_z, color='#facc15', linewidth=2.2, linestyle='--', label='Flyover Ramp (12m -> 26m, 1.77% Grade)')

ax2.annotate('14.0m Vertical Clearance\n(Grade-Separated Crossing)', xy=(5225, 19), xytext=(5420, 21),
             color='#a78bfa', fontsize=9, fontweight='bold',
             arrowprops=dict(arrowstyle='<->', color='#a78bfa', lw=1.6),
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#1e293b', edgecolor='#7c3aed', alpha=0.9))

ax2.set_xlim(4300, 6100)
ax2.set_ylim(0, 36)
ax2.set_title('Cross-Section Elevation Profile (Z Coordinate [m])', color='#f8fafc', fontsize=12, pad=10)
ax2.set_xlabel('X Coordinate [m]', color='#94a3b8', fontsize=9)
ax2.set_ylabel('Elevation Z [m]', color='#94a3b8', fontsize=9)
ax2.grid(True, color='#1e293b', linestyle='--', alpha=0.6)
ax2.tick_params(colors='#64748b', labelsize=8)
for spine in ax2.spines.values(): spine.set_color('#334155')
ax2.legend(loc='lower left', facecolor='#1e293b', edgecolor='#475569', labelcolor='#ffffff', fontsize=8)

plt.tight_layout()
plt.savefig(OUTPUT_IMG, facecolor='#090d16', edgecolor='none')
plt.close()
print(f'Successfully rendered City_3 Bi-Level Hub visualization to: {OUTPUT_IMG}')
