import xml.etree.ElementTree as ET
from xml.dom import minidom
import subprocess
import os

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

def create_bidirectional_track(edges_root, track_id, n_from, n_to, speed="33.33", allow="rail rail_electric", shape=None):
    """Helper to create two parallel tracks for bidirectional train traffic."""
    e1 = ET.SubElement(edges_root, 'edge', id=f"{track_id}_fw", **{"from": n_from, "to": n_to, "speed": speed, "numLanes": "1", "allow": allow})
    if shape: e1.set("shape", shape)
    
    e2 = ET.SubElement(edges_root, 'edge', id=f"{track_id}_bw", **{"from": n_to, "to": n_from, "speed": speed, "numLanes": "1", "allow": allow})
    if shape: e2.set("shape", " ".join(reversed(shape.split())))

def add_station(stops_root, station_id, edge_id, platforms=1, length=200):
    """Helper to add platforms/stops to an edge."""
    for i in range(platforms):
        ET.SubElement(stops_root, 'trainStop', id=f"{station_id}_p{i+1}", lane=f"{edge_id}_0", startPos=str(10 + i*length), endPos=str(10 + i*length + length - 10))

def generate_sumo_network():
    print(f"Generating dense railway network in {OUTPUT_DIR}...")
    
    # 1. NODES
    nodes_root = ET.Element('nodes')
    nodes_data = [
        {"id": "Capital_Hub", "x": "0", "y": "0", "type": "rail_signal"},
        {"id": "North_City", "x": "0", "y": "6000", "type": "rail_signal"},
        {"id": "East_City", "x": "6000", "y": "0", "type": "rail_signal"},
        {"id": "West_City", "x": "-5000", "y": "0", "type": "rail_signal"},
        {"id": "Sub_North_1", "x": "0", "y": "2000", "type": "rail_signal"},
        {"id": "Sub_North_2", "x": "0", "y": "4000", "type": "rail_signal"},
        {"id": "Sub_East_1", "x": "2000", "y": "0", "type": "rail_signal"},
        {"id": "Sub_East_2", "x": "4000", "y": "0", "type": "rail_signal"},
        {"id": "Sub_West_1", "x": "-2500", "y": "0", "type": "rail_signal"},
        {"id": "Junction_NE", "x": "4000", "y": "4000", "type": "rail_signal"}
    ]
    for n in nodes_data:
        ET.SubElement(nodes_root, 'node', id=n['id'], x=n['x'], y=n['y'], type=n['type'])
    with open(get_path("dense_network.nod.xml"), "w") as f: f.write(prettify(nodes_root))

    # 2. EDGES (Tracks)
    edges_root = ET.Element('edges')
    create_bidirectional_track(edges_root, "track_cap_n1", "Capital_Hub", "Sub_North_1", speed="33.33")
    create_bidirectional_track(edges_root, "track_n1_n2", "Sub_North_1", "Sub_North_2", speed="33.33")
    create_bidirectional_track(edges_root, "track_n2_nCity", "Sub_North_2", "North_City", speed="33.33")
    create_bidirectional_track(edges_root, "track_cap_e1", "Capital_Hub", "Sub_East_1", speed="33.33")
    create_bidirectional_track(edges_root, "track_e1_e2", "Sub_East_1", "Sub_East_2", speed="33.33")
    create_bidirectional_track(edges_root, "track_e2_eCity", "Sub_East_2", "East_City", speed="33.33")
    create_bidirectional_track(edges_root, "track_cap_w1", "Capital_Hub", "Sub_West_1", speed="27.78")
    create_bidirectional_track(edges_root, "track_w1_wCity", "Sub_West_1", "West_City", speed="27.78")
    create_bidirectional_track(edges_root, "track_bypass_n_ne", "North_City", "Junction_NE", speed="44.44")
    create_bidirectional_track(edges_root, "track_bypass_ne_e", "Junction_NE", "East_City", speed="44.44")
    with open(get_path("dense_network.edg.xml"), "w") as f: f.write(prettify(edges_root))

    # 3. STOPS (Stations & Platforms)
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
    
    # 4. RUN NETCONVERT
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
