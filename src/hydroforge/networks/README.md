# Networks Module

The `networks` module provides comprehensive tools for working with water distribution network models, including data access, modification, selection, and leak management. It supports both WNTR (Water Network Tool for Resilience) models and NetworkX graph representations of EPANET networks.

## Overview

This module implements:
- **Data Access**: Structured access to EPANET network components via dataclasses
- **Model Modification**: Modify network parameters (diameters, roughness, demands, valves)
- **Graph Modification**: Topology modifications (pipe removal, network simplification)
- **Component Selection**: Filter and select network components based on criteria
- **Leak Management**: Dictionary-like interface for managing junction leakages

## Key Features

- 🔧 **Modular Design**: Strategy pattern for extensible modifications
- 📊 **Structured Logging**: Track all modifications with detailed logs
- 🎯 **Type Safety**: Comprehensive type hints throughout
- 🔄 **Uncertainty Support**: Integrate with Parameter and Uncertainty classes
- 📝 **I/O Support**: JSON, CSV, INP file formats
- 🔍 **Component Selection**: Flexible filtering by name, diameter, material, etc.

## Module Contents

### Core Components

#### 1. Network Data Accessor (`network_data_accessor.py`)
Provides structured access to EPANET network data using dataclasses.

**Key Classes:**
- `NetworkDataAccessor`: Main accessor class with file I/O support
- `NetworkCollection`: Lazy-loading collection for network components
- Component dataclasses: `Junction`, `Pipe`, `Tank`, `Reservoir`, `Pump`, `Valve`, etc.

#### 2. Network Model Modifier (`network_model_modifier.py`)
Modify WNTR network model parameters with uncertainty support.

**Key Classes:**
- `WNTRNetworkModifier`: Main interface for network modifications
- `NetworkModifierPipeline`: Chain multiple modifications
- Modifier classes:
  - `PipeDiameterModifier`: Modify pipe diameters
  - `PipeDiameterMultiplierModifier`: Scale pipe diameters
  - `PipeRoughnessModifier`: Modify pipe roughness
  - `NodeDemandModifier`: Modify nodal demands
  - `NodeDemandDataFrameModifier`: Bulk demand modifications from DataFrame
  - `NodeLeakageModifier`: Add leakage to nodes
  - `NodeEmitterModifier`: Add pressure-dependent leakage via emitters
  - `ValveModifier`: Modify valve settings
  - `NetworkPipeRemover`: Remove pipes from network

#### 3. Network Graph Modifier (`network_graph_modifier.py`)
Modify network topology using graph representations.

**Key Classes:**
- `NetworkGraphPipeRemover`: Remove pipes from network graph
- `PipeNotFoundException`: Exception for missing pipes
- `BridgeRemovalException`: Exception for critical pipe removal

#### 4. Component Selectors (`network_model_component_selectors.py`, `network_graph_component_selectors.py`)
Select network components based on various criteria.

**Key Classes:**
- `PipeNameSelector`: Select pipes by name
- `PipeDiameterSelector`: Select pipes by diameter range
- `PipeMaterialSelector`: Select pipes by material
- `NodeNameSelector`: Select nodes by name
- `ValveSelector`: Select valves by type

#### 5. Junction Leaks (`junction_leaks.py`)
Manage leakage data for network junctions.

**Key Class:**
- `JunctionLeaks`: Dictionary-like container for leak management


## Quick Start

### Example 1: Accessing Network Data

```python
from found.networks import NetworkDataAccessor

# Load network from INP file
accessor = NetworkDataAccessor.from_inp_file('network.inp')

# Access junctions
junction = accessor.get_junction_by_name('J1')
print(f"Junction elevation: {junction.elevation}")

# Access pipes
pipes = accessor.pipes.to_list()
print(f"Total pipes: {len(pipes)}")

# Export to JSON
accessor.to_json_file('network.json')
```

### Example 2: Modifying Network Parameters

```python
from found.networks import WNTRNetworkModifier, PipeDiameterModifier
import wntr

# Load WNTR model
wn = wntr.network.WaterNetworkModel('network.inp')
modifier = WNTRNetworkModifier(wn)

# Create diameter modifier
diameter_mod = PipeDiameterModifier(
    new_values={
        'P1': 0.4,
        'P2': 0.35,
        'P3': 0.5
    }
)

# Apply modification
modifier.pipeline.add_modifier(diameter_mod)
modifier.modify_network()

# Check log
for entry in modifier.pipeline.log:
    print(entry)

# Save modified network
modifier.save_network('modified_network.inp', overwrite=True)
```

### Example 3: Using Modification Pipeline

```python
from found.networks import (
    NetworkModifierPipeline,
    PipeDiameterModifier,
    PipeRoughnessModifier,
    NodeDemandModifier
)

# Create pipeline with multiple modifiers
pipeline = NetworkModifierPipeline(
    modifiers=[
        PipeDiameterModifier(new_values={'P1': 0.4, 'P2': 0.35}),
        PipeRoughnessModifier(new_values={'P1': 120, 'P2': 130}),
        NodeDemandModifier(new_values={'J1': 0.05, 'J2': 0.03})
    ]
)

# Apply all modifications
pipeline.apply(wn)

# Review modifications
print("\n".join(pipeline.log))
```

### Example 4: Uncertainty in Modifications

```python
from found.networks import PipeDiameterModifier
from found.uncertainty import Parameter, AdditiveUncertainty, UniformDistribution

# Define uncertain parameters
diameter_uncertainty = AdditiveUncertainty(
    distribution=UniformDistribution(-0.05, 0.05)
)

# Create modifier with uncertain values
modifier = PipeDiameterModifier(
    new_values={
        'P1': Parameter(
            name='P1_diameter',
            nominal_value=0.4,
            uncertainty=diameter_uncertainty
        ),
        'P2': 0.35  # Deterministic value
    }
)

# Each application samples from the uncertainty
modifier.apply(wn)
```

### Example 5: Diameter Scaling

```python
from found.networks import PipeDiameterMultiplierModifier

# Scale all pipes by 0.9
multiplier_mod = PipeDiameterMultiplierModifier(multipliers=0.9)
multiplier_mod.apply(wn)

# Or scale specific pipes
multiplier_mod = PipeDiameterMultiplierModifier(
    multipliers={
        'P1': 0.95,
        'P2': 0.85,
        'P3': 0.90
    }
)
multiplier_mod.apply(wn)
```

### Example 6: Bulk Demand Modifications

```python
import pandas as pd
from found.networks import NodeDemandDataFrameModifier

# Create demand data
demands = pd.DataFrame({
    'node_id': ['J1', 'J2', 'J3', 'J4'],
    'demand': [0.05, 0.03, 0.04, 0.06]
}).set_index('node_id')

# Modify demands
demand_mod = NodeDemandDataFrameModifier(
    new_values=demands,
    default_value=0.0,
    skip_nonexistent=True
)
demand_mod.apply(wn)
```

### Example 7: Adding Leakage with Emitters

```python
from found.networks import NodeEmitterModifier

# Calculate emitter coefficient from leak diameter
leak_diameter = 0.01  # 10mm leak
emitter_coeff = NodeEmitterModifier.calculate_emitter_from_diameter(
    diameter=leak_diameter,
    nominal_pressure=100.0
)

# Add emitters to nodes
emitter_mod = NodeEmitterModifier(
    emitter_coefficients={
        'J1': emitter_coeff,
        'J2': 0.001  # Direct coefficient
    },
    nominal_pressure=100.0,
    required_pressure=100.0
)
emitter_mod.apply(wn)
```

### Example 8: Component Selection

```python
from found.networks import PipeDiameterSelector, PipeNameSelector

# Select pipes by diameter range
selector = PipeDiameterSelector(
    min_diameter=0.1,
    max_diameter=0.5,
    text_logging=True
)
selected_pipes = selector.select(wn, candidates=None)
print(f"Selected {len(selected_pipes)} pipes")

# Select specific pipes
name_selector = PipeNameSelector(
    names=['P1', 'P2', 'P3']
)
selected = name_selector.select(wn, candidates=wn.pipe_name_list)
```

### Example 9: Junction Leak Management

```python
from found.networks import JunctionLeaks

# Create leak container
leaks = JunctionLeaks()

# Add leaks
leaks.add_leak('J1', 0.05)
leaks.add_leak('J2', 0.03)
leaks['J3'] = 0.04  # Dictionary-like access

# Query leaks
print(f"Total leakage: {leaks.total_leakage} m³/s")
print(f"Leak at J1: {leaks['J1']} m³/s")

# Check for leaks
if 'J1' in leaks:
    print(f"J1 has leak: {leaks['J1']}")

# Save to file
leaks.to_json('leaks.json')
leaks.to_csv('leaks.csv')

# Export to DataFrame
df = leaks.to_dataframe()
print(df)
```

### Example 10: Graph-Based Pipe Removal

```python
from found.networks import NetworkGraphPipeRemover
from found.graphs import EPANETNetworkGraph

# Create graph from WNTR model
graph = EPANETNetworkGraph.from_wntr_model(wn)

# Remove pipes from graph
remover = NetworkGraphPipeRemover(
    pipe_names=['P1', 'P2'],
    check_bridges=True,  # Prevent disconnecting network
    text_logging=True
)

try:
    remover.apply(graph)
    print(f"Successfully removed pipes: {remover.text_log}")
except BridgeRemovalException as e:
    print(f"Cannot remove pipe: {e}")
```

### Example 11: Structured Logging

```python
from found.networks import PipeDiameterModifier

# Enable structured logging
modifier = PipeDiameterModifier(
    new_values={'P1': 0.4, 'P2': 0.35},
    enable_structured_log=True
)
modifier.apply(wn)

# Access structured log
for entry in modifier.structured_log.get('PipeDiameterModifier', []):
    print(f"Component: {entry['component_name']}")
    print(f"  Old value: {entry['old_value']}")
    print(f"  New value: {entry['new_value']}")
```

## API Reference

### NetworkDataAccessor

Main class for accessing EPANET network data.

#### Methods

- `from_inp_file(file_path) -> NetworkDataAccessor`: Load from INP file
- `to_inp_file(file_path)`: Save to INP file
- `from_json_file(file_path) -> NetworkDataAccessor`: Load from JSON
- `to_json_file(file_path)`: Save to JSON
- `from_dict(data) -> NetworkDataAccessor`: Create from dictionary
- `to_dict() -> dict`: Convert to dictionary
- `get_junction_by_name(name) -> Junction`: Get junction by name
- `get_pipe_by_name(name) -> Pipe`: Get pipe by name
- Component-specific accessors for all network types

### WNTRNetworkModifier

Main class for modifying WNTR network models.

#### Attributes

- `network`: WNTR network model instance
- `pipeline`: NetworkModifierPipeline for managing modifications

#### Methods

- `modify_network()`: Apply all modifications in pipeline
- `save_network(file_path, overwrite=False)`: Save modified network
- `find_small_pipes(diameter_threshold=0.1)`: Find pipes below threshold

### NetworkModifierPipeline

Pipeline for managing multiple network modifications.

#### Methods

- `add_modifier(modifier)`: Add modifier to pipeline
- `pop_modifier()`: Remove last modifier
- `apply(wn)`: Apply all modifiers sequentially
- `register(modifier_class)`: Register custom modifier class

#### Attributes

- `modifiers`: List of modifiers to apply
- `history`: List of applied modifiers
- `log`: Text log of all modifications
- `structured_log`: Dictionary of structured modification records

### Modifier Classes

All modifier classes share common patterns:

#### PipeDiameterModifier

**Parameters:**
- `new_values`: Mapping of pipe names to new diameter values or Parameters
- `log`: List for storing modification messages
- `enable_structured_log`: Enable structured logging

#### PipeDiameterMultiplierModifier

**Parameters:**
- `multipliers`: Single multiplier or mapping of pipe names to multipliers
- `log`: Modification log
- `enable_structured_log`: Enable structured logging

#### NodeEmitterModifier

**Parameters:**
- `emitter_coefficients`: Mapping of node names to emitter coefficients
- `nominal_pressure`: Nominal pressure for calculations (default: 100.0)
- `pressure_exponent`: Pressure exponent (default: 0.5)
- `required_pressure`: Required pressure at nodes
- `minimum_pressure`: Minimum pressure at nodes

**Static Methods:**
- `calculate_emitter_from_diameter(diameter, nominal_pressure=100.0)`: Calculate emitter coefficient from leak diameter

### JunctionLeaks

Dictionary-like container for leak management.

#### Methods

- `add_leak(junction, size)`: Add or increment leak
- `remove_leak(junction, size)`: Remove or decrement leak
- `clear_leak(junction)`: Remove all leakage from junction
- `to_json(file_path)`: Export to JSON
- `from_json(file_path) -> JunctionLeaks`: Import from JSON
- `to_csv(file_path)`: Export to CSV
- `from_csv(file_path) -> JunctionLeaks`: Import from CSV
- `to_dataframe() -> pd.DataFrame`: Convert to DataFrame

#### Properties

- `total_leakage`: Sum of all leaks
- `unit`: Leak unit (default: "m³/s")

## Best Practices

### 1. Pipeline Organization

Organize related modifications into logical groups:

```python
# Group related modifications
pipeline = NetworkModifierPipeline(modifiers=[
    # Geometry modifications
    PipeDiameterModifier(new_values={...}),
    PipeRoughnessModifier(new_values={...}),
    
    # Demand modifications
    NodeDemandModifier(new_values={...}),
    
    # Operational modifications
    ValveModifier(new_values={...})
])
```

### 2. Enable Logging for Debugging

```python
# Enable logging to track modifications
modifier = PipeDiameterModifier(
    new_values={...},
    enable_structured_log=True
)

# Review modifications
for entry in modifier.structured_log.values():
    print(entry)
```

### 3. Validate Before Saving

```python
# Validate network before saving
import wntr

modifier = WNTRNetworkModifier(wn)
modifier.modify_network()

# Run hydraulic simulation to check validity
try:
    sim = wntr.sim.EpanetSimulator(modifier.network)
    results = sim.run_sim()
    print("Network is valid!")
except Exception as e:
    print(f"Network validation failed: {e}")
```

### 4. Use Uncertainty for Robustness Analysis

```python
# Perform multiple realizations with uncertainty
from found.uncertainty import Parameter, AdditiveUncertainty

results = []
for i in range(100):
    modifier = PipeDiameterModifier(
        new_values={
            'P1': Parameter(
                name=f'P1_{i}',
                nominal_value=0.4,
                uncertainty=AdditiveUncertainty(...)
            )
        }
    )
    modifier.apply(wn)
    # Reset parameter for next sample
    # ... perform simulation and collect results
```

### 5. Handle Large Bulk Modifications

```python
# Use DataFrame modifier for large-scale demand changes
import pandas as pd

# Load demands from external source
demands = pd.read_csv('demands.csv').set_index('node_id')

modifier = NodeDemandDataFrameModifier(
    new_values=demands,
    skip_nonexistent=True
)
modifier.apply(wn)
```

### 6. Prevent Network Disconnection

```python
# Always check for bridges when removing pipes
remover = NetworkGraphPipeRemover(
    pipe_names=['P1', 'P2'],
    check_bridges=True  # Prevents disconnecting network
)

try:
    remover.apply(graph)
except BridgeRemovalException as e:
    print(f"Cannot remove critical pipe: {e}")
```

### 7. Combine Selection with Modification

```python
# Select pipes, then modify them
selector = PipeDiameterSelector(min_diameter=0.1, max_diameter=0.3)
small_pipes = selector.select(wn, candidates=None)

# Apply modifications only to selected pipes
modifier = PipeRoughnessModifier(
    new_values={pipe: 120 for pipe in small_pipes}
)
modifier.apply(wn)
```

## Troubleshooting

### Issue: Parameter sample() returns wrong type

**Problem:** Getting `TypeError: float() argument must be a string or a real number`

**Solution:** Ensure Parameter is instantiated with keyword arguments:

```python
# ❌ Wrong - positional arguments
param = Parameter(0.4, AdditiveUncertainty(...))

# ✅ Correct - keyword arguments
param = Parameter(
    name='pipe_diameter',
    nominal_value=0.4,
    uncertainty=AdditiveUncertainty(...)
)
```

### Issue: Modifications not applied

**Problem:** Modifications don't appear in the network

**Solution:** Ensure you call `apply()` on the pipeline:

```python
pipeline.add_modifier(modifier)
pipeline.apply(wn)  # Don't forget this!
```

### Issue: Network becomes disconnected

**Problem:** Removing pipes causes network disconnection

**Solution:** Use graph-based removal with bridge checking:

```python
remover = NetworkGraphPipeRemover(
    pipe_names=['P1'],
    check_bridges=True  # Enable bridge detection
)
```

### Issue: Emitter coefficient calculation

**Problem:** Uncertain how to convert leak diameter to emitter coefficient

**Solution:** Use the static helper method:

```python
leak_diameter_m = 0.01  # 10mm in meters
coeff = NodeEmitterModifier.calculate_emitter_from_diameter(
    diameter=leak_diameter_m,
    nominal_pressure=100.0
)
```

### Issue: Bulk modifications slow

**Problem:** Modifying many nodes individually is slow

**Solution:** Use DataFrame-based modifier:

```python
# Instead of individual modifications
for node, demand in demands.items():
    modifier = NodeDemandModifier({node: demand})
    modifier.apply(wn)

# Use bulk modification
modifier = NodeDemandDataFrameModifier(
    new_values=demands_df,
    skip_nonexistent=True
)
modifier.apply(wn)
```

### Issue: Lost modification history

**Problem:** Can't track what was modified

**Solution:** Enable structured logging:

```python
modifier = PipeDiameterModifier(
    new_values={...},
    enable_structured_log=True
)
modifier.apply(wn)

# Save log for later analysis
import json
with open('modifications.json', 'w') as f:
    json.dump(modifier.structured_log, f, indent=2)
```

## Related Modules

- **simulation**: Run hydraulic simulations on modified networks
- **calibration**: Calibrate network parameters using modifications
- **uncertainty**: Define uncertain parameters for modifications
- **graphs**: Graph-based analysis of network topology

## Contributing

When adding new modifier classes:

1. Inherit from `NetworkComponentModifier` and `StructuredLoggingMixin`
2. Implement the `apply(wn)` method
3. Add structured logging calls for tracking
4. Register with `NetworkModifierPipeline.register(YourModifier)`
5. Add comprehensive docstrings and examples

Example template:

```python
@dataclass
class CustomModifier(NetworkComponentModifier, StructuredLoggingMixin):
    """Your modifier description.
    
    Attributes:
        param1: Description
        log: Modification log
        enable_structured_log: Enable structured logging
    """
    param1: Any
    log: list[str] = field(default_factory=list)
    enable_structured_log: bool = False
    
    def __post_init__(self):
        StructuredLoggingMixin.__init__(self, self.enable_structured_log)
    
    def apply(self, wn: WNTRNetworkModel) -> None:
        """Apply modification."""
        self.log.clear()
        # ... implementation ...
        self.add_to_structured_log(...)
```

## License

Part of the FOUND uncertainty framework. See LICENSE file for details.
