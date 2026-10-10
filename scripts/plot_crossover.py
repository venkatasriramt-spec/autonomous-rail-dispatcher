import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(SCRIPT_DIR, '..', 'network_data', 'dense_network.net.xml')
OUTPUT_IMG = os.path.join(SCRIPT_DIR, 'crossover_layout.png')

tree = ET.parse(NET_FILE)
root = tree.getroot()

# Target crossover for detailed plot
XOV_PREFIX = "c1_City_2_Town_2_xov"

fig, ax = plt.subplots(figsize=(18, 9), dpi=220)
ax.set_facecolor('#090d16')

# Collect nodes for the crossover
nodes = {}
for n in root.findall('junction'):
    jid = n.get('id', '')
    if XOV_PREFIX in jid:
        nodes[jid] = (float(n.get('x')), float(n.get('y')))

# Collect edges associated with this crossover zone
xov_edges = []
main_edges = []
for edge in root.findall('edge'):
    if edge.get('function') == 'internal': continue
    eid = edge.get('id', '')
    if XOV_PREFIX in eid:
        for lane in edge.findall('lane'):
            shape = lane.get('shape')
            if not shape: continue
            pts = [list(map(float, p.split(','))) for p in shape.split()]
            if 'xov1' in eid or 'xov2' in eid:
                xov_edges.append((eid, pts))
            else:
                main_edges.append((eid, pts))

# Compute bounding box and local coordinate transformation (align along track tangent)
# Find switch nodes
n1A = nodes.get(f"{XOV_PREFIX}_1A")
n2B = nodes.get(f"{XOV_PREFIX}_2B")
n2C = nodes.get(f"{XOV_PREFIX}_2C")
n1D = nodes.get(f"{XOV_PREFIX}_1D")

if n1A and n1D:
    # Rotate plot so track is horizontal for clean engineering schematic viewing
    dx = n1D[0] - n1A[0]
    dy = n1D[1] - n1A[1]
    angle = np.arctan2(dy, dx)
    cos_a, sin_a = np.cos(-angle), np.sin(-angle)
    ox, oy = n1A[0], n1A[1]

    def transform(pt):
        px, py = pt[0] - ox, pt[1] - oy
        rx = px * cos_a - py * sin_a
        ry = px * sin_a + py * cos_a
        return rx, ry

    # Plot Mainline running edges
    for eid, pts in main_edges:
        t_pts = [transform(p) for p in pts]
        xs = [p[0] for p in t_pts]
        ys = [p[1] for p in t_pts]
        is_t1 = 'T1' in eid
        color = '#38bdf8' if is_t1 else '#60a5fa'
        lw = 4.0 if 'mid' in eid else 2.5
        ax.plot(xs, ys, color=color, linewidth=lw, alpha=0.9, zorder=3)

    # Plot Crossover Turnout tracks
    for eid, pts in xov_edges:
        t_pts = [transform(p) for p in pts]
        xs = [p[0] for p in t_pts]
        ys = [p[1] for p in t_pts]
        ax.plot(xs, ys, color='#f59e0b', linewidth=4.5, alpha=1.0, zorder=5, label='Turnout Spline (160 km/h)' if 'xov1_fw' in eid else "")

    # Plot Switch nodes (Interlocking points)
    switches = [
        ("Switch 1A (Trk 1 Diverge)", n1A, '#10b981', 'bottom'),
        ("Switch 2B (Trk 2 Converge)", n2B, '#10b981', 'top'),
        ("Switch 2C (Trk 2 Diverge)", n2C, '#f43f5e', 'top'),
        ("Switch 1D (Trk 1 Converge)", n1D, '#f43f5e', 'bottom'),
    ]
    for label, pos, col, vpos in switches:
        if pos:
            tx, ty = transform(pos)
            ax.scatter([tx], [ty], color=col, s=120, edgecolors='#ffffff', linewidth=1.5, zorder=6)
            y_offset = 2.5 if vpos == 'top' else -2.5
            ax.text(tx, ty + y_offset, label, color='#ffffff', fontsize=9, fontweight='bold',
                    ha='center', va='center', zorder=7,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='#1e293b', edgecolor=col, alpha=0.9))

    # Add dimensions & engineering markers
    t1A = transform(n1A)
    t2B = transform(n2B)
    t2C = transform(n2C)
    t1D = transform(n1D)

    # Dimension lines:
    # 1. Lead 1 (1A -> 2B) = 150m
    ax.annotate('', xy=(t2B[0], 6.5), xytext=(t1A[0], 6.5),
                arrowprops=dict(arrowstyle='<->', color='#94a3b8', lw=1.5))
    ax.text((t1A[0] + t2B[0])/2, 7.8, "Turnout 1 Lead = 150 m\n(R ≈ 1,000 m, 160 km/h)", color='#cbd5e1', fontsize=8, ha='center', va='bottom')

    # 2. Tangent Gap (2B -> 2C) = 80m
    ax.annotate('', xy=(t2C[0], 6.5), xytext=(t2B[0], 6.5),
                arrowprops=dict(arrowstyle='<->', color='#94a3b8', lw=1.5))
    ax.text((t2B[0] + t2C[0])/2, 7.8, "Tangent Buffer\n= 80 m", color='#cbd5e1', fontsize=8, ha='center', va='bottom')

    # 3. Lead 2 (2C -> 1D) = 150m
    ax.annotate('', xy=(t1D[0], 6.5), xytext=(t2C[0], 6.5),
                arrowprops=dict(arrowstyle='<->', color='#94a3b8', lw=1.5))
    ax.text((t2C[0] + t1D[0])/2, 7.8, "Turnout 2 Lead = 150 m\n(R ≈ 1,000 m, 160 km/h)", color='#cbd5e1', fontsize=8, ha='center', va='bottom')

    # 4. Total Footprint = 380m
    ax.annotate('', xy=(t1D[0], -7.5), xytext=(t1A[0], -7.5),
                arrowprops=dict(arrowstyle='<->', color='#38bdf8', lw=2.0))
    ax.text((t1A[0] + t1D[0])/2, -9.2, "Total Interlocking Footprint = 380 m (Paired Sequential Crossovers)", color='#38bdf8', fontsize=10, fontweight='bold', ha='center', va='top')

    # Track labels
    ax.text(t1A[0] - 120, t1A[1], "Track 1 (Eastbound 300 km/h) ───►", color='#38bdf8', fontsize=10, fontweight='bold', va='center')
    ax.text(t1A[0] - 120, t2B[1], "◄─── Track 2 (Westbound 300 km/h)", color='#60a5fa', fontsize=10, fontweight='bold', va='center')
    
    # Track spacing annotation
    track_gauge = abs(t2B[1] - t1A[1])
    ax.text(t1A[0] - 30, (t1A[1] + t2B[1])/2, f"Track Centers: {track_gauge:.1f} m", color='#94a3b8', fontsize=8, ha='right', va='center')

    # Operation descriptions
    ax.text((t1A[0] + t2B[0])/2, (t1A[1] + t2B[1])/2 - 1.2, "Turnout 1 (Trk 1 ➔ Trk 2)", color='#f59e0b', fontsize=8, fontweight='bold', ha='center', rotation=-14)
    ax.text((t2C[0] + t1D[0])/2, (t2C[1] + t1D[1])/2 + 1.2, "Turnout 2 (Trk 2 ➔ Trk 1)", color='#f59e0b', fontsize=8, fontweight='bold', ha='center', rotation=14)

    # Set display limits
    ax.set_xlim(t1A[0] - 150, t1D[0] + 150)
    ax.set_ylim(-13, 13)

ax.set_title('Phase 3 Engineering Detail: High-Speed Paired Universal Crossover (Interlocking Schematic)', color='#f8fafc', fontsize=15, pad=18)
ax.set_xlabel('Corridor Distance [m] (Local Tangent Axis)', color='#94a3b8', fontsize=10)
ax.set_ylabel('Lateral Offset [m]', color='#94a3b8', fontsize=10)
ax.grid(True, color='#1e293b', linestyle='--', alpha=0.7)
ax.tick_params(colors='#64748b', labelsize=8)
for spine in ax.spines.values(): spine.set_color('#334155')

plt.tight_layout()
plt.savefig(OUTPUT_IMG, facecolor='#090d16', edgecolor='none')
print(f'Successfully rendered crossover schematic to: {OUTPUT_IMG}')
