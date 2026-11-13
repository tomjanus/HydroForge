# Sampling Strategies Module

This module provides comprehensive sampling strategies for uncertainty quantification in water distribution network models and elsewhere.

## Available Sampling Strategies

### Basic Strategies

#### 1. Monte Carlo Sampling (`MonteCarloSampler`)
Random sampling where each parameter is sampled independently using its distribution.

**Use Cases:**
- General-purpose uncertainty propagation
- When computational resources are abundant

**Advantages:**
- Simple implementation
- Works with any distribution type
- Unbiased estimator

**Limitations:**
- May require many samples for good space coverage
- Can miss important regions of parameter space

#### 2. Latin Hypercube Sampling (`LatinHypercubeSampler`)
Stratified sampling that divides each parameter range into equally probable intervals and samples once from each interval.

**Use Cases:**
- When sample budget is limited

**Advantages:**
- Better space-filling properties than Monte Carlo
- More efficient for small sample sizes
- Ensures coverage across entire parameter range

**Limitations:**
- Requires knowing sample size in advance
- Cannot easily add more samples incrementally

#### 3. Sobol Sequence Sampling (`SobolSampler`)
Quasi-random low-discrepancy sequences that provide excellent coverage of parameter space.

**Use Cases:**
- When deterministic reproducibility is needed

**Advantages:**
- Excellent space-filling properties
- Low discrepancy (better than random)
- Deterministic and reproducible
- Ideal for sensitivity analysis

**Parameters:**
- `calc_second_order`: Generate samples for second-order sensitivity indices
- `skip_values`: Number of initial sequence values to skip (improves quality)

**Limitations:**
- Best used with sample sizes that are powers of 2
- More complex to implement

#### 4. Halton Sequence Sampling (`HaltonSampler`)
Alternative quasi-random sequences based on prime numbers.

**Use Cases:**
- Alternative to Sobol sequences
- When simpler implementation is preferred
- Low to moderate dimensional problems

**Advantages:**
- Simple to implement
- Good space-filling properties
- No restrictions on sample size

**Parameters:**
- `skip_values`: Number of initial values to skip
- `primes`: Custom prime bases (default: 2, 3, 5, 7, 11, ...)

**Limitations:**
- May have correlation issues in higher dimensions
- Generally less efficient than Sobol for high-dimensional problems

### Advanced Strategies

#### 5. Conditional/Hierarchical Monte Carlo (`ConditionalMonteCarloSampler`)
Sequential sampling where parameters are sampled in layers with dependencies: p(X₁)p(X₂|X₁)p(X₃|X₁,X₂)...

**Use Cases:**
- Hierarchical models (Bayesian inference)
- Natural dependency structures, e.g. Climate → Temperature → Demand cascades

**Advantages:**
- Respects parameter dependencies
- Natural for hierarchical models
- Common in probabilistic programming

**Example:**
```python
from found.sampling.sampling import ConditionalMonteCarloSampler, ConditionalLayer

# Define conditioning function
def adjust_for_climate(prev_values):
    regime = prev_values.get("climate", "normal")
    if regime == "dry":
        return {"temperature": prev_values["temperature"] + 5}
    return {}

layers = [
    ConditionalLayer(parameters=[climate_param]),
    ConditionalLayer(
        parameters=[temp_param, demand_param],
        condition_func=adjust_for_climate
    )
]

sampler = ConditionalMonteCarloSampler(layers)
```

#### 6. Nested Monte Carlo (`NestedMonteCarloSampler`)
Inner-outer sampling for multilevel uncertainty: E_X[E_{Y|X}[f(X,Y)]]

**Use Cases:**
- Multilevel uncertainty (macro + micro), e.g. climate scenarios + daily operations
- Nested expectations computation

**Advantages:**
- Handles hierarchical uncertainty
- Natural for two-stage problems
- Explicit outer/inner structure

**Limitations:**
- Computationally expensive
- Variance compounds across levels
- Requires careful allocation of inner samples

**Example:**
```python
from found.sampling.sampling import NestedMonteCarloSampler, NestedSamplingSpec

spec = NestedSamplingSpec(
    outer_parameters=[climate_param],      # Macro-level
    inner_parameters=[operational_params], # Micro-level
    n_inner=10,                            # 10 inner per outer
    inner_sampler_class=LatinHypercubeSampler
)

sampler = NestedMonteCarloSampler(spec)
for scenario in sampler.generate(n_outer=100):
    # scenario.metadata contains outer_index, inner_index
    pass
```

#### 7. Stratified Sampling (`StratifiedSampler`)
Custom strata definitions with flexible sampling within each stratum.

**Use Cases:**
- When domain knowledge suggests important regions

**Advantages:**
- Ensures coverage of important regions
- Incorporates domain knowledge
- Flexible stratum definitions

**Example:**
```python
from found.sampling.sampling import StratifiedSampler, Stratum

strata = [
    Stratum(
        name="low_flow",
        bounds={"flow": (0, 50)},
        weight=0.3,    # 30% of samples
    ),
    Stratum(
        name="high_flow",
        bounds={"flow": (150, 200)},
        n_samples=20,  # Fixed 20 samples
    )
]

sampler = StratifiedSampler(parameters, strata)
```

#### 8. Gibbs Sampling (`GibbsSampler`)
MCMC sampling updating one parameter at a time from conditionals.

**Use Cases:**
- Complex parameter dependencies
- When only conditional distributions available

**Advantages:**
- Handles complex dependencies
- Only needs conditional distributions
- Flexible for arbitrary models

**Limitations:**
- Requires burn-in period
- Autocorrelation between samples
- May need thinning
- Slower convergence

**Parameters:**
- `n_burn_in`: Discard first N samples (default: 100)
- `n_thin`: Keep every Nth sample (default: 1)
- `initial_values`: Starting point for chain

**Example:**
```python
from found.sampling.sampling import GibbsSampler

sampler = GibbsSampler(
    parameters,
    n_burn_in=500,
    n_thin=10,
    initial_values={"diameter": 150.0}
)

# Generates samples from stationary distribution
for scenario in sampler.generate(100):
    pass
```

#### 9. Scenario Tree Sampling (`ScenarioTreeSampler`)
Discretized branching structure for sequential decision problems.

**Use Cases:**
- Multi-stage decision analysis
- Decision trees with probabilities

**Advantages:**
- Natural for sequential decisions
- Explicit scenario probabilities
- Common in optimization under uncertainty

**Limitations:**
- Exponential growth with stages
- Requires manual tree construction
- Discrete approximation of continuous uncertainty

**Example:**
```python
from found.sampling.sampling import ScenarioTreeSampler, ScenarioTreeNode

# Build tree
root = ScenarioTreeNode(name="Root", probability=1.0)

low_demand = ScenarioTreeNode(
    name="LowDemand",
    probability=0.4,
    parameter_values={"demand": 80}
)
high_demand = ScenarioTreeNode(
    name="HighDemand",
    probability=0.6,
    parameter_values={"demand": 120}
)

root.add_child(low_demand)
root.add_child(high_demand)

# Add more stages...
sampler = ScenarioTreeSampler(parameters, root)

# Generates all paths from root to leaves
for scenario in sampler.generate():
    print(scenario.metadata['path'])  # e.g., "Root->LowDemand->Normal"
    print(scenario.metadata['path_probability'])  # Joint probability
```

### Composite Strategies

#### 10. Mixed Strategy Sampling (`MixedStrategySampler`)
Combines different sampling strategies for different parameter groups.

**Use Cases:**
- Heterogeneous parameter spaces
- When different parameter types benefit from different strategies
- Optimization of sampling efficiency

**Advantages:**
- Maximum flexibility
- Can optimize each parameter group independently
- Combines strengths of multiple methods

**Example:**
```python
from found.sampling.sampling import (
    MixedStrategySampler, 
    ParameterGroup, 
    SamplingStrategy
)

# Separate parameters by type
continuous_params = [param1, param2]   # Continuous parameters
discrete_params = [param3]             # Discrete parameters
categorical_params = [param4]          # Categorical parameters

# Define sampling strategy for each group
groups = [
    ParameterGroup(
        parameters=continuous_params,
        strategy=SamplingStrategy.SOBOL,
        sampler_kwargs={"skip_values": 128}
    ),
    ParameterGroup(
        parameters=discrete_params,
        strategy=SamplingStrategy.LATIN_HYPERCUBE
    ),
    ParameterGroup(
        parameters=categorical_params,
        strategy=SamplingStrategy.MONTE_CARLO
    )
]

# Create mixed sampler
sampler = MixedStrategySampler(groups)

# Generate scenarios
for scenario in sampler.generate(n=100):
    print(scenario.values)
```

## ID Generators

### UUIDGenerator (Default)
Generates random unique IDs using UUID4.

```python
sampler = MonteCarloSampler(parameters, id_generator=UUIDGenerator(prefix="sim"))
```

### DeterministicHashGenerator
Generates IDs based on parameter values using SHA-256 hash.

**Advantages:**
- Reproducible across runs
- Same parameter values always generate same ID
- Useful for caching and deduplication

```python
sampler = MonteCarloSampler(parameters, id_generator=DeterministicHashGenerator)
```

## Quick Start

```python
from found.sampling.sampling import MonteCarloSampler, LatinHypercubeSampler, SobolSampler
from found.uncertainty.parameters import Parameter, ParameterKind
from found.uncertainty.distributions import NormalDistribution
from found.uncertainty.uncertainties import AdditiveUncertainty

# Define uncertain parameter
diameter = Parameter(
    name="diameter",
    nominal_value=150.0,
    uncertainty=AdditiveUncertainty(NormalDistribution(0, 5)),
    kind=ParameterKind.NUMERICAL
)

# Monte Carlo sampling
mc_sampler = MonteCarloSampler([diameter])
for scenario in mc_sampler.generate(n=100):
    print(scenario.values['diameter'])

# Latin Hypercube Sampling
lhs_sampler = LatinHypercubeSampler([diameter])
for scenario in lhs_sampler.generate(n=100):
    print(scenario.values['diameter'])

# Sobol Sequence Sampling
sobol_sampler = SobolSampler([diameter], skip_values=128)
for scenario in sobol_sampler.generate(n=100):
    print(scenario.values['diameter'])
```

## Choosing the Right Strategy

| Strategy | Small Samples | Large Samples | Sensitivity | Metamodeling | Dependencies | Sequential | Mixed Params |
|----------|--------------|---------------|-------------|--------------|--------------|------------|--------------|
| Monte Carlo | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| LHS | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ |
| Sobol | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ |
| Halton | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ |
| Conditional MC | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Nested MC | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Stratified | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| Gibbs | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Scenario Tree | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Mixed | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

### Decision Guide

**For space-filling and general UQ:**
- Few samples (< 100): Sobol or LHS
- Many samples (> 1000): Monte Carlo
- Sensitivity analysis: Sobol

**For parameter dependencies:**
- Natural hierarchy (climate→temp→demand): Conditional MC
- Multilevel structure (macro + micro): Nested MC
- Complex conditionals: Gibbs

**For decision problems:**
- Sequential decisions: Scenario Tree
- Discrete stages: Scenario Tree
- Stochastic programming: Scenario Tree

**For heterogeneous parameters:**
- Mixed types (continuous/discrete/categorical): Mixed Strategy
- Different importance levels: Stratified
- Domain knowledge available: Stratified

## Advanced Use Cases

### Climate Impact Assessment
```python
# Climate regime → Temperature → Water demand
layers = [
    ConditionalLayer(parameters=[climate_regime]),
    ConditionalLayer(
        parameters=[temperature],
        condition_func=lambda prev: adjust_temp_for_climate(prev)
    ),
    ConditionalLayer(
        parameters=[demand],
        condition_func=lambda prev: adjust_demand_for_temp(prev)
    )
]
sampler = ConditionalMonteCarloSampler(layers)
```

### Multiscale Uncertainty
```python
# Outer: Long-term climate scenarios
# Inner: Short-term operational variability
spec = NestedSamplingSpec(
    outer_parameters=[annual_rainfall, temperature_trend],
    inner_parameters=[daily_demand, pipe_failures],
    n_inner=100,
    inner_sampler_class=LatinHypercubeSampler
)
sampler = NestedMonteCarloSampler(spec)
```

### Operating Regime Analysis
```python
# Define strata for different operating conditions
strata = [
    Stratum(name="low_load", bounds={"flow": (0, 30)}, weight=0.2),
    Stratum(name="normal", bounds={"flow": (30, 70)}, weight=0.6),
    Stratum(name="peak", bounds={"flow": (70, 100)}, weight=0.2)
]
sampler = StratifiedSampler(parameters, strata)
```

### Stochastic Optimization
```python
# Build decision tree
root = ScenarioTreeNode(name="t0", probability=1.0)

# Stage 1: Demand scenario
for demand in ["low", "medium", "high"]:
    stage1 = ScenarioTreeNode(
        name=f"demand_{demand}",
        probability=demand_probs[demand],
        parameter_values={"demand": demand_values[demand]}
    )
    root.add_child(stage1)
    
    # Stage 2: Supply scenario (conditional on demand)
    for supply in ["normal", "disrupted"]:
        stage2 = ScenarioTreeNode(
            name=f"supply_{supply}",
            probability=supply_probs[demand][supply],
            parameter_values={"supply": supply_values[supply]}
        )
        stage1.add_child(stage2)

sampler = ScenarioTreeSampler(parameters, root)
```

## Integration with Parameters

All samplers work seamlessly with the `Parameter` class through the `sample_from_unit()` method:

```python
# Parameters support both random sampling and unit-based sampling
param = Parameter(...)

# Random sampling (used by Monte Carlo)
value = param.sample()

# Unit-based sampling (used by LHS, Sobol, Halton)
value = param.sample_from_unit(u=0.5)  # u in [0, 1]
```

## Dependencies

- `numpy`: Numerical operations
- `SALib`: Latin Hypercube and Sobol sequence generation
- `found.uncertainty`: Parameter and uncertainty classes

## Theoretical Background

### Basic Methods
- **Monte Carlo**: Direct random sampling from probability distributions. Convergence rate: O(1/√n)
- **Latin Hypercube Sampling**: Stratified sampling ensuring coverage. Reduces variance compared to MC.
- **Quasi-Monte Carlo**: Low-discrepancy sequences (Sobol, Halton) with faster convergence than MC.

### Hierarchical Methods
- **Conditional Sampling**: Implements p(X,Y,Z) = p(X)p(Y|X)p(Z|X,Y) factorization
- **Nested Sampling**: Evaluates E_X[E_{Y|X}[f(X,Y)]] for multilevel uncertainty
- **Gibbs Sampling**: MCMC that samples from p(Xi | X_j≠i) iteratively until convergence

### Stratified Methods
- **Stratification**: Partitions parameter space into regions, samples within each
- **Scenario Trees**: Discrete approximation of continuous distributions for decision problems

## Performance Considerations

### Computational Cost
- **MC, Conditional MC**: O(n) - Linear in number of samples
- **LHS**: O(n log n) - Due to stratification algorithm
- **Sobol, Halton**: O(n) - But with setup overhead
- **Nested MC**: O(n_outer × n_inner) - Can be expensive
- **Gibbs**: O(n × n_burn × n_params) - Includes burn-in cost
- **Scenario Tree**: O(branches^depth) - Exponential in tree depth

### Memory Requirements
- Most samplers: O(n_params) - Store current scenario
- **Nested MC**: O(n_outer × n_inner × n_params) - If storing all samples
- **Scenario Tree**: O(nodes) - Store tree structure
- **Gibbs**: O(n_params) - Only current state

### Parallelization
- **MC, LHS, Sobol, Halton**: Embarrassingly parallel - samples independent
- **Conditional MC**: Parallelizable across scenarios (not within)
- **Nested MC**: Outer loop parallel, inner loops independent
- **Gibbs**: Sequential by nature - cannot parallelize chain
- **Scenario Tree**: Path generation parallelizable

## Best Practices

1. **Start Simple**: Use Monte Carlo for initial exploration, then switch to LHS/Sobol for efficiency

2. **Sample Size Guidelines**:
   - MC: 1000-10000 samples minimum
   - LHS: 10-100 times number of parameters
   - Sobol: Powers of 2 (128, 256, 512, 1024) for best properties
   - Halton: Any size, but skip first 10-100 values
   - Gibbs: Run multiple chains to check convergence

3. **Validation**:
   - Compare different samplers on small problems
   - Check convergence of statistics (mean, variance, quantiles)
   - Visualize sample coverage (scatter plots, marginal distributions)

4. **Efficiency Tips**:
   - Use Sobol/LHS for expensive models (few samples needed)
   - Use MC for cheap models (can afford many samples)
   - Use Mixed strategies to optimize different parameter groups
   - Cache expensive model evaluations

5. **Avoid Common Pitfalls**:
   - Don't use Sobol with sample sizes not powers of 2
   - Don't forget Gibbs burn-in period
   - Don't ignore autocorrelation in MCMC samples
   - Don't use stratified sampling without domain knowledge

## References

### Basic Methods
- Metropolis, N., & Ulam, S. (1949). "The Monte Carlo method." *Journal of the American Statistical Association*
- McKay, M. D., Beckman, R. J., & Conover, W. J. (1979). "A comparison of three methods for selecting values of input variables in the analysis of output from a computer code." *Technometrics*, 21(2), 239-245
- Sobol, I. M. (1967). "On the distribution of points in a cube and the approximate evaluation of integrals." *USSR Computational Mathematics and Mathematical Physics*, 7(4), 86-112
- Halton, J. H. (1960). "On the efficiency of certain quasi-random sequences of points in evaluating multi-dimensional integrals." *Numerische Mathematik*, 2(1), 84-90

### Hierarchical Methods
- Gelman, A., Carlin, J. B., Stern, H. S., & Rubin, D. B. (2013). *Bayesian Data Analysis*. CRC press
- Gelfand, A. E., & Smith, A. F. (1990). "Sampling-based approaches to calculating marginal densities." *Journal of the American Statistical Association*, 85(410), 398-409

### Applications in Water Systems
- Hutton, C., et al. (2023). "Recent developments in probabilistic water demand forecasting." *Journal of Water Resources Planning and Management*
- Creaco, E., et al. (2016). "Real time control of water distribution networks." *Water Resources Research*
- Shapiro, A., Dentcheva, D., & Ruszczyński, A. (2021). *Lectures on Stochastic Programming: Modeling and Theory*. SIAM

### Software and Tools
- Herman, J., & Usher, W. (2017). "SALib: An open-source Python library for sensitivity analysis." *Journal of Open Source Software*, 2(9)
- Kroese, D. P., Brereton, T., Taimre, T., & Botev, Z. I. (2014). "Why the Monte Carlo method is so important today." *Wiley Interdisciplinary Reviews: Computational Statistics*, 6(6), 386-392

## See Also

- `found.uncertainty.distributions`: Probability distribution implementations
- `found.uncertainty.parameters`: Parameter class with sampling support
- `found.uncertainty.uncertainties`: Uncertainty application strategies

## Contributing

When adding new sampling strategies:
1. Inherit from `Sampler` base class
2. Implement `generate(n)` method returning `Generator[Scenario, None, None]`
3. Add to `SamplingStrategy` enum
4. Include comprehensive docstrings
5. Add demonstration code in `__main__` block
6. Update this README with examples and use cases

## License

This module is part of the FOUND uncertainty quantification framework.
