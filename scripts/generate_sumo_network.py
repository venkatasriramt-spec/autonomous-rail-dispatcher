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
    "high_speed": {"speed": "83.33", "allow": "rail_electric", "capacity_tons": "2500", "voltage": "25000", "gauge": "1435", "material": "concrete", "wear_rate": "0.01"},
    "regional": {"speed": "33.33", "allow": "rail rail_electric", "capacity_tons": "5000", "voltage": "15000", "gauge": "1435", "material": "ballast", "wear_rate": "0.05"},
    "freight": {"speed": "22.22", "allow": "rail", "capacity_tons": "12000", "voltage": "none", "gauge": "1435", "material": "wood", "wear_rate": "0.10"}
}

def cubic_bezier(p0, p1, p2, p3, num_points=30):
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        x = (1-t)**3 * p0[0] + 3*(1-t)**2 * t * p1[0] + 3*(1-t) * t**2 * p2[0] + t**3 * p3[0]
        y = (1-t)**3 * p0[1] + 3*(1-t)**2 * t * p1[1] + 3*(1-t) * t**2 * p2[1] + t**3 * p3[1]
        z = (1-t)**3 * p0[2] + 3*(1-t)**2 * t * p1[2] + 3*(1-t) * t**2 * p2[2] + t**3 * p3[2]
        points.append(f"{x:.2f},{y:.2f},{z:.2f}")
    return " ".join(points)

def generate_shape(n_from, n_to, offset=0):
    p0 = (float(n_from['x']), float(n_from['y']), float(n_from.get('z', 0)))
    p3 = (float(n_to['x']), float(n_to['y']), float(n_to.get('z', 0)))
    v0 = n_from.get('out_vec', (0,0))
    v3 = n_to.get('out_vec', (0,0))
    
    L = math.hypot(p3[0]-p0[0], p3[1]-p0[1])
    if L == 0: return None
    
    # Calculate direction vectors to determine if we are pointing towards or away from target
    dx, dy = (p3[0]-p0[0])/L, (p3[1]-p0[1])/L
    cos0 = v0[0]*dx + v0[1]*dy
    cos3 = -(v3[0]*dx + v3[1]*dy)
    
    # Dynamic scaling: Use tight curves if pointing away, smooth long sweeps if pointing towards
    scale0 = L * 0.3 if cos0 > 0 else max(300, L * 0.1)
    scale3 = L * 0.3 if cos3 > 0 else max(300, L * 0.1)
    
    # Hard cap the control points to prevent 2-kilometer lasso loops
    scale0 = min(scale0, 1000)
    scale3 = min(scale3, 1000)
    
    # P1 is pushed straight out of the first station's throat
    p1 = (p0[0] + v0[0]*scale0, p0[1] + v0[1]*scale0, p0[2] + (p3[2]-p0[2])*0.33)
    # P2 is pushed straight out of the destination station's throat
    p2 = (p3[0] + v3[0]*scale3, p3[1] + v3[1]*scale3, p0[2] + (p3[2]-p0[2])*0.66)
    
    if offset != 0:
        nx, ny = -dy, dx
        p1 = (p1[0] + nx*offset, p1[1] + ny*offset, p1[2])
        p2 = (p2[0] + nx*offset, p2[1] + ny*offset, p2[2])
        
    return cubic_bezier(p0, p1, p2, p3)

def create_track(edges_root, track_id, n_from, n_to, profile="regional", curve_offset=0):
    prof = TRACK_PROFILES[profile]
    shape = generate_shape(n_from, n_to, curve_offset)
    for direction, frm, to in [("fw", n_from['id'], n_to['id']), ("bw", n_to['id'], n_from['id'])]:
        edge = ET.SubElement(edges_root, 'edge', id=f"{track_id}_{direction}", **{"from": frm, "to": to, "speed": prof['speed'], "numLanes": "1", "allow": prof['allow']})
        if shape: edge.set("shape", shape if direction == "fw" else " ".join(reversed(shape.split())))
        for key in ["capacity_tons", "voltage", "gauge", "material", "wear_rate"]: ET.SubElement(edge, 'param', key=key, value=prof[key])

def build_complex_yard(node_dict, edges_root, stops_root, stn_id, x, y, z, platforms, yards, length, orientation):
    total_tracks = platforms + yards
    spread = 6.0 
    start_off = -(total_tracks - 1) * spread / 2
    
    t_dist = length/2 + 250
    if orientation == "EW":
        dx, dy = (t_dist, 0)
        vec_t1, vec_t2 = (-1, 0), (1, 0) # Outward pointing vectors
    else:
        dx, dy = (0, t_dist)
        vec_t1, vec_t2 = (0, -1), (0, 1)

    t1_id, t2_id = f"{stn_id}_Throat1", f"{stn_id}_Throat2"
    node_dict[t1_id] = {"id": t1_id, "x": x-dx, "y": y-dy, "z": z, "type": "rail_signal", "out_vec": vec_t1}
    node_dict[t2_id] = {"id": t2_id, "x": x+dx, "y": y+dy, "z": z, "type": "rail_signal", "out_vec": vec_t2}
    
    p_dx, p_dy = (length/2, 0) if orientation == "EW" else (0, length/2)
    
    for i in range(total_tracks):
        is_yard = i >= platforms
        track_id = f"{stn_id}_{'yard' if is_yard else 'plat'}_{i+1}"
        off = start_off + i * spread
        
        if orientation == "EW":
            p1, p2, t1, t2 = (x - p_dx, y + off, z), (x + p_dx, y + off, z), (x - dx, y, z), (x + dx, y, z)
        else:
            p1, p2, t1, t2 = (x + off, y - p_dy, z), (x + off, y + p_dy, z), (x, y - dy, z), (x, y + dy, z)
            
        shape_str = f"{t1[0]:.2f},{t1[1]:.2f},{t1[2]:.2f} {p1[0]:.2f},{p1[1]:.2f},{p1[2]:.2f} {p2[0]:.2f},{p2[1]:.2f},{p2[2]:.2f} {t2[0]:.2f},{t2[1]:.2f},{t2[2]:.2f}"
        
        direction = "fw" if i % 2 == 0 else "bw"
        frm, to = (t1_id, t2_id) if direction == "fw" else (t2_id, t1_id)
        speed = "13.89" if not is_yard else "5.55"
        
        edge = ET.SubElement(edges_root, 'edge', id=track_id, **{"from": frm, "to": to, "speed": speed, "numLanes": "1", "allow": "rail rail_electric", "shape": shape_str})
        if is_yard:
            ET.SubElement(edge, 'param', key="is_yard", value="true")
        else:
            # Only put stops on platform tracks!
            ET.SubElement(stops_root, 'trainStop', id=f"{stn_id}_p{i+1}", lane=f"{track_id}_0", startPos="50", endPos=str(length-50))
            
    return t1_id, t2_id

class Location:
    def __init__(self, id_str, is_city, is_depot=False):
        self.id = id_str
        self.is_city = is_city
        self.is_depot = is_depot
        self.x = random.uniform(-15000, 15000)
        self.y = random.uniform(-15000, 15000)
        self.z = random.uniform(0, 400)
        self.ori = random.choice(["EW", "NS"])
        self.t1 = None
        self.t2 = None

def get_best_throat(loc, target_x, target_y):
    if loc.ori == "EW": return loc.t2 if target_x > loc.x else loc.t1
    else: return loc.t2 if target_y > loc.y else loc.t1

def generate_sumo_network():
    random.seed(42)
    nodes_root, edges_root, stops_root = ET.Element('nodes'), ET.Element('edges'), ET.Element('additionals')
    nd = {}
    
    num_cities = 6
    num_towns = 12
    num_depots = 4 # Pure parking spots/maintenance yards, NO passenger platforms!
    
    locations = [Location(f"City_{i+1}", True) for i in range(num_cities)] \
              + [Location(f"Town_{i+1}", False) for i in range(num_towns)] \
              + [Location(f"Depot_{i+1}", False, is_depot=True) for i in range(num_depots)]
    
    for loc in locations:
        if loc.is_depot:
            loc.t1, loc.t2 = build_complex_yard(nd, edges_root, stops_root, loc.id, loc.x, loc.y, loc.z, 
                                                platforms=0, yards=random.randint(4, 8), length=400, orientation=loc.ori)
        elif loc.is_city:
            loc.t1, loc.t2 = build_complex_yard(nd, edges_root, stops_root, loc.id, loc.x, loc.y, loc.z, 
                                                platforms=random.randint(6, 12), yards=random.randint(3, 8), length=random.randint(500, 1000), orientation=loc.ori)
        else:
            loc.t1, loc.t2 = build_complex_yard(nd, edges_root, stops_root, loc.id, loc.x, loc.y, loc.z, 
                                                platforms=random.randint(2, 4), yards=random.randint(0, 2), length=random.randint(200, 400), orientation=loc.ori)

    created_tracks = set()

    # MST
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

    for dist, l1, l2 in edges:
        if union(l1.id, l2.id):
            t1, t2 = get_best_throat(l1, l2.x, l2.y), get_best_throat(l2, l1.x, l1.y)
            track_sig = tuple(sorted([t1, t2]))
            created_tracks.add(track_sig)
            create_track(edges_root, f"mst_{l1.id}_{l2.id}", nd[t1], nd[t2], "regional", curve_offset=random.uniform(-400, 400))

    # LOOPS
    for loc in locations:
        others = sorted([o for o in locations if o != loc], key=lambda o: math.hypot(o.x - loc.x, o.y - loc.y))
        connections = random.randint(1, 2) if loc.is_city else 1
        for c in others[:connections]:
            t_loc, t_c = get_best_throat(loc, c.x, c.y), get_best_throat(c, loc.x, loc.y)
            track_sig = tuple(sorted([t_loc, t_c]))
            if track_sig not in created_tracks:
                created_tracks.add(track_sig)
                offset = random.uniform(-1200, 1200)
                profile = random.choices(["high_speed", "regional", "freight"], weights=[0.2, 0.6, 0.2])[0]
                create_track(edges_root, f"loop_{loc.id}_{c.id}", nd[t_loc], nd[t_c], profile, curve_offset=offset)

    for n in nd.values(): ET.SubElement(nodes_root, 'node', **{k:str(v) for k,v in n.items() if k != 'out_vec'})
    with open(get_path("dense_network.nod.xml"), "w") as f: f.write(prettify(nodes_root))
    with open(get_path("dense_network.edg.xml"), "w") as f: f.write(prettify(edges_root))
    with open(get_path("dense_network.add.xml"), "w") as f: f.write(prettify(stops_root))

    subprocess.run(["netconvert", "--node-files", get_path("dense_network.nod.xml"), "--edge-files", get_path("dense_network.edg.xml"), "--output-file", get_path("dense_network.net.xml"), "--junctions.join", "true"], check=True)
    print("Done! Completely random procedural map generated.")

if __name__ == "__main__": generate_sumo_network()
