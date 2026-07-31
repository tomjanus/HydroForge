# Uncertainty Module

This module provides a framework for defining, manipulating, and sampling uncertain parameters within a modeling context. It is designed to integrate into data workflows processing numerical and categorical values, allowing calculations to be performed with values that have inherent uncertainty.

The architecture is built on three core concepts:
1.  **Distributions**: Define the source and shape of randomness (e.g., Normal, Uniform).
2.  **Uncertainties**: Define how randomness is applied to a value (e.g., additively, multiplicatively).
3.  **Parameters**:    Define parameters/variables that encapsulate a nominal *''crisp''* value and an associated uncertainty.

---

## Core Concepts

The module follows a layered architecture:

```
Distribution → Uncertainty → Parameter
     ↓              ↓            ↓
  (source)      (strategy)   (container)
```

### 1. [Distribution](./distributions.py)

A `Distribution` represents a probability distribution. It is the fundamental source of randomness/uncertainty. The module provides several built-in distributions for continuous, discrete, and categorical domains.

-   **Key Methods**:
    -   : `nominal_value` : Returns the most probable or representative value.
    -   : `sample(n)` : Draws `n` random samples from the distribution.
    -   : `reduce()` : Collapses the distribution into a deterministic `DiracDeltaDistribution` at its nominal value.

**Example:** Creating a Normal (Gaussian) distribution.
```python
from hydroforge.uncertainty.distributions import NormalDistribution

# A normal distribution with mean 100 and standard deviation 5
normal_dist = NormalDistribution(mean=100.0, std_dev=5.0)

print(f"Nominal Value: {normal_dist.nominal_value}")
# > Nominal Value: 100.0

print(f"A single sample (non-deterministic example value): {normal_dist.sample(1)}")
# > A single sample: 103.45

print(f"Five samples (non-deterministic example values): {normal_dist.sample(5)}")
# > Five samples: [98.2, 101.1, 94.5, 105.0, 99.8]
```

### 2. [Uncertainty](./uncertainties.py)

An `Uncertainty` class defines the *strategy* for applying randomness to a value. It takes a `Distribution` and uses it to generate samples of uncertainty that perturb the nominal value.

-   **Key Method**:
    - `apply(value)` : Takes a value (or array of values) and returns a new version with uncertainty applied.

**Example:** Creating an additive uncertainty model that uses the `NormalDistribution` from above.
```python
from hydroforge.uncertainty.uncertainties import AdditiveUncertainty

# An uncertainty model that adds noise from the normal distribution
additive_uncertainty = AdditiveUncertainty(distribution=normal_dist)

base_value = 1000.0
perturbed_value = additive_uncertainty.apply(base_value)

print(f"Base value: {base_value}")
# > Base value: 1000.0

print(f"Value after applying additive uncertainty (non-deterministic example value): {perturbed_value}")
# > Value after applying additive uncertainty: 1103.45
```
Common uncertainty types include `AdditiveUncertainty` (x + ε), `MultiplicativeUncertainty` (x * (1 + ε)), a deterministic offset `BiasUncertainty` (x + bias) and various categorical replacement models.

### 3. [Parameter](./parameters.py)

`Parameter` is the primary user-facing class and models a variable that consists of a *nominal* value and optional uncertainty. In other words, it encapsulates a `nominal_value` and `Uncertainty` model. Parameters are divided into categories via an attribute `ParameterType` (e.g., `NUMERICAL`, `DISCRETE`, `CATEGORICAL`). It is designed to be used just like a regular variable in calculations.

-   **Key Features**:
    -   **Locked Sampling**: Within a single context, `sample()` returns the same value on subsequent calls, ensuring consistency in calculations (e.g., `p + p` uses the same sample for both operands). The user needs to call `reset()` before a new 'uncertain' parameter sample can be drawn.
    -   **Operator Overloading**: Supports standard arithmetic (`+`, `*`, etc.).
    -   **NumPy Integration**: Works seamlessly with NumPy functions and arrays.
    -   **Type Safety**: Enforces arithmetic rules based on its `type` (e.g., prevents division on discrete parameters).

**Example:** Creating and using a `Parameter`.
```python
from hydroforge.uncertainty.parameters import Parameter, ParameterType

# Create an uncertain parameter for a pipe diameter
diameter = Parameter(
    name="Pipe Diameter",
    nominal_value=200.0,
    uncertainty=AdditiveUncertainty(NormalDistribution(0, 2.5)),
    typ=ParameterType.NUMERICAL
)
print(f"Parameter definition: {diameter}")
# > Parameter definition: Parameter(name='Pipe Diameter', nominal=200.0, ...)

# Use it in calculations
circumference = diameter * 3.14159
# The sample is drawn on first use and locked
print(f"Sampled diameter: {diameter.sample()}")
# > Sampled diameter: 201.78

print(f"Calculated circumference: {circumference}")
# > Calculated circumference: 633.91

# Subsequent calls return the locked value
print(f"Same sampled diameter: {diameter.sample()}")
# > Same sampled diameter: 201.78

# To get a new random value, you must reset it
diameter.reset()
print(f"New sampled diameter: {diameter.sample()}")
# > New sampled diameter: 198.55
```

---

## Integration with Sampling Strategies

The uncertainty module is designed to work seamlessly with advanced sampling strategies (see `hydroforge.sampling`):

```python
from hydroforge.uncertainty.parameters import Parameter
from hydroforge.uncertainty.uncertainties import AdditiveUncertainty
from hydroforge.uncertainty.distributions import NormalDistribution

# Create parameter
param = Parameter(
    name="diameter",
    nominal_value=100.0,
    uncertainty=AdditiveUncertainty(NormalDistribution(0, 5)),
    type=ParameterType.NUMERICAL
)

# Random sampling (Monte Carlo)
value = param.sample()

# Controlled sampling (for LHS, Sobol, etc.)
value = param.sample_from_unit(u=0.5)  # u ∈ [0, 1]
```

The `sample_from_unit()` method enables integration with:
- Latin Hypercube Sampling (LHS)
- Sobol sequences
- Halton sequences
- Other quasi-random methods

---

## Common Patterns

### Pattern 1: Basic Parameter with Uncertainty
```python
from hydroforge.uncertainty.parameters import Parameter, ParameterType
from hydroforge.uncertainty.uncertainties import AdditiveUncertainty
from hydroforge.uncertainty.distributions import NormalDistribution

# Define uncertainty source
noise = NormalDistribution(mean=0, std_dev=2.5)

# Define how to apply it
uncertainty = AdditiveUncertainty(distribution=noise)

# Create parameter
diameter = Parameter(
    name="pipe_diameter",
    nominal_value=200.0,
    uncertainty=uncertainty,
    type=ParameterType.NUMERICAL,
    metadata={"unit": "mm", "location": "junction_42"}
)

# Use in calculations
area = 3.14159 * (diameter / 2) ** 2
```

### Pattern 2: Deterministic Parameter (No Uncertainty)
```python
from hydroforge.uncertainty.parameters import Parameter, ParameterType
from hydroforge.uncertainty.uncertainties import NoUncertainty

# Parameter without uncertainty
length = Parameter(
    name="pipe_length",
    nominal_value=1000.0,
    uncertainty=NoUncertainty(),  # or omit entirely (default)
    type=ParameterType.NUMERICAL
)
```

### Pattern 3: Categorical Parameter
```python
from hydroforge.uncertainty.distributions import CategoricalUniformDistribution
from hydroforge.uncertainty.uncertainties import CategoricalRandomReplacementUncertainty
from hydroforge.uncertainty.parameters import Parameter, ParameterType

# Material with uniform selection probability
material_dist = CategoricalUniformDistribution(
    categories=("PVC", "Steel", "Iron", "Copper")
)

material = Parameter(
    name="pipe_material",
    nominal_value="PVC",
    uncertainty=CategoricalRandomReplacementUncertainty(material_dist),
    type=ParameterType.CATEGORICAL
)
```

### Pattern 4: Discrete Integer Parameter
```python
from hydroforge.uncertainty.distributions import DiscreteUniformDistribution
from hydroforge.uncertainty.uncertainties import AdditiveUncertainty
from hydroforge.uncertainty.parameters import Parameter, ParameterType

# Number of sensors with possible variation
sensor_count = Parameter(
    name="sensor_count",
    nominal_value=10,
    uncertainty=AdditiveUncertainty(DiscreteUniformDistribution(-2, 2)),
    type=ParameterType.DISCRETE
)

# Discrete parameters prevent invalid operations
# sensor_count / 2.5  # Raises TypeError
# sensor_count * 2    # OK
```

---

## Available Components

### Distributions

-   **Continuous**: `NormalDistribution`, `UniformDistribution`
-   **Discrete**: `DiscreteNormalDistribution`, `DiscreteUniformDistribution`, `DiscreteHistogramDistribution` 
-   **Categorical**: `CategoricalNormalDistribution`, `CategoricalUniformDistribution`, `CategoricalHistogramDistribution`
-   **Deterministic**: `DiracDeltaDistribution` (generic), and typed variants: `ContinuousDiracDeltaDistribution`, `DiscreteDiracDeltaDistribution`, `CategoricalDiracDeltaDistribution`

**Key Properties:**
- All distributions have a `nominal_value` property (most probable/representative value)
- Support both random sampling via `sample(n)` and controlled sampling via `sample_from_unit(u)` for integration with advanced sampling strategies (LHS, Sobol, etc.)
- Can be reduced to deterministic values using `reduce()` method
- Each distribution has immutable `properties` (family, bounds_type, domain) as class variables

### Uncertainties

-   **General**: `NoUncertainty` (passes value through unchanged)
-   **Numeric**: `AdditiveUncertainty` (x + ε), `MultiplicativeUncertainty` (x × (1 + ε)), `BiasUncertainty` (x + bias)
-   **Categorical**: `CategoricalRandomReplacementUncertainty`, `CategoricalReplacementUncertainty` (conditional replacement), `BinaryStateFlipUncertainty`

**Key Features:**
- All uncertainties implement `apply(value, u=None)` method
- Support both random application and controlled application via unit interval parameter `u`
- Work with scalars and arrays (NumPy broadcasting)
- Can handle continuous, discrete, and categorical value types

### Parameters

-   `Parameter`: A generic class to represent uncertain values with nominal value and uncertainty
-   `ParameterType`: An enum to enforce type-specific rules:
    - `NUMERICAL`: Real-valued parameters (supports all arithmetic)
    - `DISCRETE`: Integer-valued parameters (restricted arithmetic)
    - `CATEGORICAL`: Non-numeric categorical parameters (no arithmetic)
    - `BINARY`: Two-state parameters
    - `UNDEFINED`: Unspecified type

**Key Features:**
- **Thread-safe sampling**: Uses locks to ensure consistent values within sampling context
- **Locked sampling behavior**: Call `reset()` to generate new samples
- **Operator overloading**: Works with `+`, `-`, `*`, `/` (where allowed by ParameterType)
- **NumPy integration**: Supports `np.array()`, `np.mean()`, etc.
- **External sampler support**: `sample_from_unit(u)` method for advanced sampling strategies
- **Metadata storage**: Optional dictionary for additional parameter information
