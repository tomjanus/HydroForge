""" """
from rich import print as rprint
import numpy as np
from hydroforge.uncertainty.distributions import (
    NormalDistribution,
    UniformDistribution,
    DiracDeltaDistribution,
    CategoricalUniformDistribution,
    DiscreteNormalDistribution,
    DiscreteUniformDistribution,
    DiscreteHistogramDistribution
)
from hydroforge.uncertainty.uncertainties import (
    AdditiveUncertainty,
    MultiplicativeUncertainty,
    BiasUncertainty,
    BinaryStateFlipUncertainty,
    CategoricalRandomReplacementUncertainty,
    CategoricalReplacementUncertainty
)

def main() -> None:
    """ """
    # Demonstration of Uncertainty classes
    rprint("[bold blue]=== Uncertainty Classes Demonstration ===[/bold blue]")

    # 1. Setup Data
    pipe_diameters = np.array([100.0, 200.0, 300.0])  # mm
    pipe_roughness = 100.0
    pipe_counts = np.array([10, 20, 30])  # number of pipes (discrete values)
    sensor_count = 5  # number of sensors (discrete value)
    valve_status = "OPEN"
    valve_statuses = np.array(["OPEN", "CLOSED", "OPEN"])
    
    rprint("\n[bold green]Original Data:[/bold green]")
    rprint(f"Pipe Diameters: {pipe_diameters}")
    rprint(f"Pipe Roughness: {pipe_roughness}")
    rprint(f"Pipe Counts: {pipe_counts}")
    rprint(f"Sensor Count: {sensor_count}")
    rprint(f"Valve Statuses: {valve_statuses}")

    # 2. Additive Uncertainty (e.g. measurement error)
    rprint("\n[bold green]1. Additive Uncertainty (x + ε)[/bold green]")
    
    # Gaussian noise (mean=0, std=5)
    normal_dist = NormalDistribution(mean=0.0, std_dev=5.0)
    additive_unc = AdditiveUncertainty(distribution=normal_dist)
    
    rprint(f"Distribution: {normal_dist}")
    rprint(f"Applied to scalar (roughness): {additive_unc.apply(pipe_roughness):.2f}")
    rprint(f"Applied to array (diameters): {additive_unc.apply(pipe_diameters)}")

    # 3. Multiplicative Uncertainty (e.g. scaling factor)
    rprint("\n[bold green]2. Multiplicative Uncertainty (x * (1 + ε))[/bold green]")
    
    # Uniform scaling ±10%
    uniform_dist = UniformDistribution(lower=-0.1, upper=0.1)
    mult_unc = MultiplicativeUncertainty(distribution=uniform_dist)
    
    rprint(f"Distribution: {uniform_dist}")
    rprint(f"Applied to scalar (roughness): {mult_unc.apply(pipe_roughness):.2f}")
    rprint(f"Applied to array (diameters): {mult_unc.apply(pipe_diameters)}")

    # 4. Bias Uncertainty
    rprint("\n[bold green]3. Bias Uncertainty (x + bias)[/bold green]")
    bias_unc = BiasUncertainty(bias=10.0)
    rprint(f"Bias: {bias_unc.bias}")
    rprint(f"Applied to scalar: {bias_unc.apply(pipe_roughness)}")
    rprint(f"Applied to array: {bias_unc.apply(pipe_diameters)}")

    # 4. Discrete Additive Uncertainty (e.g. count errors)
    rprint("\n[bold green]4. Discrete Additive Uncertainty with DiscreteNormalDistribution[/bold green]")
    
    # Discrete normal distribution for integer counts (mean=0, std=2)
    discrete_normal_dist = DiscreteNormalDistribution(mean=0.0, std_dev=2.0)
    discrete_additive_unc = AdditiveUncertainty(distribution=discrete_normal_dist)
    
    rprint(f"Distribution: {discrete_normal_dist}")
    rprint(f"Applied to scalar (sensor_count={sensor_count}): {discrete_additive_unc.apply(sensor_count)}")
    rprint(f"Applied to array (pipe_counts): {discrete_additive_unc.apply(pipe_counts)}")
    
    # 5. Discrete Multiplicative Uncertainty
    rprint("\n[bold green]5. Discrete Multiplicative Uncertainty with DiscreteUniformDistribution[/bold green]")
    
    # Discrete uniform distribution for integer multipliers (-2 to +2)
    discrete_uniform_dist = DiscreteUniformDistribution(lower=-2, upper=2)
    discrete_mult_unc = MultiplicativeUncertainty(distribution=discrete_uniform_dist)
    
    rprint(f"Distribution: {discrete_uniform_dist}")
    rprint(f"Applied to scalar (sensor_count={sensor_count}): {discrete_mult_unc.apply(sensor_count)}")
    rprint(f"Applied to array (pipe_counts): {discrete_mult_unc.apply(pipe_counts)}")
    
    # 6. Discrete Histogram Uncertainty
    rprint("\n[bold green]6. Discrete Additive Uncertainty with DiscreteHistogramDistribution[/bold green]")
    
    # Histogram distribution for specific count adjustments
    # values: [-3, -1, 0, 1, 3], probabilities: [0.1, 0.2, 0.4, 0.2, 0.1]
    histogram_dist = DiscreteHistogramDistribution(
        values=(-3, -1, 0, 1, 3),
        probabilities=(0.1, 0.2, 0.4, 0.2, 0.1)
    )
    histogram_additive_unc = AdditiveUncertainty(distribution=histogram_dist)
    
    rprint(f"Distribution: {histogram_dist}")
    rprint(f"Applied to scalar (sensor_count={sensor_count}): {histogram_additive_unc.apply(sensor_count)}")
    rprint(f"Applied to array (pipe_counts): {histogram_additive_unc.apply(pipe_counts)}")
    
    # Test with explicit u values for discrete distributions
    rprint("\n[bold]Using explicit u values with discrete distributions:[/bold]")
    u_discrete = [0.1, 0.5, 0.9]
    rprint(f"With u={u_discrete}:")
    rprint(f"  DiscreteNormal: {discrete_additive_unc.apply(pipe_counts, u=u_discrete)}")
    rprint(f"  DiscreteUniform: {discrete_mult_unc.apply(pipe_counts, u=u_discrete)}")
    rprint(f"  Histogram: {histogram_additive_unc.apply(pipe_counts, u=u_discrete)}")

    # 5. Flip Uncertainty (Binary)
    rprint("\n[bold green]7. Flip Uncertainty (Binary)[/bold green]")
    
    flip_unc = BinaryStateFlipUncertainty(flip_prob=0.3, states=("OPEN", "CLOSED"))
    rprint(f"Flip Probability: {flip_unc.flip_prob}")
    rprint(f"Applied to scalar ('OPEN'): {flip_unc.apply(valve_status)}")
    rprint(f"Applied to array: {flip_unc.apply(valve_statuses)}")
    
    # 6. Categorical Random Replacement Uncertainty
    rprint("\n[bold green]8. Categorical Random Replacement Uncertainty[/bold green]")
    categories = ("Low", "Medium", "High")
    cat_dist = CategoricalUniformDistribution(categories=categories)    
    # Randomly replace with a category from the distribution
    cat_random_replace_unc = CategoricalRandomReplacementUncertainty(distribution=cat_dist)
    
    rprint(f"Distribution: {cat_dist}")
    rprint(f"Applied to scalar ('Medium'): {cat_random_replace_unc.apply('Medium')}")
    rprint(f"Applied to array (3 items): {cat_random_replace_unc.apply(['Low', 'Low', 'Low'])}")
    
    # Test with provided u values
    rprint("\n[bold]Using explicit u values:[/bold]")
    u_vals = [0.1, 0.5, 0.9]  # Will map to different categories
    rprint(f"With u={u_vals}: {cat_random_replace_unc.apply(['Low', 'Low', 'Low'], u=u_vals)}")

    # 7. Categorical Replacement Uncertainty (Conditional)
    rprint("\n[bold green]9. Categorical Replacement Uncertainty (Conditional)[/bold green]")
    
    # Use a fixed high probability for demonstration
    high_prob_flip_dist = DiracDeltaDistribution(value=0.8)  # 80% chance to flip
    
    cat_cond_replace_unc = CategoricalReplacementUncertainty(
        flip_distribution=high_prob_flip_dist,
        replacement_distribution=cat_dist
    )
    
    rprint(f"Flip Probability Distribution: {high_prob_flip_dist}")
    rprint(f"Replacement Distribution: {cat_dist}")
    rprint(f"Applied to scalar ('Medium'): {cat_cond_replace_unc.apply('Medium')}")
    rprint(f"Applied to array (5 items): {cat_cond_replace_unc.apply(['Low'] * 5)}")
    
    # Test with explicit u values
    rprint("\n[bold]Using explicit u values:[/bold]")
    u_combined = [0.1, 0.5, 0.9, 0.2, 0.8, 0.3, 0.6, 0.7, 0.4, 0.9]  # 5 for flip + 5 for replacement
    rprint(f"With u={u_combined}: {cat_cond_replace_unc.apply(['Low'] * 5, u=u_combined)}")
    
    # 8. Test with Sobol-like unit samples
    rprint("\n[bold blue]=== Testing with Quasi-Random Samples (Sobol-like) ===[/bold blue]")
    # Simulate what would happen with structured sampling
    sobol_like_samples = np.array([0.00, 0.5, 1.0])
    rprint(f"\nSobol-like unit samples: {sobol_like_samples}")
    rprint(f"Applied to additive uncertainty: {additive_unc.apply(pipe_diameters, u=sobol_like_samples)}")
    rprint(f"Applied to categorical uncertainty: {cat_random_replace_unc.apply(['Low']*3, u=sobol_like_samples)}")

if __name__ == "__main__":
    main()
