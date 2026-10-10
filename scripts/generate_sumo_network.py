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

def sample_point_at_distance(pts, dists, target_d):
    """Interpolates a 3D coordinate and 2D tangent vector at distance target_d along a polyline."""
    n = len(pts)
    if target_d <= 0.0:
        p0, p1 = pts[0], pts[1]
        dx, dy = p1[0]-p0[0], p1[1]-p0[1]
        mag = math.hypot(dx, dy)
        return p0, (dx/mag, dy/mag) if mag > 0 else (1, 0)
    if target_d >= dists[-1]:
        p0, p1 = pts[-2], pts[-1]
        dx, dy = p1[0]-p0[0], p1[1]-p0[1]
        mag = math.hypot(dx, dy)
        return p1, (dx/mag, dy/mag) if mag > 0 else (1, 0)
    for i in range(n - 1):
        if dists[i] <= target_d <= dists[i+1]:
            seg_len = dists[i+1] - dists[i]
            frac = (target_d - dists[i]) / seg_len if seg_len > 0 else 0
            p0, p1 = pts[i], pts[i+1]
            x = p0[0] + frac * (p1[0] - p0[0])
            y = p0[1] + frac * (p1[1] - p0[1])
            z = p0[2] + frac * (p1[2] - p0[2])
            dx, dy = p1[0]-p0[0], p1[1]-p0[1]
            mag = math.hypot(dx, dy)
            return (round(x, 2), round(y, 2), round(z, 2)), (dx/mag, dy/mag) if mag > 0 else (1, 0)
    return pts[-1], (1, 0)

def slice_points_by_distance(pts, dists, d_start, d_end):
    """Slices a polyline by arc length distance interval [d_start, d_end]."""
    p_start, _ = sample_point_at_distance(pts, dists, d_start)
    p_end, _ = sample_point_at_distance(pts, dists, d_end)
    sliced = [p_start]
    for i in range(len(pts)):
        if d_start < dists[i] < d_end:
            sliced.append(pts[i])
    sliced.append(p_end)
    res = [sliced[0]]
    for p in sliced[1:]:
        if math.hypot(p[0]-res[-1][0], p[1]-res[-1][1]) >= 8.0:
            res.append(p)
    if len(res) == 1:
        res.append(p_end)
    return res

def generate_bidi_blocks(edges_root, nodes_root, base_id, frm, to, pts, prof):
    """Splits running track into ~1km signal blocks with paired bidirectional edges (fw & bw)."""
    total_len = sum(math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]) for i in range(len(pts)-1))
    block_len = 1000.0
    max_profile_speed = float(prof['speed'])
    
    if total_len <= block_len * 1.5:
        min_r = compute_min_radius(pts)
        safe_v = math.sqrt(min_r * 1.2) if min_r < float('inf') else max_profile_speed
        edge_speed = max(13.89, min(max_profile_speed, safe_v))
        shape_fw = " ".join([f"{p[0]:.2f},{p[1]:.2f},{p[2]:.2f}" for p in pts])
        shape_bw = " ".join([f"{p[0]:.2f},{p[1]:.2f},{p[2]:.2f}" for p in reversed(pts)])
        
        efw_id = f"{base_id}_fw"
        ebw_id = f"{base_id}_bw"
        efw = ET.SubElement(edges_root, 'edge', id=efw_id, **{"from": frm, "to": to, "speed": f"{edge_speed:.2f}", "numLanes": "1", "allow": prof['allow'], "shape": shape_fw, "bidi": ebw_id})
        ebw = ET.SubElement(edges_root, 'edge', id=ebw_id, **{"from": to, "to": frm, "speed": f"{edge_speed:.2f}", "numLanes": "1", "allow": prof['allow'], "shape": shape_bw, "bidi": efw_id})
        for key in ["capacity_tons", "voltage", "gauge", "material", "wear_rate"]:
            ET.SubElement(efw, 'param', key=key, value=prof[key])
            ET.SubElement(ebw, 'param', key=key, value=prof[key])
        return [efw_id], [ebw_id]

    num_blocks = max(2, int(total_len / block_len))
    num_blocks = min(num_blocks, len(pts) - 1)
    chunk_size = max(1, len(pts) // num_blocks)
    
    nodes = [frm]
    chunk_list = []
    for b in range(num_blocks):
        is_last = (b == num_blocks - 1)
        start_idx = b * chunk_size
        end_idx = len(pts) - 1 if is_last else (b + 1) * chunk_size
        chunk_pts = pts[start_idx:end_idx+1]
        chunk_list.append(chunk_pts)
        curr_node = to if is_last else f"{base_id}_sig_{b}"
        nodes.append(curr_node)
        if not is_last:
            last_p = chunk_pts[-1]
            ET.SubElement(nodes_root, 'node', id=curr_node, x=f"{last_p[0]:.2f}", y=f"{last_p[1]:.2f}", z=f"{last_p[2]:.2f}", type="rail_signal")
            
    created_fw = []
    created_bw = []
    for b in range(num_blocks):
        chunk_pts = chunk_list[b]
        min_r = compute_min_radius(chunk_pts)
        safe_v = math.sqrt(min_r * 1.2) if min_r < float('inf') else max_profile_speed
        edge_speed = max(13.89, min(max_profile_speed, safe_v))
        shape_fw = " ".join([f"{p[0]:.2f},{p[1]:.2f},{p[2]:.2f}" for p in chunk_pts])
        shape_bw = " ".join([f"{p[0]:.2f},{p[1]:.2f},{p[2]:.2f}" for p in reversed(chunk_pts)])
        
        u = nodes[b]
        v = nodes[b+1]
        efw_id = f"{base_id}_fw_b{b}"
        ebw_id = f"{base_id}_bw_b{b}"
        efw = ET.SubElement(edges_root, 'edge', id=efw_id, **{"from": u, "to": v, "speed": f"{edge_speed:.2f}", "numLanes": "1", "allow": prof['allow'], "shape": shape_fw, "bidi": ebw_id})
        ebw = ET.SubElement(edges_root, 'edge', id=ebw_id, **{"from": v, "to": u, "speed": f"{edge_speed:.2f}", "numLanes": "1", "allow": prof['allow'], "shape": shape_bw, "bidi": efw_id})
        for key in ["capacity_tons", "voltage", "gauge", "material", "wear_rate"]:
            ET.SubElement(efw, 'param', key=key, value=prof[key])
            ET.SubElement(ebw, 'param', key=key, value=prof[key])
        created_fw.append(efw_id)
        created_bw.append(ebw_id)
        
    return created_fw, created_bw

def create_corridor_track(edges_root, nodes_root, conns_root, track_id, n_from, n_to, profile="regional", v0_override=None, v1_override=None, cd0=None, cd1=None, has_xover=False):
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
    
    if not has_xover:
        fw_edges = generate_block_sections(edges_root, nodes_root, f"{track_id}_fw", n_from['id'], n_to['id'], fw_pts, prof)
        bw_pts_rev = list(reversed(bw_pts))
        bw_edges = generate_block_sections(edges_root, nodes_root, f"{track_id}_bw", n_to['id'], n_from['id'], bw_pts_rev, prof)
        return fw_edges, bw_edges, None, None

    # Calculate cumulative distances along corridor
    dists = [0.0] * len(base_pts)
    for i in range(1, len(base_pts)):
        dists[i] = dists[i-1] + math.hypot(base_pts[i][0]-base_pts[i-1][0], base_pts[i][1]-base_pts[i-1][1])
    total_len = dists[-1]

    # Paired high-speed universal crossover footprint
    s_mid = total_len / 2.0
    L_xov = 150.0  # Turnout lead distance (giving R ~ 1000m)
    L_gap = 80.0   # Buffer tangent between crossovers
    W_xov = 2 * L_xov + L_gap # 380m total footprint
    s_A = s_mid - W_xov / 2.0
    s_B = s_A + L_xov
    s_C = s_B + L_gap
    s_D = s_C + L_xov

    pos_1A, vec_1A = sample_point_at_distance(fw_pts, dists, s_A)
    pos_2B, vec_2B = sample_point_at_distance(bw_pts, dists, s_B)
    pos_2C, vec_2C = sample_point_at_distance(bw_pts, dists, s_C)
    pos_1D, vec_1D = sample_point_at_distance(fw_pts, dists, s_D)

    xov_id = f"{track_id}_xov"
    n1A = f"{xov_id}_1A"
    n2B = f"{xov_id}_2B"
    n2C = f"{xov_id}_2C"
    n1D = f"{xov_id}_1D"

    ET.SubElement(nodes_root, 'node', id=n1A, x=f"{pos_1A[0]:.2f}", y=f"{pos_1A[1]:.2f}", z=f"{pos_1A[2]:.2f}", type='rail_signal')
    ET.SubElement(nodes_root, 'node', id=n2B, x=f"{pos_2B[0]:.2f}", y=f"{pos_2B[1]:.2f}", z=f"{pos_2B[2]:.2f}", type='rail_signal')
    ET.SubElement(nodes_root, 'node', id=n2C, x=f"{pos_2C[0]:.2f}", y=f"{pos_2C[1]:.2f}", z=f"{pos_2C[2]:.2f}", type='rail_signal')
    ET.SubElement(nodes_root, 'node', id=n1D, x=f"{pos_1D[0]:.2f}", y=f"{pos_1D[1]:.2f}", z=f"{pos_1D[2]:.2f}", type='rail_signal')

    # Polyline shapes for track sections
    fw_pre_pts = slice_points_by_distance(fw_pts, dists, 0.0, s_A)
    fw_mid_pts = slice_points_by_distance(fw_pts, dists, s_A, s_D)
    fw_post_pts = slice_points_by_distance(fw_pts, dists, s_D, total_len)

    bw_post_pts = slice_points_by_distance(bw_pts, dists, 0.0, s_B)
    bw_mid_pts = slice_points_by_distance(bw_pts, dists, s_B, s_C)
    bw_pre_pts = slice_points_by_distance(bw_pts, dists, s_C, total_len)

    # Approach and departure blocks with bidirectional edges
    t1_pre_fw, t1_pre_bw = generate_bidi_blocks(edges_root, nodes_root, f"{xov_id}_T1_pre", n_from['id'], n1A, fw_pre_pts, prof)
    t1_post_fw, t1_post_bw = generate_bidi_blocks(edges_root, nodes_root, f"{xov_id}_T1_post", n1D, n_to['id'], fw_post_pts, prof)

    t2_post_fw, t2_post_bw = generate_bidi_blocks(edges_root, nodes_root, f"{xov_id}_T2_post", n_from['id'], n2B, bw_post_pts, prof)
    t2_pre_fw, t2_pre_bw = generate_bidi_blocks(edges_root, nodes_root, f"{xov_id}_T2_pre", n2C, n_to['id'], bw_pre_pts, prof)

    def to_shape_str(pts): return " ".join([f"{p[0]:.2f},{p[1]:.2f},{p[2]:.2f}" for p in pts])
    def to_rev_shape_str(pts): return " ".join([f"{p[0]:.2f},{p[1]:.2f},{p[2]:.2f}" for p in reversed(pts)])

    # Straight mainline edges inside the crossover zone (maintaining full line speed)
    e_T1_mid_fw = f"{xov_id}_T1_mid_fw"
    e_T1_mid_bw = f"{xov_id}_T1_mid_bw"
    efw = ET.SubElement(edges_root, 'edge', id=e_T1_mid_fw, **{"from": n1A, "to": n1D, "speed": prof['speed'], "numLanes": "1", "allow": prof['allow'], "shape": to_shape_str(fw_mid_pts), "bidi": e_T1_mid_bw})
    ebw = ET.SubElement(edges_root, 'edge', id=e_T1_mid_bw, **{"from": n1D, "to": n1A, "speed": prof['speed'], "numLanes": "1", "allow": prof['allow'], "shape": to_rev_shape_str(fw_mid_pts), "bidi": e_T1_mid_fw})
    for k in ["capacity_tons", "voltage", "gauge", "material", "wear_rate"]:
        ET.SubElement(efw, 'param', key=k, value=prof[k]); ET.SubElement(ebw, 'param', key=k, value=prof[k])

    e_T2_mid_fw = f"{xov_id}_T2_mid_fw"
    e_T2_mid_bw = f"{xov_id}_T2_mid_bw"
    efw = ET.SubElement(edges_root, 'edge', id=e_T2_mid_fw, **{"from": n2B, "to": n2C, "speed": prof['speed'], "numLanes": "1", "allow": prof['allow'], "shape": to_shape_str(bw_mid_pts), "bidi": e_T2_mid_bw})
    ebw = ET.SubElement(edges_root, 'edge', id=e_T2_mid_bw, **{"from": n2C, "to": n2B, "speed": prof['speed'], "numLanes": "1", "allow": prof['allow'], "shape": to_rev_shape_str(bw_mid_pts), "bidi": e_T2_mid_fw})
    for k in ["capacity_tons", "voltage", "gauge", "material", "wear_rate"]:
        ET.SubElement(efw, 'param', key=k, value=prof[k]); ET.SubElement(ebw, 'param', key=k, value=prof[k])

    # Diagonal crossover turnouts (speed: 160 km/h on high_speed, 80 km/h on regional)
    xov_speed = "44.44" if profile == "high_speed" else "22.22"
    xov1_pts = generate_natural_rail_spline((pos_1A[0], pos_1A[1]), vec_1A, (pos_2B[0], pos_2B[1]), (-vec_2B[0], -vec_2B[1]), pos_1A[2], pos_2B[2], scale_factor=0.35)
    xov2_pts = generate_natural_rail_spline((pos_2C[0], pos_2C[1]), vec_2C, (pos_1D[0], pos_1D[1]), (-vec_1D[0], -vec_1D[1]), pos_2C[2], pos_1D[2], scale_factor=0.35)

    e_xov1_fw = f"{xov_id}_xov1_fw"
    e_xov1_bw = f"{xov_id}_xov1_bw"
    efw = ET.SubElement(edges_root, 'edge', id=e_xov1_fw, **{"from": n1A, "to": n2B, "speed": xov_speed, "numLanes": "1", "allow": prof['allow'], "shape": to_shape_str(xov1_pts), "bidi": e_xov1_bw})
    ebw = ET.SubElement(edges_root, 'edge', id=e_xov1_bw, **{"from": n2B, "to": n1A, "speed": xov_speed, "numLanes": "1", "allow": prof['allow'], "shape": to_rev_shape_str(xov1_pts), "bidi": e_xov1_fw})
    for k in ["capacity_tons", "voltage", "gauge", "material", "wear_rate"]:
        ET.SubElement(efw, 'param', key=k, value=prof[k]); ET.SubElement(ebw, 'param', key=k, value=prof[k])
    ET.SubElement(efw, 'param', key="is_crossover", value="true")
    ET.SubElement(ebw, 'param', key="is_crossover", value="true")

    e_xov2_fw = f"{xov_id}_xov2_fw"
    e_xov2_bw = f"{xov_id}_xov2_bw"
    efw = ET.SubElement(edges_root, 'edge', id=e_xov2_fw, **{"from": n2C, "to": n1D, "speed": xov_speed, "numLanes": "1", "allow": prof['allow'], "shape": to_shape_str(xov2_pts), "bidi": e_xov2_bw})
    ebw = ET.SubElement(edges_root, 'edge', id=e_xov2_bw, **{"from": n1D, "to": n2C, "speed": xov_speed, "numLanes": "1", "allow": prof['allow'], "shape": to_rev_shape_str(xov2_pts), "bidi": e_xov2_fw})
    for k in ["capacity_tons", "voltage", "gauge", "material", "wear_rate"]:
        ET.SubElement(efw, 'param', key=k, value=prof[k]); ET.SubElement(ebw, 'param', key=k, value=prof[k])
    ET.SubElement(efw, 'param', key="is_crossover", value="true")
    ET.SubElement(ebw, 'param', key="is_crossover", value="true")

    # Explicit interlocking switch connections
    # At X1A (Track 1 Switch 1):
    ET.SubElement(conns_root, 'connection', **{"from": t1_pre_fw[-1], "to": e_T1_mid_fw, "fromLane": "0", "toLane": "0"})
    ET.SubElement(conns_root, 'connection', **{"from": t1_pre_fw[-1], "to": e_xov1_fw, "fromLane": "0", "toLane": "0"})
    ET.SubElement(conns_root, 'connection', **{"from": e_T1_mid_bw, "to": t1_pre_bw[-1], "fromLane": "0", "toLane": "0"})
    ET.SubElement(conns_root, 'connection', **{"from": e_xov1_bw, "to": t1_pre_bw[-1], "fromLane": "0", "toLane": "0"})

    # At X2B (Track 2 Switch 1):
    ET.SubElement(conns_root, 'connection', **{"from": e_xov1_fw, "to": e_T2_mid_fw, "fromLane": "0", "toLane": "0"})
    ET.SubElement(conns_root, 'connection', **{"from": t2_post_fw[-1], "to": e_T2_mid_fw, "fromLane": "0", "toLane": "0"})
    ET.SubElement(conns_root, 'connection', **{"from": e_T2_mid_bw, "to": t2_post_bw[-1], "fromLane": "0", "toLane": "0"})
    ET.SubElement(conns_root, 'connection', **{"from": e_T2_mid_bw, "to": e_xov1_bw, "fromLane": "0", "toLane": "0"})

    # At X2C (Track 2 Switch 2):
    ET.SubElement(conns_root, 'connection', **{"from": e_T2_mid_fw, "to": t2_pre_fw[0], "fromLane": "0", "toLane": "0"})
    ET.SubElement(conns_root, 'connection', **{"from": e_T2_mid_fw, "to": e_xov2_fw, "fromLane": "0", "toLane": "0"})
    ET.SubElement(conns_root, 'connection', **{"from": t2_pre_bw[0], "to": e_T2_mid_bw, "fromLane": "0", "toLane": "0"})
    ET.SubElement(conns_root, 'connection', **{"from": e_xov2_bw, "to": e_T2_mid_bw, "fromLane": "0", "toLane": "0"})

    # At X1D (Track 1 Switch 2):
    ET.SubElement(conns_root, 'connection', **{"from": e_T1_mid_fw, "to": t1_post_fw[0], "fromLane": "0", "toLane": "0"})
    ET.SubElement(conns_root, 'connection', **{"from": e_xov2_fw, "to": t1_post_fw[0], "fromLane": "0", "toLane": "0"})
    ET.SubElement(conns_root, 'connection', **{"from": t1_post_bw[0], "to": e_T1_mid_bw, "fromLane": "0", "toLane": "0"})
    ET.SubElement(conns_root, 'connection', **{"from": t1_post_bw[0], "to": e_xov2_bw, "fromLane": "0", "toLane": "0"})

    # Route edge sequences for through-trains across corridor
    fw_edges = t1_pre_fw + [e_T1_mid_fw] + t1_post_fw
    bw_edges = list(reversed(t2_pre_bw)) + [e_T2_mid_bw] + list(reversed(t2_post_bw))
    return fw_edges, bw_edges, t2_post_fw[0], t1_post_bw[-1]

def build_angled_yard(node_dict, nodes_root, edges_root, stops_root, stn_id, x, y, z, angle_deg, platforms, yards, length=600, thru_tracks=0, thru_speed=83.33):
    theta = math.radians(angle_deg)
    ux, uy = math.cos(theta), math.sin(theta)
    nx, ny = -uy, ux
    
    t_dist = length / 2.0 + (220.0 if thru_tracks > 0 else 150.0)
    t1_pos = (x - ux * t_dist, y - uy * t_dist, z)
    t2_pos = (x + ux * t_dist, y + uy * t_dist, z)
    
    t1_id, t2_id = f"{stn_id}_Throat1", f"{stn_id}_Throat2"
    node_dict[t1_id] = {"id": t1_id, "x": t1_pos[0], "y": t1_pos[1], "z": z, "type": "rail_signal", "out_vec": (-ux, -uy)}
    node_dict[t2_id] = {"id": t2_id, "x": t2_pos[0], "y": t2_pos[1], "z": z, "type": "rail_signal", "out_vec": (ux, uy)}
    
    half_len = length / 2.0
    station_fw_edges = []
    station_bw_edges = []
    
    track_specs = []
    if thru_tracks == 0:
        total_tracks = platforms + yards
        spread = 6.0
        start_off = -(total_tracks - 1) * spread / 2.0
        for i in range(total_tracks):
            off = start_off + i * spread
            if i < platforms:
                track_specs.append(('plat', i+1, off, 13.89, False, True))
            else:
                track_specs.append(('yard', i-platforms+1, off, 5.55, True, False))
    else:
        # Center high-speed / inter-city express through-tracks
        track_specs.append(('thru', 1, -2.5, thru_speed, False, False))
        track_specs.append(('thru', 2, 2.5, thru_speed, False, False))
        
        # Flanking platform loops for stopping passenger trains
        if platforms >= 1:
            track_specs.append(('plat', 1, -8.5, 13.89, False, True))
        if platforms >= 2:
            track_specs.append(('plat', 2, 8.5, 13.89, False, True))
        if platforms >= 3:
            track_specs.append(('plat', 3, 14.5, 13.89, False, True))
        for p in range(4, platforms + 1):
            track_specs.append(('plat', p, 14.5 + (p-3)*6.0, 13.89, False, True))
            
        # Outer maintenance and freight siding tracks
        right_most = max(s[2] for s in track_specs)
        for y_idx in range(yards):
            track_specs.append(('yard', y_idx+1, right_most + 6.0 * (y_idx+1), 5.55, True, False))
            
    track_specs.sort(key=lambda s: s[2])
    
    t_lead = t_dist - half_len
    stop_start = t_lead + 30.0
    stop_end = t_lead + length - 30.0
    
    for ttype, tnum, off, speed, is_yard, has_plat in track_specs:
        track_id = f"{stn_id}_{ttype}_{tnum}"
        p1 = (x - ux * half_len + nx * off, y - uy * half_len + ny * off, z)
        p2 = (x + ux * half_len + nx * off, y + uy * half_len + ny * off, z)
        
        shape_str = f"{t1_pos[0]:.2f},{t1_pos[1]:.2f},{t1_pos[2]:.2f} {p1[0]:.2f},{p1[1]:.2f},{p1[2]:.2f} {p2[0]:.2f},{p2[1]:.2f},{p2[2]:.2f} {t2_pos[0]:.2f},{t2_pos[1]:.2f},{t2_pos[2]:.2f}"
        
        edge_fw_id = f"{track_id}_fw"
        edge_bw_id = f"{track_id}_bw"
        
        edge_fw = ET.SubElement(edges_root, 'edge', id=edge_fw_id, **{"from": t1_id, "to": t2_id, "speed": f"{speed:.2f}", "numLanes": "1", "allow": "rail rail_electric", "shape": shape_str, "bidi": edge_bw_id})
        edge_bw = ET.SubElement(edges_root, 'edge', id=edge_bw_id, **{"from": t2_id, "to": t1_id, "speed": f"{speed:.2f}", "numLanes": "1", "allow": "rail rail_electric", "shape": " ".join(reversed(shape_str.split())), "bidi": edge_fw_id})
        
        station_fw_edges.append(edge_fw_id)
        station_bw_edges.append(edge_bw_id)
        
        prof_key = 'high_speed' if speed >= 80.0 else ('freight' if is_yard else 'regional')
        prof = TRACK_PROFILES[prof_key]
        for key in ["capacity_tons", "voltage", "gauge", "material", "wear_rate"]:
            ET.SubElement(edge_fw, 'param', key=key, value=prof[key])
            ET.SubElement(edge_bw, 'param', key=key, value=prof[key])
            
        if ttype == 'thru':
            ET.SubElement(edge_fw, 'param', key="is_through", value="true")
            ET.SubElement(edge_bw, 'param', key="is_through", value="true")
        elif ttype == 'yard':
            ET.SubElement(edge_fw, 'param', key="is_yard", value="true")
            ET.SubElement(edge_bw, 'param', key="is_yard", value="true")
        elif ttype == 'plat':
            ET.SubElement(edge_fw, 'param', key="is_platform", value="true")
            ET.SubElement(edge_bw, 'param', key="is_platform", value="true")
            ET.SubElement(stops_root, 'trainStop', id=f"{stn_id}_p{tnum}_fw", lane=f"{track_id}_fw_0", startPos=f"{stop_start:.1f}", endPos=f"{stop_end:.1f}")
            ET.SubElement(stops_root, 'trainStop', id=f"{stn_id}_p{tnum}_bw", lane=f"{track_id}_bw_0", startPos=f"{stop_start:.1f}", endPos=f"{stop_end:.1f}")
            
    return t1_id, t2_id, station_fw_edges, station_bw_edges

class StationSpec:
    def __init__(self, stn_id, x, y, z, angle, platforms, yards, length=600, thru_tracks=0, thru_speed=83.33):
        self.id = stn_id
        self.x = x
        self.y = y
        self.z = z
        self.angle = angle
        self.platforms = platforms
        self.yards = yards
        self.length = length
        self.thru_tracks = thru_tracks
        self.thru_speed = thru_speed
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
    # Intermediate towns feature 4-track Shinkansen/TGV layouts with central 300 km/h or 120 km/h through-tracks
    stations = {
        # Corridor 1: East-West Trans-Regional High-Speed Trunk
        'City_1': StationSpec('City_1', -13000, 1000, 15, 12.0, platforms=5, yards=2, length=800, thru_tracks=0),
        'Town_1': StationSpec('Town_1', -8800, 1800, 25, 8.0, platforms=2, yards=1, length=400, thru_tracks=2, thru_speed=83.33),
        'City_2': StationSpec('City_2', -4200, 2200, 38, 5.0, platforms=6, yards=2, length=900, thru_tracks=0),
        'Town_2': StationSpec('Town_2', 400, 2000, 30, -2.5, platforms=2, yards=1, length=400, thru_tracks=2, thru_speed=83.33),
        'City_3_EW': StationSpec('City_3_EW', 5200, 1500, 12, -6.0, platforms=4, yards=2, length=900, thru_tracks=0),
        'Town_3': StationSpec('Town_3', 9800, 800, 12, -8.6, platforms=2, yards=1, length=400, thru_tracks=2, thru_speed=83.33),
        'City_4': StationSpec('City_4', 14200, 0, 2, -10.0, platforms=5, yards=2, length=800, thru_tracks=0),

        # Corridor 2: North-South Inter-City Trunk (elevated viaduct passing overhead through City_3_NS)
        'City_5': StationSpec('City_5', 4200, 12500, 60, -86.0, platforms=5, yards=2, length=800, thru_tracks=0),
        'Town_4': StationSpec('Town_4', 4500, 8800, 45, -85.4, platforms=2, yards=1, length=400, thru_tracks=2, thru_speed=33.33),
        'Town_5': StationSpec('Town_5', 4850, 5100, 32, -84.6, platforms=2, yards=1, length=400, thru_tracks=2, thru_speed=33.33),
        'City_3_NS': StationSpec('City_3_NS', 5250, 1500, 26, -83.7, platforms=4, yards=1, length=900, thru_tracks=0),
        'Town_6': StationSpec('Town_6', 5650, -2200, 14, -83.8, platforms=2, yards=1, length=400, thru_tracks=2, thru_speed=33.33),
        'Town_7': StationSpec('Town_7', 6050, -5900, 8, -83.8, platforms=2, yards=1, length=400, thru_tracks=2, thru_speed=33.33),
        'City_6': StationSpec('City_6', 6500, -10000, 2, -83.7, platforms=5, yards=2, length=800, thru_tracks=0),

        # Corridor 3: Northwest Alpine Mountain Line (branches Northwest from City_2)
        'Town_8': StationSpec('Town_8', -7500, 5200, 80, 135.0, platforms=2, yards=1, length=400, thru_tracks=0),
        'Town_9': StationSpec('Town_9', -10500, 8200, 130, 135.0, platforms=2, yards=1, length=400, thru_tracks=0),
        'Depot_1': StationSpec('Depot_1', -13500, 11200, 165, 135.0, platforms=0, yards=4, length=500, thru_tracks=0),

        # Corridor 4: Southern Coastal Arc (Natural parabolic sweep from City_1 to City_6)
        'Town_10': StationSpec('Town_10', -13500, -3200, 10, -80.0, platforms=2, yards=1, length=400, thru_tracks=2, thru_speed=33.33),
        'Town_11': StationSpec('Town_11', -11200, -7200, 6, -42.0, platforms=2, yards=1, length=400, thru_tracks=2, thru_speed=33.33),
        'Depot_2': StationSpec('Depot_2', -5600, -9600, 3, -15.0, platforms=0, yards=4, length=500, thru_tracks=0),
        'Town_12': StationSpec('Town_12', 600, -8400, 2, -8.0, platforms=2, yards=1, length=400, thru_tracks=2, thru_speed=33.33),

        # Heavy Industrial Logistics Depots
        'Depot_3': StationSpec('Depot_3', 7500, 15000, 55, 30.0, platforms=0, yards=4, length=500, thru_tracks=0),
        'Depot_4': StationSpec('Depot_4', 9200, 2800, 18, 20.0, platforms=0, yards=4, length=500, thru_tracks=0),
    }

    for s in stations.values():
        s.t1, s.t2, s.fw_edges, s.bw_edges = build_angled_yard(
            nd, nodes_root, edges_root, stops_root, s.id, s.x, s.y, s.z, s.angle, s.platforms, s.yards, s.length, s.thru_tracks, s.thru_speed
        )

    # Inter-station track definitions with optimized tangents
    corridor_segments = [
        # Corridor 1 (East-West High Speed Trunk - 27 km with Universal Crossovers every ~5-6 km)
        ('City_1', 2, 'Town_1', 1, 'high_speed', 'c1_City_1_Town_1', None, None, None, None, False),
        ('Town_1', 2, 'City_2', 1, 'high_speed', 'c1_Town_1_City_2', None, None, None, None, True),
        ('City_2', 2, 'Town_2', 1, 'high_speed', 'c1_City_2_Town_2', None, None, None, None, True),
        ('Town_2', 2, 'City_3_EW', 1, 'high_speed', 'c1_Town_2_City_3_EW', None, None, None, None, True),
        ('City_3_EW', 2, 'Town_3', 1, 'high_speed', 'c1_City_3_EW_Town_3', None, None, None, None, True),
        ('Town_3', 2, 'City_4', 1, 'high_speed', 'c1_Town_3_City_4', None, None, None, None, False),

        # Corridor 2 (North-South Regional Trunk straight through City_3_NS)
        ('City_5', 2, 'Town_4', 1, 'regional', 'c2_City_5_Town_4', None, None, None, None, False),
        ('Town_4', 2, 'Town_5', 1, 'regional', 'c2_Town_4_Town_5', None, None, None, None, True),
        ('Town_5', 2, 'City_3_NS', 1, 'regional', 'c2_Town_5_City_3_NS', None, None, None, None, False),
        ('City_3_NS', 2, 'Town_6', 1, 'regional', 'c2_City_3_NS_Town_6', None, None, None, None, False),
        ('Town_6', 2, 'Town_7', 1, 'regional', 'c2_Town_6_Town_7', None, None, None, None, True),
        ('Town_7', 2, 'City_6', 1, 'regional', 'c2_Town_7_City_6', None, None, None, None, False),

        # Corridor 3 (Northwest Alpine Line: branches Northwest from City_2)
        ('City_2', 1, 'Town_8', 1, 'regional', 'c3_City_2_Town_8', (-0.85, 0.52), None, None, None, False),
        ('Town_8', 2, 'Town_9', 1, 'regional', 'c3_Town_8_Town_9', None, None, None, None, False),
        ('Town_9', 2, 'Depot_1', 1, 'freight', 'c3_Town_9_Depot_1', None, None, None, None, False),

        # Corridor 4 (Southern Coastal Arc: sweeps naturally from City_1 to City_6)
        ('City_1', 1, 'Town_10', 1, 'regional', 'c4_City_1_Town_10', (-0.35, -0.94), None, None, None, False),
        ('Town_10', 2, 'Town_11', 1, 'regional', 'c4_Town_10_Town_11', None, None, None, None, True),
        ('Town_11', 2, 'Depot_2', 1, 'regional', 'c4_Town_11_Depot_2', None, None, None, None, False),
        ('Depot_2', 2, 'Town_12', 1, 'regional', 'c4_Depot_2_Town_12', None, None, None, None, True),
        ('Town_12', 2, 'City_6', 1, 'regional', 'c4_Town_12_City_6', None, (-0.60, 0.80), None, None, False),

        # Industrial Depot spurs
        ('City_5', 1, 'Depot_3', 1, 'freight', 'spur_City_5_Depot_3', (0.45, 0.89), None, None, None, False),
        ('City_3_EW', 2, 'Depot_4', 1, 'freight', 'spur_City_3_EW_Depot_4', (0.70, 0.71), None, None, None, False),

        # Central Hub transfer track between East-West and North-South stations
        ('City_3_EW', 1, 'City_3_NS', 1, 'regional', 'transfer_City_3_EW_NS', (0.707, 0.707), (-0.707, -0.707), None, None, False),

        # High-Speed Diagonal Bypass (City_2 to City_5)
        ('City_2', 2, 'City_5', 2, 'high_speed', 'bypass_City_2_City_5', (0.80, 0.60), (-0.40, -0.92), None, None, False),
    ]

    mainline_edges_info = []
    for s_from_id, t_from_idx, s_to_id, t_to_idx, prof, track_id, v0_ovr, v1_ovr, cd0, cd1, has_xov in corridor_segments:
        s_from = stations[s_from_id]
        s_to = stations[s_to_id]
        node_from = nd[s_from.t1 if t_from_idx == 1 else s_from.t2]
        node_to = nd[s_to.t1 if t_to_idx == 1 else s_to.t2]
        
        fw_edges, bw_edges, a_from, a_to = create_corridor_track(edges_root, nodes_root, conns_root, track_id, node_from, node_to, prof, v0_ovr, v1_ovr, cd0, cd1, has_xover=has_xov)
        if fw_edges and bw_edges:
            mainline_edges_info.append((node_from['id'], node_to['id'], fw_edges, bw_edges, a_from, a_to))

    # Explicit throat interlocking connections
    for s in stations.values():
        in_m1 = [bw_e[-1] for t_start, t_end, fw_e, bw_e, a_from, a_to in mainline_edges_info if t_start == s.t1] + \
                [fw_e[-1] for t_start, t_end, fw_e, bw_e, a_from, a_to in mainline_edges_info if t_end == s.t1]
        out_m1 = [fw_e[0] for t_start, t_end, fw_e, bw_e, a_from, a_to in mainline_edges_info if t_start == s.t1] + \
                 [bw_e[0] for t_start, t_end, fw_e, bw_e, a_from, a_to in mainline_edges_info if t_end == s.t1]
        for t_start, t_end, fw_e, bw_e, a_from, a_to in mainline_edges_info:
            if t_start == s.t1 and a_from: out_m1.append(a_from)
            if t_end == s.t1 and a_to: out_m1.append(a_to)
                 
        for in_e in in_m1:
            for plat_fw in s.fw_edges:
                ET.SubElement(conns_root, 'connection', **{"from": in_e, "to": plat_fw, "fromLane": "0", "toLane": "0"})
        for plat_bw in s.bw_edges:
            for out_e in out_m1:
                ET.SubElement(conns_root, 'connection', **{"from": plat_bw, "to": out_e, "fromLane": "0", "toLane": "0"})

        in_m2 = [bw_e[-1] for t_start, t_end, fw_e, bw_e, a_from, a_to in mainline_edges_info if t_start == s.t2] + \
                [fw_e[-1] for t_start, t_end, fw_e, bw_e, a_from, a_to in mainline_edges_info if t_end == s.t2]
        out_m2 = [fw_e[0] for t_start, t_end, fw_e, bw_e, a_from, a_to in mainline_edges_info if t_start == s.t2] + \
                 [bw_e[0] for t_start, t_end, fw_e, bw_e, a_from, a_to in mainline_edges_info if t_end == s.t2]
        for t_start, t_end, fw_e, bw_e, a_from, a_to in mainline_edges_info:
            if t_start == s.t2 and a_from: out_m2.append(a_from)
            if t_end == s.t2 and a_to: out_m2.append(a_to)
                 
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
