# Simulation Module

This document describes the simulation logic implemented in:

- `common.py`
- `events.py`
- `results.py`
- `tsnet_simulator.py`
- `wntr_simulator.py`

It is implementation-aligned and intended as a module reference for developers and users.

## Overview

The simulation package uses a strategy pattern with a shared abstraction layer:

- Static hydraulic simulation:
  - `WNTRSimulator` (WNTR solver)
  - `EPANETSimulator` (EPANET solver through WNTR wrapper)
- Transient hydraulic simulation:
  - `TSNetSimulator` (TSNet MOC workflow)
- Shared interfaces and helpers:
  - `Simulator` and `SimulationResults` abstract base classes
  - model loaders (`load_wntr_model`, `load_tsnet_model`)
  - common demand model enum (`DemandModel`)
- Result wrappers:
  - `WNTRSimulationResults`
  - `TSNetSimulationResults`
- Event objects for transient pre-configuration:
  - valve, pump, burst, and demand-pulse events

## Architecture

### Core abstractions

`common.py` defines the generic contracts:

- `Simulator[ModelT, ResultT]`
  - single abstract method: `run(model) -> ResultT`
- `SimulationResults`
  - requires subclasses to expose:
    - `node_variables: ClassVar[tuple[str, ...]]`
    - `link_variables: ClassVar[tuple[str, ...]]`
  - requires methods:
    - `get_node_variable(...)`
    - `get_link_variable(...)`

`SimulationResults.__init_subclass__` validates at class definition time that concrete result classes declare both supported variable tuples.

### Type aliases used across modules

Defined in `common.py`:

- `NodeVariable = str`
- `LinkVariable = str`
- `TimeLocation = int | slice | tuple[int, int] | Sequence[int]`

Defined per backend module:

- `WNTRNetworkModel = wntr.network.WaterNetworkModel`
- `TSNetNetworkModel = tsnet.network.TransientModel`

## Module: `common.py`

## Demand model enum

`DemandModel`:

- `DemandModel.DD` -> `"DD"` (demand-driven)
- `DemandModel.PDD` -> `"PDD"` (pressure-driven)

Used by static and transient config objects to keep demand mode explicit and type-safe.

## Model loading functions

### `load_wntr_model(model)`

- Input: path-like (`str | pathlib.Path`) to INP file
- Behavior:
  - verifies path exists and is a file
  - returns `wntr.network.WaterNetworkModel`
- Raises:
  - `FileNotFoundError` when path is missing

### `load_tsnet_model(model)`

- Input: path-like (`str | pathlib.Path`) to INP file
- Behavior:
  - verifies path exists and is a file
  - returns `tsnet.network.TransientModel`
- Raises:
  - `FileNotFoundError` when path is missing

## Module: `wntr_simulator.py`

This module implements static hydraulic strategies and configurations.

## Configuration dataclasses

### `WNTRSimulatorConfig`

Fields:

- `sim_time: int = 0`
- `hydraulic_timestep: int = 3600`
- `demand_model: DemandModel = DemandModel.DD`

Method:

- `apply_to(model)`
  - applies simulation duration and hydraulic timestep
  - sets `model.options.hydraulic.demand_model` when hydraulic options exist

### `EPANETSimulatorConfig`

Fields:

- `sim_time: int = 0`
- `hydraulic_timestep: int = 3600`
- `demand_model: DemandModel = DemandModel.DD`
- `file_prefix: str = "temp"`
- `cleanup_files: bool = True`

Method:

- `apply_to(model)` with same base behavior as WNTR config

Additional EPANET behavior settings:

- temp artifact naming is controlled by `file_prefix`
- post-run cleanup is controlled by `cleanup_files`

## Simulator classes

### `WNTRSimulator`

Fields:

- `config: WNTRSimulatorConfig`
- `inplace: bool = True`

Method:

- `run(model) -> WNTRSimulationResults`
  - deep-copies model when `inplace=False`
  - applies config to effective model
  - runs `wntr.sim.WNTRSimulator(wn).run_sim()`
  - wraps raw result in `WNTRSimulationResults`

### `EPANETSimulator`

Fields:

- `config: EPANETSimulatorConfig`
- `inplace: bool = False`

Methods:

- `_create_solver(model)`
  - returns `wntr.sim.EpanetSimulator(model)`
- `_cleanup_temp_files()`
  - removes files matching:
    - `<prefix>.inp`
    - `<prefix>.rpt`
    - `<prefix>.bin`
    - `<prefix>.hyd`
    - `<prefix>.out`
  - ignores missing/unremovable files
- `run(model) -> WNTRSimulationResults`
  - deep-copies model when `inplace=False`
  - applies config to effective model
  - warns through logger if `demand_model == DemandModel.PDD`
  - runs `solver.run_sim(file_prefix=self.config.file_prefix)`
  - wraps in `WNTRSimulationResults`
  - conditionally cleans files if `cleanup_files=True`

## Module: `tsnet_simulator.py`

This module implements transient simulation strategy on TSNet.

## Type aliases

- `WaveSpeed = float | Sequence[float]`
- `FrictionModel = Literal['steady', 'quasi-steady', 'unsteady']`

## `TSNetSimulatorConfig`

Fields:

- `duration: float`
- `wave_speed: WaveSpeed = 1200.0`
- `friction_model: FrictionModel = 'steady'`
- `time_step: float | None = None`
- `steady_state_engine: DemandModel = DemandModel.DD`
- `initial_time: float = 0.0`
- `results_name: str | None = "tsnet_simulation_results.obj"`
- `clean_files: bool = True`

Semantics:

- `duration` and `time_step` define transient time setup
- `steady_state_engine` controls TSNet steady-state initializer backend mode
- `results_name=None` disables pickled output persistence

## `TSNetSimulator`

Fields:

- `config: TSNetSimulatorConfig`
- `inplace: bool = True`

Methods:

- `_cleanup_temp_files()`
  - removes default EPANET temp filenames prefixed with `temp`
- `run(model) -> TSNetSimulationResults`

Execution sequence in `run`:

1. copy model unless `inplace=True`
2. `set_wavespeed(config.wave_speed)`
3. `set_time(config.duration, config.time_step)`
4. call `tsnet.simulation.Initializer(...)` using:
   - `initial_time`
   - `steady_state_engine.value`
5. optionally cleanup temp files if `clean_files=True`
6. run MOC solver:
   - `tsnet.simulation.MOCSimulator(..., results_obj='no', friction=config.friction_model)`
7. wrap output model as `TSNetSimulationResults`
8. optionally save pickle when `results_name` is not `None`

Notes:

- `TSNetSimulator` mutates model state during simulation by design.
- Use `inplace=False` when preserving original transient model object is required.

## Module: `events.py`

This module provides event objects that modify a TSNet transient model before simulation.

## Base event contract

`TransientEvent`:

- abstract method: `apply_to(model: TransientModel) -> None`

All concrete events call corresponding TSNet model APIs.

## Valve events

### `ValveClosureEvent`

Fields:

- `valve: str`
- `duration: float`
- `start_time: float = 0.0`
- `final_opening: float = 0.0`
- `exponent: float = 1.0`
- `curve: list[tuple[float, float]] | None = None`

Validation in `__post_init__`:

- non-empty valve name
- `0 <= final_opening <= 1`
- `duration > 0`
- `start_time >= 0`
- `exponent > 0`

Application:

- `model.valve_closure(name=..., rule=[duration, start_time, final_opening, exponent], curve=curve)`

### `ValveOpeningEvent`

Fields:

- `valve: str`
- `duration: float`
- `start_time: float = 0.0`
- `final_opening: float = 1.0`
- `exponent: float = 1.0`
- `curve: list[tuple[float, float]] | None = None`

Application:

- `model.valve_opening(name=..., rule=[duration, start_time, final_opening, exponent], curve=curve)`

## Pump events

### `PumpShutdownEvent`

Fields:

- `pump: str`
- `duration: float`
- `start_time: float = 0.0`
- `final_opening: float = 0.0`
- `exponent: float = 1.0`

Application:

- `model.pump_shut_off(name=..., rule=[duration, start_time, final_opening, exponent])`

### `PumpStartupEvent`

Fields:

- `pump: str`
- `duration: float`
- `start_time: float = 0.0`
- `final_opening: float = 1.0`
- `exponent: float = 1.0`

Application:

- `model.pump_start_up(name=..., rule=[duration, start_time, final_opening, exponent])`

## Demand and burst events

### `BurstEvent`

Fields:

- `node: str`
- `start_time: float`
- `burst_development_time: float`
- `final_burst_coeff: float`

Application:

- `model.add_burst(name=node, ts=start_time, tc=burst_development_time, final_burst_coeff=final_burst_coeff)`

### `DemandPulseEvent`

Fields:

- `node: str`
- `pulse_duration: float`
- `start_time: float`
- `duration_time: float`
- `multiplier: float = 1.0`

Application:

- `model.add_demand_pulse(name=node, rule=[pulse_duration, start_time, duration_time, multiplier])`

## Module: `results.py`

This module provides result wrappers and time selection logic.

## Time selector helper

### `_resolve_times(index, times)`

Supported `times` forms:

- `slice`: direct pandas label slicing
- `int`:
  - `0` maps to first available index entry
  - exact timestamp if present
  - nearest timestamp otherwise
- `(start, end)` tuple:
  - inclusive range selection
- `Sequence[int]`:
  - each value mapped to exact or nearest index label

Raises:

- `ValueError` for empty result indexes
- `ValueError` for invalid `times` format

## `WNTRSimulationResults`

Wrapper around `wntr.sim.SimulationResults`.

Declared supported variables:

- node:
  - `leak_demand`, `pressure`, `head`, `demand`, `quality`
- link:
  - `flowrate`, `velocity`, `status`, `setting`

Core behavior:

- validates variable name against declared supported tuples
- checks variable availability in raw result tables
- extracts via `.loc[_resolve_times(...), requested_columns]`
- returns DataFrame or NumPy array based on `as_dataframe`

Primary methods:

- `get_node_variable(variable, nodes, times=slice(None), as_dataframe=False)`
- `get_link_variable(variable, links, times=slice(None), as_dataframe=False)`

Failure modes:

- invalid variable -> `ValueError`
- missing variable in raw output -> `ValueError`

## `TSNetSimulationResults`

Wrapper around TSNet `TransientModel` with transient arrays on nodes/links.

Declared supported variables:

- node:
  - `head`, `emitter_discharge`, `demand_discharge`
- link:
  - `start_node_head`, `start_node_velocity`, `start_node_flowrate`, `end_node_head`, `end_node_velocity`, `end_node_flowrate`

Initialization checks:

- validates that `model.simulation_timestamps` exists
- raises `ValueError` when transient simulation outputs are not present

Extraction strategy:

- builds full matrix from per-node/per-link arrays
- verifies extracted matrix time dimension equals timestamp length
- converts matrix to DataFrame with timestamp index and requested columns
- applies `_resolve_times` through label-based `.loc`
- returns selected values and selected timestamp index

Primary methods:

- `get_node_variable(variable, nodes, times=slice(None), as_dataframe=False)`
- `get_link_variable(variable, links, times=slice(None), as_dataframe=False)`

Failure modes:

- invalid variable -> `ValueError`
- no timestamps -> `ValueError`
- inconsistent array length vs timestamps -> `RuntimeError`

## End-to-end usage patterns

## Static workflow (WNTR or EPANET)

1. load model with `load_wntr_model(...)`
2. create config (`WNTRSimulatorConfig` or `EPANETSimulatorConfig`)
3. run solver strategy
4. extract node/link variables with result wrapper

```python
from hydroforge.simulation import (
    load_wntr_model,
    WNTRSimulator,
    WNTRSimulatorConfig,
    DemandModel,
)

wn = load_wntr_model("network.inp")
sim = WNTRSimulator(
    config=WNTRSimulatorConfig(sim_time=3600, demand_model=DemandModel.DD),
    inplace=False,
)
res = sim.run(wn)
pressure = res.get_node_variable("pressure", ["J1", "J2"], times=(0, 3600), as_dataframe=True)
```

## Transient workflow (TSNet)

1. load model with `load_tsnet_model(...)`
2. optionally apply events (`events.py`) to model
3. create `TSNetSimulatorConfig`
4. run `TSNetSimulator`
5. extract transient node/link variables

```python
from hydroforge.simulation import load_tsnet_model, TSNetSimulator, TSNetSimulatorConfig
from hydroforge.simulation.events import DemandPulseEvent

tm = load_tsnet_model("network.inp")
DemandPulseEvent(node="N3", pulse_duration=2.0, start_time=2.0, duration_time=8.0, multiplier=1.2).apply_to(tm)

sim = TSNetSimulator(
    config=TSNetSimulatorConfig(duration=20.0, wave_speed=1200.0, time_step=0.1, results_name=None),
    inplace=False,
)
res = sim.run(tm)
head = res.get_node_variable("head", ["N1", "N2"], times=slice(None), as_dataframe=True)
```

## Practical behavior notes

- Static solvers and transient solver use different result backing structures but identical extraction method names.
- `times=0` is interpreted as first available simulation timestep in result wrappers.
- Non-exact requested times are mapped to nearest available timestamps.
- For EPANET static runs, keep `cleanup_files=True` unless diagnostic artifacts are needed.
- For TSNet runs, event application order matters and should be done before `run(...)`.

## References

- WNTR: https://wntr.readthedocs.io/
- EPANET 2.2 docs: https://epanet22.readthedocs.io/
- TSNet: https://tsnet.readthedocs.io/
