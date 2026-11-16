"""HydroForge backend API documentation."""

# HydroForge Backends

`hydroforge.wdn_modelling.backends` provides a common entry point for selecting
hydraulic and transient simulation engines. The registry lazily imports
optional solver dependencies, so importing the package does not require every
supported solver to be installed.

## Select a Backend

```python
from hydroforge.wdn_modelling.backends import get_backend

backend = get_backend("wntr")
model = backend.load_model("network.inp")
```

Supported backend names are `wntr`, `tsnet`, `tsnetplus`, and `ptsnet`.

## Configuration Scopes

Backends separate persistent model configuration from simulator runtime
configuration:

```python
backend.apply_config(model_config)
simulator = backend.create_simulator(run_config)
results = simulator.run(model)
```

For TSNet, TSNetPlus, and PTSNet, their current configuration class is used in
both places. WNTR uses two explicit scopes:

```python
from hydroforge.wdn_modelling.backends.wntr import (
	EPANETSimulatorConfig,
	WNTRConfig,
	WNTRSimulatorConfig,
)
from hydroforge.wdn_modelling.backends.wntr_backend import WNTRBackend

backend = WNTRBackend(simulator="epanet")
model = backend.load_model("network.inp")
backend.apply_config(WNTRConfig(...))
simulator = backend.create_simulator(
	EPANETSimulatorConfig(file_prefix="scenario_01")
)
results = simulator.run(model)
```

`WNTRConfig` applies only to `model.options`. `WNTRSimulatorConfig` represents
runtime options for the Python WNTR solver, while `EPANETSimulatorConfig`
controls EPANET-only behavior such as temporary-file prefixes and cleanup.
Passing the wrong runtime configuration for the selected simulator raises a
`TypeError`.

## Transient Events

TSNet, TSNetPlus, and PTSNet support validated transient events. Events are
added after loading the model and before running the simulator:

```python
from hydroforge.wdn_modelling.backends import get_backend
from hydroforge.wdn_modelling.backends.tsnetplus.events import DemandPulseEvent

backend = get_backend("tsnetplus")
model = backend.load_model("network.inp")
backend.add_event(
	DemandPulseEvent(
		node="N2",
		pulse_duration=1.0,
		start_time=2.0,
		duration_time=4.0,
		multiplier=1.5,
	)
)
```

Available event classes are `ValveClosureEvent`, `ValveOpeningEvent`,
`PumpShutdownEvent`, `PumpStartupEvent`, `BurstEvent`, and `DemandPulseEvent`.
WNTR is a steady-state/extended-period backend; its `add_event()` method logs
an informational message and makes no changes.

## Examples

Runnable backend examples are located in the repository's
[`examples/backends`](../../../examples/backends) directory. They cover registry
discovery, configuration inspection, WNTR and EPANET runtime configuration, and
transient TSNet, TSNetPlus, and PTSNet workflows.

See [`examples/backends/README.md`](../../../examples/backends/README.md) for
the exact commands.
