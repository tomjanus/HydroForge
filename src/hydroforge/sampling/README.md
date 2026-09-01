# Sampling Strategies

The `hydroforge.sampling` module provides sampling methods for **uncertainty propagation, sensitivity analysis, scenario generation, and stochastic decision modelling** in water distribution network (WDN) simulations.

The module supports both classical Monte Carlo methods and structured sampling approaches designed to improve the representation of uncertain input spaces or to represent dependencies, multiple uncertainty scales, and sequential decisions.

The available methods range from independent random sampling to low-discrepancy sequences, hierarchical sampling, Markov chain Monte Carlo, stratification, and scenario-tree generation.

## Overview

For a WDN model represented by

```math
\mathbf{y} = f(\mathbf{x}),
```

where $\mathbf{x}=(x_1,\ldots,x_d)$ denotes uncertain model parameters and $f$ is the hydraulic, water-quality, or other simulation model, sampling defines a finite set of realizations

```math
\{\mathbf{x}^{(1)},\ldots,\mathbf{x}^{(N)}\}
```

from which the distribution of model outputs can be approximated.

For example, an uncertain WDN model may include pipe roughness, nodal demand, emitter coefficients, valve settings, or other uncertain parameters. Each sampled parameter vector defines a **scenario** that can subsequently be evaluated by a HydroForge simulation backend.

The appropriate sampling method depends on the structure of the uncertainty, the computational cost of the model, and the purpose of the analysis.

### Available strategies

| Strategy            | Main purpose                    | Typical application                                    |
| ------------------- | ------------------------------- | ------------------------------------------------------ |
| **Monte Carlo**     | General uncertainty propagation | Reliability and probabilistic simulation               |
| **Latin Hypercube** | Stratified space filling        | Expensive models with limited sample budgets           |
| **Sobol**           | Low-discrepancy sampling        | Sensitivity analysis and global exploration            |
| **Halton**          | Low-discrepancy sampling        | Alternative QMC design, especially moderate dimensions |
| **Conditional MC**  | Hierarchical dependencies       | Climate → temperature → demand                         |
| **Nested MC**       | Multiple uncertainty levels     | Long-term scenarios + short-term variability           |
| **Stratified**      | Domain-informed partitioning    | Distinct operating regimes                             |
| **Gibbs**           | MCMC for dependent variables    | Complex joint distributions                            |
| **Scenario Tree**   | Sequential uncertainty          | Multi-stage stochastic optimisation                    |
| **Mixed**           | Composite sampling              | Heterogeneous parameter groups                         |

---

## Quick Start

```python
from hydroforge.sampling import MonteCarloSampler
from hydroforge.uncertainty import (
    Parameter,
    ParameterType,
    NormalDistribution,
    AdditiveUncertainty,
)

diameter = Parameter(
    name="diameter",
    nominal_value=150.0,
    uncertainty=AdditiveUncertainty(
        NormalDistribution(0, 5)
    ),
    type=ParameterType.NUMERICAL,
)

sampler = MonteCarloSampler([diameter])

for scenario in sampler.generate(n=100):
    run_simulation(scenario.values)
```

All sampling strategies ultimately generate `Scenario` objects containing parameter values and strategy-specific metadata.

---

# Sampling Methods

## 1. Monte Carlo Sampling

**Implementation:** `MonteCarloSampler`

Monte Carlo (MC) sampling generates independent realizations from the specified probability distributions:

```math
\mathbf{X}^{(i)} \overset{\mathrm{iid}}{\sim} p(\mathbf{x}),
\qquad i=1,\ldots,N.
```

For an output quantity

```math
Y=f(\mathbf{X}),
```

the expectation can be estimated by

```math
\widehat{\mathbb{E}}[Y]
=
\frac{1}{N}
\sum_{i=1}^{N} f(\mathbf{X}^{(i)}).
```

Under the usual finite-variance assumptions, the standard error of the Monte Carlo estimator decreases at a rate proportional to

```math
O(N^{-1/2}).
```

This makes MC statistically robust and broadly applicable, but convergence can require a large number of expensive model evaluations.

### Use cases

* General uncertainty propagation
* Reliability analysis
* Probabilistic hydraulic simulation
* Large sample budgets
* Models for which individual simulations are inexpensive

Monte Carlo sampling has been widely applied to uncertainty analysis of water distribution systems, including uncertainty in pipe properties and nodal demands.

### Example

```python
sampler = MonteCarloSampler(parameters)

for scenario in sampler.generate(n=1000):
    run_simulation(scenario.values)
```

### Advantages

* Conceptually simple
* Applicable to arbitrary probability distributions
* Straightforward statistical interpretation
* Independent scenarios can be evaluated in parallel
* Provides a useful reference method for comparing alternative designs

### Limitations

* Convergence is relatively slow
* Random samples can leave regions of the input space sparsely represented
* Expensive when each WDN simulation requires substantial computational effort

---

## 2. Latin Hypercube Sampling

**Implementation:** `LatinHypercubeSampler`

Latin Hypercube Sampling (LHS) is a stratified sampling method designed to improve coverage of the marginal distributions compared with independent random sampling.

For a parameter $X_j$, its cumulative distribution function $F_j$ can be divided into $N$ intervals of equal probability:

```math
I_k =
\left[
\frac{k-1}{N},
\frac{k}{N}
\right],
\qquad k=1,\ldots,N.
```

One value is selected from each interval. The resulting values are then randomly permuted across dimensions to construct the $N$ multidimensional samples.

The method was introduced by McKay, Beckman and Conover (1979) as a sampling strategy for computer experiments and has subsequently become widely used for uncertainty and sensitivity analysis.

### Use cases

LHS is particularly useful when:

* the simulation model is computationally expensive;
* the number of simulations must be limited;
* good marginal coverage is important;
* the objective is uncertainty propagation or surrogate/metamodel construction.

LHS has also been investigated specifically for uncertainty analysis of water distribution systems, where it can provide useful estimates of output uncertainty with substantially fewer simulations than conventional Monte Carlo in some applications.

### Example

```python
sampler = LatinHypercubeSampler(parameters)

for scenario in sampler.generate(n=100):
    run_simulation(scenario.values)
```

### Advantages

* Good marginal coverage
* Often more efficient than simple random sampling for limited sample budgets
* Applicable to non-uniform parameter distributions through inverse-CDF transformation
* Suitable for computationally expensive WDN models

### Limitations

* The design size must generally be specified in advance
* Adding samples while preserving the original LHS structure is not straightforward
* Good marginal stratification does not automatically guarantee optimal multidimensional space filling
* Correlations or dependence structures require additional treatment

---

## 3. Sobol Sequence Sampling

**Implementation:** `SobolSampler`

Sobol sampling is a **quasi-Monte Carlo (QMC)** method based on low-discrepancy sequences.

Instead of generating independent random points, a deterministic sequence

```math
\mathbf{u}^{(1)},\mathbf{u}^{(2)},\ldots
\in [0,1]^d
```

is constructed to provide more uniform coverage of the unit hypercube than typical pseudorandom sequences.

The samples are subsequently transformed to the required parameter distributions using the inverse CDF:

```math
x_j^{(i)}
=
F_j^{-1}(u_j^{(i)}).
```

Sobol sequences were introduced by Sobol for multidimensional numerical integration and are now widely used in uncertainty and global sensitivity analysis.

### Use cases

* Global sensitivity analysis
* Variance-based sensitivity analysis
* Expensive simulation models
* Space-filling experimental designs
* Reproducible sampling

HydroForge exposes options related to sensitivity analysis, including `calc_second_order` and `skip_values`.

### Example

```python
sampler = SobolSampler(
    parameters,
    skip_values=128,
)

for scenario in sampler.generate(n=256):
    run_simulation(scenario.values)
```

### Sobol sampling and sensitivity analysis

Sobol sequences are particularly useful when the generated samples are subsequently used for variance-based global sensitivity analysis. HydroForge integrates with `SALib` for this class of analysis. The SALib library provides implementations of established sensitivity-analysis methods and is described by Herman & Usher (2017).

### Advantages

* Low-discrepancy coverage of the parameter space
* Deterministic and reproducible
* Effective for space-filling designs
* Well suited to global sensitivity analysis
* Can be extended incrementally using appropriate sequence construction

### Practical considerations

Powers of two are commonly used when constructing Sobol designs because many Sobol implementations are naturally extensible in blocks of $2^m$ points. This is a **design recommendation rather than a mathematical requirement**.

For example:

```text
128 → 256 → 512 → 1024 → ...
```

The `skip_values` option can be used to omit an initial part of the sequence.

---

## 4. Halton Sequence Sampling

**Implementation:** `HaltonSampler`

Halton sampling is another quasi-Monte Carlo method. An $d$-dimensional Halton sequence is constructed using radical-inverse functions in distinct prime bases.

For a prime base $b$, the radical-inverse function is

```math
\phi_b(n)
=
\sum_{k=0}^{\infty}
a_k b^{-(k+1)},
```

where

```math
n=\sum_{k=0}^{\infty}a_k b^k.
```

A multidimensional Halton point can therefore be written as

```math
\mathbf{u}^{(n)}
=
\left[
\phi_{b_1}(n),
\phi_{b_2}(n),
\ldots,
\phi_{b_d}(n)
\right],
```

typically using successive prime numbers as the bases.

The method was introduced by Halton (1960).

### Use cases

* Alternative QMC sampling
* Moderate-dimensional problems
* Deterministic space-filling designs
* Situations where arbitrary sample sizes are convenient

### Example

```python
sampler = HaltonSampler(
    parameters,
    skip_values=32,
)

for scenario in sampler.generate(n=100):
    run_simulation(scenario.values)
```

### Advantages

* Deterministic
* Good space-filling properties
* Arbitrary numbers of samples can be generated
* Simple underlying construction
* Custom prime bases can be specified

### Limitations

Classical Halton sequences can exhibit undesirable correlations as dimensionality increases. For higher-dimensional problems, scrambled or alternative digital-net constructions may therefore be preferable.

HydroForge exposes:

```python
skip_values
primes
```

to control the generated sequence.

---

# Hierarchical Sampling

## 5. Conditional / Hierarchical Monte Carlo

**Implementation:** `ConditionalMonteCarloSampler`

HydroForge uses conditional sampling to represent **hierarchical parameter dependencies**.

For parameters ordered as

```math
X_1,X_2,\ldots,X_d,
```

the joint distribution can be factorised as

```math
p(x_1,\ldots,x_d)
=
p(x_1)
p(x_2\mid x_1)
p(x_3\mid x_1,x_2)
\cdots
p(x_d\mid x_1,\ldots,x_{d-1}).
```

Sampling therefore proceeds sequentially:

```math
X_1\sim p(X_1),
```

followed by

```math
X_2\sim p(X_2\mid X_1),
```

and so forth.

This structure is useful when one uncertain process naturally modifies the distribution or value of another.

> **Terminology:** this implementation is best understood as *hierarchical/conditional sampling*. In the broader Monte Carlo literature, “conditional Monte Carlo” can also refer to variance-reduction estimators based on conditional expectations.

### Example: climate → temperature → demand

```python
layers = [
    ConditionalLayer(
        parameters=[climate]
    ),
    ConditionalLayer(
        parameters=[temperature],
        condition_func=adjust_temperature
    ),
    ConditionalLayer(
        parameters=[demand],
        condition_func=adjust_demand
    ),
]

sampler = ConditionalMonteCarloSampler(layers)

for scenario in sampler.generate(n=100):
    run_simulation(scenario.values)
```

### WDN applications

Examples include:

```text
Climate regime
      ↓
Temperature
      ↓
Water demand
      ↓
Network hydraulic response
```

or

```text
Operational condition
      ↓
Demand pattern
      ↓
Pressure / flow response
```

### Advantages

* Explicit representation of dependency structure
* Natural representation of hierarchical uncertainty
* Avoids treating dependent parameters as independent
* Allows domain-specific conditional relationships

### Important consideration

The conditional functions should represent scientifically defensible relationships. A dependency encoded through `condition_func` is part of the probabilistic model and should therefore be documented and, where possible, calibrated against data.

---

## 6. Nested Monte Carlo

**Implementation:** `NestedMonteCarloSampler`

Nested Monte Carlo is appropriate when uncertainty exists at multiple levels.

Let $X$ represent an outer or macro-scale uncertainty and $Y$ represent an inner uncertainty conditional on $X$. For a model output $f(X,Y)$,

```math
\mathbb{E}[f(X,Y)]
=
\mathbb{E}_X
\left[
\mathbb{E}_{Y\mid X}
\left[
f(X,Y)
\mid X
\right]
\right].
```

HydroForge represents this structure explicitly through outer and inner parameter groups.

```python
spec = NestedSamplingSpec(
    outer_parameters=[annual_rainfall, temperature_trend],
    inner_parameters=[daily_demand, pipe_failures],
    n_inner=100,
    inner_sampler_class=LatinHypercubeSampler,
)

sampler = NestedMonteCarloSampler(spec)
```

### Example

A WDN planning analysis might distinguish:

```text
Outer uncertainty
Long-term climate / annual demand trend
                ↓
Inner uncertainty
Daily demand / operational variability
                ↓
Network simulation
```

This is useful when the quantity of interest explicitly depends on multiple uncertainty scales.

### Computational cost

With $N_\mathrm{out}$ outer samples and $N_\mathrm{in}$ inner samples, the number of model evaluations is approximately

```math
N_\mathrm{sim}
=
N_\mathrm{out}N_\mathrm{in}.
```

Consequently, nested sampling can become computationally expensive very quickly.

### Advantages

* Explicit representation of multiple uncertainty levels
* Natural for two-stage or multilevel uncertainty
* Allows a different sampling strategy to be used at the inner level

### Limitations

* Computational cost grows multiplicatively
* The allocation of samples between levels affects estimator efficiency
* Inner and outer sampling errors both contribute to the final estimate

---

# Stratified and MCMC Sampling

## 7. Stratified Sampling

**Implementation:** `StratifiedSampler`

Stratified sampling partitions the input space into predefined regions, or **strata**, and samples separately within each region.

For strata $S_h$, with probability $W_h=P(X\in S_h)$, an expectation can be decomposed as

```math
\mathbb{E}[Y]
=
\sum_{h=1}^{H}
W_h
\mathbb{E}[Y\mid X\in S_h].
```

An estimator is therefore

```math
\hat{\mu}
=
\sum_{h=1}^{H}
W_h
\frac{1}{n_h}
\sum_{i=1}^{n_h}Y_{hi}.
```

HydroForge allows strata to be defined using parameter bounds and either relative weights or explicit sample counts.

### CDF Requirements

Stratified sampling requires access to cumulative distribution functions (CDFs) to map stratum bounds to the parameter's probability space. This is used internally to ensure that samples within a stratum follow the conditional distribution within those bounds.

**CDFs are available for:**
- Parameters with **NoUncertainty** (deterministic)
- Parameters with **AdditiveUncertainty** (e.g., nominal ± noise)
- Parameters with **MultiplicativeUncertainty** (e.g., nominal × (1 ± noise))

**CDFs are NOT available for:**
- **Categorical parameters**: No well-defined CDF for non-numeric domains
- **BiasUncertainty**: Deterministic transformations with no variability
- Other categorical uncertainty models

If you attempt stratified sampling on a parameter without CDF support, `StratifiedSampler` will raise a `CDFNotAvailable` error with guidance on how to fix it.

### Example

```python
strata = [
    Stratum(
        name="low_load",
        bounds={"flow": (0, 30)},
        weight=0.2,
    ),
    Stratum(
        name="normal",
        bounds={"flow": (30, 70)},
        weight=0.6,
    ),
    Stratum(
        name="peak",
        bounds={"flow": (70, 100)},
        weight=0.2,
    ),
]

sampler = StratifiedSampler(parameters, strata)
```

### Example with Uncertainty

For parameters with uncertainty, stratification works with the distribution of realized values:

```python
from hydroforge.uncertainty import (
    Parameter, ParameterType,
    AdditiveUncertainty, NormalDistribution
)
from hydroforge.sampling import StratifiedSampler, Stratum

# Create parameter with additive uncertainty
flow_param = Parameter(
    name="flow",
    nominal_value=50.0,  # nominal flow
    uncertainty=AdditiveUncertainty(NormalDistribution(0, 5)),  # ±5 units
    type=ParameterType.NUMERICAL,
)

# Define strata in terms of realized values (accounting for uncertainty)
strata = [
    Stratum(name="low", bounds={"flow": (35, 50)}, weight=0.3),
    Stratum(name="normal", bounds={"flow": (50, 65)}, weight=0.4),
    Stratum(name="high", bounds={"flow": (65, 80)}, weight=0.3),
]

# Create sampler - it automatically uses parameter CDFs internally
sampler = StratifiedSampler([flow_param], strata)

# Generate scenarios
for scenario in sampler.generate(100):
    flow_value = scenario.values['flow']
    print(f"Flow: {flow_value:.2f}")
```

### WDN applications

Stratification is useful when domain knowledge identifies physically or operationally important regions, for example:

* low-flow operation;
* normal operation;
* peak-demand operation;
* drought conditions;
* high-demand events;
* particular hydraulic regimes.

The statistical foundations of stratified sampling were established by Neyman (1934).

### Advantages

* Guarantees representation of specified regions
* Incorporates domain knowledge directly into the sampling design
* Allows explicit allocation of computational effort
* Particularly useful for rare or operationally important regimes
* Works seamlessly with distribution-based uncertainties through automatic CDF computation

### Limitations

* Strata should have a defensible statistical or physical interpretation. Arbitrary strata can introduce an inefficient allocation of simulations and may distort the intended uncertainty distribution if their weights are not specified consistently with the underlying probability model.
* Only works with parameters that have available CDFs (numerical parameters with appropriate uncertainty models).
* For categorical parameters, consider other sampling methods like `MixedStrategySampler` which applies different strategies to different parameter groups.

### Troubleshooting

**Error: "CDFNotAvailable: Cannot use stratified sampling with parameter..."**

This occurs when a parameter doesn't support CDF evaluation. Solutions:

1. **For categorical parameters**: Use stratification only on numerical parameters. For categorical parameters, use `MixedStrategySampler` with separate strategies for each parameter group.

2. **For BiasUncertainty**: Replace with a distribution-based uncertainty model (e.g., `AdditiveUncertainty` with a very narrow distribution).

3. **For custom uncertainty models**: Implement the `transform_cdf()` method in your uncertainty class.

Example of workaround:

```python
from hydroforge.sampling import MixedStrategySampler, ParameterGroup, SamplingStrategy, Stratum

# Separate parameters by type
numerical_params = [p for p in parameters if not p.is_categorical()]
categorical_params = [p for p in parameters if p.is_categorical()]

# Apply stratified sampling to numerical parameters only
if numerical_params:
    strata = [
        Stratum(name="low", bounds={"flow": (30, 50)}, weight=0.5),
        Stratum(name="high", bounds={"flow": (50, 70)}, weight=0.5),
    ]
    groups = [
        ParameterGroup(numerical_params, SamplingStrategy.STRATIFIED, 
                      {"strata": strata}),
        ParameterGroup(categorical_params, SamplingStrategy.MONTE_CARLO),
    ]
    sampler = MixedStrategySampler(groups)
```

---

## 8. Gibbs Sampling

**Implementation:** `GibbsSampler`

Gibbs sampling is a Markov chain Monte Carlo (MCMC) method for generating samples from a joint distribution when its full conditional distributions are available.

For a parameter vector

```math
\mathbf{X}=(X_1,\ldots,X_d),
```

a Gibbs iteration updates each component conditionally on the current values of the remaining components:

```math
X_i^{(t+1)}
\sim
p\left(
X_i
\mid
X_1^{(t+1)},\ldots,X_{i-1}^{(t+1)},
X_{i+1}^{(t)},\ldots,X_d^{(t)}
\right).
```

After an appropriate burn-in period and under suitable regularity conditions, the chain can be used to approximate the target joint distribution.

Gelfand & Smith (1990) established the importance of Gibbs sampling and related sampling-based approaches for Bayesian computation.

### Example

```python
sampler = GibbsSampler(
    parameters,
    n_burn_in=500,
    n_thin=10,
    initial_values={
        "diameter": 150.0,
    },
)

for scenario in sampler.generate(100):
    run_simulation(scenario.values)
```

### Important MCMC considerations

Unlike MC, LHS, Sobol and Halton sampling, successive Gibbs samples are generally **not independent**.

Consequently, the effective sample size can be substantially smaller than the nominal number of generated samples.

The following should therefore be considered:

* burn-in;
* chain convergence;
* autocorrelation;
* effective sample size;
* sensitivity to initial values;
* potentially multiple independent chains.

`n_thin` is provided as an option, but thinning should not automatically be interpreted as improving statistical efficiency.

### Use cases

* Complex parameter dependencies
* Joint distributions specified through full conditional distributions
* Bayesian or hierarchical models
* Cases where direct independent sampling is difficult

---

# Sequential Decision Modelling

## 9. Scenario Tree Sampling

**Implementation:** `ScenarioTreeSampler`

A scenario tree represents uncertainty as a finite set of discrete paths through time or decision stages.

For a path

```math
\omega_k
=
(x_1,x_2,\ldots,x_T),
```

its probability is obtained from the product of conditional branch probabilities:

```math
P(\omega_k)
=
\prod_{t=1}^{T}
P(x_t\mid x_1,\ldots,x_{t-1}).
```

Scenario trees therefore provide an explicit representation of both **uncertainty and information revelation**.

### Example

```python
root = ScenarioTreeNode(
    name="Root",
    probability=1.0,
)

low_demand = ScenarioTreeNode(
    name="LowDemand",
    probability=0.4,
    parameter_values={"demand": 80},
)

high_demand = ScenarioTreeNode(
    name="HighDemand",
    probability=0.6,
    parameter_values={"demand": 120},
)

root.add_child(low_demand)
root.add_child(high_demand)

sampler = ScenarioTreeSampler(
    parameters,
    root,
)

for scenario in sampler.generate():
    print(scenario.metadata["path"])
    print(scenario.metadata["path_probability"])
```

### WDN applications

Scenario trees are particularly appropriate for:

* multi-stage infrastructure planning;
* adaptive network expansion;
* future-demand scenarios;
* drought and climate scenarios;
* supply disruption scenarios;
* stochastic optimisation.

Scenario-based stochastic programming explicitly represents uncertainty through a finite set of scenarios, and scenario trees are commonly used for multistage formulations.

A WDN example could be:

```text
t0
│
├── Low demand
│   ├── Normal supply
│   └── Disruption
│
└── High demand
    ├── Normal supply
    └── Disruption
```

### Limitations

The number of nodes can grow rapidly with the number of stages and branches:

```math
N_\mathrm{nodes}
\sim
O(B^T),
```

for a tree with approximately $B$ branches per stage and $T$ stages.

Consequently, scenario reduction or pruning may become necessary for large multistage problems.

---

# Composite Sampling

## 10. Mixed Strategy Sampling

**Implementation:** `MixedStrategySampler`

Different groups of uncertain parameters may have different statistical characteristics and therefore benefit from different sampling designs.

`MixedStrategySampler` allows parameters to be partitioned into groups and assigns a sampling strategy to each group.

```python
groups = [
    ParameterGroup(
        parameters=continuous_params,
        strategy=SamplingStrategy.SOBOL,
        sampler_kwargs={"skip_values": 128},
    ),
    ParameterGroup(
        parameters=discrete_params,
        strategy=SamplingStrategy.LATIN_HYPERCUBE,
    ),
    ParameterGroup(
        parameters=categorical_params,
        strategy=SamplingStrategy.MONTE_CARLO,
    ),
]

sampler = MixedStrategySampler(groups)
```

### Example: heterogeneous WDN parameters

A WDN model might contain:

```text
Continuous physical parameters
    → Sobol

Discrete parameters
    → LHS

Categorical scenarios
    → Monte Carlo
```

This is particularly useful when the uncertain parameter space contains continuous, discrete and categorical variables or when different groups have different modelling requirements.

### Important consideration

Mixed sampling is a **composite design provided by HydroForge**, rather than a distinct classical sampling algorithm. The statistical properties of the resulting design depend on how the individual parameter groups are combined.

---

# Parameter Integration

All samplers operate through the HydroForge `Parameter` abstraction.

In particular, unit-based sampling methods use

```python
param.sample_from_unit(u)
```

to transform a value

```math
u\in[0,1]
```

from the sampling design into a realization of the parameter distribution:

```math
x = F_X^{-1}(u).
```

This allows the same parameter and uncertainty definitions to be used with random, stratified and quasi-random sampling methods.

For example:

```python
param = Parameter(...)

# Distribution-driven random sampling
value = param.sample()

# Sampling controlled externally
value = param.sample_from_unit(0.5)
```

The `sample_from_unit()` interface is particularly important for LHS, Sobol and Halton sampling.

---

# Choosing a Sampling Strategy

There is no universally optimal sampling strategy. Selection should be based on the statistical structure of the problem and the computational budget.

| Requirement                                  | Recommended starting point |
| -------------------------------------------- | -------------------------- |
| General uncertainty propagation              | Monte Carlo                |
| Expensive model, limited simulations         | LHS                        |
| Space-filling design                         | Sobol or LHS               |
| Global sensitivity analysis                  | Sobol                      |
| Alternative QMC design                       | Halton                     |
| Hierarchical parameter dependence            | Conditional sampling       |
| Multiple uncertainty scales                  | Nested MC                  |
| Known important operating regimes            | Stratified sampling        |
| Complex joint distribution with conditionals | Gibbs                      |
| Sequential decisions                         | Scenario tree              |
| Heterogeneous parameter groups               | Mixed strategy             |

### A practical decision guide

```text
Start
│
├─ Sequential decisions?
│      └─ Yes → Scenario Tree
│
├─ Multiple uncertainty levels?
│      └─ Yes → Nested MC
│
├─ Explicit parameter hierarchy?
│      └─ Yes → Conditional Sampling
│
├─ Only conditional distributions available?
│      └─ Yes → Gibbs
│
├─ Important physical/operational regimes known?
│      └─ Yes → Stratified
│
├─ Global sensitivity analysis?
│      └─ Yes → Sobol
│
├─ Limited simulation budget?
│      └─ Yes → LHS or Sobol
│
├─ Heterogeneous parameter types?
│      └─ Yes → Mixed Strategy
│
└─ General-purpose uncertainty propagation
       └─ Monte Carlo
```

These should be treated as **starting recommendations rather than fixed rules**. Sample-size requirements depend on the dimensionality of the problem, output quantity, estimator, distribution of the inputs, and computational objective.

---

# WDN Use Cases

## Climate impact assessment

Conditional sampling can represent a hierarchy such as

```text
Climate regime
      ↓
Temperature
      ↓
Water demand
      ↓
Hydraulic response
```

```python
layers = [
    ConditionalLayer(
        parameters=[climate_regime]
    ),
    ConditionalLayer(
        parameters=[temperature],
        condition_func=adjust_temp_for_climate,
    ),
    ConditionalLayer(
        parameters=[demand],
        condition_func=adjust_demand_for_temperature,
    ),
]

sampler = ConditionalMonteCarloSampler(layers)
```

This approach is appropriate when the conditional relationships are part of the assumed probabilistic model.

---

## Multiscale uncertainty

Nested sampling can distinguish long-term uncertainty from short-term operational variability:

```python
spec = NestedSamplingSpec(
    outer_parameters=[
        annual_rainfall,
        temperature_trend,
    ],
    inner_parameters=[
        daily_demand,
        pipe_failures,
    ],
    n_inner=100,
    inner_sampler_class=LatinHypercubeSampler,
)

sampler = NestedMonteCarloSampler(spec)
```

Conceptually:

```text
Long-term climate uncertainty
            ↓
Annual operating conditions
            ↓
Daily variability
            ↓
Hydraulic simulation
```

---

## Operating-regime analysis

Stratification is useful when specific hydraulic regimes are of particular interest:

```python
strata = [
    Stratum(
        name="low_load",
        bounds={"flow": (0, 30)},
        weight=0.2,
    ),
    Stratum(
        name="normal",
        bounds={"flow": (30, 70)},
        weight=0.6,
    ),
    Stratum(
        name="peak",
        bounds={"flow": (70, 100)},
        weight=0.2,
    ),
]

sampler = StratifiedSampler(parameters, strata)
```

This can be useful for analysing model behaviour under normal operation while retaining explicit representation of low-load and peak-load conditions.

---

## Stochastic infrastructure planning

Scenario trees can represent uncertainty that is progressively revealed over a planning horizon:

```text
Year 1
│
├── Low demand
│   ├── Normal supply
│   └── Disrupted supply
│
└── High demand
    ├── Normal supply
    └── Disrupted supply
```

Such representations are particularly relevant when decisions at one stage depend on information observed at earlier stages.

Applications of sampling and decision-tree approaches to uncertain WDS design have been demonstrated for future water-demand uncertainty.

---

# Computational Considerations

The computational cost of a sampling strategy should be considered together with the cost of evaluating the underlying WDN model.

For $N$ scenarios and $C_f$ computational cost per simulation, the dominant model-evaluation cost is approximately

```math
C_\mathrm{model}
\approx
N C_f.
```

Consequently, reducing the number of simulations can be particularly valuable for transient or extended-period hydraulic models.

| Strategy      |                 Approximate sampling cost | Scenario independence     |
| ------------- | ----------------------------------------: | ------------------------- |
| Monte Carlo   |                                  $O(N)$ | Yes                       |
| LHS           | $O(N\log N)$ in typical implementations | Yes                       |
| Sobol         |                    approximately $O(N)$ | Yes                       |
| Halton        |                    approximately $O(N)$ | Yes                       |
| Conditional   |                                 $O(NL)$ | Across scenarios          |
| Nested        |        $O(N_\mathrm{out}N_\mathrm{in})$ | Across outer/inner groups |
| Stratified    |                    approximately $O(N)$ | Yes                       |
| Gibbs         |                   $O(Nd)$, plus burn-in | No, within chain          |
| Scenario tree |                Depends on number of nodes | Paths can be independent  |
| Mixed         |           Depends on component strategies | Usually yes               |

These are sampling-level estimates; actual runtime is usually dominated by the WDN simulation itself.

---

# Parallel Execution

The independent nature of many sampling strategies makes them suitable for parallel simulation.

### Naturally parallel

* Monte Carlo
* LHS
* Sobol
* Halton
* Stratified sampling

Each scenario can generally be evaluated independently once generated.

### Hierarchical parallelism

Conditional sampling can be parallelised across independent scenarios, although the layers within an individual scenario are sequential.

Nested sampling can generally parallelise across outer scenarios and, where appropriate, across inner simulations.

### Sequential methods

Gibbs sampling is inherently sequential within a Markov chain because each state depends on the previous state.

Scenario trees have a different structure: individual paths may be evaluated independently once the tree has been generated, although decisions and information-sharing constraints must be respected in subsequent stochastic optimisation.

---

# Reproducibility

Reproducibility is important for uncertainty analysis because differences between simulation runs should be attributable to the model or sampling design rather than uncontrolled changes in the generated scenarios.

HydroForge provides two ID-generation mechanisms:

### `UUIDGenerator`

Generates unique identifiers using UUID4.

```python
sampler = MonteCarloSampler(
    parameters,
    id_generator=UUIDGenerator(prefix="sim"),
)
```

### `DeterministicHashGenerator`

Generates identifiers from parameter values using a deterministic hash.

```python
sampler = MonteCarloSampler(
    parameters,
    id_generator=DeterministicHashGenerator,
)
```

The latter is useful for caching and deduplication because identical parameter values generate identical identifiers.

For complete numerical reproducibility, deterministic identifiers should not be confused with deterministic sampling: pseudorandom samplers also require their random-number-generator state or seed to be controlled.

---

# Scenario Metadata

Sampling methods can attach information describing how a scenario was generated.

For example:

### Nested sampling

```python
scenario.metadata = {
    "outer_index": int,
    "inner_index": int,
    "outer_values": dict,
    "inner_values": dict,
}
```

### Gibbs sampling

```python
scenario.metadata = {
    "iteration": int,
    "chain_position": int,
}
```

### Scenario tree

```python
scenario.metadata = {
    "path": str,
    "path_probability": float,
    "tree_depth": int,
}
```

### Stratified sampling

```python
scenario.metadata = {
    "stratum": str,
}
```

This metadata can be used to trace simulation results back to the sampling design and is particularly useful for post-processing and uncertainty decomposition.

---

# Best Practices

### 1. Start with a reference design

For a new uncertainty analysis, Monte Carlo provides a useful baseline against which more structured sampling methods can be compared.

### 2. Match the sampler to the model cost

For computationally expensive WDN simulations, LHS or QMC methods may provide better space coverage for a fixed simulation budget.

For inexpensive models, the statistical robustness and simplicity of MC may justify using a much larger number of scenarios.

### 3. Validate sample coverage

For low-dimensional problems, inspect:

* marginal distributions;
* pairwise scatter plots;
* empirical CDFs;
* parameter correlations;
* coverage of physically important regions.

### 4. Check convergence

Do not select a sample size solely from a generic rule of thumb.

Instead, examine convergence of quantities of interest such as:

```math
\hat{\mu}_N,\qquad
\hat{\sigma}_N^2,\qquad
\hat{q}_{0.05,N},\qquad
\hat{q}_{0.95,N}.
```

### 5. Treat MCMC differently

For Gibbs sampling, assess:

* burn-in;
* autocorrelation;
* effective sample size;
* convergence across chains;
* sensitivity to initial conditions.

### 6. Preserve the probabilistic interpretation

Structured sampling should improve computational efficiency without changing the intended input distribution.

In particular, domain-informed stratification and conditional relationships should be accompanied by explicit probability weights or scientifically justified conditional distributions.

### 7. Consider model-evaluation cost

For WDN uncertainty analysis, the cost of sampling is often negligible relative to the hydraulic or water-quality simulation. The main objective should therefore be to obtain an informative ensemble of simulations with as few model evaluations as reasonably possible.

This is particularly relevant for transient and extended-period simulations, where conventional Monte Carlo can become computationally demanding.

---

# References

### Monte Carlo

**[1]** Metropolis, N. & Ulam, S. (1949). The Monte Carlo method. *Journal of the American Statistical Association*, 44(247), 335–341. DOI: `10.1080/01621459.1949.10483310`.

### Latin Hypercube Sampling

**[2]** McKay, M. D., Beckman, R. J. & Conover, W. J. (1979). A comparison of three methods for selecting values of input variables in the analysis of output from a computer code. *Technometrics*, 21(2), 239–245. DOI: `10.1080/00401706.1979.10489755`.

**[3]** Helton, J. C. & Davis, F. J. (2003). Latin hypercube sampling and the propagation of uncertainty in analyses of complex systems. *Reliability Engineering & System Safety*, 81(1), 23–69. DOI: `10.1016/S0951-8320(03)00058-9`.

### Sobol Sequences

**[4]** Sobol', I. M. (1967). On the distribution of points in a cube and the approximate evaluation of integrals. *USSR Computational Mathematics and Mathematical Physics*, 7(4), 86–112. DOI: `10.1016/0041-5553(67)90144-9`.

### Halton Sequences

**[5]** Halton, J. H. (1960). On the efficiency of certain quasi-random sequences of points in evaluating multi-dimensional integrals. *Numerische Mathematik*, 2(1), 84–90. DOI: `10.1007/BF01386213`.

### Hierarchical and Conditional Sampling

**[6]** Gelman, A., Carlin, J. B., Stern, H. S., Dunson, D. B., Vehtari, A. & Rubin, D. B. (2013). *Bayesian Data Analysis*, 3rd ed. Chapman & Hall/CRC.

**[7]** Lindqvist, B. H., Erlemann, R. & Taraldsen, G. (2022). Conditional Monte Carlo revisited. *Scandinavian Journal of Statistics*. DOI: `10.1111/sjos.12549`. This reference is particularly useful for distinguishing classical conditional Monte Carlo from hierarchical conditional sampling.

### Nested Sampling

**[8]** Hironaka, T. & Goda, T. (2023). An efficient estimation of nested expectations without conditional sampling. *Journal of Computational and Applied Mathematics*, 421, 114811. DOI: `10.1016/j.cam.2022.114811`.

### Stratified Sampling

**[9]** Neyman, J. (1934). On the two different aspects of the representative method: The method of stratified sampling and the method of purposive selection. *Journal of the Royal Statistical Society*, 97(4), 558–606. DOI: `10.1111/j.2397-2335.1934.tb04184.x`.

### Gibbs Sampling / MCMC

**[10]** Gelfand, A. E. & Smith, A. F. M. (1990). Sampling-based approaches to calculating marginal densities. *Journal of the American Statistical Association*, 85(410), 398–409. DOI: `10.1080/01621459.1990.10476213`.

### Scenario Trees and Stochastic Programming

**[11]** Ruszczyński, A. & Shapiro, A. (2003). Stochastic programming models. *Handbooks in Operations Research and Management Science*, 10, 1–64. DOI: `10.1016/S0927-0507(03)10001-1`.

### Sensitivity Analysis / Software

**[12]** Herman, J. & Usher, W. (2017). SALib: An open-source Python library for sensitivity analysis. *Journal of Open Source Software*, 2(9), 97. DOI: `10.21105/joss.00097`.

### Applications to Water Distribution Systems

**[13]** Basupi, I. & Kapelan, Z. (2015). Flexible water distribution system design under future demand uncertainty. *Journal of Water Resources Planning and Management*, 141(4). DOI: `10.1061/(ASCE)WR.1943-5452.0000416`.

**[14]** Kapelan, Z., Savic, D. A. & Walters, G. A. (2005). Multiobjective design of water distribution systems under uncertainty. *Water Resources Research*. DOI: `10.1029/2004WR003787`.

**[15]** Approximate methods for uncertainty analysis of water distribution systems. *Urban Water Journal*, 6(3). DOI: `10.1080/15730620802566844`. This study compares Monte Carlo, LHS and other approximation approaches for hydraulic and water-quality uncertainty analysis in WDS models.

---

# Dependencies

The sampling module uses:

* `numpy` — numerical operations;
* `SALib` — sensitivity-analysis and sampling functionality;
* `hydroforge.uncertainty` — parameter and uncertainty definitions.

## Integration Between Uncertainty and Sampling Modules

The integration between the sampling and uncertainty modules is built on three key mechanisms:

### 1. Unit-Interval Sampling (`sample_from_unit()`)

Each parameter provides a `sample_from_unit(u)` method that accepts unit-interval values (0 ≤ u ≤ 1) and produces samples through inverse-transform sampling:

```python
param = Parameter(
    name="diameter",
    nominal_value=100.0,
    uncertainty=AdditiveUncertainty(NormalDistribution(0, 5)),
    type=ParameterType.NUMERICAL
)

# Monte Carlo (random u)
sample1 = param.sample()  # u ~ Uniform(0, 1)

# Controlled sampling (user-provided u)
sample2 = param.sample_from_unit(u=0.5)  # u = 0.5 exactly
```

This interface enables all sampling strategies (Monte Carlo, LHS, Sobol, etc.) to control the transformation of probability space.

### 2. CDF Transformations

For advanced sampling methods like stratified sampling, cumulative distribution functions (CDFs) must be available to map stratum bounds to probability space:

**Distribution CDF:**
```
F_ε(x) = P(ε ≤ x) where ε ~ distribution
```

**Uncertainty-transformed CDF:**
For a parameter Y with uncertainty, the CDF depends on the uncertainty type:
- Additive (Y = x + ε): F_Y(y) = F_ε(y - x)
- Multiplicative (Y = x(1 + ε)): F_Y(y) = F_ε(y/x - 1)

**Parameter CDF:**
```python
param = Parameter(...)
cdf_at_100 = param.cdf(100.0)  # P(parameter ≤ 100)
```

### 3. Stratified Sampling and CDF Requirements

Stratified sampling internally uses parameter CDFs to ensure samples within each stratum follow the conditional distribution within those bounds:

```python
# Bounds are interpreted as value-space bounds
strata = [
    Stratum(name="low", bounds={"diameter": (95, 100)}, weight=0.33),
    Stratum(name="mid", bounds={"diameter": (100, 105)}, weight=0.34),
    Stratum(name="high", bounds={"diameter": (105, 110)}, weight=0.33),
]

# Internally uses: F(105) - F(100) to compute stratum probability
sampler = StratifiedSampler([param], strata)
```

**Supported parameter types for stratified sampling:**
- ✓ Numerical with NoUncertainty
- ✓ Numerical with AdditiveUncertainty
- ✓ Numerical with MultiplicativeUncertainty
- ✗ Categorical (no CDF defined)
- ✗ Numerical with BiasUncertainty (deterministic)

If stratified sampling is attempted on an unsupported parameter type, a `CDFNotAvailable` error is raised with guidance.

---

# API

The main public classes include:

```python
from hydroforge.sampling import (
    MonteCarloSampler,
    LatinHypercubeSampler,
    SobolSampler,
    HaltonSampler,
    ConditionalMonteCarloSampler,
    NestedMonteCarloSampler,
    StratifiedSampler,
    GibbsSampler,
    ScenarioTreeSampler,
    MixedStrategySampler,
    SamplingStrategy,
    ParameterGroup,
    ConditionalLayer,
    NestedSamplingSpec,
    Stratum,
    ScenarioTreeNode,
    Scenario,
)
```

---

# Contributing

When adding a new sampling strategy:

1. Inherit from the appropriate `Sampler` abstraction.
2. Implement `generate(n)`.
3. Add the strategy to `SamplingStrategy`.
4. Provide comprehensive scientific and API documentation.
5. Add tests and demonstration code.
6. Document the statistical assumptions of the method.
7. Include appropriate literature references.
8. Add at least one representative use case.
9. Update the sampling-strategy comparison and decision guide where appropriate.

---

# Related Modules

* `hydroforge.uncertainty.distributions` — probability distributions
* `hydroforge.uncertainty.parameters` — uncertain model parameters
* `hydroforge.uncertainty.uncertainties` — uncertainty transformations
* `hydroforge.sampling` — scenario generation and sampling designs

---

## License

This module is part of the HydroForge library for uncertainty-aware modelling of water distribution network systems.

