# SUMO Dense Railway Network Generator

This repository is dedicated solely to generating a dense, highly structured railway **track infrastructure** network using SUMO (Simulation of Urban MObility). It produces a fully routable track map with physical speed limits, bi-directional rails, bypassing junctions, and multi-platform stations.

This network provides the foundational physical infrastructure for future downstream experiments. **Trains, rolling stock, traffic schedules, and routing live in a separate external repository** — this directory strictly maintains physical tracks, junctions, platforms, and signaling.

## Project Structure

```
.
├── scripts/
│   ├── generate_sumo_network.py  # Procedural corridor railway network generator
│   └── plot_network.py           # Network topology visualization & rendering tool
├── network_data/
│   ├── dense_network.nod.xml     # Generated nodes (stations, throats & signals)
│   ├── dense_network.edg.xml     # Generated tracks (edges, lanes & physical speeds)
│   ├── dense_network.con.xml     # Station throat interlocking switch connections
│   ├── dense_network.add.xml     # Generated platform placements (trainStops)
│   ├── dense_network.net.xml     # The compiled, routable SUMO railway network
│   └── railway_topology.xml      # SUMO topology analyzer report (0 error nodes)
├── project_history.md            # Chronological log of how the network evolved
├── README.md
└── .gitignore
```

## How to Build the Network

If you make any changes to the network layout in the generator script, you can rebuild the network by running:

```bash
python3 scripts/generate_sumo_network.py
```

This will instantly output fresh XML files into the `network_data/` directory and compile the network with `netconvert`.

## Viewing the Network Visually

To inspect and interact with the physical tracks, junctions, and block signals in Netedit:

```bash
netedit -s network_data/dense_network.net.xml -a network_data/dense_network.add.xml
```

To render a 2D high-resolution map of the entire network:

```bash
python3 scripts/plot_network.py
```

## Repository Conventions

- This folder is strictly dedicated to **tracks, junctions, signals, and stations**. Trains and scheduling are maintained externally.
- The generated `.xml` network files are intentionally tracked by Git — they are the primary deliverable of this repository.
- Python caches and virtual environments are ignored via `.gitignore`.