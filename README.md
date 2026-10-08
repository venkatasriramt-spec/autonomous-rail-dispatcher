# SUMO Dense Railway Network Generator

This repository is dedicated solely to generating a dense, highly structured railway network using SUMO (Simulation of Urban MObility). It produces a fully routable track map with physical speed limits, bi-directional rails, bypassing junctions, and multi-platform stations.

This network is intended to be used as the foundational map for future Reinforcement Learning (RL) scheduling and train kinematic simulations.

## Project Structure

```
.
├── scripts/
│   └── generate_sumo_network.py  # Procedural python generator script
├── network_data/
│   ├── dense_network.nod.xml     # Generated nodes (stations/junctions)
│   ├── dense_network.edg.xml     # Generated tracks (edges & speeds)
│   ├── dense_network.add.xml     # Generated platform placements
│   └── dense_network.net.xml     # The compiled, routable SUMO network
└── README.md
```

## How to Build the Network

If you make any changes to the network layout in the generator script, you can rebuild the network by running:

```bash
python3 scripts/generate_sumo_network.py
```

This will instantly output fresh XML files into the `network_data/` directory and run `netconvert` to compile them.

## Viewing the Network Visually

To see and interact with the physical tracks, you can open the compiled network in Netedit (SUMO's GUI editor).

Run the following command from the root of this project:

```bash
netedit -s network_data/dense_network.net.xml -a network_data/dense_network.add.xml
```
