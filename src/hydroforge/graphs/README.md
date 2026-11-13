# FOUND Graphs Module

**Graph representation, analysis, and visualization for EPANET water distribution networks**

This module provides comprehensive tools for working with water distribution networks as graph structures using NetworkX, enabling advanced network analysis, sensor placement optimization, and pressure zone identification.

---

## 📦 Module Contents

- **`graph.py`** - Core graph representation and analysis (`EPANETNetworkGraph`)
- **`visualization.py`** - Network visualization tools (`EPANETGraphPlotter`)

---

## 🚀 Quick Start

### Creating a Network Graph

```python
from found.graphs.graph import EPANETNetworkGraph
from pathlib import Path

# From EPANET .inp file
network = EPANETNetworkGraph.from_epanet_file(Path("network.inp"))

# From existing model dictionary
from found.auxiliary.swmm_file_parser import read_inp_file
model = read_inp_file("network.inp")
network = EPANETNetworkGraph.from_model(model)

# From existing NetworkX graph
import networkx as nx
G = nx.Graph()
# ... build graph ...
network = EPANETNetworkGraph.from_graph(G)
```

### Visualizing Networks

```python
from found.graphs.visualization import EPANETGraphPlotter

# Create plotter
plotter = EPANETGraphPlotter(network)

# Basic visualization
plotter.plot(title="My Water Network")

# With sensors highlighted
plotter.plot(
    title="Network with Sensors",
    sensors=['J1', 'J5', 'J10'],
    show_legend=True
)

# Color pipes by property
plotter.plot(
    title="Pipes Colored by Length",
    pipe_color_property='len',
    show_labels=False
)

# Save to file
plotter.plot(
    title="Network Analysis",
    sensors=['J1', 'J5'],
    pipe_color_property='Wei',
    save_path=Path("outputs/network.png")
)
```

---

## 📊 Core Classes

### `EPANETNetworkGraph`

A wrapper around NetworkX graphs with water distribution network-specific functionality.

#### Key Features

- **Graph Creation**: Multiple constructors for flexible initialization
- **Network Analysis**: Shortest paths, total length, bridge detection
- **Pressure Zones**: Assign nodes to sensor zones and identify zone boundaries
- **Graph Comparison**: Detailed diff between network versions
- **Node/Edge Attributes**: Automatic extraction from EPANET models

#### Common Operations

```python
# Network statistics
total_length = network.find_total_length()  # Total pipe length
num_nodes = len(network)
num_edges = network.number_of_edges()

# Shortest path analysis
distances = network.shortest_distances_all_nodes(weight='len')
# Returns DataFrame with all pairwise distances

# Find bridges (critical pipes connecting zones)
bridges = network.find_bridges()
# Returns list of (node1, node2) tuples

# Pressure zone assignment
sensor_assignments = network.assign_pressure_zones(
    sensors=['S1', 'S2', 'S3'],
    weight='len'
)
# Returns Dict[NodeName, SensorInfo]

# Add sensor info to graph
network.set_closest_sensor_attribute(sensor_assignments, inplace=True)

# Find pressure zones
pressure_zones = network.find_pressure_zones()
# Returns PressureZones(zone_graph, bridges)

# Compute zone sizes
zone_lengths = pressure_zones.compute_zone_pipe_lengths(
    sensors=['S1', 'S2', 'S3'],
    weight='len'
)
```

#### Node Attributes

Nodes are automatically populated with:
- `pos`: (x, y) coordinates tuple
- `node_type`: 'JUNCTION', 'RESERVOIR', or 'TANK'
- `elevation`: Node elevation
- `demand`: Base demand (junctions only)

#### Edge Attributes

Edges include:
- `link_type`: 'PIPE', 'PUMP', or 'VALVE'
- `len`: Length (physical for pipes, 0.5 for pumps/valves)
- `dia`: Diameter
- `Wei`: Weight coefficient = (len × 1000) / diameter
- `key`: Original EPANET element ID
- `status`: Pipe status (pipes only)
- `setting`: Valve setting (valves only)

---

### `EPANETGraphPlotter`

Matplotlib-based visualization with NetworkX drawing capabilities.

#### Unified `plot()` Method

All visualization features in one method:

```python
def plot(
    title: Optional[str] = None,
    sensors: Optional[list] = None,
    show_labels: bool = True,
    show_legend: bool = True,
    show_edge_labels: bool = False,
    pipe_color_property: Optional[str] = None,
    save_path: Optional[pathlib.Path] = None
) -> None:
```

#### Parameters

- **`title`**: Plot title (default: "Water Distribution Network")
- **`sensors`**: List of node IDs to highlight as sensors with star markers
- **`show_labels`**: Show node IDs (auto-disabled for networks > 150 nodes)
- **`show_legend`**: Show legend for node/edge types
- **`show_edge_labels`**: Show edge lengths (auto-enabled only for < 60 edges)
- **`pipe_color_property`**: Edge attribute for pipe coloring
  - Common: `'len'` (length), `'dia'` (diameter), `'Wei'` (weight)
  - Any custom edge attribute
  - `None` = uniform gray pipes
- **`save_path`**: Path to save PNG (300 DPI), `None` = display plot

#### Visual Styling

**Nodes:**
- Junctions: Light blue circles (#8fd3f4)
- Reservoirs: Dark blue squares (#1f77b4)
- Tanks: Orange triangles (#ff7f0e)
- Sensors: Red stars (#e45756) overlaid on nodes

**Edges:**
- Pipes: Gray lines (#888888), optionally colored by property
- Pumps: Red lines (#d62728)
- Valves: Purple lines (#9467bd)

#### Advanced Examples

```python
# Large network without labels
plotter.plot(
    title="City Water Network",
    show_labels=False,
    pipe_color_property='diameter'
)

# Sensor placement analysis
plotter.plot(
    title="Optimal Sensor Placement",
    sensors=optimal_sensor_locations,
    pipe_color_property='Wei',
    show_legend=True,
    save_path=Path("results/sensors.png")
)

# Edge labels for small networks
plotter.plot(
    title="Neighborhood Network",
    show_edge_labels=True,
    show_labels=True
)

# Publication-ready figure
plotter.plot(
    title="Water Distribution System Analysis",
    sensors=['J42', 'J108', 'J256'],
    pipe_color_property='len',
    show_legend=True,
    save_path=Path("paper/figure3.png")
)
```

---

## 🔬 Pressure Zone Analysis

The module provides specialized tools for pressure zone analysis based on sensor placement.

### Workflow Example

```python
from found.graphs.graph import EPANETNetworkGraph

# Load network
network = EPANETNetworkGraph.from_epanet_file("network.inp")

# Define sensor locations
sensors = ['J10', 'J45', 'J78', 'J120']

# Assign each node to nearest sensor
assignments = network.assign_pressure_zones(sensors, weight='len')

# assignments is Dict[NodeName, SensorInfo]
# SensorInfo has: .sensor (sensor name), .pressure_zone (0-based index)

# Add to graph as node attribute
network.set_closest_sensor_attribute(assignments, inplace=True)

# Find pressure zones (removes inter-zone edges)
pressure_zones = network.find_pressure_zones(inplace=False)

# pressure_zones.zone_graph = graph with bridges removed
# pressure_zones.bridges = list of edges connecting different zones

# Calculate total pipe length per zone
zone_lengths = pressure_zones.compute_zone_pipe_lengths(
    sensors=sensors,
    weight='len'
)

print(f"Zone lengths: {zone_lengths}")
# {'J10': 1250.5, 'J45': 980.2, 'J78': 1100.8, 'J120': 890.3}

# Visualize zones
from found.graphs.visualization import EPANETGraphPlotter
plotter = EPANETGraphPlotter(network)
plotter.plot(
    title="Pressure Zones",
    sensors=sensors,
    show_legend=True
)
```

---

## 🧪 Graph Comparison

Compare two network versions with detailed diff reporting:

```python
# Load two versions
network_v1 = EPANETNetworkGraph.from_epanet_file("network_v1.inp")
network_v2 = EPANETNetworkGraph.from_epanet_file("network_v2.inp")

# Compare
diffs = network_v1.compare(network_v2, float_tol=1e-9)

# diffs contains:
# - nodes_only_in_g1: nodes removed
# - nodes_only_in_g2: nodes added
# - node_attr_diffs: attribute changes per node
# - edges_only_in_g1: edges removed
# - edges_only_in_g2: edges added
# - edge_attr_diffs: attribute changes per edge
# - _summary: counts of each category

# Pretty print comparison
from found.graphs.graph import pretty_print_graph_diffs
pretty_print_graph_diffs(diffs, max_examples=10)
```

---

## 📐 Network Analysis Methods

### Distance Calculations

```python
# All pairwise shortest paths
distances_df = network.shortest_distances_all_nodes(
    weight='len',
    as_dataframe=True
)
# Returns DataFrame: rows=sources, cols=targets, values=distances

distances_dict = network.shortest_distances_all_nodes(
    weight='len',
    as_dataframe=False
)
# Returns nested dict: {node1: {node2: distance}}
```

### Bridge Detection

Bridges are critical edges whose removal would disconnect the network:

```python
bridges = network.find_bridges()
# Returns: [(node1, node2), (node3, node4), ...]

# Get pipe IDs for bridges
bridge_pipe_ids = []
for u, v in bridges:
    edge_data = network.get_edge_data(u, v)
    if 'key' in edge_data:
        bridge_pipe_ids.append(edge_data['key'])
```

### Sensor Position Lookup

```python
sensors = ['J1', 'J5', 'J10']
positions = network.get_sensor_positions(sensors)
# Returns: Dict[SensorName, Position(x, y)]

for sensor, pos in positions.items():
    print(f"{sensor}: x={pos.x}, y={pos.y}")
```

---

## 🎨 Customization

### Custom Node/Edge Styles

Modify class constants before creating plotter:

```python
from found.graphs.visualization import EPANETGraphPlotter

# Customize node styles
EPANETGraphPlotter.NODE_TYPE_STYLES['JUNCTION']['color'] = '#ff0000'
EPANETGraphPlotter.NODE_TYPE_STYLES['JUNCTION']['size'] = 200

# Customize edge styles
EPANETGraphPlotter.EDGE_TYPE_STYLES['PIPE']['width'] = 2.0
EPANETGraphPlotter.EDGE_TYPE_STYLES['PUMP']['color'] = '#00ff00'

# Create plotter with custom styles
plotter = EPANETGraphPlotter(network)
plotter.plot(title="Custom Styled Network")
```

### Custom Figure Size

```python
plotter.plot(
    title="Large Format Plot",
    figsize=(20, 15)  # passed as **kwargs
)
```

---

## 🔧 Advanced Usage

### Working with NetworkX Directly

Access the underlying NetworkX graph:

```python
nx_graph = network.get_networkx_graph()
# or
nx_graph = network.graph

# Use any NetworkX function
import networkx as nx

centrality = nx.betweenness_centrality(nx_graph, weight='Wei')
clustering = nx.clustering(nx_graph)
degree_dist = dict(nx_graph.degree())
```

### Custom Graph Construction

```python
import networkx as nx
from found.graphs.graph import EPANETNetworkGraph

# Build custom graph
G = nx.Graph()

# Add nodes with required attributes
G.add_node('J1', pos=(0, 0), node_type='JUNCTION', elevation=100)
G.add_node('R1', pos=(10, 0), node_type='RESERVOIR', elevation=120)

# Add edges with attributes
G.add_edge('R1', 'J1', 
    link_type='PIPE',
    len=100.0,
    dia=300.0,
    Wei=100000/300,
    key='P1'
)

# Wrap in EPANETNetworkGraph
network = EPANETNetworkGraph.from_graph(G)

# Use all methods
plotter = EPANETGraphPlotter(network)
plotter.plot(title="Custom Network")
```

---

## 📋 Best Practices

1. **Large Networks**: Disable labels and edge labels for networks > 150 nodes
2. **Performance**: Use `inplace=False` when you need to preserve original graph
3. **Visualization**: Always specify meaningful titles for saved plots
4. **Sensor Analysis**: Validate sensor names exist before assignment
5. **File Paths**: Use `pathlib.Path` for cross-platform compatibility
6. **Comparison**: Set appropriate `float_tol` based on your precision needs
7. **Memory**: For very large networks, use `as_dataframe=False` for distance calculations

---

## 🐛 Common Issues

### KeyError when accessing nodes
```python
# Check if node exists first
if 'J1' in network:
    node_data = network.nodes['J1']
```

### Missing positions for visualization
```python
# The plotter automatically falls back to spring layout
# To use custom positions:
import networkx as nx
pos = nx.spring_layout(network.graph, k=0.5, iterations=100)
nx.set_node_attributes(network.graph, pos, 'pos')
```

### Sensors not in network
```python
# Filter valid sensors
valid_sensors = [s for s in sensor_list if s in network]
plotter.plot(sensors=valid_sensors)
```

---

## 📚 Dependencies

- **NetworkX** (≥ 2.5): Graph data structures and algorithms
- **Matplotlib** (≥ 3.0): Visualization
- **NumPy**: Numerical operations
- **Pandas**: Distance matrix DataFrames
- **Rich**: Console formatting

---

## 🔗 Related Modules

- `found.auxiliary.swmm_file_parser` - EPANET .inp file parsing
- `found.network_dict_wrapper` - Network data access layer
- `found.auxiliary.utils` - Utility functions

---

## 📖 Examples in Code

Run the module directly to see demonstrations:

```bash
# Graph module demo
python -m found.graphs.graph

# Visualization module demo
python -m found.graphs.visualization
```

---

## 🤝 Contributing

When adding new features:
1. Follow existing code style (dataclasses, type hints)
2. Add docstrings with clear parameter descriptions
3. Include usage examples in `if __name__ == "__main__"` blocks
4. Update this README with new functionality

---

## 📄 License

Part of the FOUND (Fault detectiOn in water distribUtioN networks) uncertainty analysis framework.

---

**Last Updated**: December 30, 2025
