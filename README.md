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
│   ├── dense_network.con.xml     # Station throat interlocking connections
│   ├── dense_network.add.xml     # Generated platform placements
│   ├── dense_network.rou.xml     # Validated train schedules/routes
│   ├── dense_network.sumocfg     # Ready-to-run SUMO simulation configuration
│   └── dense_network.net.xml     # The compiled, routable SUMO network
├── project_history.md            # Chronological log of how the network evolved
├── README.md
└── .gitignore
```

## How to Build the Network

If you make any changes to the network layout in the generator script, you can rebuild the network by running:

```bash
python3 scripts/generate_sumo_network.py
```

This will instantly output fresh XML files into the `network_data/` directory, compile the network with `netconvert`, route traffic with `duarouter`, and update `dense_network.sumocfg`.

## Viewing and Simulating the Network

### Option 1: Track Editor (Netedit)
To inspect track geometry and signals in Netedit:

```bash
netedit -s network_data/dense_network.net.xml -a network_data/dense_network.add.xml
```

### Option 2: Live Train Simulation (SUMO GUI)
To run the live train simulation with animated rolling stock:

```bash
sumo-gui -c network_data/dense_network.sumocfg
```

Or run headlessly for benchmarking:

```bash
sumo -c network_data/dense_network.sumocfg --end 3600
```

## Repository Conventions

- The generated `.xml` network files are intentionally tracked by Git — they are the primary deliverable of this repository.
- Python caches and virtual environments are ignored via `.gitignore`.
- The generator script is seeded (`random.seed(42)`), so rebuilding always produces the same network.