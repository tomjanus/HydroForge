# HydroForge Domain Glossary

This glossary defines the canonical terms and meanings used throughout the HydroForge codebase.
Terms should be resolved inline as they are encountered during development.

---

## Network Components

### Junction
A node in a water distribution network where pipes meet. Junctions can have associated leakage
recorded via the `JunctionLeaks` container.

### Pipe
A conduit connecting two junctions in a water distribution network, characterized by length,
diameter, roughness (Manning/Hazen-Williams), and elevation.

### Reservoir
A network component with a fixed head (pressure source) that supplies water to the network.

### Tank
A storage tank in a water distribution network with variable water level, providing
equalization and storage capacity.

### Link
A general term for a connection between network nodes, encompassing both pipes and
open channels.

### Valve
A flow control component that can be OPEN or CLOSED, regulating flow through a
connection in the network.

---

## Simulation

### DemandModel
An enumeration of supported hydraulic demand models used in simulation.

- **DD (Demand-Driven)**: The demand-driven model assumes that the demand at each
  junction is fully satisfied regardless of available pressure. If insufficient
  pressure is available, the model may still compute flows but results may be
  physically unrealistic.

- **PDD (Pressure-Driven)**: The pressure-driven model adjusts demand satisfaction
  based on available pressure. Demand is reduced when pressure falls below
  specified thresholds.

### SimulationResults
The abstract interface returned by a `Simulator` run, providing access to node and
link time series variables through `get_node_variable()` and `get_link_variable()`.

### Simulator
An abstract base class defining the interface for hydraulic simulation strategies.
Concrete implementations include `WNTRSimulator` and `EPANETSimulator`.

### WNTRSimulator
A concrete `Simulator` strategy that uses the WNTR Python package's solver to run
hydraulic simulations.

### EPANETSimulator
A concrete `Simulator` strategy that uses the original EPANET C library via
temporary INP file invocation.

### DemandDriven vs PressureDriven
Synonyms for `DemandModel.DD` and `DemandModel.PDD` respectively.

### NodeVariable
A string alias for node-related variable names in simulation results (e.g., "head",
"pressure", "demand", "quality").

### LinkVariable
A string alias for link-related variable names in simulation results (e.g.,
"flow", "velocity", "headloss").

### TimeLocation
A type alias specifying locations in time series data: `int | slice | tuple[int, int]
| Sequence[int]`.

### SteadyStateSimulation
A simulation with `sim_time=0` (or no duration), where hydraulic calculations
are performed once without time variation.

### ExtendedDurationSimulation
A transient simulation with `sim_time > 0` and `hydraulic_timestep > 0`, producing
time series results across the simulation duration.

---

## Uncertainty Analysis

### UncertainParameter
An uncertain parameter encapsulating a nominal value along with an associated
uncertainty model, allowing for sampling and manipulation of values with uncertainty.

### ParameterType
Classification of a parameter's type for validation and arithmetic rules:

- **NUMERICAL**: Continuous numerical parameter.
- **DISCRETE**: Integer-valued discrete parameter.
- **CATEGORICAL**: Non-numeric categorical parameter.
- **BINARY**: Binary (two-state) parameter.
- **UNDEFINED**: Parameter type not yet determined.

### Uncertainty
An abstract base class for uncertainty models that perturb deterministic quantities
according to probability distributions or predefined rules. Supported models include:

- **NoUncertainty**: Identity model that returns the original value.
- **AdditiveUncertainty**: Applies additive noise sampled from a probability distribution
  (x' = x + ε).
- **MultiplicativeUncertainty**: Applies multiplicative noise (x' = x(1 + ε)).
- **BiasUncertainty**: Applies a deterministic additive bias.
- **CategoricalRandomReplacementUncertainty**: Replaces categorical values with
  independently sampled categories.
- **CategoricalReplacementUncertainty**: Conditionally replaces categorical values
  according to a replacement probability.
- **BinaryStateFlipUncertainty**: Flips between two categorical states with a fixed
  probability.

### Distribution
A probability distribution object used to represent uncertain model parameters.
Supports continuous, discrete, categorical and deterministic (Dirac delta)
distributions. Key subclasses include:

- **NormalDistribution**: Normal (Gaussian) distribution.
- **UniformDistribution**: Continuous uniform distribution.
- **DiracDeltaDistribution**: Generic deterministic point-mass distribution.
- **ContinuousDiracDeltaDistribution**: Deterministic Dirac distribution over real-valued
  outcomes.
- **DiscreteDiracDeltaDistribution**: Deterministic Dirac distribution over discrete outcomes.
- **DiscreteNormalDistribution**: Discretised normal distribution for integer-valued outcomes.
- **DiscreteUniformDistribution**: Discrete uniform distribution over an inclusive integer
  interval.
- **DiscreteHistogramDistribution**: Discrete numerical distribution defined by values and
  probabilities.
- **CategoricalNormalDistribution**: Ordered categorical distribution with Gaussian-shaped
  PMF.
- **CategoricalUniformDistribution**: Uniform categorical distribution.
- **CategoricalHistogramDistribution**: Categorical distribution defined by values and
  probabilities.
- **NormalDistribution**: Normal (Gaussian) distribution for continuous values.

### Parameter
A concrete implementation of `IUncertainParameter` that provides thread-safe sampling
with optional caching via a locking mechanism.

### SampleCache
A context manager that ensures each uncertain parameter is sampled only once within an
evaluation context, so repeated references to the same parameter use the same sampled
realization.

### CDF (Cumulative Distribution Function)
A function that gives the probability that a random variable is less than or equal to
a given value. Used for stratified and advanced sampling methods.

### TheoreticalCDFAbsent
Raised when a theoretical CDF is not available for a parameter or uncertainty model,
typically for categorical parameters or advanced sampling methods requiring CDF
evaluation.

### CDFNotAvailable
Raised when a CDF cannot be computed for a parameter because the underlying uncertainty
model doesn't support CDF transformation, or the parameter type (e.g., categorical) doesn't
have a well-defined CDF.

---

## Uncertainty Specification

### UncertaintySpecification
A model-independent document that maps observation points to sensor definitions and,
in later stages, model components to parameters. It is the in-memory form of a
`.json` or `.yaml` specification file.

### Sensor
A measurement-imperfection model that transforms a true signal into an observed
measurement (for example quantization, Gaussian noise, offset, saturation, or drift).
Sensor models are generic and have no network or simulator dependence.

### SensorDefinition
A named, declarative sensor model configuration: a sensor type, its parameters, and
an optional network location. A sensor definition describes a sensor; it is not
itself a live sensor.

### Measurement
The observed value produced by applying a sensor to a true signal.
_Avoid_: using "measurement" as a synonym for a sensor or a sensor definition.
(The on-disk key `measurements` is accepted only as a legacy alias for the
`sensors` section of a specification; it is not a separate domain concept.)

### SensorType
The registry name identifying which sensor class a sensor definition constructs, such
as `FixedPrecision` or `FixedPrecisionSensor`.

---

## Leak Management

### JunctionLeaks
A dictionary-like container (`MutableMapping`) for managing leakage data at network
junctions. Supports adding, removing, and querying leaks with validation and
JSON/DataFrame conversion.

Key operations:
- `add_leak(junction, size)`: Add or increase leakage at a junction.
- `remove_leak(junction, size)`: Decrease leak size or remove entry if zeroed.
- `total_leakage`: Total leakage across all junctions.
- `to_json()` / `from_json()`: JSON serialization/deserialization.
- `to_dataframe()`: Conversion to pandas DataFrame.

### LeakSize
The magnitude of leakage at a junction, measured in m³/s (default unit).

### TotalLeakage
The sum of all leakage values across all junctions in a `JunctionLeaks` instance.

### LeakLocation
The junction at which leakage is recorded or simulated.

### LeakGrowth
The incremental increase in leakage size over time or across sampling sessions.

---

## Sensor Placement

### SensorPlacement
The optimization of sensor locations in a water distribution network for leak
detection or state estimation purposes.

### SensorLocation
A specific junction or link in a water distribution network where a sensor is placed.

### SensorPlacementResult
The output of a sensor placement optimization, typically containing selected sensor
locations and associated metrics (e.g., coverage, accuracy).

### SensorPlacementStrategy
An algorithm for selecting sensor locations in a network. Supported strategies include:

- **GreedySensorPlacement**: Iteratively places sensors at nodes farthest from sources.
- **KCentreSensorPlacement**: K-center placement maximizing minimum coverage radius.
- **RandomSensorPlacement**: Random sampling of sensor locations.
- **CentralityBasedSensorPlacement**: Places sensors at nodes with highest centrality.
- **CoverageBasedSensorPlacement**: Maximizes number of nodes covered within a radius.
- **DominatingSetBasedSensorPlacement**: Ensures every target node is dominated by a sensor.
- **FixedLocationSensorPlacement**: Places sensors at pre-determined locations.

### SourceNode
A reservoir or tank node that provides water to the network, typically identified
by name pattern (e.g., "R" prefix).

### SensorNetworkGraph
A graph representation of a water distribution network built on top of NetworkX,
used by sensor placement strategies.

---

## Core Types and Abstractions

### ModelT
A TypeVar representing the water network model type used as input to simulators.

### ResultT
A TypeVar bound to `SimulationResults`, representing the output type of a simulator run.

### IUncertainParameter
Abstract base class for uncertain parameters, defining the interface for accessing
nominal values and generating samples with uncertainty.

### Value, Scalar, Array, CatValue
Type aliases from `hydroforge.uncertainty.common` for consistent type handling:
- **Value**: `Union[Scalar, Array, CatValue]` - generic value that may be numeric or categorical
- **Scalar**: `Union[int, float, np.int_, np.float64]` - numeric scalar
- **Array**: `Union[npt.NDArray[NumpyFloat], npt.NDArray[np.int_]]` - numeric array
- **CatScalar**: `Any` - str, Enum, label for categorical data
- **CatArray**: `npt.NDArray[Any]` - categorical array
- **CatValue**: `Union[CatScalar, CatArray]` - categorical value
- **NumValue**: `Union[Scalar, Array]` - numeric values only

### UnitSystem
The informal unit convention used throughout HydroForge:
- Leakage sizes: m³/s
- Flow: m³/s
- Head/pressure: m
- Length: m
- Time: s (seconds)
- Diameter: m

Note: Unit tracking is informal in the core code; explicit unit conversion should be
handled by the user or upstream I/O utilities.

---

## Uncertainty Arithmetic Rules

### Allowed Operations by ParameterType

- **NUMERICAL**: All arithmetic operations (add, sub, mul, div) allowed.
- **DISCRETE**: Addition, subtraction allowed. Multiplication allowed only with integer
  multipliers. Division not allowed.
- **CATEGORICAL**: No arithmetic operations allowed (raises TypeError).
- **BINARY**: Treated as categorical for arithmetic purposes.

### Arithmetic Edge Cases

- **Division by zero**: Raises `ValueError` or propagates depending on implementation.
- **Multiplication of discrete by non-integer**: Raises `TypeError`.
- **Categorical + numeric**: Always raises `TypeError`, regardless of operand order.

---

## Backends

### Backend
A simulation backend implementation that provides a consistent API for loading models,
applying configurations, and running simulators. Supported backends:

- **WNTR backend**: Uses the WNTR Python package (with a WNTR or EPANET solver).
- **TSNet backend**: Uses the TSNet transient model.
- **TSNetPlus backend**: Enhanced TSNet implementation.
- **PTSNet backend**: Uses the PTSNet transient model.

The registry names are `wntr`, `tsnet`, `tsnetplus`, and `ptsnet`.

### WNTRConfig, WNTRTimeConfig, WNTRSimulatorConfig, EPANETSimulatorConfig, TSNetConfig
Configuration classes specific to each backend, typically containing:
- Time configuration (duration, timestep)
- Hydraulic configuration (demand model)
- Solver-specific options

---

## Examples from Codebase

### Typical Workflow 1: Static Simulation
1. Load an EPANET `.inp` file model with `get_backend("wntr")`.
2. Apply model configuration (`WNTRConfig`) through the backend.
3. Create a simulator (`create_simulator(...)`) and run it on the model.
4. Extract results via `results.get_node_variable(...)`.

### Typical Workflow 2: Uncertainty Quantification
1. Create `Parameter` instances with nominal values and uncertainty models.
2. Use `SampleCache` context manager for consistent sampling.
3. Sample parameters: `p.sample()` or `p.sample_from_unit(u)`.
4. Run simulations with perturbed parameters.
5. Compute CDFs or other statistics from sample results.

### Typical Workflow 3: Leak Management
1. Create a `JunctionLeaks()` instance.
2. Add leaks: `leaks.add_leak("J1", 0.05)`.
3. Query leaks: `leaks["J1"]`, `leaks.total_leakage`.
4. Serialize: `leaks.to_json()`, `JunctionLeaks.from_json(json_str)`.
5. Remove leaks: `leaks.remove_leak("J1", 0.02)`.

### Typical Workflow 4: Sensor Placement
1. Load a network graph: `EPANETNetworkGraph.from_model(network_model)`.
2. Create a placement strategy (e.g., `GreedySensorPlacement`).
3. Orchestrate placement: `SensorPlacer(strategy=strategy).place_sensors()`.
4. Retrieve sensor locations: `sensor_placer.sensors`.
5. Optionally plot: `sensor_placer.plot_sensors(graph)`.