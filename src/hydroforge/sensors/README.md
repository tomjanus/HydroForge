# Sensors Module

A toolkit for sensor network analysis, placement, and measurement modelling in water distribution networks (WDNs).

---

## Overview

The sensors module provides tools for:
- **Sensor Network Analysis**: Graph-based representation and of sensor networks
- **Sensor Placement**: Multiple algorithms for optimal sensor placement strategies
- **Sensor Modelling**: Representations of sensor behavior including measurement errors, noise, drift, etc.

---

## Module Structure

```
sensors/
├── __init__.py             # Module init file
├── sensor_network.py       # Graph representation of sensor networks
├── placement.py            # Sensor placement algorithms
└── sensors.py              # Sensor models with measurement errors
```

---

## Core Components

### 1. Sensor Network Graph ([sensor_network.py](./sensor_network.py))

The `SensorNetworkGraph` class provides a graph-based representation of sensor networks built on [NetworkX](https://networkx.org/en/).

#### Key Features

- **Graph Operations**: Length, iteration, containment checks
- **Attribute Delegation**: Direct access to NetworkX graph methods
- **Sensor-Level Metrics**: Path weights and distance matrices
- **Zone Analysis**: Integration with pressure zone calculations

#### Usage Example

```python
from hydroforge.sensors import SensorNetworkGraph, Position

# Define sensor locations
sensor_locations = {
    "S1": Position(x=0.0, y=0.0),
    "S2": Position(x=10.0, y=0.0),
    "S3": Position(x=20.0, y=0.0),
}

# Define zone sizes (pipe lengths monitored)
zone_sizes = {
    "S1": 150.0,  # meters
    "S2": 200.0,
    "S3": 180.0,
}

class MockPressureZones:
        def __init__(self, bridges):
            self.bridges = bridges

# Define connections between pressure zones
bridges = [("S1", "S2"), ("S2", "S3")]

pressure_zones = MockPressureZones(bridges=bridges)

# Create sensor network
sensor_graph = SensorNetworkGraph.from_sensor_zones(
    sensor_locations=sensor_locations,
    zone_sizes=zone_sizes,
    pressure_zones=pressure_zones  # PressureZones object
)

# Compute sensor-level distance matrix
sensor_matrix = sensor_graph.sensor_path_costs().matrix
```

#### Methods

- `from_sensor_zones(sensor_locations, zone_sizes, pressure_zones)`: Create from pressure zone analysis
- `from_network_graph(graph, sensors)`: Create from existing NetworkX graph of the network
- `from_sensor_graph(graph)`: Create from existing NetworkX graph of sensors
- `sensor_path_costs()`: Compute the sensor-level shortest-path weight matrix
- `get_networkx_graph()`: Access underlying NetworkX graph

---

### 2. Sensor Placement ([placement.py](./placement.py))

Multiple algorithms for optimal sensor placement in water distribution networks.

#### Available Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| **Greedy** | Iteratively place sensors at maximum distance from sources/existing sensors | Maximizing coverage |
| **K-Center** | Minimize maximum distance to nearest sensor | Uniform coverage |
| **Random** | Random placement with optional seed | Baseline comparison |
| **Centrality-Based** | Place at high-centrality nodes (degree, betweenness, closeness, eigenvector) | Strategic locations |
| **Coverage-Based** | Maximize nodes within coverage radius | Area coverage |
| **Dominating Set** | Ensure every node is adjacent to a sensor | Complete monitoring |
| **Fixed Location** | Use predefined sensor locations | Existing infrastructure |

#### Usage Example

```python
from hydroforge.sensors import (
    SensorPlacer,
    GreedySensorPlacement,
    KCentreSensorPlacement,
    CentralityBasedSensorPlacement
)
from hydroforge.graphs.graph import EPANETNetworkGraph

# Load network
network_graph = EPANETNetworkGraph.from_epanet_file("network.inp")

# 1. Greedy placement
greedy_strategy = GreedySensorPlacement(
    graph=network_graph,
    num_sensors=25,
    sources=["R1", "R2"],
    weight="len"
)
placer = SensorPlacer(strategy=greedy_strategy)
placer.place_sensors()
print(f"Sensors: {placer.sensors}")
placer.plot_sensors(graph=network_graph, title="Greedy Placement")

# 2. Centrality-based placement
centrality_strategy = CentralityBasedSensorPlacement(
    graph=network_graph,
    num_sensors=25,
    sources=["R1", "R2"],
    centrality_type="betweenness"  # or "degree", "closeness", "eigenvector"
)
placer = SensorPlacer(strategy=centrality_strategy)
placer.place_sensors()

# 3. Fixed locations
fixed_strategy = FixedLocationSensorPlacement(
    fixed_locations=["n27", "n120", "n212"],
    graph=network_graph
)
placer = SensorPlacer(strategy=fixed_strategy)
placer.place_sensors()
```

#### Strategy Pattern

All placement strategies implement the `SensorPlacementStrategy` protocol:

```python
class SensorPlacementStrategy(Protocol):
    def place(self) -> list:
        """Place sensors and return list of node IDs."""
```

This enables easy comparison and swapping of sensor placement strategies.

---

### 3. Sensor Models ([sensors.py](./sensors.py))

Realistic sensor behavior modeling with various measurement artifacts.

#### Sensor Types

| Sensor | Description | Parameters |
|--------|-------------|------------|
| `PerfectSensor` | Returns exact measurement | None |
| `FixedPrecisionSensor` | Truncates to fixed precision | `delta_y` (precision) |
| `RandomNoiseSensor` | Adds Gaussian noise | `sigma`, `seed` |
| `OffsetSensor` | Adds constant bias | `offset` |
| `SensitivityErrorSensor` | Applies scaling factor | `scale` (e.g., 1.05 = +5%) |
| `DeadBandSensor` | Zero output within threshold | `threshold` |
| `SaturationSensor` | Clips to min/max range | `min_val`, `max_val` |
| `DriftSensor` | Accumulating bias over time | `offset_rate` |
| `CompositeSensor` | Chain multiple sensors | `*sensors` |

#### Usage Example

```python
from hydroforge.sensors import (
    FixedPrecisionSensor,
    RandomNoiseSensor,
    OffsetSensor,
    CompositeSensor,
    Averager
)
import numpy as np

# 1. Single sensor with fixed precision
sensor = FixedPrecisionSensor(delta_y=0.1)
measurement = sensor.measure(1.234)  # Returns 1.2

# 2. Sensor with Gaussian noise
noisy_sensor = RandomNoiseSensor(sigma=0.05, seed=42)
measurement = noisy_sensor.measure(1.0)  # Returns ~1.0 ± noise

# 3. Composite sensor (multiple effects)
composite = CompositeSensor(
    FixedPrecisionSensor(delta_y=0.1),
    RandomNoiseSensor(sigma=0.05),
    OffsetSensor(offset=0.1)
)
measurement = composite.measure(1.234)

# 4. Works with arrays and DataFrames
vector_data = np.array([1.03, 1.07, 0.94, 1.12])
measurements = sensor.measure(vector_data)

# 5. Averaging measurements
averager = Averager(num_measurements=3)
averaged = averager.average(vector_data)  # Non-overlapping windows
```

#### Type Support

All sensors support multiple input types:
- **Scalars**: `float`, `int`
- **Arrays**: `np.ndarray` (1D and 2D)
- **Pandas**: `pd.Series`, `pd.DataFrame`

Output type matches input type for seamless integration.

---

## Common Workflows

### Workflow 1: Complete Sensor Network Analysis

```python
from hydroforge.sensors.placement import GreedySensorPlacement, SensorPlacer
from hydroforge.graphs.graph import EPANETNetworkGraph

# 1. Load network and place sensors
network = EPANETNetworkGraph.from_epanet_file("network.inp")
strategy = GreedySensorPlacement(
    graph=network,
    num_sensors=20,
    sources=["R1"]
)
placer = SensorPlacer(strategy=strategy)
placer.place_sensors()
sensors = placer.sensors

# 2. Assign nodes to pressure zones
node_zones = nodes_sensor(
    path_network="network.inp",
    path_network_statistics="stats.csv",
    sensors=sensors,
    name="MyNetwork"
)

# 3. Compute sensor-level distances
sensor_distances = level_sensors(
    network_path="network.inp",
    node_sensor_zone_datafile="zones.csv",
    sensors=sensors,
    node_pressure_zone=node_zones,
    name="MyNetwork"
)

# 4. Visualize
placer.plot_sensors(graph=network, title="Sensor Network")
```

### Workflow 2: Comparing Placement Strategies

```python
from hydroforge.sensors.sensor_placement import (
    GreedySensorPlacement,
    KCentreSensorPlacement,
    CentralityBasedSensorPlacement
)

strategies = {
    "Greedy": GreedySensorPlacement(network, 20, ["R1"]),
    "K-Center": KCentreSensorPlacement(network, 20, ["R1"]),
    "Centrality": CentralityBasedSensorPlacement(
        network, 20, ["R1"], centrality_type="betweenness"
    )
}

for name, strategy in strategies.items():
    placer = SensorPlacer(strategy=strategy)
    placer.place_sensors()
    print(f"{name}: {placer.sensors}")
    placer.plot_sensors(graph=network, title=f"{name} Placement")
```

### Workflow 3: Realistic Sensor Simulation

```python
from hydroforge.sensors.sensors import CompositeSensor, FixedPrecisionSensor, RandomNoiseSensor
import pandas as pd

# Simulate realistic pressure sensor
realistic_sensor = CompositeSensor(
    FixedPrecisionSensor(delta_y=0.01),  # 0.01 bar precision
    RandomNoiseSensor(sigma=0.005, seed=42),  # ±0.005 bar noise
)

# Apply to time series data
pressure_data = pd.DataFrame({
    'sensor1': [1.234, 1.245, 1.238, 1.241],
    'sensor2': [2.156, 2.162, 2.159, 2.164],
    'sensor3': [3.089, 3.095, 3.091, 3.093],
})

measured_data = realistic_sensor.measure(pressure_data)
print(measured_data)
```

---

## Integration with Other Modules

### With `hydroforge.graphs`

Sensor placement and analysis heavily rely on the `EPANETNetworkGraph`:

```python
from hydroforge.graphs.graph import EPANETNetworkGraph
from hydroforge.sensors.sensor_network import SensorNetworkGraph

# Load EPANET network
network = EPANETNetworkGraph.from_epanet_file("network.inp")

# Get sensor positions
sensors = ["n1", "n5", "n10"]
sensor_positions = network.get_sensor_positions(sensors)

# Assign pressure zones
zone_info = network.assign_pressure_zones(sensors)

# Find pressure zones
pressure_zones = network.find_pressure_zones()

# Create sensor network
sensor_net = SensorNetworkGraph.from_sensor_zones(
    sensor_positions,
    pressure_zones.zone_sizes,
    pressure_zones
)
```

### With `hydroforge.uncertainty`

Combine sensor models with uncertainty quantification:

```python
from hydroforge.sensors.sensors import RandomNoiseSensor
from hydroforge.uncertainty.parameters import Parameter
from hydroforge.uncertainty.uncertainties import AdditiveUncertainty
from hydroforge.uncertainty.distributions import NormalDistribution

# Create uncertain measurement
measurement_noise = NormalDistribution(mean=0, std_dev=0.05)
uncertainty = AdditiveUncertainty(distribution=measurement_noise)

measured_value = Parameter(
    name="pressure_reading",
    nominal_value=1.5,
    uncertainty=uncertainty,
    kind=ParameterKind.NUMERICAL
)

# Apply sensor model
sensor = RandomNoiseSensor(sigma=0.01, seed=42)
noisy_measurement = sensor.measure(measured_value.sample())
```

---

## Performance Considerations

### Graph Operations

- Use `inplace=True` in placement strategies to avoid graph copying
- For multiple analyses, create graph once and reuse
- Pressure zone calculation is expensive—cache results

### Sensor Measurements

- Batch processing: Use NumPy/Pandas for vectorized operations
- For large time series, consider chunking with `Averager`
- Composite sensors apply transformations sequentially

---

## Testing and Validation

### Demonstrations of the Module functionalities in `examples/sensors`

```python

# Test sensor models
python ex1_sensors.py

# Test sensor placement strategies
python ex2_sensor_placement.py

# Test sensor network functionality
python ex3_sensor_network.py
```

---

## Advanced Topics

### Custom Sensor Placement Strategy

Implement your own strategy using the Protocol:

```python
from hydroforge.sensors.sensor_placement import SensorPlacementStrategy
from dataclasses import dataclass

@dataclass
class CustomSensorPlacement:
    graph: EPANETNetworkGraph
    num_sensors: int
    # ... your parameters
    
    def place(self) -> list:
        # Your algorithm here
        selected_nodes = []
        # ... selection logic
        return selected_nodes

# Use with SensorPlacer
strategy = CustomSensorPlacement(network, 20)
placer = SensorPlacer(strategy=strategy)
placer.place_sensors()
```

### Custom Sensor Model

Extend the `Sensor` abstract class:

```python
from hydroforge.sensors.sensors import Sensor
from dataclasses import dataclass

@dataclass
class CustomSensor(Sensor):
    # Your parameters
    
    def measure(self, y: T) -> T:
        # Your measurement logic
        if isinstance(y, float):
            return self._process_scalar(y)
        if isinstance(y, np.ndarray):
            return self._process_array(y)
        # ... handle other types
```

---

## Dependencies

- **NetworkX**: Graph operations and algorithms
- **NumPy**: Numerical computations
- **Pandas**: Data structures and analysis
- **Rich**: Console output formatting
- **Matplotlib**: Visualization (via `hydroforge.visualization`)

---

## References

### Publications

- Pérez et al. (2014). "A Model-Based Methodology Using Pressure Sensors Applied to a Real Network in Barcelona." *IEEE Control Systems Magazine*

### Related Modules

- `hydroforge.graphs`: Network graph representations
- `hydroforge.uncertainty`: Uncertainty quantification
- `hydroforge.visualization`: Network visualization tools

---

## Contributing

When adding new sensor placement strategies:
1. Implement the `SensorPlacementStrategy` protocol
2. Add to the comparison examples in `__main__`
3. Document use cases and performance characteristics
4. Include visualization example

When adding new sensor models:
1. Inherit from `Sensor` base class
2. Implement `measure()` for all supported types
3. Add to sensor demonstrations
4. Include validation tests

---

## License

This module is part of the HydroForge uncertainty injection framework.
