# uncertainty_sampling (deprecated)

This package is a deprecated, divergent copy of `hydroforge.sampling`. The two
packages contain similarly named samplers but have different implementations
and APIs. `hydroforge.sampling` is the canonical package.

## Status

- Use `hydroforge.sampling` for new code.
- `hydroforge.uncertainty_sampling.strategies` imports `SALib` and the removed
  `ParameterKind` symbol. It currently fails to import even if `SALib` is
  installed.
- The package is a candidate for removal; see
  `spec/0002-code-review-remediation.md`.

## Preferred import

```python
from hydroforge.sampling import MonteCarloSampler
```

The legacy module contains similarly named classes, but its API differs and
should not be treated as a drop-in replacement. It includes:

- `MonteCarloSampler`
- `LatinHypercubeSampler`
- `SobolSampler`
- `HaltonSampler`
- `ConditionalMonteCarloSampler` with `ConditionalLayer`
- `NestedMonteCarloSampler` with `NestedSamplingSpec`
- `StratifiedSampler` with `Stratum`
- `GibbsSampler` (legacy independent marginal resampling; not Gibbs/MCMC)
- `ScenarioTreeSampler` with `ScenarioTreeNode`
- `MixedStrategySampler` with `ParameterGroup`
- `Scenario`, `SamplingStrategy`, `UUIDGenerator`, `DeterministicHashGenerator`

See [`../sampling/README.md`](../sampling/README.md) for current documentation.

## Historical notes

- `strategies.py` in this package was previously named `sampling.py`.
- Older revisions of this README used `found.sampling.*` imports. Those paths no
  longer exist. Use `hydroforge.sampling` and `hydroforge.uncertainty`.
