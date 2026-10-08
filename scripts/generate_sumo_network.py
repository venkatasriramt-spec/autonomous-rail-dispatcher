import xml.etree.ElementTree as ET
from xml.dom import minidom
import subprocess
import os
import math

# Define output directory relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, '..', 'network_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_path(filename):
    return os.path.join(OUTPUT_DIR, filename)

def prettify(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="    ")

# --- PROFILES ---
TRACK_PROFILES = {
    "high_speed": {
        "speed": "83.33", # 300 km/h
        "allow": "rail_electric",
        "capacity_tons": "2500",
        "voltage": "25000",
        "gauge": "1435",
        "material": "concrete_slab",
        "wear_rate": "0.01"
    },
    "regional": {
        "speed": "33.33", # 120 km/h
        "allow": "rail rail_electric",
        "capacity_tons": "5000",
        "voltage": "15000",
        "gauge": "1435",
        "material": "ballast_concrete_sleeper",
        "wear_rate": "0.05"
    },
    "freight_heavy": {
        "speed": "22.22", # 80 km/h
        "allow": "rail",
        "capacity_tons": "10000",
        "voltage": "none",
        "gauge": "1435",
        "material": "ballast_wood_sleeper",
        "wear_rate": "0.10"
    }
}

# --- MATH HELPERS ---
def quadratic_bezier(p0, p1, p2, num_points=20):
    """Generates points along a quadratic Bezier curve."""
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        x = (1-t)**2 * p0[0] + 2*(1-t)*t * p1[0] + t**2 * p2[0]
        y = (1-t)**2 * p0[1] + 2*(1-t)*t * p1[1] + t**2 * p2[1]
        z = (1-t)**2 * p0[2] + 2*(1-t)*t * p1[2] + t**2 * p2[2]
        points.append(f"{x:.2f},{y:.2f},{z:.2f}")
    return " ".join(points)

def generate_shape(n_from_data, n_to_data, curve_offset=0):
    """Generates a shape string. If curve_offset is 0, returns None (straight line)."""
    if curve_offset == 0:
        return None
    
    p0 = (float(n_from_data['x']), float(n_from_data['y']), float(n_from_data.get('z', 0)))
    p2 = (float(n_to_data['x']), float(n_to_data['y']), float(n_to_data.get('z', 0)))
    
    # Midpoint
    mid_x = (p0[0] + p2[0]) / 2
    mid_y = (p0[1] + p2[1]) / 2
    mid_z = (p0[2] + p2[2]) / 2
    
    # Calculate normal vector for the offset
    dx = p2[0] - p0[0]
    dy = p2[1] - p0[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return None
    
    nx = -dy / length
    ny = dx / length
    
    # Control point (offset orthogonally from midpoint)
    p1 = (mid_x + nx * curve_offset, mid_y + ny * curve_offset, mid_z)
    
    return quadratic_bezier(p0, p1, p2)

# --- BUILDER FUNCTIONS ---
def create_bidirectional_track(edges_root, track_id, n_from_data, n_to_data, profile="regional", curve_offset=0):
    """Creates bidirectional tracks with physics profiles and optional curves."""
    prof = TRACK_PROFILES[profile]
    shape = generate_shape(n_from_data, n_to_data, curve_offset)
    
    for direction, frm, to in [("fw", n_from_data['id'], n_to_data['id']), ("bw", n_to_data['id'], n_from_data['id'])]:
        edge = ET.SubElement(edges_root, 'edge', id=f"{track_id}_{direction}", 
                             **{"from": frm, "to": to, "speed": prof['speed'], "numLanes": "1", "allow": prof['allow']})
        
        if shape:
            # Reverse shape coordinates for the backward track
            edge.set("shape", shape if direction == "fw" else " ".join(reversed(shape.split())))
            
        # Embed physical metadata as parameters for RL
        for key in ["capacity_tons", "voltage", "gauge", "material", "wear_rate"]:
            ET.SubElement(edge, 'param', key=key, value=prof[key])

def add_station(stops_root, station_id, edge_id, platforms=1, length=200):
    for i in range(platforms):
        ET.SubElement(stops_root, 'trainStop', id=f"{station_id}_p{i+1}", lane=f"{edge_id}_0", startPos=str(10 + i*length), endPos=str(10 + i*length + length - 10))

def generate_sumo_network():
    print(f"Generating dense, curved, elevated railway network in {OUTPUT_DIR}...")
    
    # 1. NODES (Added Z axis for elevation)
    nodes_root = ET.Element('nodes')
    nodes_data = [
        {"id": "Capital_Hub", "x": "0", "y": "0", "z": "0", "type": "rail_signal"},
        {"id": "North_City", "x": "0", "y": "6000", "z": "150", "type": "rail_signal"}, # 150m elevation (mountain)
        {"id": "East_City", "x": "6000", "y": "0", "z": "0", "type": "rail_signal"},
        {"id": "West_City", "x": "-5000", "y": "0", "z": "50", "type": "rail_signal"},
        {"id": "Sub_North_1", "x": "0", "y": "2000", "z": "50", "type": "rail_signal"},
        {"id": "Sub_North_2", "x": "0", "y": "4000", "z": "100", "type": "rail_signal"},
        {"id": "Sub_East_1", "x": "2000", "y": "0", "z": "0", "type": "rail_signal"},
        {"id": "Sub_East_2", "x": "4000", "y": "0", "z": "0", "type": "rail_signal"},
        {"id": "Sub_West_1", "x": "-2500", "y": "0", "z": "25", "type": "rail_signal"},
        {"id": "Junction_NE", "x": "4000", "y": "4000", "z": "200", "type": "rail_signal"} # Mountain pass
    ]
    node_dict = {n['id']: n for n in nodes_data}
    
    for n in nodes_data:
        ET.SubElement(nodes_root, 'node', id=n['id'], x=n['x'], y=n['y'], z=n['z'], type=n['type'])
    with open(get_path("dense_network.nod.xml"), "w") as f: f.write(prettify(nodes_root))

    # 2. EDGES (Tracks with curves, elevation gradients, and profiles)
    edges_root = ET.Element('edges')
    
    # Main Line North (Gradual climb, straight)
    create_bidirectional_track(edges_root, "track_cap_n1", node_dict["Capital_Hub"], node_dict["Sub_North_1"], profile="regional")
    create_bidirectional_track(edges_root, "track_n1_n2", node_dict["Sub_North_1"], node_dict["Sub_North_2"], profile="regional")
    create_bidirectional_track(edges_root, "track_n2_nCity", node_dict["Sub_North_2"], node_dict["North_City"], profile="regional")
    
    # Main Line East (Flat, straight)
    create_bidirectional_track(edges_root, "track_cap_e1", node_dict["Capital_Hub"], node_dict["Sub_East_1"], profile="regional")
    create_bidirectional_track(edges_root, "track_e1_e2", node_dict["Sub_East_1"], node_dict["Sub_East_2"], profile="regional")
    create_bidirectional_track(edges_root, "track_e2_eCity", node_dict["Sub_East_2"], node_dict["East_City"], profile="regional")
    
    # Main Line West (Gentle curve to avoid a lake, heavy freight supported)
    create_bidirectional_track(edges_root, "track_cap_w1", node_dict["Capital_Hub"], node_dict["Sub_West_1"], profile="freight_heavy", curve_offset=-800)
    create_bidirectional_track(edges_root, "track_w1_wCity", node_dict["Sub_West_1"], node_dict["West_City"], profile="freight_heavy", curve_offset=800)
    
    # High-Speed Mountain Bypass (North to East, very curvy to handle the mountains, high elevation)
    create_bidirectional_track(edges_root, "track_bypass_n_ne", node_dict["North_City"], node_dict["Junction_NE"], profile="high_speed", curve_offset=1500)
    create_bidirectional_track(edges_root, "track_bypass_ne_e", node_dict["Junction_NE"], node_dict["East_City"], profile="high_speed", curve_offset=-1500)

    with open(get_path("dense_network.edg.xml"), "w") as f: f.write(prettify(edges_root))

    # 3. STOPS (Stations)
    stops_root = ET.Element('additionals')
    add_station(stops_root, "Station_Capital", "track_cap_n1_fw", platforms=4, length=300)
    add_station(stops_root, "Station_North_City", "track_n2_nCity_fw", platforms=3, length=250)
    add_station(stops_root, "Station_East_City", "track_e2_eCity_fw", platforms=3, length=250)
    add_station(stops_root, "Station_West_City", "track_w1_wCity_fw", platforms=2, length=200)
    add_station(stops_root, "Station_Sub_N1", "track_cap_n1_fw", platforms=1, length=150)
    add_station(stops_root, "Station_Sub_N2", "track_n1_n2_fw", platforms=1, length=150)
    add_station(stops_root, "Station_Sub_E1", "track_cap_e1_fw", platforms=1, length=150)
    add_station(stops_root, "Station_Sub_E2", "track_e1_e2_fw", platforms=1, length=150)
    add_station(stops_root, "Station_Sub_W1", "track_cap_w1_fw", platforms=1, length=150)
    with open(get_path("dense_network.add.xml"), "w") as f: f.write(prettify(stops_root))

    print("XML definitions written. Running netconvert...")
    subprocess.run([
        "netconvert",
        "--node-files", get_path("dense_network.nod.xml"),
        "--edge-files", get_path("dense_network.edg.xml"),
        "--output-file", get_path("dense_network.net.xml"),
        "--junctions.join", "true"
    ], check=True)
    print("Done! Network compiled successfully.")

if __name__ == "__main__":
    generate_sumo_network()
