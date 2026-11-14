# Sampling Strategies Implementation Summary (historical)

This file is a historical summary of an earlier sampling implementation.
`hydroforge.sampling` is now the canonical package, but the legacy package is a
divergent copy rather than the same implementation.

## Current location

Use `hydroforge.sampling`:

```python
from hydroforge.sampling import MonteCarloSampler
```

`hydroforge.uncertainty_sampling.strategies` is a deprecated, divergent copy
with overlapping class names but different APIs. It imports the removed
`ParameterKind` symbol and currently fails to import. See
[`../sampling/README.md`](../sampling/README.md) for current documentation and
[`README.md`](README.md) for the deprecation notice.

## Implemented strategies

The legacy copy contains classes with these names:

- Basic: `MonteCarloSampler`, `LatinHypercubeSampler`, `SobolSampler`,
  `HaltonSampler`
- Hierarchical: `ConditionalMonteCarloSampler` (with `ConditionalLayer`),
  `NestedMonteCarloSampler` (with `NestedSamplingSpec`)
- Stratified: `StratifiedSampler` (with `Stratum`)
- `GibbsSampler` (legacy name; independent marginal resampling, not Gibbs/MCMC)
- Decision trees: `ScenarioTreeSampler` (with `ScenarioTreeNode`)
- Composite: `MixedStrategySampler` (with `ParameterGroup`)

All strategies yield `Scenario` objects from `generate(...)`.

## Known limitations

These were not validated in this documentation pass. In particular, the module
test suite does not exercise sampling. Known concerns recorded in
`spec/0002-code-review-remediation.md` include:

- `GibbsSampler` resamples parameters independently rather than from
  conditional distributions.
- `StratifiedSampler` does not use a base sampler's unit-space design.
- `Stratum` validation is currently not executed because `__post_init__` is
  defined outside the class body.
- `SALib` is imported but not declared as a dependency.

## Historical note

Earlier versions of this document used `found.sampling.*` import paths. Those
paths no longer exist.
