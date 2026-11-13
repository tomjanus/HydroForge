# Quick Reference: Sampling Strategies

## One-Line Descriptions

| Strategy | Description |
|----------|-------------|
| **Monte Carlo** | Random independent sampling |
| **Latin Hypercube** | Stratified sampling for better coverage |
| **Sobol** | Quasi-random low-discrepancy sequences |
| **Halton** | Alternative quasi-random sequences |
| **Conditional MC** | Sequential sampling with dependencies |
| **Nested MC** | Inner-outer multilevel sampling |
| **Stratified** | Custom strata with domain knowledge |
| **Gibbs** | MCMC for complex dependencies |
| **Scenario Tree** | Discretized branching for decisions |
| **Mixed** | Combine strategies for parameter groups |

## Quick Start Examples

### Monte Carlo
```python
sampler = MonteCarloSampler(parameters)
for scenario in sampler.generate(100):
    run_simulation(scenario.values)
```

### Latin Hypercube
```python
sampler = LatinHypercubeSampler(parameters)
for scenario in sampler.generate(50):
    run_simulation(scenario.values)
```

### Sobol
```python
sampler = SobolSampler(parameters, skip_values=128)
for scenario in sampler.generate(256):
    run_simulation(scenario.values)
```

### Conditional
```python
layers = [
    ConditionalLayer([param1]),
    ConditionalLayer([param2, param3], condition_func=adjust)
]
sampler = ConditionalMonteCarloSampler(layers)
for scenario in sampler.generate(100):
    run_simulation(scenario.values)
```

### Nested
```python
spec = NestedSamplingSpec(
    outer_parameters=[macro_params],
    inner_parameters=[micro_params],
    n_inner=10
)
sampler = NestedMonteCarloSampler(spec)
for scenario in sampler.generate(n_outer=20):
    run_simulation(scenario.values)
```

### Scenario Tree
```python
root = ScenarioTreeNode("Root", probability=1.0)
# ... build tree
sampler = ScenarioTreeSampler(parameters, root)
for scenario in sampler.generate():
    run_simulation(scenario.values)
```

### Mixed
```python
groups = [
    ParameterGroup(cont_params, SamplingStrategy.SOBOL),
    ParameterGroup(cat_params, SamplingStrategy.MONTE_CARLO)
]
sampler = MixedStrategySampler(groups)
for scenario in sampler.generate(100):
    run_simulation(scenario.values)
```

## Decision Tree

```
Start
│
├─ Need sensitivity analysis? 
│  └─ Yes → Sobol (256-1024 samples)
│
├─ Have parameter dependencies?
│  ├─ Sequential (A→B→C) → Conditional MC
│  ├─ Multilevel (macro+micro) → Nested MC
│  └─ Complex → Gibbs
│
├─ Sequential decisions?
│  └─ Yes → Scenario Tree
│
├─ Domain knowledge about regions?
│  └─ Yes → Stratified
│
├─ Mixed parameter types?
│  └─ Yes → Mixed Strategy
│
├─ Budget < 100 samples?
│  └─ Yes → LHS or Sobol
│
└─ Default → Monte Carlo (1000+ samples)
```

## Common Patterns

### Climate Impact Analysis
```python
# Climate → Temperature → Demand
layers = [
    ConditionalLayer([climate]),
    ConditionalLayer([temp], lambda p: adjust_temp(p['climate'])),
    ConditionalLayer([demand], lambda p: adjust_demand(p['temp']))
]
```

### Multi-stage Planning
```python
# Year 1 decisions → Year 2 scenarios → Year 3 outcomes
root = ScenarioTreeNode("Y1", 1.0)
for y2_scenario in ["low", "high"]:
    node_y2 = ScenarioTreeNode(f"Y2_{y2_scenario}", prob)
    root.add_child(node_y2)
    for y3_outcome in ["success", "failure"]:
        node_y3 = ScenarioTreeNode(f"Y3_{y3_outcome}", prob)
        node_y2.add_child(node_y3)
```

### Heterogeneous Parameters
```python
groups = [
    ParameterGroup(physics_params, SamplingStrategy.SOBOL),
    ParameterGroup(counts, SamplingStrategy.LATIN_HYPERCUBE),
    ParameterGroup(categories, SamplingStrategy.MONTE_CARLO)
]
```

## Parameter Requirements

### All Parameters Need
- `name`: str
- `nominal_value`: Value of appropriate type
- `uncertainty`: Uncertainty object
- `kind`: ParameterKind enum

### Conditional MC Needs
- `ConditionalLayer` with optional `condition_func`
- Function signature: `condition_func(prev_values: dict) -> dict`

### Nested MC Needs
- Clear separation of outer/inner parameters
- `n_inner` specification

### Scenario Tree Needs
- Tree structure with `ScenarioTreeNode` objects
- Probabilities (conditional on parent)
- Parameter values at nodes

## Metadata in Scenarios

Different samplers add different metadata:

```python
# Nested MC
scenario.metadata = {
    'outer_index': int,
    'inner_index': int,
    'outer_values': dict,
    'inner_values': dict
}

# Gibbs
scenario.metadata = {
    'iteration': int,
    'chain_position': int
}

# Scenario Tree
scenario.metadata = {
    'path': str,  # e.g., "Root->Branch1->Leaf2"
    'path_probability': float,
    'tree_depth': int
}

# Stratified
scenario.metadata = {
    'stratum': str
}
```

## Import Statement

```python
from found.sampling.sampling import (
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
    Scenario
)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Parameter has no sample_from_unit" | Update to latest version with enhanced Parameter class |
| Sobol warning about skip_values | Use powers of 2: 64, 128, 256, 512 |
| Gibbs not converging | Increase `n_burn_in`, check parameter dependencies |
| Tree growing too large | Prune branches, limit depth, use probability thresholds |
| Conditional sampling not working | Check `condition_func` return values match parameter names |
| Nested MC too slow | Reduce `n_inner`, use faster inner sampler (MC vs LHS) |

## See Also

- Full documentation: `src/found/sampling/README.md`
- Implementation details: `src/found/sampling/IMPLEMENTATION_SUMMARY.md`
- Demo code: `python -m found.sampling.sampling`
