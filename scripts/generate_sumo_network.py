import xml.etree.ElementTree as ET
from xml.dom import minidom
import subprocess
import os
import math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, '..', 'network_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_path(filename): return os.path.join(OUTPUT_DIR, filename)
def prettify(elem): return minidom.parseString(ET.tostring(elem, 'utf-8')).toprettyxml(indent="    ")

# Realistic physical track infrastructure profiles
TRACK_PROFILES = {
    "high_speed": {"speed": "83.33", "allow": "rail_electric", "capacity_tons": "2500", "voltage": "25000", "gauge": "1435", "material": "concrete", "wear_rate": "0.01"},
    "regional": {"speed": "33.33", "allow": "rail rail_electric", "capacity_tons": "5000", "voltage": "15000", "gauge": "1435", "material": "ballast", "wear_rate": "0.05"},
    "freight": {"speed": "22.22", "allow": "rail", "capacity_tons": "12000", "voltage": "none", "gauge": "1435", "material": "wood", "wear_rate": "0.10"}
}

def compute_min_radius(pts):
    """Computes minimum curve radius along 2D points to calculate physics speed limit."""
    if len(pts) < 3: return float('inf')
    min_r = float('inf')
    for i in range(1, len(pts)-1):
        p1, p2, p3 = pts[i-1], pts[i], pts[i+1]
        x1, y1 = p1[0], p1[1]
        x2, y2 = p2[0], p2[1]
        x3, y3 = p3[0], p3[1]
        a = math.hypot(x2-x1, y2-y1)
        b = math.hypot(x3-x2, y3-y2)
        c = math.hypot(x3-x1, y3-y1)
        area = abs((x2-x1)*(y3-y1) - (y2-y1)*(x3-x1)) / 2.0
        if area > 0.001 and a > 0.1 and b > 0.1 and c > 0.1:
            r = (a * b * c) / (4.0 * area)
            if r < min_r: min_r = r
    return min_r

def generate_natural_rail_spline(p0, v0, p1, v1, z0, z1, scale_factor=0.28, custom_d0=None, custom_d1=None):
    """
    Generates a natural, realistic railway curve between (p0, v0) and (p1, v1).
    Ensures zero S-bends or overshoot kinks by tuning control point lengths to chord projection.
    """
    chord_x = p1[0] - p0[0]
    chord_y = p1[1] - p0[1]
    L = math.hypot(chord_x, chord_y)
    if L < 10.0: return None
    
    ux_c, uy_c = chord_x / L, chord_y / L
    dot0 = v0[0] * ux_c + v0[1] * uy_c
    dot1 = -(v1[0] * ux_c + v1[1] * uy_c)
    
    d0 = custom_d0 if custom_d0 is not None else max(L * 0.15, min(L * 0.38, L * scale_factor * max(0.4, (1.0 + dot0) / 2.0)))
    d1 = custom_d1 if custom_d1 is not None else max(L * 0.15, min(L * 0.38, L * scale_factor * max(0.4, (1.0 + dot1) / 2.0)))
    
    c0 = (p0[0] + v0[0] * d0, p0[1] + v0[1] * d0)
    c1 = (p1[0] + v1[0] * d1, p1[1] + v1[1] * d1)
    
    num_points = max(35, int(L / 80))
    pts_2d = []
    for i in range(num_points + 1):
        t = i / float(num_points)
        bx = (1-t)**3 * p0[0] + 3*(1-t)**2*t * c0[0] + 3*(1-t)*t**2 * c1[0] + t**3 * p1[0]
        by = (1-t)**3 * p0[1] + 3*(1-t)**2*t * c0[1] + 3*(1-t)*t**2 * c1[1] + t**3 * p1[1]
        pts_2d.append((bx, by))
        
    res_2d = [pts_2d[0]]
    for p in pts_2d[1:-1]:
        if math.hypot(p[0]-res_2d[-1][0], p[1]-res_2d[-1][1]) >= 30.0:
            res_2d.append(p)
    if math.hypot(pts_2d[-1][0]-res_2d[-1][0], pts_2d[-1][1]-res_2d[-1][1]) >= 15.0:
        res_2d.append(pts_2d[-1])
    else:
        res_2d[-1] = pts_2d[-1]
        
    n = len(res_2d)
    dists = [0.0] * n
    for i in range(1, n):
        dists[i] = dists[i-1] + math.hypot(res_2d[i][0]-res_2d[i-1][0], res_2d[i][1]-res_2d[i-1][1])
    total_len = dists[-1]
    
    flat_dist = min(100.0, total_len * 0.05)
    pts_3d = []
    for i in range(n):
        d = dists[i]
        if d <= flat_dist: z = z0
        elif d >= total_len - flat_dist: z = z1
        else:
            eff_len = total_len - 2 * flat_dist
            s = (d - flat_dist) / eff_len if eff_len > 0 else 0
            s_smooth = s * s * (3.0 - 2.0 * s)
            z = z0 + (z1 - z0) * s_smooth
        pts_3d.append((res_2d[i][0], res_2d[i][1], z))
        
    return pts_3d

def smooth_offset_shape(pts_3d, track_offset, taper_dist=120.0):
    """Generates parallel running tracks with standard center-to-center spacing, tapering at switches."""
    n = len(pts_3d)
    dists = [0.0] * n
    for i in range(1, n):
        dists[i] = dists[i-1] + math.hypot(pts_3d[i][0]-pts_3d[i-1][0], pts_3d[i][1]-pts_3d[i-1][1])
    total_len = dists[-1]
    
    new_pts = []
    for i in range(n):
        p = pts_3d[i]
        d = dists[i]
        taper_start = min(1.0, d / taper_dist) if taper_dist > 0 else 1.0
        taper_end = min(1.0, (total_len - d) / taper_dist) if taper_dist > 0 else 1.0
        w = min(taper_start, taper_end)
        w = w * w * (3.0 - 2.0 * w)
        curr_offset = track_offset * w
        
        if i == 0:
            nx, ny = p[0] - pts_3d[1][0], p[1] - pts_3d[1][1]
        elif i == n - 1:
            nx, ny = pts_3d[-2][0] - p[0], pts_3d[-2][1] - p[1]
        else:
            n1 = (pts_3d[i-1][0]-p[0], pts_3d[i-1][1]-p[1])
            n2 = (p[0]-pts_3d[i+1][0], p[1]-pts_3d[i+1][1])
            nx, ny = n1[0]+n2[0], n1[1]+n2[1]
            
        mag = math.hypot(nx, ny)
        if mag == 0: mag = 1.0
        px, py = -ny/mag, nx/mag
        new_pts.append((round(p[0] + px*curr_offset, 2), round(p[1] + py*curr_offset, 2), round(p[2], 2)))
        
    return new_pts

def generate_block_sections(edges_root, nodes_root, base_id, frm, to, pts, prof):
    """Splits running track into 1km signal blocks and calculates physics speed limits."""
    total_len = sum(math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]) for i in range(len(pts)-1))
    block_len = 1000.0
    max_profile_speed = float(prof['speed'])
    
    if total_len <= block_len * 1.5:
        min_r = compute_min_radius(pts)
        safe_v = math.sqrt(min_r * 1.2) if min_r < float('inf') else max_profile_speed
        edge_speed = max(13.89, min(max_profile_speed, safe_v))
        shape_str = " ".join([f"{p[0]:.2f},{p[1]:.2f},{p[2]:.2f}" for p in pts])
        edge = ET.SubElement(edges_root, 'edge', id=base_id, **{"from": frm, "to": to, "speed": f"{edge_speed:.2f}", "numLanes": "1", "allow": prof['allow'], "shape": shape_str})
        for key in ["capacity_tons", "voltage", "gauge", "material", "wear_rate"]: ET.SubElement(edge, 'param', key=key, value=prof[key])
        return [base_id]

    num_blocks = max(2, int(total_len / block_len))
    num_blocks = min(num_blocks, len(pts) - 1)
    chunk_size = max(1, len(pts) // num_blocks)
    
    prev_node = frm
    created_edges = []
    for b in range(num_blocks):
        is_last = (b == num_blocks - 1)
        start_idx = b * chunk_size
        end_idx = len(pts) - 1 if is_last else (b + 1) * chunk_size
        
        chunk_pts = pts[start_idx:end_idx+1]
        if len(chunk_pts) < 2: continue
        
        min_r = compute_min_radius(chunk_pts)
        safe_v = math.sqrt(min_r * 1.2) if min_r < float('inf') else max_profile_speed
        edge_speed = max(13.89, min(max_profile_speed, safe_v))
        chunk_shape = " ".join([f"{p[0]:.2f},{p[1]:.2f},{p[2]:.2f}" for p in chunk_pts])
        
        curr_node = to if is_last else f"{base_id}_signal_{b}"
        if not is_last:
            last_p = chunk_pts[-1]
            ET.SubElement(nodes_root, 'node', id=curr_node, x=f"{last_p[0]:.2f}", y=f"{last_p[1]:.2f}", z=f"{last_p[2]:.2f}", type="rail_signal")
        
        edge_id = f"{base_id}_b{b}"
        edge = ET.SubElement(edges_root, 'edge', id=edge_id, **{"from": prev_node, "to": curr_node, "speed": f"{edge_speed:.2f}", "numLanes": "1", "allow": prof['allow'], "shape": chunk_shape})
        for key in ["capacity_tons", "voltage", "gauge", "material", "wear_rate"]: ET.SubElement(edge, 'param', key=key, value=prof[key])
        created_edges.append(edge_id)
        prev_node = curr_node
        
    return created_edges

def create_corridor_track(edges_root, nodes_root, track_id, n_from, n_to, profile="regional", v0_override=None, v1_override=None, cd0=None, cd1=None):
    prof = TRACK_PROFILES[profile]
    p0 = (float(n_from['x']), float(n_from['y']))
    p1 = (float(n_to['x']), float(n_to['y']))
    v0 = v0_override if v0_override else n_from.get('out_vec', (1, 0))
    v1 = v1_override if v1_override else n_to.get('out_vec', (-1, 0))
    z0 = float(n_from.get('z', 0))
    z1 = float(n_to.get('z', 0))
    
    base_pts = generate_natural_rail_spline(p0, v0, p1, v1, z0, z1, custom_d0=cd0, custom_d1=cd1)
    if not base_pts: return None, None
    
    fw_pts = smooth_offset_shape(base_pts, 2.0)
    bw_pts = smooth_offset_shape(base_pts, -2.0)
    
    fw_edges = generate_block_sections(edges_root, nodes_root, f"{track_id}_fw", n_from['id'], n_to['id'], fw_pts, prof)
    bw_pts_rev = list(reversed(bw_pts))
    bw_edges = generate_block_sections(edges_root, nodes_root, f"{track_id}_bw", n_to['id'], n_from['id'], bw_pts_rev, prof)
    
    return fw_edges, bw_edges

def build_angled_yard(node_dict, nodes_root, edges_root, stops_root, stn_id, x, y, z, angle_deg, platforms, yards, length=600):
    theta = math.radians(angle_deg)
    ux, uy = math.cos(theta), math.sin(theta)
    nx, ny = -uy, ux
    
    total_tracks = platforms + yards
    spread = 6.0
    start_off = -(total_tracks - 1) * spread / 2.0
    
    t_dist = length / 2.0 + 150.0
    t1_pos = (x - ux * t_dist, y - uy * t_dist, z)
    t2_pos = (x + ux * t_dist, y + uy * t_dist, z)
    
    t1_id, t2_id = f"{stn_id}_Throat1", f"{stn_id}_Throat2"
    node_dict[t1_id] = {"id": t1_id, "x": t1_pos[0], "y": t1_pos[1], "z": z, "type": "rail_signal", "out_vec": (-ux, -uy)}
    node_dict[t2_id] = {"id": t2_id, "x": t2_pos[0], "y": t2_pos[1], "z": z, "type": "rail_signal", "out_vec": (ux, uy)}
    
    half_len = length / 2.0
    station_fw_edges = []
    station_bw_edges = []
    
    for i in range(total_tracks):
        is_yard = i >= platforms
        track_id = f"{stn_id}_{'yard' if is_yard else 'plat'}_{i+1}"
        off = start_off + i * spread
        
        p1 = (x - ux * half_len + nx * off, y - uy * half_len + ny * off, z)
        p2 = (x + ux * half_len + nx * off, y + uy * half_len + ny * off, z)
        
        shape_str = f"{t1_pos[0]:.2f},{t1_pos[1]:.2f},{t1_pos[2]:.2f} {p1[0]:.2f},{p1[1]:.2f},{p1[2]:.2f} {p2[0]:.2f},{p2[1]:.2f},{p2[2]:.2f} {t2_pos[0]:.2f},{t2_pos[1]:.2f},{t2_pos[2]:.2f}"
        speed = "13.89" if not is_yard else "5.55"
        
        edge_fw_id = f"{track_id}_fw"
        edge_bw_id = f"{track_id}_bw"
        
        edge_fw = ET.SubElement(edges_root, 'edge', id=edge_fw_id, **{"from": t1_id, "to": t2_id, "speed": speed, "numLanes": "1", "allow": "rail rail_electric", "shape": shape_str, "bidi": edge_bw_id})
        edge_bw = ET.SubElement(edges_root, 'edge', id=edge_bw_id, **{"from": t2_id, "to": t1_id, "speed": speed, "numLanes": "1", "allow": "rail rail_electric", "shape": " ".join(reversed(shape_str.split())), "bidi": edge_fw_id})
        
        station_fw_edges.append(edge_fw_id)
        station_bw_edges.append(edge_bw_id)
        
        if is_yard:
            ET.SubElement(edge_fw, 'param', key="is_yard", value="true")
            ET.SubElement(edge_bw, 'param', key="is_yard", value="true")
        else:
            ET.SubElement(stops_root, 'trainStop', id=f"{stn_id}_p{i+1}_fw", lane=f"{track_id}_fw_0", startPos="50", endPos=str(length-50))
            ET.SubElement(stops_root, 'trainStop', id=f"{stn_id}_p{i+1}_bw", lane=f"{track_id}_bw_0", startPos="50", endPos=str(length-50))
            
    return t1_id, t2_id, station_fw_edges, station_bw_edges

class StationSpec:
    def __init__(self, stn_id, x, y, z, angle, platforms, yards, length=600):
        self.id = stn_id
        self.x = x
        self.y = y
        self.z = z
        self.angle = angle
        self.platforms = platforms
        self.yards = yards
        self.length = length
        self.t1 = None
        self.t2 = None
        self.fw_edges = []
        self.bw_edges = []

def generate_sumo_network():
    nodes_root = ET.Element('nodes')
    edges_root = ET.Element('edges')
    stops_root = ET.Element('additionals')
    conns_root = ET.Element('connections')
    nd = {}

    # 22 Stations organized along natural geographic railway corridors
    # Angles strictly aligned with corridor tangents to eliminate kinks and S-bends
    stations = {
        # Corridor 1: East-West Trans-Regional High-Speed Trunk
        'City_1': StationSpec('City_1', -13000, 1000, 15, 12.0, platforms=5, yards=2, length=800),
        'Town_1': StationSpec('Town_1', -8800, 1800, 25, 8.0, platforms=3, yards=1, length=400),
        'City_2': StationSpec('City_2', -4200, 2200, 38, 5.0, platforms=6, yards=2, length=900),
        'Town_2': StationSpec('Town_2', 400, 2000, 30, -2.5, platforms=2, yards=1, length=400),
        'City_3_EW': StationSpec('City_3_EW', 5200, 1500, 20, -6.0, platforms=4, yards=2, length=900),
        'Town_3': StationSpec('Town_3', 9800, 800, 12, -8.6, platforms=3, yards=1, length=400),
        'City_4': StationSpec('City_4', 14200, 0, 2, -10.0, platforms=5, yards=2, length=800),

        # Corridor 2: North-South Inter-City Trunk (passes straight through City_3_NS)
        'City_5': StationSpec('City_5', 4200, 12500, 60, -86.0, platforms=5, yards=2, length=800),
        'Town_4': StationSpec('Town_4', 4500, 8800, 45, -85.4, platforms=2, yards=1, length=400),
        'Town_5': StationSpec('Town_5', 4850, 5100, 32, -84.6, platforms=3, yards=1, length=400),
        'City_3_NS': StationSpec('City_3_NS', 5250, 1500, 20, -83.7, platforms=4, yards=1, length=900),
        'Town_6': StationSpec('Town_6', 5650, -2200, 14, -83.8, platforms=3, yards=1, length=400),
        'Town_7': StationSpec('Town_7', 6050, -5900, 8, -83.8, platforms=2, yards=1, length=400),
        'City_6': StationSpec('City_6', 6500, -10000, 2, -83.7, platforms=5, yards=2, length=800),

        # Corridor 3: Northwest Alpine Mountain Line (branches Northwest from City_2)
        'Town_8': StationSpec('Town_8', -7500, 5200, 80, 135.0, platforms=2, yards=1, length=400),
        'Town_9': StationSpec('Town_9', -10500, 8200, 130, 135.0, platforms=2, yards=1, length=400),
        'Depot_1': StationSpec('Depot_1', -13500, 11200, 165, 135.0, platforms=0, yards=4, length=500),

        # Corridor 4: Southern Coastal Arc (Natural parabolic sweep from City_1 to City_6)
        'Town_10': StationSpec('Town_10', -13500, -3200, 10, -80.0, platforms=2, yards=1, length=400),
        'Town_11': StationSpec('Town_11', -11200, -7200, 6, -42.0, platforms=3, yards=1, length=400),
        'Depot_2': StationSpec('Depot_2', -5600, -9600, 3, -15.0, platforms=0, yards=4, length=500),
        'Town_12': StationSpec('Town_12', 600, -8400, 2, -8.0, platforms=2, yards=1, length=400),

        # Heavy Industrial Logistics Depots
        'Depot_3': StationSpec('Depot_3', 7500, 15000, 55, 30.0, platforms=0, yards=4, length=500),
        'Depot_4': StationSpec('Depot_4', 9200, 2800, 18, 20.0, platforms=0, yards=4, length=500),
    }

    for s in stations.values():
        s.t1, s.t2, s.fw_edges, s.bw_edges = build_angled_yard(
            nd, nodes_root, edges_root, stops_root, s.id, s.x, s.y, s.z, s.angle, s.platforms, s.yards, s.length
        )

    # Inter-station track definitions with optimized tangents
    corridor_segments = [
        # Corridor 1 (East-West High Speed Trunk)
        ('City_1', 2, 'Town_1', 1, 'high_speed', 'c1_City_1_Town_1', None, None, None, None),
        ('Town_1', 2, 'City_2', 1, 'high_speed', 'c1_Town_1_City_2', None, None, None, None),
        ('City_2', 2, 'Town_2', 1, 'high_speed', 'c1_City_2_Town_2', None, None, None, None),
        ('Town_2', 2, 'City_3_EW', 1, 'high_speed', 'c1_Town_2_City_3_EW', None, None, None, None),
        ('City_3_EW', 2, 'Town_3', 1, 'high_speed', 'c1_City_3_EW_Town_3', None, None, None, None),
        ('Town_3', 2, 'City_4', 1, 'high_speed', 'c1_Town_3_City_4', None, None, None, None),

        # Corridor 2 (North-South Regional Trunk straight through City_3_NS)
        ('City_5', 2, 'Town_4', 1, 'regional', 'c2_City_5_Town_4', None, None, None, None),
        ('Town_4', 2, 'Town_5', 1, 'regional', 'c2_Town_4_Town_5', None, None, None, None),
        ('Town_5', 2, 'City_3_NS', 1, 'regional', 'c2_Town_5_City_3_NS', None, None, None, None),
        ('City_3_NS', 2, 'Town_6', 1, 'regional', 'c2_City_3_NS_Town_6', None, None, None, None),
        ('Town_6', 2, 'Town_7', 1, 'regional', 'c2_Town_6_Town_7', None, None, None, None),
        ('Town_7', 2, 'City_6', 1, 'regional', 'c2_Town_7_City_6', None, None, None, None),

        # Corridor 3 (Northwest Alpine Line: branches Northwest from City_2)
        ('City_2', 1, 'Town_8', 1, 'regional', 'c3_City_2_Town_8', (-0.85, 0.52), None, None, None),
        ('Town_8', 2, 'Town_9', 1, 'regional', 'c3_Town_8_Town_9', None, None, None, None),
        ('Town_9', 2, 'Depot_1', 1, 'freight', 'c3_Town_9_Depot_1', None, None, None, None),

        # Corridor 4 (Southern Coastal Arc: sweeps naturally from City_1 to City_6)
        ('City_1', 1, 'Town_10', 1, 'regional', 'c4_City_1_Town_10', (-0.35, -0.94), None, None, None),
        ('Town_10', 2, 'Town_11', 1, 'regional', 'c4_Town_10_Town_11', None, None, None, None),
        ('Town_11', 2, 'Depot_2', 1, 'regional', 'c4_Town_11_Depot_2', None, None, None, None),
        ('Depot_2', 2, 'Town_12', 1, 'regional', 'c4_Depot_2_Town_12', None, None, None, None),
        ('Town_12', 2, 'City_6', 1, 'regional', 'c4_Town_12_City_6', None, (-0.60, 0.80), None, None),

        # Industrial Depot spurs
        ('City_5', 1, 'Depot_3', 1, 'freight', 'spur_City_5_Depot_3', (0.45, 0.89), None, None, None),
        ('City_3_EW', 2, 'Depot_4', 1, 'freight', 'spur_City_3_EW_Depot_4', (0.70, 0.71), None, None, None),

        # Central Hub transfer track between East-West and North-South stations
        ('City_3_EW', 1, 'City_3_NS', 1, 'regional', 'transfer_City_3_EW_NS', (0.707, 0.707), (-0.707, -0.707), None, None),

        # High-Speed Diagonal Bypass (City_2 to City_5)
        ('City_2', 2, 'City_5', 2, 'high_speed', 'bypass_City_2_City_5', (0.80, 0.60), (-0.40, -0.92), None, None),
    ]

    mainline_edges_info = []
    for s_from_id, t_from_idx, s_to_id, t_to_idx, prof, track_id, v0_ovr, v1_ovr, cd0, cd1 in corridor_segments:
        s_from = stations[s_from_id]
        s_to = stations[s_to_id]
        node_from = nd[s_from.t1 if t_from_idx == 1 else s_from.t2]
        node_to = nd[s_to.t1 if t_to_idx == 1 else s_to.t2]
        
        fw_edges, bw_edges = create_corridor_track(edges_root, nodes_root, track_id, node_from, node_to, prof, v0_ovr, v1_ovr, cd0, cd1)
        if fw_edges and bw_edges:
            mainline_edges_info.append((node_from['id'], node_to['id'], fw_edges, bw_edges))

    # Explicit throat interlocking connections
    for s in stations.values():
        in_m1 = [bw_e[-1] for t_start, t_end, fw_e, bw_e in mainline_edges_info if t_start == s.t1] + \
                [fw_e[-1] for t_start, t_end, fw_e, bw_e in mainline_edges_info if t_end == s.t1]
        out_m1 = [fw_e[0] for t_start, t_end, fw_e, bw_e in mainline_edges_info if t_start == s.t1] + \
                 [bw_e[0] for t_start, t_end, fw_e, bw_e in mainline_edges_info if t_end == s.t1]
                 
        for in_e in in_m1:
            for plat_fw in s.fw_edges:
                ET.SubElement(conns_root, 'connection', **{"from": in_e, "to": plat_fw, "fromLane": "0", "toLane": "0"})
        for plat_bw in s.bw_edges:
            for out_e in out_m1:
                ET.SubElement(conns_root, 'connection', **{"from": plat_bw, "to": out_e, "fromLane": "0", "toLane": "0"})

        in_m2 = [bw_e[-1] for t_start, t_end, fw_e, bw_e in mainline_edges_info if t_start == s.t2] + \
                [fw_e[-1] for t_start, t_end, fw_e, bw_e in mainline_edges_info if t_end == s.t2]
        out_m2 = [fw_e[0] for t_start, t_end, fw_e, bw_e in mainline_edges_info if t_start == s.t2] + \
                 [bw_e[0] for t_start, t_end, fw_e, bw_e in mainline_edges_info if t_end == s.t2]
                 
        for in_e in in_m2:
            for plat_bw in s.bw_edges:
                ET.SubElement(conns_root, 'connection', **{"from": in_e, "to": plat_bw, "fromLane": "0", "toLane": "0"})
        for plat_fw in s.fw_edges:
            for out_e in out_m2:
                ET.SubElement(conns_root, 'connection', **{"from": plat_fw, "to": out_e, "fromLane": "0", "toLane": "0"})

    # Write network source XMLs
    for n in nd.values(): ET.SubElement(nodes_root, 'node', **{k:str(v) for k,v in n.items() if k != 'out_vec'})
    with open(get_path("dense_network.nod.xml"), "w") as f: f.write(prettify(nodes_root))
    with open(get_path("dense_network.edg.xml"), "w") as f: f.write(prettify(edges_root))
    with open(get_path("dense_network.add.xml"), "w") as f: f.write(prettify(stops_root))
    with open(get_path("dense_network.con.xml"), "w") as f: f.write(prettify(conns_root))

    # Compile network with netconvert
    cmd = [
        "netconvert",
        "--node-files", get_path("dense_network.nod.xml"),
        "--edge-files", get_path("dense_network.edg.xml"),
        "--connection-files", get_path("dense_network.con.xml"),
        "--output-file", get_path("dense_network.net.xml"),
        "--junctions.join", "true",
        "--no-turnarounds", "true",
        "--railway.topology.output", get_path("railway_topology.xml")
    ]
    subprocess.run(cmd, check=True)
    print("Done! Railway network compiled cleanly into dense_network.net.xml")

if __name__ == "__main__":
    generate_sumo_network()
