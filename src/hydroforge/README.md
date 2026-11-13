# HydroForge - An uncertainty injection and scenario generation framework for water distribution network simulations

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## Project Overview

The HydroForge toolkit provides a comprehensive suite of tools for injecting model
and measurement uncertainties into water distribution network simulations. This package enables researchers and practitioners to:

- **Perform uncertainty analysis** on water network models with various uncertainty sources (model uncertainty and measurment uncertainty via sensors)
- **Generate uncertainty scenarios for subsequent probabilistic simulations** using multiple uncertainty sampling algorithms.
- **Prvide various methods for sensor placement** 
- **Conduct hydraulic simulations** with high-performance numerical methods
- **Analyze network topology** using graph-based approaches

---

## File Structure

```
found/
├── __init__.py                              # Package initialization and exports
│
├── Core Analysis Modules
│   ├── simulator.py                         # Hydraulic simulation strategies (WNTR-based)
│   ├── uncertainty.py                       # Uncertainty models for parameters
│   ├── calibration.py                       # Network calibration tools
│   ├── sensor_placement.py                  # Sensor placement algorithms
│   ├── sensors.py                           # Sensor management and data handling
│   ├── ga.py                                # Genetic algorithm optimization
│   └── graph.py                             # Network graph representation and analysis
│
├── Network Manipulation
│   ├── network_dict_wrapper.py              # Lightweight network data wrapper
│   ├── network_graph_component_selectors.py # Graph component selectors
│   ├── network_graph_modifier.py            # Graph structure modification
│   ├── network_model_component_selectors.py # WNTR model component selectors
│   ├── network_model_modifier.py            # WNTR model modification
│   └── swmm_file_parser.py                  # EPANET/SWMM file parser
│
├── Utilities
│   ├── utils.py                             # General utility functions
│   ├── config.py                            # Configuration management
│   ├── constants.py                         # Project constants
│   ├── logging.py                           # Logging utilities
│   ├── visualization.py                     # Plotting and visualization
│   └── colebrook_white.py                   # High-performance friction calculations
│
├── Legacy Files (Scheduled for Removal)
│   ├── _case_study_analysis.py              # ⚠️ Legacy - use new modules
│   ├── _case_study_editing.py               # ⚠️ Legacy - use new modules
│   ├── _graph_editing.py                    # ⚠️ Legacy - use graph.py
│   ├── _hydraulic_tools.py                  # ⚠️ Legacy - use simulator.py
│   ├── _measurement_data_creation.py        # ⚠️ Legacy - use new modules
│   ├── _GIS_data_preparation.py             # ⚠️ Legacy - use new modules
│   ├── _misc_light.py                       # ⚠️ Legacy - use utils.py
│   └── _plotting.py                         # ⚠️ Legacy - use visualization.py
│
├── Subdirectories
│   ├── burst_detection/                     # Burst detection algorithms
│   ├── cython/                              # Cython-compiled extensions
│   │   ├── setup.py                         # Cython build configuration
│   │   └── colebrook_white_cython.pyx       # Cython implementation
│   ├── superceded/                          # Deprecated code (reference only)
│   └── __pycache__/                         # Python bytecode cache
│
└── README.md                                # This file
```

---

### Key Features

- 🔧 **Multiple Calculation Backends**: Supports Numba JIT, Cython, and pure Python implementations for optimal performance
- 📊 **Comprehensive Uncertainty Modeling**: Handles uncertainties in GIS data, sensor measurements, and hydraulic parameters
- 🎯 **Advanced Sensor Placement**: Implements greedy, k-center, centrality-based, and coverage-based algorithms
- 🚰 **Leakage Localization**: Multiple methods including differential pressure, graph state interpolation, and genetic algorithms
- 📈 **Visualization Tools**: Rich plotting capabilities for network analysis and results presentation
- ⚡ **High Performance**: Optimized Colebrook-White friction factor calculations with JIT compilation

---

## Directory Structure

Below is a description of the main files in this directory and their functionality.

### Core Modules

| File | Description |
|------|-------------|
| `simulator.py` | Abstract simulator interface and concrete implementations for hydraulic simulations using WNTR |
| `uncertainty.py` | Uncertainty models for continuous parameters (diameters, roughness, demands) with sampling capabilities |
| `calibration.py` | Network calibration tools for parameter estimation |
| `sensor_placement.py` | Sensor placement strategies (greedy, k-center, random, centrality-based, coverage-based, dominating set) |
| `sensors.py` | Sensor management and data handling |
| `ga.py` | Genetic algorithm implementation for optimization problems |
| `graph.py` | Water network graph representation and analysis using NetworkX |
| `colebrook_white.py` | High-performance Colebrook-White friction factor calculations with multiple backend options |

### Network Manipulation

| File | Description |
|------|-------------|
| `network_dict_wrapper.py` | Lightweight wrapper for network data using dataclasses and named tuples |
| `network_graph_component_selectors.py` | Selectors for graph-based network components |
| `network_graph_modifier.py` | Tools to modify network graph structure |
| `network_model_component_selectors.py` | Selectors for WNTR model components |
| `network_model_modifier.py` | Tools to modify WNTR network models |
| `swmm_file_parser.py` | Parser for EPANET/SWMM input files |

### Utilities and Configuration

| File | Description |
|------|-------------|
| `utils.py` | General utility functions (file I/O, directory management, timers) |
| `config.py` | Configuration management for project settings |
| `constants.py` | Project-wide constants and default values |
| `logging.py` | Logging configuration and utilities |
| `visualization.py` | Plotting and visualization tools for networks and results |

### Legacy Files (Underscore Prefix)

Files prefixed with an underscore are **legacy implementations** retained temporarily during the refactoring process. These files are scheduled for removal once the transition to the new modular architecture is complete:

- `_case_study_analysis.py` - Legacy case study analysis functions
- `_case_study_editing.py` - Legacy case study editing tools
- `_graph_editing.py` - Legacy graph manipulation functions
- `_hydraulic_tools.py` - Legacy hydraulic modeling utilities
- `_measurement_data_creation.py` - Legacy measurement data generation
- `_GIS_data_preparation.py` - Legacy GIS data processing
- `_misc_light.py` - Legacy miscellaneous utilities
- `_plotting.py` - Legacy plotting functions

> ⚠️ **Note**: Do not use underscore-prefixed files for new development. Refer to the non-underscore equivalents or the new modular architecture.

### Subdirectories

- `burst_detection/` - Tools for burst detection in water networks
- `cython/` - Cython implementations for performance-critical calculations
- `superceded/` - Deprecated code kept for reference

---

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Standard Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/iut-ibk/FOUND_uncertainty.git
   cd FOUND_uncertainty
   ```

2. **Install the package**:
   ```bash
   pip install -e .
   ```

   This will automatically:
   - Install all required dependencies
   - Attempt to build Cython extensions (falls back to Numba if compilation fails)
   - Set up the package in development mode

### Dependencies

Core dependencies (automatically installed):

```
numpy>=1.26.4
pandas>=2.3.1
networkx>=3.5
wntr>=1.3.2
matplotlib>=3.10.5
scipy>=1.16.1
numba>=0.61.2
pyyaml>=6.0.2
rich>=14.1.0
pygad>=3.5.0
```

Optional dependencies:
- `Cython>=3.1.2` - For compiled performance optimizations
- `pytest>=8.3.4` - For running tests
- `pytest-cov>=6.0.0` - For test coverage reports

### Verifying Installation

```python
import found
from found import set_speedup, SpeedupMethod, get_speedup_info

# Check available speedup methods
print(get_speedup_info())

# Set preferred calculation method
set_speedup(SpeedupMethod.NUMBA)
```

---

## Usage

### Quick Start

```python
from found import simulator, uncertainty, sensor_placement
import wntr

# Load a water network
wn = wntr.network.WaterNetworkModel('path/to/network.inp')

# Create a simulator
from found.simulator import WNTRSimulator
sim = WNTRSimulator(wn)

# Run simulation
results = sim.run_sim()

# Get pressure data for specific sensors
sensors = ['n1', 'n10', 'n20']
pressures = sim.get_pressures(sensors, times=0)
```

### Sensor Placement Example

```python
from found.sensor_placement import SensorPlacer, GreedySensorPlacement

# Initialize sensor placer
placer = SensorPlacer(
    inp_file='network.inp',
    num_sensors=10,
    strategy=GreedySensorPlacement
)

# Place sensors
sensor_locations = placer.place_sensors()
print(f"Optimal sensor locations: {sensor_locations}")

# Visualize placement
placer.visualize_placement()
```

### Uncertainty Analysis Example

```python
from found.uncertainty import Normal, Uniform, SampleCache

# Define uncertainties
diameter_uncertainty = Normal(mean=100, std=5)
roughness_uncertainty = Uniform(lower=0.01, upper=0.05)

# Sample with caching to ensure consistency
with SampleCache():
    diameter_sample = diameter_uncertainty.sample()
    roughness_sample = roughness_uncertainty.sample()
```

### High-Performance Calculations

```python
from found import set_speedup, SpeedupMethod, calculate_colebrook_white

# Set fastest available method (Cython > Numba > Python)
set_speedup(SpeedupMethod.AUTO)

# Calculate friction factor
friction = calculate_colebrook_white(
    diameter=0.1,      # meters
    roughness=0.05,    # mm
    reynolds=100000.0  # Reynolds number
)
```

### Network Data Wrapper Example

```python
from found.network_dict_wrapper import WaterNetworkData

# Load network data
network = WaterNetworkData.from_json_file('network_dict.json')

# Access components with named fields
for junction in network.junctions:
    print(f"Junction {junction.id}: elevation={junction.elevation}")

# Modify components
network.modify_junction_by_id('n157', 
                              demand_pattern='Commercial',
                              elevation='75.0')

# Save modified network
network.to_json_file('modified_network.json')
```

---

## Workflow

The typical workflow for uncertainty analysis and leakage localization:

### 1. Setup (`1_setup.py`)
- Create directory structure for case studies
- Configure network files and scenarios
- Set up uncertainty parameters

### 2. Dataset Generation (`2_dataset_generation.py`)
- Generate measurement data for calibration and leakage scenarios
- Create synthetic sensor readings with uncertainties
- Prepare training/validation datasets

### 3. Simulation (`3b_simulation_leakages_auto.py`)
Run leakage localization with various methods:

**a) Differential Pressure & Graph State Methods**
```python
scenarios = [
    ['L-Town'], 
    ['differential_pressure', 'graph_state'], 
    list(uncertainty_scenarios['GIS_data'].keys()), 
    list(uncertainty_scenarios['sensors'].keys()), 
    list(uncertainty_scenarios['pressure_calibration'].keys()), 
    list(uncertainty_scenarios['pressure_leakage'].keys())
]
```

**b) Sensitivity Analysis (No Leakage)**
```python
scenarios = [
    ['L-Town'], 
    ['sensitivity_analyse'], 
    list(uncertainty_scenarios['GIS_data'].keys()), 
    list(uncertainty_scenarios['sensors'].keys()), 
    list(uncertainty_scenarios['pressure_calibration'].keys()), 
    ['0']
]
```

**c) Genetic Algorithm-Based Localization**
```python
scenarios = [
    ['L-Town'], 
    ['graph-based_GA'], 
    list(uncertainty_scenarios['GIS_data'].keys()), 
    list(uncertainty_scenarios['sensors'].keys()), 
    list(uncertainty_scenarios['pressure_calibration'].keys()), 
    list(uncertainty_scenarios['pressure_leakage'].keys())
]
```

### 4. Evaluation (`4_evaluation.py`)
- Analyze localization performance
- Generate performance metrics and visualizations
- Compare different methods and uncertainty scenarios

---

## Configuration

The project uses YAML configuration files for managing case studies and scenarios. Example `config.yaml`:

```yaml
network:
  filename: "L-Town.inp"

leakage_scenarios:
  single_time_step:
    small_leak:
      flow_rate: 10.0
      location: "n100"
    large_leak:
      flow_rate: 50.0
      location: "n200"

uncertainties:
  GIS_data:
    diameter_uncertainty: 0.05
    roughness_uncertainty: 0.1
  sensors:
    measurement_noise: 0.5
  pressure_calibration:
    calibration_error: 1.0
```

---

## Performance Optimization

The package offers multiple performance backends for computationally intensive operations:

### Available Backends

1. **Cython** (Fastest)
   - Pre-compiled C extensions
   - ~100x faster than pure Python
   - Requires compilation during installation

2. **Numba JIT** (Fast)
   - Just-in-time compilation
   - ~50x faster than pure Python
   - No compilation needed, works out of the box

3. **Pure Python** (Fallback)
   - Always available
   - Used when other backends fail

### Selecting a Backend

```python
from found import set_speedup, SpeedupMethod, benchmark_speedup_methods

# Automatic selection (prefers Cython > Numba > Python)
set_speedup(SpeedupMethod.AUTO)

# Manual selection
set_speedup(SpeedupMethod.NUMBA)  # or CYTHON, PYTHON

# Benchmark all methods
results = benchmark_speedup_methods(n_iterations=10000)
```

---

## Documentation

Additional documentation is available:

- **[MODIFICATION_GUIDE.md](../MODIFICATION_GUIDE.md)** - Guide for modifying network data using the wrapper
- **[NETWORK_WRAPPER_GUIDE.md](../NETWORK_WRAPPER_GUIDE.md)** - Detailed documentation on the network data wrapper

---

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=found --cov-report=html

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m "not slow"    # Skip slow tests
```

---

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Code Style**: Follow PEP 8 conventions
2. **Documentation**: Add docstrings to all public functions and classes
3. **Testing**: Include tests for new features
4. **Legacy Code**: Do not modify underscore-prefixed files; update their modern equivalents instead

### Development Setup

```bash
# Clone the repository
git clone https://github.com/iut-ibk/FOUND_uncertainty.git
cd FOUND_uncertainty

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

---

## Authors and Acknowledgments

**Institution**: Institute of Urban Water Management and Landscape Water Engineering (IUT-IBK)

**Repository**: [https://github.com/iut-ibk/FOUND_uncertainty](https://github.com/iut-ibk/FOUND_uncertainty)

---

## Citation

If you use this software in your research, please cite:

```bibtex
@software{found_uncertainty,
  title = {FOUND: Water Network Uncertainty Analysis and Leakage Localization Toolkit},
  author = {{IUT-IBK}},
  year = {2025},
  url = {https://github.com/iut-ibk/FOUND_uncertainty}
}
```

---

## Contact

For questions, issues, or contributions, please open an issue on the [GitHub repository](https://github.com/iut-ibk/FOUND_uncertainty/issues).
