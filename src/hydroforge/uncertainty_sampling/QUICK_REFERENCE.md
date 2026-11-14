# Quick Reference: Sampling Strategies (deprecated)

This file belongs to the deprecated `hydroforge.uncertainty_sampling` package.
The maintained implementation is `hydroforge.sampling`.

## Preferred import

```python
from hydroforge.sampling import MonteCarloSampler
```

## One-line descriptions

| Strategy | Description |
|----------|-------------|
| **Monte Carlo** | Independent random sampling |
| **Latin Hypercube** | Stratified sampling for better coverage |
| **Sobol** | Quasi-random low-discrepancy sequence |
| **Halton** | Alternative quasi-random sequence |
| **Conditional MC** | Sequential sampling with dependencies |
| **Nested MC** | Inner/outer multilevel sampling |
| **Stratified** | User-defined strata |
| **GibbsSampler** | Independent marginal resampling under a misleading legacy name |
| **Scenario Tree** | Discretized branching for decisions |
| **Mixed** | Combine strategies for parameter groups |

## Minimal example

```python
from hydroforge.sampling import MonteCarloSampler
from hydroforge.uncertainty import (
    AdditiveUncertainty,
    NormalDistribution,
    Parameter,
    ParameterType,
)

diameter = Parameter(
    name="diameter",
    nominal_value=150.0,
    uncertainty=AdditiveUncertainty(NormalDistribution(0, 5)),
    type=ParameterType.NUMERICAL,
)

for scenario in MonteCarloSampler([diameter]).generate(n=100):
    print(scenario.values)
```

`hydroforge.sampling` imports `SALib`; install it before importing the module.

## Caveats

The current implementation has known limitations, documented in
`spec/0002-code-review-remediation.md`:

- `GibbsSampler` does not implement conditional updates or MCMC.
- `StratifiedSampler` does not use the base sampler's unit-space design.
- `Stratum` validation does not run.
- Sampling is not covered by the test suite.

For current documentation, see [`../sampling/README.md`](../sampling/README.md).
