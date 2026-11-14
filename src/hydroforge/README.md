# HydroForge Package

This directory contains the `hydroforge` Python package: uncertainty injection
and scenario-generation support for water distribution network (WDN) models.

For installation, examples, and development commands, see the repository
[`README.md`](../../README.md).

## Package map

```
hydroforge/
├── __init__.py                  # Version and default logging configuration
├── __main__.py                  # python -m hydroforge entry point
├── cli.py                       # Placeholder command-line interface
│
├── auxiliary/                   # Configuration I/O, logging, exceptions, utilities
├── uncertainty/                 # Distributions, uncertainties, parameters, CDFs
├── sampling/                    # Monte Carlo, LHS, Sobol, Halton and structured samplers
├── sensors/                     # Sensor models, placement strategies, sensor-network graph
├── graphs/                      # EPANETNetworkGraph and EPANETGraphPlotter
├── networks/                    # Component selectors and JunctionLeaks
├── modifiers/                   # WNTR model and graph modifiers
├── epanetfile_io/               # Typed EPANET .inp parsing, editing and writing
├── backends/                    # WNTR, EPANET, TSNet, TSNetPlus and PTSNet facade
├── topology/                    # Partial topology helpers for sensor/transient networks
│
├── simulation/                  # Legacy Simulator interface (currently incomplete)
├── scenario_generation/         # Synthetic measurement generation (not yet migrated)
└── uncertainty_sampling/        # Deprecated, divergent legacy sampling copy
```

## Supported entry points

### Uncertainty and sampling

```python
from hydroforge.uncertainty import (
    Parameter,
    ParameterType,
    AdditiveUncertainty,
    NormalDistribution,
)
from hydroforge.sampling import LatinHypercubeSampler

diameter = Parameter(
    name="diameter",
    nominal_value=200.0,
    uncertainty=AdditiveUncertainty(NormalDistribution(0.0, 2.5)),
    type=ParameterType.NUMERICAL,
)

for scenario in LatinHypercubeSampler([diameter]).generate(10):
    print(scenario.values)
```

`hydroforge.sampling` imports `SALib`; install it before importing the sampling
package.

### Sensors

```python
from hydroforge.sensors import RandomNoiseSensor
from hydroforge.sensors.sensors import WindowAverager

sensor = RandomNoiseSensor(sigma=0.05, seed=42)
print(sensor.measure([1.0, 1.1, 0.9]))

print(WindowAverager(window_size=2).average([1.0, 1.1, 0.9, 1.2]))
```

### Simulation backends

```python
from hydroforge.backends import get_backend

backend = get_backend("wntr")
model = backend.load_model("network.inp")
results = backend.create_simulator().run(model)
pressure = results.get_node_variable("pressure", ["J1"], as_dataframe=True)
```

Supported backend names are `wntr`, `tsnet`, `tsnetplus`, and `ptsnet`. Only
`wntr` is installed as a core dependency. `get_backend()` currently returns a
cached mutable instance, so consecutive runs in one process are not isolated;
see `spec/0002-code-review-remediation.md`.

### EPANET files, graphs and sensor placement

- `hydroforge.epanetfile_io` provides `EPANETFileIO` for low-level tokenized
  sections and `EPANETNetworkModelIO` / `EPANETNetworkModel` for a typed,
  editable model.
- `hydroforge.graphs` provides `EPANETNetworkGraph` and `EPANETGraphPlotter`.
- `hydroforge.sensors.placement` provides the placement strategies and
  `SensorPlacer`.
- `hydroforge.networks` provides model component selectors and `JunctionLeaks`;
  model and graph modification classes live in `hydroforge.modifiers`.

## Legacy and incomplete packages

- `hydroforge.simulation` defines an older `Simulator`/`SimulationResults`
  abstraction. Its `__init__.py` imports modules that are not present, and
  `common.py` imports `tsnet` unconditionally. Use `hydroforge.backends` for new
  work.
- `hydroforge.scenario_generation.measurement_creator` still imports the retired
  `found` package and does not import successfully. The intended replacement is
  specified in `spec/0001-uncertainty-scenario-generation.md`.
- `hydroforge.uncertainty_sampling` is a divergent legacy copy and currently
  fails to import because it references the removed `ParameterKind` symbol.
  Use `hydroforge.sampling`.
- `hydroforge.cli` provides argument parsing only; its subcommands print a
  not-implemented message and return a failure status.

## Related documentation

- [`auxiliary/README.md`](auxiliary/README.md)
- [`uncertainty/README.md`](uncertainty/README.md)
- [`sampling/README.md`](sampling/README.md)
- [`sensors/README.md`](sensors/README.md)
- [`graphs/README.md`](graphs/README.md)
- [`networks/README.md`](networks/README.md)
- [`epanetfile_io/README.md`](epanetfile_io/README.md)
- [`backends/README.md`](backends/README.md)
- [`simulation/README.md`](simulation/README.md)
- [`scenario_generation/README.md`](scenario_generation/README.md)

## License

HydroForge is distributed under the GNU General Public License v3.0. See the
repository [`LICENSE`](../../LICENSE).
