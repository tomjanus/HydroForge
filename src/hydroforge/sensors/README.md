# Sensors Module

Sensor measurement models, placement strategies, and a sensor-level network
graph for water distribution networks.

---

## Module Contents

```
sensors/
├── __init__.py          # Re-exports sensor models, placement strategies, SensorNetworkGraph
├── sensors.py           # Sensor models and window averagers
├── placement.py         # Placement strategies and SensorPlacer
├── sensor_network.py    # SensorNetworkGraph, SensorPathCosts, Position
└── README.md
```

Public imports from the package root:

```python
from hydroforge.sensors import (
    PerfectSensor,
    FixedPrecisionSensor,
    RandomNoiseSensor,
    OffsetSensor,
    SensitivityErrorSensor,
    DeadBandSensor,
    SaturationSensor,
    DriftSensor,
    CompositeSensor,
    SourceFinder,
    GreedySensorPlacement,
    KCentreSensorPlacement,
    RandomSensorPlacement,
    CentralityBasedSensorPlacement,
    CoverageBasedSensorPlacement,
    DominatingSetBasedSensorPlacement,
    FixedLocationSensorPlacement,
    SensorPlacer,
    SensorNetworkGraph,
)
```

`WindowAverager`, `MovingWindowAverager`, `Sensor`, and `SensorPathCosts` are
defined in the submodules and are not all re-exported at package level:

```python
from hydroforge.sensors.sensors import WindowAverager, MovingWindowAverager
from hydroforge.sensors.sensor_network import Position, SensorPathCosts
```

---

## Sensor models (`sensors.py`)

All sensors derive from the abstract `Sensor` class and implement
`measure(y)`. Scalars, NumPy arrays, and pandas `Series`/`DataFrame` are
supported; the output type matches the input type.

| Class | Field(s) | Effect |
|-------|----------|--------|
| `PerfectSensor` | — | Returns the input unchanged |
| `FixedPrecisionSensor` | `delta_y` | Rounds/truncates to a fixed precision |
| `RandomNoiseSensor` | `sigma`, `seed=None` | Adds Gaussian noise |
| `OffsetSensor` | `offset` | Adds a constant bias |
| `SensitivityErrorSensor` | `scale` | Multiplies by a gain factor |
| `DeadBandSensor` | `threshold` | Returns zero inside the dead band |
| `SaturationSensor` | `min_val`, `max_val` | Clips to a range |
| `DriftSensor` | `offset_rate`, `current_offset=0.0` | Accumulates bias on each call |
| `CompositeSensor` | `*sensors` | Applies sensors sequentially |

```python
import numpy as np
from hydroforge.sensors import (
    CompositeSensor,
    FixedPrecisionSensor,
    RandomNoiseSensor,
    OffsetSensor,
)

sensor = CompositeSensor(
    FixedPrecisionSensor(delta_y=0.01),
    RandomNoiseSensor(sigma=0.005, seed=42),
    OffsetSensor(offset=0.1),
)
values = sensor.measure(np.array([1.03, 1.07, 0.94]))
```

`RandomNoiseSensor` creates its random generator lazily; passing the same
`seed` reproduces the sequence. `DriftSensor` mutates `current_offset`
between calls.

### Window averaging

`WindowAverager(window_size)` averages non-overlapping windows;
`MovingWindowAverager(window_size, overlap=0)` averages overlapping windows.
Both expose `average(x)`.

```python
from hydroforge.sensors.sensors import WindowAverager, MovingWindowAverager

print(WindowAverager(window_size=2).average([1.0, 1.1, 0.9, 1.2]))
print(MovingWindowAverager(window_size=3, overlap=1).average([1, 2, 3, 4, 5]))
```

---

## Placement (`placement.py`)

Each strategy is a dataclass implementing `place() -> list[str]`.

| Strategy | Required fields | Notes |
|----------|-----------------|-------|
| `GreedySensorPlacement` | `graph`, `num_sensors` | Optional `sources`, `weight`, `update_method`, `inplace` |
| `KCentreSensorPlacement` | `graph`, `num_sensors`, `sources` | Minimizes maximum distance |
| `RandomSensorPlacement` | `graph`, `num_sensors`, `sources` | Optional `seed` |
| `CentralityBasedSensorPlacement` | `graph`, `num_sensors`, `sources` | `centrality_type` in `degree`, `betweenness`, `closeness`, `eigenvector` |
| `CoverageBasedSensorPlacement` | `graph`, `num_sensors`, `sources` | `coverage_radius` (default 100) |
| `DominatingSetBasedSensorPlacement` | `graph`, `num_sensors`, `sources` | Every node adjacent to a sensor |
| `FixedLocationSensorPlacement` | `sensors` | Optional `graph`, `sources` |

`SourceFinder(graph, source_keyword="R", case_sensitive=False, use_regex=False)`
finds reservoir/source nodes by name when an explicit `sources` list is
inconvenient.

`SensorPlacer(strategy)` orchestrates a strategy:

```python
import pathlib
from hydroforge.graphs.graph import EPANETNetworkGraph
from hydroforge.sensors import GreedySensorPlacement, SensorPlacer

network = EPANETNetworkGraph.from_epanet_file(pathlib.Path("network.inp"))
strategy = GreedySensorPlacement(graph=network, num_sensors=10, sources=["R1"])
placer = SensorPlacer(strategy=strategy)
placer.place_sensors()
print(placer.sensors)

placer.plot_sensors(graph=network, title="Greedy placement")
placer.save_sensors(pathlib.Path("sensors.json"))
```

`SensorPlacer` also provides `load_sensors(file)` and
`plot_sensors(graph, title=..., save_path=...)`.

---

## Sensor network graph (`sensor_network.py`)

`SensorNetworkGraph` wraps a NetworkX graph whose nodes are sensors and whose
edges connect sensors across pressure-zone boundaries.

```python
from hydroforge.sensors.sensor_network import SensorNetworkGraph

sensor_graph = SensorNetworkGraph.from_sensor_zones(
    sensor_locations=positions,      # Dict[sensor, Position(x, y)]
    zone_sizes=zone_lengths,         # Dict[sensor, float]
    pressure_zones=pressure_zones,   # PressureZones from hydroforge.graphs.graph
)

costs = sensor_graph.sensor_path_costs()
print(costs.matrix, costs.sensors)
```

Constructors:

- `from_sensor_zones(sensor_locations, zone_sizes, pressure_zones)`
- `from_network_graph(graph, sensor_nodes)` — subgraph of the given network graph
- `from_sensor_graph(graph)` — wrap an existing sensor graph (no validation)

Other methods: `shortest_path(source, target)`, `get_networkx_graph()`, and
`graph`. Unknown attributes are delegated to the wrapped NetworkX graph.

---

## Related modules

- Network graphs and pressure zones: `hydroforge.graphs.graph`
- Uncertainty parameters and distributions: `hydroforge.uncertainty`
- Sampling: `hydroforge.sampling` (requires `SALib`)

---

## License

Part of the HydroForge uncertainty injection toolbox. See the repository
`LICENSE` file.
