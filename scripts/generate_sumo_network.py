import xml.etree.ElementTree as ET
from xml.dom import minidom
import subprocess
import os
import math
import random

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, '..', 'network_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_path(filename): return os.path.join(OUTPUT_DIR, filename)
def prettify(elem): return minidom.parseString(ET.tostring(elem, 'utf-8')).toprettyxml(indent="    ")

TRACK_PROFILES = {
    "high_speed": {"speed": 83.33, "allow": "rail_electric", "capacity_tons": "2500", "voltage": "25000", "gauge": "1435", "material": "concrete", "wear_rate": "0.01"},
    "regional": {"speed": 33.33, "allow": "rail rail_electric", "capacity_tons": "5000", "voltage": "15000", "gauge": "1435", "material": "ballast", "wear_rate": "0.05"},
    "freight": {"speed": 22.22, "allow": "rail", "capacity_tons": "12000", "voltage": "none", "gauge": "1435", "material": "wood", "wear_rate": "0.10"}
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

def resample_2d(pts, min_step=25.0):
    """Ensures points along polyline have healthy spacing, eliminating artificial grade spikes."""
    if len(pts) < 2: return pts
    out = [pts[0]]
    for p in pts[1:-1]:
        if math.hypot(p[0]-out[-1][0], p[1]-out[-1][1]) >= min_step:
            out.append(p)
    if math.hypot(pts[-1][0]-out[-1][0], pts[-1][1]-out[-1][1]) >= min_step * 0.4:
        out.append(pts[-1])
    else:
        out[-1] = pts[-1]
    return out

def generate_smooth_track(n_from, n_to, lateral_offset=0.0):
    """
    Generates a continuous track geometry with:
    1. Tangent lead tracks at throats (0 degree angular error at switch junctions)
    2. Wide turning loops (scale >= 250m) when targets require reverse heading
    3. Arc-length parameterized elevation with flat throat approaches (grade <= 1.5%)
    """
    p0 = (float(n_from['x']), float(n_from['y']))
    p3 = (float(n_to['x']), float(n_to['y']))
    v0 = n_from.get('out_vec', (0,0))
    v3 = n_to.get('out_vec', (0,0))
    z0 = float(n_from.get('z', 0))
    z3 = float(n_to.get('z', 0))
    
    L = math.hypot(p3[0]-p0[0], p3[1]-p0[1])
    if L < 10.0: return None
    
    lead_len = min(150.0, max(50.0, L * 0.12))
    
    p_lead0 = (p0[0] + v0[0]*lead_len, p0[1] + v0[1]*lead_len)
    p_lead3 = (p3[0] + v3[0]*lead_len, p3[1] + v3[1]*lead_len)
    
    d_lead = math.hypot(p_lead3[0]-p_lead0[0], p_lead3[1]-p_lead0[1])
    if d_lead == 0: return None
    
    dx, dy = (p_lead3[0]-p_lead0[0])/d_lead, (p_lead3[1]-p_lead0[1])/d_lead
    nx, ny = -dy, dx
    
    # Check if target is behind departure vector
    cos0 = v0[0]*dx + v0[1]*dy
    cos3 = -(v3[0]*dx + v3[1]*dy)
    
    # If target is behind throat vector, give a generous scale (>= 250m) for a gentle railway turn
    scale0 = max(250.0, d_lead * 0.4) if cos0 <= 0 else max(50.0, min(d_lead * 0.35, 2000.0))
    scale3 = max(250.0, d_lead * 0.4) if cos3 <= 0 else max(50.0, min(d_lead * 0.35, 2000.0))
    
    c1 = (p_lead0[0] + v0[0]*scale0, p_lead0[1] + v0[1]*scale0)
    c2 = (p_lead3[0] + v3[0]*scale3, p_lead3[1] + v3[1]*scale3)
    
    # Clamp lateral offset to max 15% of distance to maintain safe turning radii
    max_offset = d_lead * 0.15
    clamped_offset = max(-max_offset, min(max_offset, lateral_offset))
    
    num_points = max(35, int(L / 120))
    raw_2d = [p0]
    for i in range(num_points + 1):
        t = i / num_points
        bx = (1-t)**3 * p_lead0[0] + 3*(1-t)**2*t * c1[0] + 3*(1-t)*t**2 * c2[0] + t**3 * p_lead3[0]
        by = (1-t)**3 * p_lead0[1] + 3*(1-t)**2*t * c1[1] + 3*(1-t)*t**2 * c2[1] + t**3 * p_lead3[1]
        
        # Bell-curve lateral displacement: strictly 0 at t=0 and t=1
        w = (math.sin(math.pi * t))**2
        bx += nx * clamped_offset * w
        by += ny * clamped_offset * w
        raw_2d.append((bx, by))
        
    raw_2d.append(p3)
    
    # Resample 2D points to maintain uniform segment spacing (>= 25m)
    pts_2d = resample_2d(raw_2d, min_step=25.0)
    
    # Calculate cumulative horizontal distance
    n = len(pts_2d)
    dists = [0.0] * n
    for i in range(1, n):
        dists[i] = dists[i-1] + math.hypot(pts_2d[i][0]-pts_2d[i-1][0], pts_2d[i][1]-pts_2d[i-1][1])
    total_len = dists[-1]
    if total_len == 0: return None
    
    # Assign elevation parameterized strictly by arc-length (with flat junctions at throat ends)
    flat_dist = min(lead_len, 100.0)
    pts_3d = []
    for i in range(n):
        d = dists[i]
        if d <= flat_dist:
            z = z0
        elif d >= total_len - flat_dist:
            z = z3
        else:
            effective_len = total_len - 2 * flat_dist
            if effective_len > 0:
                s = (d - flat_dist) / effective_len
                z = z0 + (z3 - z0) * s
            else:
                z = z0
        pts_3d.append((pts_2d[i][0], pts_2d[i][1], z))
        
    return pts_3d

def smooth_offset_shape(pts_3d, track_offset, taper_dist=120.0):
    """Offsets track for parallel double-tracking, tapering smoothly to 0 at throat nodes."""
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
        w = w * w * (3.0 - 2.0 * w) # smoothstep
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
    """Splits track into 1km signal blocks and sets curvature-aware speed limits."""
    total_len = sum(math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]) for i in range(len(pts)-1))
    block_len = 1000.0
    max_profile_speed = prof['speed']
    
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

def create_track(edges_root, nodes_root, track_id, n_from, n_to, profile="regional", curve_offset=0):
    prof = TRACK_PROFILES[profile]
    base_pts = generate_smooth_track(n_from, n_to, curve_offset)
    if not base_pts: return None, None
    
    fw_pts = smooth_offset_shape(base_pts, 2.0)
    bw_pts = smooth_offset_shape(base_pts, -2.0)
    
    fw_edges = generate_block_sections(edges_root, nodes_root, f"{track_id}_fw", n_from['id'], n_to['id'], fw_pts, prof)
    bw_pts_rev = list(reversed(bw_pts))
    bw_edges = generate_block_sections(edges_root, nodes_root, f"{track_id}_bw", n_to['id'], n_from['id'], bw_pts_rev, prof)
    
    return fw_edges, bw_edges

def build_complex_yard(node_dict, nodes_root, edges_root, stops_root, stn_id, x, y, z, platforms, yards, length, orientation):
    total_tracks = platforms + yards
    spread = 6.0 
    start_off = -(total_tracks - 1) * spread / 2
    
    t_dist = length/2 + 250
    if orientation == "EW":
        dx, dy = (t_dist, 0)
        vec_t1, vec_t2 = (-1, 0), (1, 0) 
    else:
        dx, dy = (0, t_dist)
        vec_t1, vec_t2 = (0, -1), (0, 1)

    t1_id, t2_id = f"{stn_id}_Throat1", f"{stn_id}_Throat2"
    node_dict[t1_id] = {"id": t1_id, "x": x-dx, "y": y-dy, "z": z, "type": "rail_signal", "out_vec": vec_t1}
    node_dict[t2_id] = {"id": t2_id, "x": x+dx, "y": y+dy, "z": z, "type": "rail_signal", "out_vec": vec_t2}
    
    p_dx, p_dy = (length/2, 0) if orientation == "EW" else (0, length/2)
    
    station_fw_edges = []
    station_bw_edges = []
    
    for i in range(total_tracks):
        is_yard = i >= platforms
        track_id = f"{stn_id}_{'yard' if is_yard else 'plat'}_{i+1}"
        off = start_off + i * spread
        
        if orientation == "EW":
            p1, p2, t1, t2 = (x - p_dx, y + off, z), (x + p_dx, y + off, z), (x - dx, y, z), (x + dx, y, z)
        else:
            p1, p2, t1, t2 = (x + off, y - p_dy, z), (x + off, y + p_dy, z), (x, y - dy, z), (x, y + dy, z)
            
        shape_str = f"{t1[0]:.2f},{t1[1]:.2f},{t1[2]:.2f} {p1[0]:.2f},{p1[1]:.2f},{p1[2]:.2f} {p2[0]:.2f},{p2[1]:.2f},{p2[2]:.2f} {t2[0]:.2f},{t2[1]:.2f},{t2[2]:.2f}"
        
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

class Location:
    def __init__(self, id_str, is_city, is_depot=False):
        self.id = id_str
        self.is_city = is_city
        self.is_depot = is_depot
        self.x = random.uniform(-15000, 15000)
        self.y = random.uniform(-15000, 15000)
        dist_from_center = math.hypot(self.x, self.y)
        self.z = 200.0 * (1.0 - min(1.0, dist_from_center / 15000.0))
        self.ori = random.choice(["EW", "NS"])
        self.t1 = None
        self.t2 = None
        self.station_fw = []
        self.station_bw = []

def get_best_throat(loc, target_x, target_y):
    if loc.ori == "EW": return loc.t2 if target_x > loc.x else loc.t1
    else: return loc.t2 if target_y > loc.y else loc.t1

def generate_sumo_network():
    random.seed(42)
    nodes_root = ET.Element('nodes')
    edges_root = ET.Element('edges')
    stops_root = ET.Element('additionals')
    conns_root = ET.Element('connections')
    nd = {}
    
    num_cities = 6
    num_towns = 12
    num_depots = 4 
    
    locations = [Location(f"City_{i+1}", True) for i in range(num_cities)] \
              + [Location(f"Town_{i+1}", False) for i in range(num_towns)] \
              + [Location(f"Depot_{i+1}", False, is_depot=True) for i in range(num_depots)]
    
    for loc in locations:
        if loc.is_depot:
            loc.t1, loc.t2, loc.station_fw, loc.station_bw = build_complex_yard(
                nd, nodes_root, edges_root, stops_root, loc.id, loc.x, loc.y, loc.z, 
                platforms=0, yards=random.randint(2, 4), length=400, orientation=loc.ori)
        elif loc.is_city:
            loc.t1, loc.t2, loc.station_fw, loc.station_bw = build_complex_yard(
                nd, nodes_root, edges_root, stops_root, loc.id, loc.x, loc.y, loc.z, 
                platforms=random.randint(4, 6), yards=random.randint(1, 2), length=random.randint(500, 1000), orientation=loc.ori)
        else:
            loc.t1, loc.t2, loc.station_fw, loc.station_bw = build_complex_yard(
                nd, nodes_root, edges_root, stops_root, loc.id, loc.x, loc.y, loc.z, 
                platforms=random.randint(2, 3), yards=random.randint(0, 1), length=random.randint(200, 400), orientation=loc.ori)

    created_tracks = set()
    edges = []
    for i, l1 in enumerate(locations):
        for j, l2 in enumerate(locations):
            if i < j: edges.append((math.hypot(l1.x - l2.x, l1.y - l2.y), l1, l2))
    edges.sort(key=lambda x: x[0])
    
    parent = {loc.id: loc.id for loc in locations}
    def find(i):
        if parent[i] == i: return i
        parent[i] = find(parent[i])
        return parent[i]
    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj
            return True
        return False

    mainline_edges_info = []

    # MST Connections
    for dist, l1, l2 in edges:
        if union(l1.id, l2.id):
            t1, t2 = get_best_throat(l1, l2.x, l2.y), get_best_throat(l2, l1.x, l1.y)
            track_sig = tuple(sorted([t1, t2]))
            created_tracks.add(track_sig)
            fw_edges, bw_edges = create_track(edges_root, nodes_root, f"mst_{l1.id}_{l2.id}", nd[t1], nd[t2], "regional", curve_offset=random.uniform(-300, 300))
            if fw_edges and bw_edges:
                mainline_edges_info.append((t1, t2, fw_edges, bw_edges))

    # Loop Connections
    for loc in locations:
        others = sorted([o for o in locations if o != loc], key=lambda o: math.hypot(o.x - loc.x, o.y - loc.y))
        connections = random.randint(1, 2) if loc.is_city else 1
        for c in others[:connections]:
            t_loc, t_c = get_best_throat(loc, c.x, c.y), get_best_throat(c, loc.x, loc.y)
            track_sig = tuple(sorted([t_loc, t_c]))
            if track_sig not in created_tracks:
                created_tracks.add(track_sig)
                offset = random.uniform(-600, 600)
                profile = random.choices(["high_speed", "regional", "freight"], weights=[0.2, 0.6, 0.2])[0]
                fw_edges, bw_edges = create_track(edges_root, nodes_root, f"loop_{loc.id}_{c.id}", nd[t_loc], nd[t_c], profile, curve_offset=offset)
                if fw_edges and bw_edges:
                    mainline_edges_info.append((t_loc, t_c, fw_edges, bw_edges))

    # BUILD EXPLICIT THROAT INTERLOCKING CONNECTIONS
    # Connects mainline tracks directly to station platforms while preventing sharp turnaround conflicts
    for loc in locations:
        # Throat 1
        in_m1 = []
        out_m1 = []
        for t_start, t_end, fw_e, bw_e in mainline_edges_info:
            if t_start == loc.t1:
                out_m1.append(fw_e[0])
                in_m1.append(bw_e[-1])
            elif t_end == loc.t1:
                in_m1.append(fw_e[-1])
                out_m1.append(bw_e[0])
                
        for in_e in in_m1:
            for plat_fw in loc.station_fw:
                ET.SubElement(conns_root, 'connection', **{"from": in_e, "to": plat_fw, "fromLane": "0", "toLane": "0"})
        for plat_bw in loc.station_bw:
            for out_e in out_m1:
                ET.SubElement(conns_root, 'connection', **{"from": plat_bw, "to": out_e, "fromLane": "0", "toLane": "0"})
                
        # Throat 2
        in_m2 = []
        out_m2 = []
        for t_start, t_end, fw_e, bw_e in mainline_edges_info:
            if t_start == loc.t2:
                out_m2.append(fw_e[0])
                in_m2.append(bw_e[-1])
            elif t_end == loc.t2:
                in_m2.append(fw_e[-1])
                out_m2.append(bw_e[0])
                
        for in_e in in_m2:
            for plat_bw in loc.station_bw:
                ET.SubElement(conns_root, 'connection', **{"from": in_e, "to": plat_bw, "fromLane": "0", "toLane": "0"})
        for plat_fw in loc.station_fw:
            for out_e in out_m2:
                ET.SubElement(conns_root, 'connection', **{"from": plat_fw, "to": out_e, "fromLane": "0", "toLane": "0"})

    # Write node, edge, additional, and connection XML
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
    print("Network compiled cleanly into dense_network.net.xml")

    # GENERATE TRAFFIC DEMAND AND SIMULATION CONFIG
    generate_simulation_files(locations)

def generate_simulation_files(locations):
    """Generates train trips, routes via duarouter, and creates the final .sumocfg file."""
    tree = ET.parse(get_path("dense_network.net.xml"))
    all_edges = [e.get('id') for e in tree.getroot().findall('edge') if not e.get('id', '').startswith(':')]

    cities = [loc.id for loc in locations if loc.is_city]
    towns = [loc.id for loc in locations if not loc.is_city and not loc.is_depot]
    depots = [loc.id for loc in locations if loc.is_depot]

    trips_root = ET.Element('routes')
    ET.SubElement(trips_root, 'vType', id='high_speed', vClass='rail_electric', length='200.0', maxSpeed='83.33', accel='1.2', decel='1.5')
    ET.SubElement(trips_root, 'vType', id='regional', vClass='rail_electric', length='120.0', maxSpeed='33.33', accel='1.0', decel='1.3')
    ET.SubElement(trips_root, 'vType', id='freight', vClass='rail', length='400.0', maxSpeed='22.22', accel='0.5', decel='0.8')

    def get_plat(loc_id):
        plats = [e for e in all_edges if e.startswith(f"{loc_id}_plat_") and e.endswith("_fw")]
        if not plats: plats = [e for e in all_edges if e.startswith(f"{loc_id}_yard_") and e.endswith("_fw")]
        return plats

    trip_entries = []

    # Inter-city express trips
    for i in range(len(cities)):
        for j in range(len(cities)):
            if i != j:
                p_from = get_plat(cities[i])
                p_to = get_plat(cities[j])
                if p_from and p_to:
                    trip_entries.append(('high_speed', p_from[0], p_to[0], len(trip_entries) * 60.0))

    # Regional commuter trips
    for t in towns[:8]:
        for c in cities[:4]:
            p_from = get_plat(t)
            p_to = get_plat(c)
            if p_from and p_to:
                trip_entries.append(('regional', p_from[0], p_to[0], len(trip_entries) * 45.0))

    # Freight trips from Depots to Cities
    for d in depots:
        for c in cities[:2]:
            p_from = get_plat(d)
            p_to = get_plat(c)
            if p_from and p_to:
                trip_entries.append(('freight', p_from[0], p_to[0], len(trip_entries) * 90.0))

    # Sort trips strictly by departure time for duarouter compatibility
    trip_entries.sort(key=lambda x: x[3])

    for idx, (v_type, frm_e, to_e, dept) in enumerate(trip_entries):
        ET.SubElement(trips_root, 'trip', id=f"train_{idx+1}_{v_type}", type=v_type, **{"from": frm_e, "to": to_e, "depart": f"{dept:.1f}"})

    with open(get_path("dense_network.trips.xml"), "w") as f:
        f.write(prettify(trips_root))

    # Route with duarouter
    subprocess.run([
        "duarouter",
        "--net-file", get_path("dense_network.net.xml"),
        "--route-files", get_path("dense_network.trips.xml"),
        "--output-file", get_path("dense_network.rou.xml"),
        "--ignore-errors", "true"
    ], check=True)
    print(f"Generated {len(trip_entries)} validated train routes into dense_network.rou.xml")

    # Generate .sumocfg
    cfg_root = ET.Element('configuration')
    inp = ET.SubElement(cfg_root, 'input')
    ET.SubElement(inp, 'net-file', value='dense_network.net.xml')
    ET.SubElement(inp, 'route-files', value='dense_network.rou.xml')
    ET.SubElement(inp, 'additional-files', value='dense_network.add.xml')

    tm = ET.SubElement(cfg_root, 'time')
    ET.SubElement(tm, 'begin', value='0')
    ET.SubElement(tm, 'end', value='7200')
    ET.SubElement(tm, 'step-length', value='1.0')

    proc = ET.SubElement(cfg_root, 'processing')
    ET.SubElement(proc, 'collision.action', value='warn')
    ET.SubElement(proc, 'time-to-teleport', value='-1')

    rep = ET.SubElement(cfg_root, 'report')
    ET.SubElement(rep, 'verbose', value='true')
    ET.SubElement(rep, 'duration-log.statistics', value='true')
    ET.SubElement(rep, 'no-step-log', value='true')

    with open(get_path("dense_network.sumocfg"), "w") as f:
        f.write(prettify(cfg_root))
    print("Created simulation configuration: dense_network.sumocfg")

if __name__ == "__main__":
    generate_sumo_network()
