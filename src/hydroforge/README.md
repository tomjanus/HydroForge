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
├── auxiliary/                   # GENERIC: Configuration I/O, logging, exceptions, utilities
├── uncertainty/                 # GENERIC: Distributions, uncertainties, parameters, CDFs
├── sampling/                    # GENERIC: Monte Carlo, LHS, Sobol, Halton and structured samplers
├── measurements/                # GENERIC: Sensor / measurement imperfection models
│
└── wdn_modelling/               # WDN / EPANET-specific modelling
    ├── __init__.py              # Convenience re-exports (get_backend, EPANETNetworkGraph, ...)
    ├── backends/                # WNTR, EPANET, TSNet, TSNetPlus and PTSNet facade
    ├── epanetfile_io/           # Typed EPANET .inp parsing, editing and writing
    ├── graphs/                  # EPANETNetworkGraph and EPANETGraphPlotter
    ├── modifiers/               # WNTR model and graph modifiers
    ├── networks/                # Component selectors and JunctionLeaks
    └── measurement_placement/   # Sensor placement and sensor-network graph (depends on graphs)
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
from hydroforge.measurements import RandomNoiseSensor, WindowAverager

sensor = RandomNoiseSensor(sigma=0.05, seed=42)
print(sensor.measure([1.0, 1.1, 0.9]))

print(WindowAverager(window_size=2).average([1.0, 1.1, 0.9, 1.2]))
```

### Simulation backends

```python
from hydroforge.wdn_modelling.backends import get_backend

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

- `hydroforge.wdn_modelling.epanetfile_io` provides `EPANETFileIO` for low-level tokenized
  sections and `EPANETNetworkModelIO` / `EPANETNetworkModel` for a typed,
  editable model.
- `hydroforge.wdn_modelling.graphs` provides `EPANETNetworkGraph` and
  `EPANETGraphPlotter`.
- `hydroforge.wdn_modelling.measurement_placement` provides the placement
  strategies and `SensorPlacer`.
- `hydroforge.wdn_modelling.networks` provides model component selectors and
  `JunctionLeaks`; model and graph modification classes live in
  `hydroforge.wdn_modelling.modifiers`.

## Legacy and incomplete packages

- `hydroforge.cli` provides argument parsing only; its subcommands print a
  not-implemented message and return a failure status.

The legacy `hydroforge.simulation`, `hydroforge.scenario_generation`,
`hydroforge.topology`, and `hydroforge.uncertainty_sampling` packages have been
removed from the source tree. `hydroforge.wdn_modelling.backends` is the sole
supported simulation implementation and `hydroforge.sampling` is the canonical
sampling package; see
[`spec/SPEC-legacy-surface-retirement.md`](../../spec/SPEC-legacy-surface-retirement.md)
for the retirement record.

## Related documentation

- [`auxiliary/README.md`](auxiliary/README.md)
- [`uncertainty/README.md`](uncertainty/README.md)
- [`sampling/README.md`](sampling/README.md)
- [`measurements/README.md`](measurements/README.md)
- [`wdn_modelling/backends/README.md`](wdn_modelling/backends/README.md)
- [`wdn_modelling/epanetfile_io/README.md`](wdn_modelling/epanetfile_io/README.md)
- [`wdn_modelling/graphs/README.md`](wdn_modelling/graphs/README.md)
- [`wdn_modelling/networks/README.md`](wdn_modelling/networks/README.md)
- [`wdn_modelling/modifiers/README.md`](wdn_modelling/modifiers/README.md)

## License

HydroForge is distributed under the GNU General Public License v3.0. See the
repository [`LICENSE`](../../LICENSE).
