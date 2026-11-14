# Scenario Generation Module (not currently functional)

Intended purpose: generate synthetic sensor measurements for a network under
model and measurement uncertainty, for testing calibration and leak-detection
workflows.

## Actual contents

```
scenario_generation/
├── __init__.py          # Empty
├── measurement_creator.py
└── README.md
```

The only implementation is `measurement_creator.py`, which defines two
dataclasses:

- `ArtificialMeasurementCreator`
- `ArtificialMeasurementMultiCreator`

## Current status: import fails

`measurement_creator.py` imports the retired `found` package for its simulator,
sensor, and modifier interfaces. `found` is not part of this repository, so:

```python
import hydroforge.scenario_generation.measurement_creator
```

raises `ModuleNotFoundError: No module named 'found'`. The module also depends
on the incomplete `hydroforge.simulation` abstraction and on modifier and
sensor classes that have since moved or been renamed. It is not covered by
tests.

Do not rely on the class signatures described in older revisions of this file.
They referenced `GaussianNoiseSensor`, `hydroforge.simulation.simulator`,
`RoughnessModifier`, and a constructor shape that do not match the current
source.

## Intended design (as written in the module)

`ArtificialMeasurementCreator` fields:

- `simulator`
- `name`
- `network_modifiers`
- `simulation_time_hours` (default 24)
- `pressure_sensor_names`, `flow_sensor_names`
- `pressure_sensors`, `flow_sensors`
- `output_measurements` (set internally)

Its `create_artificial_measurements(save_to_csv=False, output_dir=None)`
orchestrates model modification, simulation, measurement perturbation, and
optional CSV export. `ArtificialMeasurementMultiCreator` batches multiple
creators and can export CSV or Excel.

These are design intentions, not currently working APIs.

## Path forward

The migration is specified in
[`spec/0001-uncertainty-scenario-generation.md`](../../../spec/0001-uncertainty-scenario-generation.md).
Replacement building blocks already exist:

- `hydroforge.backends` for simulation
- `hydroforge.modifiers` for network modification
- `hydroforge.sensors` for sensor measurement models
- `hydroforge.sampling` for scenario sampling (requires `SALib`)

See `spec/0002-code-review-remediation.md` for the remediation plan. No source
modules have been deleted in this documentation pass.

## License

Part of the HydroForge uncertainty injection toolbox. See the repository
`LICENSE` file.
