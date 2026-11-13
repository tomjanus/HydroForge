# HydroForge

[![License: GPL-3.0](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://opensource.org/licenses/GPL-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Status: Alpha](https://img.shields.io/badge/status-Alpha-orange.svg)](https://github.com/tomjanus/HydroForge)

**HydroForge** is an uncertainty injection and scenario generation framework for water distribution network (WDN) model simulations. It allows creating perturbed EPANET network models and applying non-ideal sensors for measuring flows and pressures in WDN network models.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Features](#core-features)
- [API Overview](#api-overview)
- [Examples](#examples)
- [Configuration](#configuration)
- [Development](#development)
- [Citation](#citation)
- [License](#license)

## Installation

HydroForge can be installed via `pip` or `uv`.

### Using pip

```bash
pip install hydroforge
```

### Using uv

```bash
uv add hydroforge
```

### From source

If you want to install from the source code:

```bash
# Clone the repository
git clone https://github.com/tomjanus/HydroForge.git
cd HydroForge

# Install in development mode
pip install -e .
# or with uv
uv pip install -e .
```

## Quick Start

After installation, you can use the HydroForge command-line interface:

```bash
hydroforge --version
```

Available commands:
- `hydroforge run-analysis config.yaml` - Run uncertainty analysis
- `hydroforge localize network.inp measurements.csv` - Run leak localization
- `hydroforge sensor-placement network.inp` - Optimize sensor placement

Or import the package directly in Python:

```python
from hydroforge import __version__
print(f"HydroForge version {__version__}")

from hydroforge.sensors.sensors import PerfectSensor, RandomNoiseSensor
sensor = PerfectSensor()
result = sensor.measure(1.0)
```

## Core Features

- **Uncertainty distributions**: Normal, Uniform, Dirac Delta, Discrete Normal, Discrete Histogram, Categorical Uniform, Categorical Histogram, Categorical Normal
- **Sensor models**: PerfectSensor, FixedPrecisionSensor, RandomNoiseSensor, OffsetSensor, SensitivityErrorSensor, DeadBandSensor, SaturationSensor, DriftSensor, CompositeSensor
- **Water network backends**: WNTR, EPANET integration
- **Scenario generation**: Sobol sequences, Latin Hypercube Sampling
- **Leak localization**: Differential pressure, graph interpolation, genetic algorithm methods
- **Sensor placement optimization**: Shortest-path-based sensor placement

## API Overview

### Uncertainty distributions (`hydroforge.uncertainty`)

- `NormalDistribution(mean, std_dev)` - Continuous normal distribution
- `UniformDistribution(lower, upper)` - Continuous uniform distribution
- `DiracDeltaDistribution(value)` - Point mass distribution
- `DiscreteNormalDistribution(mean, std_dev)` - Discrete normal approximation
- `DiscreteHistogramDistribution(values, probabilities)` - Discrete histogram
- `CategoricalUniformDistribution(categories, nominal_category)` - Categorical uniform
- `CategoricalHistogramDistribution(categories, probabilities)` - Categorical histogram
- `CategoricalNormalDistribution(categories, spread, nominal_category)` - Categorical normal
- `DistributionChecker` - Helper functions for distribution properties

### Sensor models (`hydroforge.sensors`)

- `PerfectSensor` - Ideal sensor with no error
- `FixedPrecisionSensor(delta_y)` - Fixed precision error
- `RandomNoiseSensor(sigma, seed)` - Additive Gaussian noise
- `OffsetSensor(offset)` - Constant offset bias
- `SensitivityErrorSensor(scale)` - Multiplicative scale error
- `DeadBandSensor(threshold)` - Deadband/hysteresis effect
- `SaturationSensor(min_val, max_val)` - Saturation limits
- `DriftSensor(offset_rate)` - Time-dependent drift
- `CompositeSensor` - Combination of multiple sensors

### Water network simulation (`hydroforge.backends`)

- `get_backend("wntr")` - WNTR backend for EPANET simulations
- `get_backend("epanet")` - Direct EPANET integration

### CLI

```
hydroforge --version
hydroforge run-analysis config.yaml
hydroforge localize network.inp measurements.csv
hydroforge sensor-placement network.inp
```

## Examples

Run the included example scripts:

```bash
# Sensor demonstration
python examples/sensors/ex1_sensors.py

# Uncertainty distributions
python examples/uncertainty/ex1_pdfs.py

# Static hydraulic simulation
python examples/simulation/ex1_static_simulation.py
```

Full example list is available in the `examples/` directory.

## Configuration

HydroForge uses YAML configuration files for experiment setup. A typical configuration includes:

- Network model path (EPANET `.inp` file)
- Uncertainty parameters and their distributions
- Sensor placement specifications
- Simulation time settings
- Output directory and file naming

See `examples/` and `docs/` for sample configuration files.

## Development

### Setting up the development environment

```bash
# Clone and install in development mode
git clone https://github.com/tomjanus/HydroForge.git
cd HydroForge
pip install -e ".[dev]"  # installs dev dependencies
# or with uv
uv pip install -e ".[dev]"
```

### Running tests

```bash
pytest
# or with uv
uv run pytest
```

### Linting

```bash
ruff check .
# or with uv
uv run ruff check .
```

## Citation

If you use HydroForge in your research, please cite:

> Janus, T. (2024). HydroForge: An uncertainty injection and scenario generation framework for water distribution network model simulations. doi:10.5281/zenodo.XXXXXXX

## License

HydroForge is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

HydroForge is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with HydroForge. If not, see <https://www.gnu.org/licenses/>.

## Contributing

We welcome contributions to HydroForge! Please see the following guidelines:

- **Bug reports**: Use the issue tracker on GitHub
- **Feature requests**: Open a discussion with your proposal
- **Code contributions**: Fork the repository, make your changes, and submit a pull request
- **Documentation**: Feel free to improve or expand this README, examples, or docs
- **Testing**: Add or update tests for new functionality
- **Citation**: If you use HydroForge in your research, please cite the package

See the `.github/` directory for issue templates and pull request guidelines.

Contributions must follow the project's code style (checked via `ruff`) and include appropriate tests.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/tomjanus/HydroForge.git
cd HydroForge

# Install in development mode with optional dev dependencies
pip install -e ".[dev]"
# or with uv
uv pip install -e ".[dev]"

# Run the test suite
pytest

# Lint the code
ruff check .
```
