# Uncertainty-to-simulation workflow

HydroForge connects a simulator-independent uncertainty specification to
backend-specific mappings, deterministic sampling, model runs, and sensor
measurements. The examples in `examples/` demonstrate the complete workflow:

- [`wntr_static_uncertainty.py`](../examples/wntr_static_uncertainty.py) and its
  [notebook](../examples/wntr_static_uncertainty.ipynb);
- [`ptsnet_dynamic_uncertainty.py`](../examples/ptsnet_dynamic_uncertainty.py)
  and its [notebook](../examples/ptsnet_dynamic_uncertainty.ipynb).

## 1. Define uncertainty and sensors

Specifications are backend-independent. A version 2 document keeps uncertain
parameters and sensor definitions, but leaves component identifiers, result
quantities, and measurement locations to a typed backend mapper.

```python
specification = UncertaintySpecification.from_dict(
    {
        "schema_version": "2.0",
        "parameters": {
            "pipe_diameter": {
                "nominal_value": 0.30,
                "uncertainty": {
                    "type": "Additive",
                    "parameters": {
                        "distribution": {
                            "type": "Normal",
                            "parameters": {"mean": 0.0, "std_dev": 0.02},
                        }
                    },
                },
            },
            "sensor_sigma": {"nominal_value": 0.05},
        },
        "sensors": {
            "flow_sensor": {
                "type": "Composite",
                "parameters": {
                    "sensors": [
                        {
                            "type": "RandomNoise",
                            "parameters": {
                                "sigma": {"$parameter": "sensor_sigma"}
                            },
                        }
                    ]
                },
            }
        },
    }
)
```

`$parameter` references are resolved from each sampled scenario before sensor
construction. Version 1.0 specifications without sensor locations remain
loadable; saving a loaded specification writes version 2.0. A version 1.0
document that still embeds `SensorDefinition.location` is rejected with
migration guidance. Parameter values use model-native units; there is no
automatic unit conversion.

## 2. Sample reproducible scenarios

Keep sampler choice, sample count, and seed separate from the specification.
Seeded LHS and Sobol samplers produce scenarios with reproducibility metadata:

```python
diameter = specification.create_parameter("pipe_diameter")
sampler = SobolSampler([diameter], seed=42)
scenarios = list(sampler.generate(8))
```

Supported parameter domains include continuous, discrete, categorical, and
binary parameters. Distribution-domain inference takes precedence when the
domain is informative; nominal-value inference is the fallback. An explicitly
conflicting type is rejected.

Sampling currently treats parameter marginals as independent. No correlation
matrix, copula, or dependent multivariate sampling is implemented in Stage 3;
see [Stage 4 out of scope](stage4-correlation-out-of-scope.md).

## 3. Map each scenario to a fresh model

Use a backend mapper to keep simulator-specific targets out of the
specification. `map(specification, model)` returns an uncertain model;
`realize(scenario)` creates an isolated, simulation-ready instance. Invalid or
unmapped values fail before application instead of being silently ignored.

Examples of typed configuration are:

```python
WNTRParameterBinding("P1", "diameter", "pipe_diameter")
PTSNetWaveSpeedBinding(parameter_key="wave_speed", pipes=None)
PTSNetInteriorSensorBinding(
    pipe_id="P1",
    sensor_key="flow_sensor",
    quantity="flowrate",
    fraction=0.5,
)
```

The implemented model parameter targets are:

| Backend | Supported parameter targets |
| --- | --- |
| WNTR | Pipe diameter, diameter multiplier, roughness, initial `OPEN`/`CLOSED` status; single-timeseries junction base demand; supported valve setting |
| TSNetPlus | Shared/per-pipe wave speed and fixed-node open/closed surge-tank settings |
| PTSNET | Shared/per-pipe wave speed and fixed-node open/closed surge protection |

WNTR pipe-status uncertainty changes the initial status only; it does not rewrite
control rules. Junction base-demand uncertainty currently requires exactly one
demand timeseries on the mapped junction.

Surge topology is fixed in the mapping; sampled parameters may control supported
physical values such as tank area, height, or initial level. A fresh model is
loaded or cloned for each realization to prevent parameter compounding.

## 4. Run sensors against supported results

Each `SimulationInstance.run()` returns raw backend results, measured outputs,
and scenario/sensor-seed provenance. Sensor processing uses copied series and
does not mutate backend raw tables.

| Backend | Currently mapped result quantities |
| --- | --- |
| WNTR | Node pressure and link flowrate |
| TSNetPlus | Node head; selected pipe-interior head, velocity, and flowrate |
| PTSNET | Node head, emitter discharge, and demand discharge; selected pipe-interior head and flowrate |

PTSNET and TSNetPlus capture only requested interior locations, not the full
interior mesh history. A physical fraction is measured from the pipe's declared
start and interpolated between adjacent computational points. A mesh index is
mesh-relative and is validated against the current pipe discretization; it is
not stable if the mesh changes. PTSNET's index is zero-based among the pipe's
interior points and excludes endpoints. The PTSNET interior API currently
supports `head` and `flowrate`; `velocity` is not available there.

Sensor definitions may be composites. A new sensor instance is created for
each realization and measurement. Random streams are derived from the
realization seed and sensor name; a seed explicitly supplied in a sensor
definition takes precedence. The effective sensor seeds are kept in result
provenance. `DriftSensor` advances its offset using elapsed simulation time and
has isolated state per measurement.

## 5. Save and reload a realization

`save_realization(instance, directory)` writes a per-realization bundle with a
native `model.inp` artifact and `manifest.json`. The manifest records the
specification, sampled values, scenario metadata, typed mappings, backend
settings, and sensor setup. Existing non-empty bundles are not silently
overwritten. The loader checks manifest fields and artifact paths before
loading.

`load_realization(directory)` returns a simulation-ready instance that can be
run again. It restores dynamic wave-speed/surge configuration, PTSNET selected
interior requests, sensor definitions, deterministic sensor seeds, and
provenance without applying sampled parameters twice. Simulation output files
are separate from the model artifact and manifest.

PTSNET and TSNetPlus require their optional solver dependencies. PTSNET
interior capture specifically requires the
[`tomjanus/ptsnet` development branch](https://github.com/tomjanus/ptsnet/tree/development),
which provides `add_pipe_output` and `interior_results`. Without that API the
mapper fails with an actionable compatibility error.

## Limitations

- Values are assumed to use the target model's units; no unit conversion is
  performed.
- Parameter correlations and dependent marginals are deferred to Stage 4.
- Mesh-index measurements are tied to the selected backend's discretization.
- PTSNET interior measurements currently support only `head` and `flowrate`.
- Optional dynamic solver integration depends on upstream solver versions and
  native EPANET/MPI dependencies. The PTSNET example tests skip only when the
  optional solver/API cannot initialize.
- Result tables and workspace files are backend outputs, not part of a saved
  model bundle.
