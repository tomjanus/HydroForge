""" """
from rich import print as rprint
from rich.table import Table
from hydroforge.uncertainty import (
    NormalDistribution,
    UniformDistribution,
    CategoricalUniformDistribution,
    DiscreteUniformDistribution
)
from hydroforge.uncertainty import (
    AdditiveUncertainty,
    MultiplicativeUncertainty,
    CategoricalRandomReplacementUncertainty
)
from hydroforge.sampling import (
    MonteCarloSampler,
    LatinHypercubeSampler,
    SobolSampler,
    HaltonSampler,
    ConditionalLayer,
    ConditionalMonteCarloSampler,
    NestedMonteCarloSampler,
    NestedSamplingSpec,
    ScenarioTreeSampler,
    ScenarioTreeNode,
    MixedStrategySampler,
    ParameterGroup,
    SamplingStrategy,
    DeterministicHashGenerator,
    StratifiedSampler,
    Stratum,
)
from hydroforge.sampling import nearest_power_of_2
from hydroforge.uncertainty import Parameter, ParameterType

def main():

    rprint("[bold blue]=== Sampling Strategies Demonstration ===[/bold blue]")

    # 1. Define test parameters
    test_parameters = [
        Parameter(
            name="diameter",
            nominal_value=150.0,
            uncertainty=AdditiveUncertainty(NormalDistribution(0, 5)),
            type=ParameterType.NUMERICAL,
            metadata={"unit": "mm", "group": "continuous"}
        ),
        Parameter(
            name="roughness",
            nominal_value=0.1,
            uncertainty=MultiplicativeUncertainty(UniformDistribution(-0.2, 0.2)),
            type=ParameterType.NUMERICAL,
            metadata={"unit": "mm", "group": "continuous"}
        ),
        Parameter(
            name="sensor_count",
            nominal_value=10,
            uncertainty=AdditiveUncertainty(DiscreteUniformDistribution(-2, 2)),
            type=ParameterType.DISCRETE,
            metadata={"unit": "count", "group": "discrete"}
        ),
        Parameter(
            name="material",
            nominal_value="PVC",
            uncertainty=CategoricalRandomReplacementUncertainty(
                CategoricalUniformDistribution(categories=("PVC", "Iron", "Steel"))
            ),
            type=ParameterType.CATEGORICAL,
            metadata={"group": "categorical"}
        )
    ]

    NSAMPLES = 20

    # 2. Monte Carlo Sampling
    rprint("\n[bold green]1. Monte Carlo Sampling[/bold green]")
    rprint("Random sampling - each parameter sampled independently")
    mc_sampler = MonteCarloSampler(test_parameters)
    
    table = Table(title="Monte Carlo Samples")
    table.add_column("ID", style="cyan")
    table.add_column("Diameter", style="green")
    table.add_column("Roughness", style="green")
    table.add_column("Sensors", style="yellow")
    table.add_column("Material", style="magenta")
    
    for scenario in mc_sampler.generate(NSAMPLES):
        table.add_row(
            scenario.id[:15] + "...",
            f"{scenario.values['diameter']:.2f}",
            f"{scenario.values['roughness']:.4f}",
            str(scenario.values['sensor_count']),
            scenario.values['material']
        )
    rprint(table)

    # 3. Latin Hypercube Sampling
    rprint("\n[bold green]2. Latin Hypercube Sampling (LHS)[/bold green]")
    rprint("Stratified sampling - better space coverage than MC")
    lhs_sampler = LatinHypercubeSampler(test_parameters)
    
    table = Table(title="LHS Samples")
    table.add_column("ID", style="cyan")
    table.add_column("Diameter", style="green")
    table.add_column("Roughness", style="green")
    table.add_column("Sensors", style="yellow")
    table.add_column("Material", style="magenta")
    
    for scenario in lhs_sampler.generate(NSAMPLES):
        table.add_row(
            scenario.id[:15] + "...",
            f"{scenario.values['diameter']:.2f}",
            f"{scenario.values['roughness']:.4f}",
            str(scenario.values['sensor_count']),
            scenario.values['material']
        )
    rprint(table)

    # 4. Sobol Sequence Sampling
    rprint("\n[bold green]3. Sobol Sequence Sampling[/bold green]")
    rprint("Quasi-random low-discrepancy sequences - excellent for sensitivity analysis")
    sobol_sampler = SobolSampler(test_parameters, skip_values=nearest_power_of_2(100))
    
    table = Table(title="Sobol Samples")
    table.add_column("ID", style="cyan")
    table.add_column("Diameter", style="green")
    table.add_column("Roughness", style="green")
    table.add_column("Sensors", style="yellow")
    table.add_column("Material", style="magenta")
    
    for scenario in sobol_sampler.generate(NSAMPLES):
        table.add_row(
            scenario.id[:15] + "...",
            f"{scenario.values['diameter']:.2f}",
            f"{scenario.values['roughness']:.4f}",
            str(scenario.values['sensor_count']),
            scenario.values['material']
        )
    rprint(table)

    # 5. Halton Sequence Sampling
    rprint("\n[bold green]4. Halton Sequence Sampling[/bold green]")
    rprint("Alternative quasi-random sequences")
    halton_sampler = HaltonSampler(test_parameters, skip_values=10)
    
    table = Table(title="Halton Samples")
    table.add_column("ID", style="cyan")
    table.add_column("Diameter", style="green")
    table.add_column("Roughness", style="green")
    table.add_column("Sensors", style="yellow")
    table.add_column("Material", style="magenta")
    
    for scenario in halton_sampler.generate(NSAMPLES):
        table.add_row(
            scenario.id[:15] + "...",
            f"{scenario.values['diameter']:.2f}",
            f"{scenario.values['roughness']:.4f}",
            str(scenario.values['sensor_count']),
            scenario.values['material']
        )
    rprint(table)

    # 6. Mixed Strategy Sampling
    rprint("\n[bold green]5. Mixed Strategy Sampling[/bold green]")
    rprint("Different strategies for different parameter groups")
    
    # Separate parameters into groups
    continuous_params = [p for p in test_parameters if p.metadata.get("group") == "continuous"]
    discrete_params = [p for p in test_parameters if p.metadata.get("group") == "discrete"]
    categorical_params = [p for p in test_parameters if p.metadata.get("group") == "categorical"]
    
    # Create parameter groups with different strategies
    groups = [
        ParameterGroup(
            parameters=continuous_params,
            strategy=SamplingStrategy.SOBOL,
            sampler_kwargs={"skip_values": nearest_power_of_2(100)}
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
    
    mixed_sampler = MixedStrategySampler(groups)
    
    table = Table(title="Mixed Strategy Samples")
    table.add_column("ID", style="cyan")
    table.add_column("Diameter\n(Sobol)", style="green")
    table.add_column("Roughness\n(Sobol)", style="green")
    table.add_column("Sensors\n(LHS)", style="yellow")
    table.add_column("Material\n(MC)", style="magenta")
    
    for scenario in mixed_sampler.generate(NSAMPLES):
        table.add_row(
            scenario.id[:15] + "...",
            f"{scenario.values['diameter']:.2f}",
            f"{scenario.values['roughness']:.4f}",
            str(scenario.values['sensor_count']),
            scenario.values['material']
        )
    rprint(table)

    # 6. Stratified Sampling
    rprint("\n[bold green]6. Stratified Sampling[/bold green]")
    rprint(
        "Explicitly divides the parameter space into regions and "
        "samples from the conditional distribution within each region"
    )

    # Divide diameter into three physically meaningful strata.
    #
    # The bounds are interpreted in value space. For each stratum,
    # StratifiedSampler samples from the original diameter distribution
    # conditional on the specified interval.
    strata = [
        Stratum(
            name="small",
            bounds={"diameter": (135.0, 145.0)},
            weight=0.25,
        ),
        Stratum(
            name="nominal",
            bounds={"diameter": (145.0, 155.0)},
            weight=0.50,
        ),
        Stratum(
            name="large",
            bounds={"diameter": (155.0, 165.0)},
            weight=0.25,
        ),
    ]

    stratified_sampler = StratifiedSampler(
        test_parameters,
        strata,
    )

    table = Table(title="Stratified Samples")
    table.add_column("ID", style="cyan")
    table.add_column("Stratum", style="blue")
    table.add_column("Diameter", style="green")
    table.add_column("Roughness", style="green")
    table.add_column("Sensors", style="yellow")
    table.add_column("Material", style="magenta")

    for scenario in stratified_sampler.generate(NSAMPLES):
        table.add_row(
            scenario.id[:15] + "...",
            scenario.metadata["stratum"],
            f"{scenario.values['diameter']:.2f}",
            f"{scenario.values['roughness']:.4f}",
            str(scenario.values['sensor_count']),
            scenario.values['material'],
        )

    rprint(table)
    
    # 7. Demonstrate deterministic hash IDs
    rprint("\n[bold green]7. Deterministic Hash IDs[/bold green]")
    rprint("IDs based on parameter values - reproducible across runs")
    mc_sampler_hash = MonteCarloSampler(
        test_parameters[:2],  # Use fewer params for clarity
        id_generator=DeterministicHashGenerator
    )
    
    table = Table(title="Hash-based IDs")
    table.add_column("Scenario ID", style="cyan")
    table.add_column("Diameter", style="green")
    table.add_column("Roughness", style="green")
    
    for scenario in mc_sampler_hash.generate(3):
        table.add_row(
            scenario.id,
            f"{scenario.values['diameter']:.2f}",
            f"{scenario.values['roughness']:.4f}"
        )
    rprint(table)

    # 8. Comparison of sampling strategies
    rprint("\n[bold blue]=== Strategy Comparison ===[/bold blue]")
    rprint("""
[bold]Basic Strategies:[/bold]

[bold]Monte Carlo (MC):[/bold]
  ✓ Simple and intuitive
  ✓ Works with any distribution
  ✗ May have poor space coverage with few samples
  
[bold]Latin Hypercube Sampling (LHS):[/bold]
  ✓ Better space-filling than MC
  ✓ More efficient for small sample sizes
  ✓ Good for metamodeling
  
[bold]Sobol Sequences:[/bold]
  ✓ Excellent space coverage
  ✓ Low discrepancy (quasi-random)
  ✓ Preferred for sensitivity analysis
  ✓ Deterministic and reproducible
  
[bold]Halton Sequences:[/bold]
  ✓ Good alternative to Sobol
  ✓ Simple to implement
  ✗ May have correlation issues in higher dimensions

[bold]Advanced Strategies:[/bold]

[bold]Conditional/Hierarchical MC:[/bold]
  ✓ Respects parameter dependencies
  ✓ Natural for hierarchical models
  ✓ Used in Bayesian inference
  
[bold]Nested Monte Carlo:[/bold]
  ✓ Handles multilevel uncertainty
  ✓ Computes nested expectations
  ✗ Computationally expensive (compounds variance)
  
[bold]Stratified Sampling:[/bold]
  ✓ Ensures coverage of important regions
  ✓ Domain knowledge incorporation
  ✓ Flexible stratum definitions
  
[bold]Gibbs Sampling (MCMC):[/bold]
  ✓ Handles complex dependencies
  ✓ Only needs conditional distributions
  ✗ Requires burn-in and thinning
  ✗ Autocorrelation between samples
  
[bold]Scenario Trees:[/bold]
  ✓ Natural for sequential decisions
  ✓ Explicit probabilities
  ✓ Common in stochastic programming
  ✗ Exponential growth with stages
  
[bold]Mixed Strategies:[/bold]
  ✓ Flexibility to optimize each parameter group
  ✓ Can combine strengths of different methods
  ✓ Useful for heterogeneous parameter spaces
    """)
    
    # 9. Advanced Sampling Examples
    rprint("\n[bold blue]=== Advanced Sampling Examples ===[/bold blue]")
    
    # 9a. Conditional Monte Carlo
    rprint("\n[bold green]8. Conditional Monte Carlo[/bold green]")
    rprint("Sequential sampling with dependencies: climate → temperature → demand")
    
    # Define climate regime parameter
    climate_param = Parameter(
        name="climate_regime",
        nominal_value="normal",
        uncertainty=CategoricalRandomReplacementUncertainty(
            CategoricalUniformDistribution(categories=("dry", "normal", "wet"))
        ),
        type=ParameterType.CATEGORICAL
    )
    
    temp_param = Parameter(
        name="temperature",
        nominal_value=20.0,
        uncertainty=AdditiveUncertainty(NormalDistribution(0, 3)),
        type=ParameterType.NUMERICAL
    )
    
    demand_param = Parameter(
        name="demand",
        nominal_value=100.0,
        uncertainty=MultiplicativeUncertainty(UniformDistribution(-0.1, 0.1)),
        type=ParameterType.NUMERICAL
    )
    
    # Define conditional function
    def condition_on_climate(prev_values):
        """Adjust temperature and demand based on climate regime."""
        regime = prev_values.get("climate_regime", "normal")
        adjustments = {}
        
        if regime == "dry":
            # Hotter, higher demand
            adjustments["temperature"] = prev_values.get("temperature", 20) + 5
            adjustments["demand"] = prev_values.get("demand", 100) * 1.2
        elif regime == "wet":
            # Cooler, lower demand
            adjustments["temperature"] = prev_values.get("temperature", 20) - 3
            adjustments["demand"] = prev_values.get("demand", 100) * 0.9
        
        return adjustments
    
    layers = [
        ConditionalLayer(parameters=[climate_param]),
        ConditionalLayer(
            parameters=[temp_param, demand_param], 
            condition_func=condition_on_climate)
    ]
    
    conditional_sampler = ConditionalMonteCarloSampler(layers)
    
    table = Table(title="Conditional MC Samples")
    table.add_column("Climate", style="cyan")
    table.add_column("Temperature", style="yellow")
    table.add_column("Demand", style="magenta")
    
    for scenario in conditional_sampler.generate(5):
        table.add_row(
            scenario.values['climate_regime'],
            f"{scenario.values['temperature']:.1f}°C",
            f"{scenario.values['demand']:.1f}"
        )
    rprint(table)
    
    # 9b. Nested Monte Carlo
    rprint("\n[bold green]9. Nested Monte Carlo[/bold green]")
    rprint("Outer: climate scenarios | Inner: daily operations (2 inner per outer)")
    
    # Outer: climate
    outer_params = [climate_param]
    
    # Inner: operational variables
    inner_params = [
        Parameter(
            name="daily_flow",
            nominal_value=50.0,
            uncertainty=MultiplicativeUncertainty(UniformDistribution(-0.2, 0.2)),
            type=ParameterType.NUMERICAL
        )
    ]
    
    nested_spec = NestedSamplingSpec(
        outer_parameters=outer_params,
        inner_parameters=inner_params,
        n_inner=2
    )
    
    nested_sampler = NestedMonteCarloSampler(nested_spec)
    
    table = Table(title="Nested MC Samples")
    table.add_column("Outer", style="cyan")
    table.add_column("Inner", style="cyan")
    table.add_column("Climate", style="yellow")
    table.add_column("Daily Flow", style="magenta")
    
    for scenario in nested_sampler.generate(n=3):
        table.add_row(
            str(scenario.metadata['outer_index']),
            str(scenario.metadata['inner_index']),
            scenario.values['climate_regime'],
            f"{scenario.values['daily_flow']:.1f}"
        )
    rprint(table)
    
    # 9c. Scenario Tree
    rprint("\n[bold green]10. Scenario Tree[/bold green]")
    rprint("Tree: Root → (Low/High demand) → (Normal/Peak usage)")
    
    # Build scenario tree
    root = ScenarioTreeNode(name="Root", probability=1.0, parameter_values={})
    
    # Stage 1: Demand level
    low_demand = ScenarioTreeNode(
        name="LowDemand",
        probability=0.4,
        parameter_values={"demand_level": 80.0}
    )
    high_demand = ScenarioTreeNode(
        name="HighDemand",
        probability=0.6,
        parameter_values={"demand_level": 120.0}
    )
    root.add_child(low_demand)
    root.add_child(high_demand)
    
    # Stage 2: Usage pattern (conditional on demand)
    normal_usage_low = ScenarioTreeNode(
        name="Normal",
        probability=0.7,
        parameter_values={"usage_factor": 1.0}
    )
    peak_usage_low = ScenarioTreeNode(
        name="Peak",
        probability=0.3,
        parameter_values={"usage_factor": 1.3}
    )
    low_demand.add_child(normal_usage_low)
    low_demand.add_child(peak_usage_low)
    
    normal_usage_high = ScenarioTreeNode(
        name="Normal",
        probability=0.5,
        parameter_values={"usage_factor": 1.0}
    )
    peak_usage_high = ScenarioTreeNode(
        name="Peak",
        probability=0.5,
        parameter_values={"usage_factor": 1.5}
    )
    high_demand.add_child(normal_usage_high)
    high_demand.add_child(peak_usage_high)
    
    # Create parameters that can be used with tree
    tree_params = [
        Parameter(
            name="demand_level",
            nominal_value=100.0,
            uncertainty=AdditiveUncertainty(NormalDistribution(0, 5)),
            type=ParameterType.NUMERICAL
        ),
        Parameter(
            name="usage_factor",
            nominal_value=1.0,
            uncertainty=MultiplicativeUncertainty(UniformDistribution(-0.05, 0.05)),
            type=ParameterType.NUMERICAL
        )
    ]
    
    tree_sampler = ScenarioTreeSampler(tree_params, root)
    
    table = Table(title="Scenario Tree Paths")
    table.add_column("Path", style="cyan")
    table.add_column("Probability", style="yellow")
    table.add_column("Demand", style="green")
    table.add_column("Usage", style="magenta")
    
    for scenario in tree_sampler.generate():
        table.add_row(
            scenario.metadata['path'],
            f"{scenario.metadata['path_probability']:.2%}",
            f"{scenario.values['demand_level']:.1f}",
            f"{scenario.values['usage_factor']:.2f}"
        )
    rprint(table)
    
    rprint("\n[bold cyan]✓ All sampling strategies demonstrated successfully![/bold cyan]")
    

if __name__ == "__main__":
    main()
