# Graphs Module

Graph representation, analysis, and visualization of EPANET water distribution
networks using NetworkX.

---

## Module Contents

```
graphs/
├── __init__.py        # Empty; import from the submodules below
├── graph.py           # EPANETNetworkGraph, PressureZones, SensorInfo, pretty_print_graph_diffs
├── visualization.py   # EPANETGraphPlotter
└── README.md
```

Import paths:

```python
from hydroforge.graphs.graph import EPANETNetworkGraph, pretty_print_graph_diffs
from hydroforge.graphs.visualization import EPANETGraphPlotter
```

---

## Creating a graph

```python
import pathlib
import networkx as nx
from hydroforge.graphs.graph import EPANETNetworkGraph

# From an EPANET .inp file
network = EPANETNetworkGraph.from_epanet_file(pathlib.Path("network.inp"))

# From a parsed model (OrderedDict or EPANETNetworkModel)
from hydroforge.epanetfile_io import EPANETFileIO, EPANETNetworkModelIO

raw = EPANETFileIO.read_inp_file("network.inp")      # OrderedDict
model = EPANETNetworkModelIO.from_dict(raw)          # EPANETNetworkModel
network = EPANETNetworkGraph.from_model(model)

# From an existing NetworkX graph
G = nx.Graph()
network = EPANETNetworkGraph.from_graph(G)
```

`from_model` accepts an `OrderedDict` or an `EPANETNetworkModel`; keyword
arguments `as_undirected` and `extra_safety` are forwarded to the graph builder.
`extra_safety=True` prints a warning for nodes without coordinates.

### Node attributes

- `pos`: `(x, y)` coordinates
- `node_type`: `"JUNCTION"`, `"RESERVOIR"`, or `"TANK"`
- `elevation`: junction elevation, reservoir head, or tank elevation
- `demand`: base demand (junctions only)

### Edge attributes

- `len`: physical pipe length; `0.5` for pumps and valves
- `dia`: diameter
- `Wei`: `(len * 1000) / dia`
- `key`: original EPANET element ID
- `link_type`: `"PIPE"`, `"PUMP"`, or `"VALVE"`
- `status`: pipe status (pipes)
- `setting`: valve setting (valves)

---

## Analysis

```python
total_length = network.find_total_length()
bridges = network.find_bridges()

distances_df = network.shortest_distances_all_nodes(weight="len", as_dataframe=True)
distances_dict = network.shortest_distances_all_nodes(weight="len", as_dataframe=False)

sensor_info = network.assign_pressure_zones(["S1", "S2"], weight="len")
# Dict[node_name, SensorInfo(sensor=sensor_name, pressure_zone=index)]

network.set_closest_sensor_attribute(sensor_info, inplace=True)
pressure_zones = network.find_pressure_zones(inplace=False)
zone_lengths = pressure_zones.compute_zone_pipe_lengths(sensors=["S1", "S2"])
```

`find_pressure_zones` requires `closest_sensor` to be set on every node first
(via `set_closest_sensor_attribute`). Its `PressureZones` result exposes
`zone_graph` (pressure zones with inter-zone edges removed) and `bridges` (edges
connecting different zones). `compute_zone_pipe_lengths` returns `None` for a
sensor whose zone contains more than one sensor.

`SensorInfo` fields are `sensor` and `pressure_zone` (0-based index following
the order of the `sensors` argument).

### Graph comparison

```python
diffs = network_v1.compare(network_v2, float_tol=1e-9)
pretty_print_graph_diffs(diffs, max_examples=10)
```

The diff dictionary contains `nodes_only_in_g1`, `nodes_only_in_g2`,
`node_attr_diffs`, `edges_only_in_g1`, `edges_only_in_g2`, `edge_attr_diffs`, and
`_summary`.

### Sensor positions

```python
positions = network.get_sensor_positions(["S1", "S2"])
# Dict[sensor_name, Position(x=..., y=...)]
```

`Position` is a named tuple defined in `hydroforge.graphs.graph`.

---

## Visualization

```python
import pathlib
from hydroforge.graphs.graph import EPANETNetworkGraph
from hydroforge.graphs.visualization import EPANETGraphPlotter

network = EPANETNetworkGraph.from_epanet_file(pathlib.Path("network.inp"))
plotter = EPANETGraphPlotter(network)
plotter.plot(
    title="Network",
    sensors=["J1", "J5"],
    show_labels=True,
    show_legend=True,
    show_edge_labels=False,
    pipe_color_property="len",
    save_path=pathlib.Path("out/network.png"),
)
```

`plot()` signature:

```python
plot(
    title=None,
    sensors=None,
    show_labels=True,
    show_legend=True,
    show_edge_labels=False,
    pipe_color_property=None,
    save_path=None,
    **kwargs,
)
```

- `show_labels` is auto-disabled above 150 nodes.
- `show_edge_labels` is effective only for small visible edge sets and must be
  requested explicitly.
- `pipe_color_property` selects an edge attribute (`"len"`, `"dia"`, `"Wei"`,
  or a custom attribute); `None` draws uniform grey pipes.
- `save_path` writes a 300 DPI PNG; otherwise the plot is displayed.
- `figsize` can be passed through `**kwargs`.

Node and edge styling is controlled by the class dictionaries
`NODE_TYPE_STYLES` and `EDGE_TYPE_STYLES`.

> **Headless environments:** importing `hydroforge.graphs.visualization` calls
> `matplotlib.use("TkAgg")` unconditionally. On machines without a display,
> import this module only when plotting, or set a non-interactive backend first.

---

## Student / legacy notes

- `EPANETNetworkGraph` delegates unknown attributes to the wrapped NetworkX
  graph, so `network.nodes`, `network.edges`, and NetworkX functions work
  directly. `network.graph` / `network.get_networkx_graph()` return the wrapped
  graph.
- The historical `found.*` import paths no longer exist. Use `hydroforge.*`.
  EPANET `.inp` parsing now lives in `hydroforge.epanetfile_io`.
- `hydroforge.graphs` has no module-level exports (`__init__.py` is empty);
  import from `hydroforge.graphs.graph` and `hydroforge.graphs.visualization`.

---

## License

Part of the HydroForge uncertainty injection toolbox. See the repository
`LICENSE` file.
