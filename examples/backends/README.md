# Backend Examples

These examples demonstrate the `hydroforge.backends` API: selecting a backend,
loading a model, applying backend-specific configuration, and constructing the
matching HydroForge simulator.

They are intentionally separate from `examples/simulation`, whose examples focus
on running particular network simulations. The examples here focus on the
backend abstraction and its integration points.

## Requirements

Run the examples from the HydroForge repository root with the project source
directory on `PYTHONPATH`:

```bash
PYTHONPATH=src python examples/backends/backend_registry.py
```

The examples use the optional solver packages only when their corresponding
script is run. The project currently declares no optional-dependency extras for
those solvers, so install TSNet, TSNetPlus, or PTSNet through your normal
environment-management workflow if you want to run the corresponding script.
WNTR is a core dependency.

## Examples

### `backend_registry.py`

Lists the backends registered with HydroForge and resolves each adapter lazily.
Unavailable optional dependencies are reported in the table; they do not stop
the other backends from being inspected.

### `configuration.py`

Displays the fields and defaults of `TSNetConfig` and `PTSNetConfig`:

```python
from hydroforge.backends.ptsnet.config import PTSNetConfig
from hydroforge.backends.tsnet.config import TSNetConfig
```

These configuration modules are safe to import without loading TSNet, TSNetPlus,
PTSNet, or WNTR. The configurations are applied later to a loaded model or
simulator by the selected backend.

### `configuration_management.py`

Shows how configuration for the WNTR backend can be updated, settings overriden
and differences displayed using rich.Console.

### `wntr_backend.py`

Selects the WNTR adapter, loads `tests/base_networks/Net1.inp`, applies a
`WNTRConfig`, creates a WNTR Python simulator, and runs a steady-state model.
It then creates an EPANET adapter to demonstrate that `EPANETSimulatorConfig`
is supplied only when constructing the EPANET simulator.

```bash
PYTHONPATH=src python examples/backends/wntr_backend.py
```

### `tsnet_backend.py`

Selects TSNet, loads the same EPANET model, applies `TSNetConfig`, and runs a
transient simulation through the HydroForge adapter. If TSNet or one of its
runtime dependencies is unavailable, the example reports the reason and exits
without affecting other examples.

```bash
PYTHONPATH=src python examples/backends/tsnet_backend.py
```

### `ptsnet_backend.py`

Selects PTSNet, applies `PTSNetConfig` to the PTSNet simulation settings, and
runs the model through the HydroForge adapter. PTSNet has stricter Python and
NumPy compatibility requirements; an unavailable or incompatible installation
is reported cleanly.

```bash
PYTHONPATH=src python examples/backends/ptsnet_backend.py
```

### `tsnetplus_backend.py`

Selects TSNetPlus, applies `TSNetPlusConfig`, schedules a validated
`DemandPulseEvent`, and runs the transient model.

```bash
PYTHONPATH=src python examples/backends/tsnetplus_backend.py
```

## Common Pattern

Every backend adapter follows the same selection and execution shape:

```python
from hydroforge.backends import get_backend

backend = get_backend("wntr")
model = backend.load_model("network.inp")
backend.apply_config(model_config)
results = backend.create_simulator(run_config).run(model)
```

The config type and simulation details are backend-specific. WNTR uses a
`WNTRConfig` for persistent model options and a separate runtime config:
`WNTRSimulatorConfig` for the Python solver or `EPANETSimulatorConfig` for the
EPANET solver. TSNet, TSNetPlus, and PTSNet currently use one configuration
type for both scopes.

## Supported Backends

| Name | Adapter | Solver package |
| --- | --- | --- |
| `wntr` | `WNTRBackend` | WNTR |
| `tsnet` | `TSNetBackend` | TSNet |
| `tsnetplus` | `TSNetPlusBackend` | TSNetPlus |
| `ptsnet` | `PTSNetBackend` | PTSNet |

For an extended TSNetPlus event example, see
`examples/simulation/ex2_dynamic_simulation.py`.
