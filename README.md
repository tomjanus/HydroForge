# HydroForge

[![License: GPL-3.0](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://opensource.org/licenses/GPL-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Status: Alpha](https://img.shields.io/badge/status-Alpha-orange.svg)](https://github.com/tomjanus/HydroForge)

**HydroForge** is a toolkit for uncertainty injection and scenario generation in
water distribution network (WDN) simulations. It provides probability
distributions and uncertain parameters, sampling strategies, sensor-imperfection
models, network modifiers, EPANET file I/O, graph analysis, sensor placement, and
a common simulation-backend facade.

## Project status

HydroForge is alpha software. The supported simulation entry point is
`hydroforge.backends`. The older `hydroforge.simulation` package is retained for
compatibility but is currently incomplete, and
`hydroforge.scenario_generation` is not yet connected to the current API. See
[`spec/0002-code-review-remediation.md`](spec/0002-code-review-remediation.md)
for the reviewed defects and remediation plan.

## Installation

HydroForge requires Python 3.10 or newer. Install from a source checkout:

```bash
git clone https://github.com/tomjanus/HydroForge.git
cd HydroForge

# Runtime installation
pip install -e .

# Development installation (black, flake8, mypy, pytest)
pip install -e ".[dev]"
```

The core dependencies are declared in `pyproject.toml` and include NumPy, SciPy,
pandas, NetworkX, Matplotlib, PyYAML, Rich, pygad, cloudpickle, and WNTR.

Optional transient backends are not yet declared as package extras. Install
their solver packages separately when needed:

| Backend | Solver package |
| --- | --- |
| `wntr` | WNTR (core dependency) |
| `tsnet` | TSNet |
| `tsnetplus` | TSNetPlus |
| `ptsnet` | PTSNet |

The sampling package imports `SALib`. `SALib` is required by the current source
but is not yet declared in `pyproject.toml`; install it explicitly until the
packaging defect is fixed.

## Quick start

```python
from hydroforge import __version__
from hydroforge.sensors import RandomNoiseSensor

print(f"HydroForge version {__version__}")

sensor = RandomNoiseSensor(sigma=0.05, seed=42)
measurement = sensor.measure(1.0)
```

The command-line interface is currently a placeholder. `hydroforge --version`
works, but `run-analysis`, `localize`, and `sensor-placement` report that they
are not implemented and exit with a non-zero status.

## Package layout

| Package | Purpose | Current state |
| --- | --- | --- |
| `hydroforge.uncertainty` | Distributions, uncertainty transforms, parameters, CDFs | Supported |
| `hydroforge.sampling` | Monte Carlo, LHS, Sobol, Halton, stratified, conditional, nested, scenario-tree and mixed sampling | Supported once `SALib` is installed |
| `hydroforge.sensors` | Imperfect-sensor models, window averaging, sensor placement, sensor-network graph | Supported |
| `hydroforge.graphs` | EPANET network graph analysis and visualization | Supported |
| `hydroforge.networks` | Model/graph selectors and `JunctionLeaks` | Supported |
| `hydroforge.modifiers` | WNTR model and graph modifiers | Supported |
| `hydroforge.epanetfile_io` | Typed EPANET `.inp` parsing, editing, and writing without WNTR | Supported |
| `hydroforge.backends` | Common backend facade for WNTR, EPANET, TSNet, TSNetPlus, and PTSNet | Supported; optional solvers required |
| `hydroforge.auxiliary` | Configuration I/O, logging, exceptions, utility helpers | Supported |
| `hydroforge.topology` | Topology helpers for sensor and transient networks | Partial |
| `hydroforge.simulation` | Legacy `Simulator`/`SimulationResults` interface | Legacy; currently incomplete |
| `hydroforge.scenario_generation` | Synthetic measurement generation | Not functional; pending migration |
| `hydroforge.uncertainty_sampling` | Divergent legacy sampling copy | Deprecated and currently unimportable; use `hydroforge.sampling` |

## API overview

### Uncertainty distributions and parameters

```python
from hydroforge.uncertainty import (
    NormalDistribution,
    UniformDistribution,
    AdditiveUncertainty,
    Parameter,
    ParameterType,
)

diameter = Parameter(
    name="diameter",
    nominal_value=200.0,
    uncertainty=AdditiveUncertainty(NormalDistribution(mean=0.0, std_dev=2.5)),
    type=ParameterType.NUMERICAL,
)

value = diameter.sample()
controlled = diameter.sample_from_unit(0.5)
cdf_at_200 = diameter.cdf(200.0)
```

Available distributions include `NormalDistribution`, `UniformDistribution`,
`DiscreteNormalDistribution`, `DiscreteUniformDistribution`,
`DiscreteHistogramDistribution`, `DiracDeltaDistribution`, the categorical
variants, and `DistributionChecker`.

### Sampling

```python
from hydroforge.sampling import MonteCarloSampler, LatinHypercubeSampler

sampler = LatinHypercubeSampler([diameter])
for scenario in sampler.generate(100):
    print(scenario.id, scenario.values)
```

The sampling package also exports `SobolSampler`, `HaltonSampler`,
`StratifiedSampler`, `ConditionalMonteCarloSampler`,
`NestedMonteCarloSampler`, `ScenarioTreeSampler`, `MixedStrategySampler`,
`GibbsSampler` (a legacy independent marginal resampler, not MCMC), and
supporting specification types. See
[`src/hydroforge/sampling/README.md`](src/hydroforge/sampling/README.md) for the
statistical assumptions and current limitations.

### Sensors and sensor placement

```python
from hydroforge.sensors import (
    FixedPrecisionSensor,
    RandomNoiseSensor,
    CompositeSensor,
)
from hydroforge.sensors.sensors import WindowAverager

sensor = CompositeSensor(
    FixedPrecisionSensor(delta_y=0.01),
    RandomNoiseSensor(sigma=0.005, seed=42),
)
measured = sensor.measure(1.234)

averager = WindowAverager(window_size=3)
averaged = averager.average([1.0, 1.1, 0.9, 1.2, 1.0, 1.1])
```

Placement strategies are available through `hydroforge.sensors.placement`:
`GreedySensorPlacement`, `KCentreSensorPlacement`, `RandomSensorPlacement`,
`CentralityBasedSensorPlacement`, `CoverageBasedSensorPlacement`,
`DominatingSetBasedSensorPlacement`, and `FixedLocationSensorPlacement`, all
orchestrated by `SensorPlacer`.

### Simulation backends

```python
from hydroforge.backends import get_backend

backend = get_backend("wntr")
model = backend.load_model("tests/base_networks/Net1_shortened.inp")
results = backend.create_simulator().run(model)

pressure = results.get_node_variable(
    "pressure",
    list(model.junction_name_list)[:3],
    as_dataframe=True,
)
```

Backend configuration is split into persistent model options
(`backend.apply_config(...)`) and simulator runtime options
(`backend.create_simulator(...)`). WNTR uses `WNTRConfig`,
`WNTRSimulatorConfig`, and `EPANETSimulatorConfig`; the transient backends
currently use one configuration type for both scopes.

`get_backend()` currently caches backend instances. Do not assume isolation
between successive runs in one process; this is a known defect tracked in
`spec/0002-code-review-remediation.md`.

### EPANET file I/O

```python
from hydroforge.epanetfile_io import EPANETNetworkModelIO

network = EPANETNetworkModelIO.from_inp_file("network.inp")
network.junctions.modify_by_field("id", "J1", elevation=105.0)
EPANETNetworkModelIO.to_inp_file(network, "modified.inp")
```

### Graphs

```python
from hydroforge.graphs.graph import EPANETNetworkGraph
from hydroforge.graphs.visualization import EPANETGraphPlotter

network = EPANETNetworkGraph.from_epanet_file("network.inp")
print(network.find_total_length())
print(network.find_bridges())

EPANETGraphPlotter(network).plot(title="Water network")
```

## Examples

Examples are grouped under `examples/`. The following example is verified to run
with the core dependencies:

```bash
PYTHONPATH=src python examples/sensors/ex1_sensors.py
```

Other examples demonstrate the backend registry, EPANET file I/O, graph
analysis, sampling, uncertainty distributions, and sensor placement. Some
require optional solvers or `SALib`; several are currently being repaired (see
`spec/0002-code-review-remediation.md`). In particular,
`examples/graphs/ex1_graph_creation.py` and
`examples/simulation/ex1_static_simulation.py` contain stale API calls, and
`examples/uncertainty/ex1_pdfs.py` requires `SALib`.

## Configuration

`hydroforge.auxiliary.load_config()` reads YAML with `yaml.safe_load`. The
repository contains legacy configuration files under `data/config/`; they
reference retired modules and should not be treated as working templates until
migrated.

## Development

```bash
# Formatting
black --check .

# Linting
flake8 --config=.flake8 .

# Type checking
mypy .

# Tests
pytest
```

The CI workflow runs the same commands on Python 3.12 and builds the package.
Test coverage is currently minimal; adding behavioural tests is part of the
remediation plan.

Repository conventions and the development workflow are described in
[`WORKFLOW_GUIDELINES.md`](WORKFLOW_GUIDELINES.md). Domain terminology is in
[`GLOSSARY.md`](GLOSSARY.md).

## Citation

If you use HydroForge in research, cite the HydroForge repository and record the
version or commit used. A formal archived citation and DOI have not yet been
assigned for this project, so no DOI is provided here.

## License

HydroForge is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

HydroForge is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
HydroForge. If not, see <https://www.gnu.org/licenses/>.

## Contributing

Bug reports and feature requests can be opened on the GitHub issue tracker.
Contributions should follow the repository style checks (`black`, `flake8`,
`mypy`) and include tests for new behaviour. Do not open a pull request that
claims validation for a backend or optional dependency that was not actually
exercised.
