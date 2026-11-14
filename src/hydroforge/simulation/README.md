# Simulation Module (legacy, incomplete)

This package is an older `Simulator` / `SimulationResults` abstraction. It is
**not currently importable** and is superseded by `hydroforge.backends`.

## Actual contents

```
simulation/
├── __init__.py        # Imports modules that do not exist
├── common.py          # DemandModel, Simulator, SimulationResults, model loaders
├── wntr_simulator.py  # WNTRSimulator/EPANETSimulator and config dataclasses
└── README.md
```

There is no `tsnet_simulator.py`, `events.py`, or `results.py` in the source
tree, although `__init__.py` and `wntr_simulator.py` import them.

## Current status

- `import hydroforge.simulation` fails. Without TSNet installed, the first
  failure is the unconditional `tsnet` import in `common.py`; after that,
  imports of the missing `.results` and `.tsnet_simulator` modules also prevent
  the package from loading.
- `common.py` imports `tsnet` unconditionally, so it requires the optional
  `tsnet` package even for WNTR-only use.
- `wntr_simulator.py` imports `.results`, which does not exist.
- The package does not receive test coverage.

## Intended abstractions (as written)

`common.py` defines:

- `DemandModel` — enum with `DemandModel.DD` and `DemandModel.PDD`
- `Simulator` — abstract generic with `run(model) -> results`
- `SimulationResults` — abstract interface declaring `node_variables` and
  `link_variables`
- `load_wntr_model(path)` and `load_tsnet_model(path)`

`wntr_simulator.py` defines `WNTRSimulatorConfig`, `EPANETSimulatorConfig`,
`WNTRSimulator`, and `EPANETSimulator` with `run(model)`. The module cannot be
imported successfully in the current tree because it imports the missing
`.results` module.

## Recommended replacement

Use `hydroforge.backends`, which provides working WNTR, EPANET, TSNet,
TSNetPlus, and PTSNet adapters:

```python
from hydroforge.backends import get_backend

backend = get_backend("wntr")
model = backend.load_model("network.inp")
backend.apply_config(model_config)
results = backend.create_simulator(run_config).run(model)
```

See [`../backends/README.md`](../backends/README.md).

## Historical note

Earlier revisions of this README described a TSNet transient workflow, event
classes, and result wrappers. Those modules are not present in the current
source tree and the descriptions have been removed rather than retained as
inaccurate documentation. The transient equivalents now live under
`hydroforge.backends.tsnet`, `hydroforge.backends.tsnetplus`, and
`hydroforge.backends.ptsnet`.

## Remediation

See `spec/0002-code-review-remediation.md` for the recommendation to remove or
rewrite this package. No modules have been deleted in this documentation pass.
