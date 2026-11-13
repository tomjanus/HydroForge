from rich import print as rprint
from SALib.sample import sobol
from hydroforge.uncertainty.distributions import (
    NormalDistribution,
    UniformDistribution,
    DiracDeltaDistribution,
    DiscreteNormalDistribution,
    DiscreteHistogramDistribution,
    DiscreteUniformDistribution,
    CategoricalUniformDistribution,
    CategoricalHistogramDistribution,
    CategoricalNormalDistribution,
    DistributionChecker,
)


def main() -> None:
    # Demonstration of Distribution classes
    rprint("[bold blue]=== Distribution Classes Demonstration ===[/bold blue]")

    # 1. Continuous Distributions
    rprint("\n[bold green]1. Continuous Distributions[/bold green]")

    # Normal Distribution
    normal_dist = NormalDistribution(mean=10.0, std_dev=2.0)
    rprint(f"Normal Distribution: {normal_dist}")
    rprint(f"Nominal Value: {normal_dist.nominal_value}")
    rprint(f"Single Sample: {normal_dist.sample(1)}")
    rprint(f"Multiple Samples (5): {normal_dist.sample(5)}")

    # Uniform Distribution
    uniform_dist = UniformDistribution(lower=0.0, upper=10.0)
    rprint(f"\nUniform Distribution: {uniform_dist}")
    rprint(f"Nominal Value: {uniform_dist.nominal_value}")
    rprint(f"Multiple Samples (5): {uniform_dist.sample(5)}")

    # Dirac Delta Distribution
    dirac_dist = DiracDeltaDistribution(value=42.0)
    rprint(f"\nDirac Delta Distribution: {dirac_dist}")
    rprint(f"Nominal Value: {dirac_dist.nominal_value}")
    rprint(f"Multiple Samples (5): {dirac_dist.sample(5)}")

    # 2. Discrete Distributions
    rprint("\n[bold green]2. Discrete Distributions[/bold green]")

    # Discrete Normal
    disc_normal = DiscreteNormalDistribution(mean=5, std_dev=1.5)
    rprint(f"Discrete Normal: {disc_normal}")
    rprint(f"Nominal Value: {disc_normal.nominal_value}")
    rprint(f"Samples (5): {disc_normal.sample(5)}")

    dirac_disc_normal = disc_normal.reduce()
    rprint(f"Reduced to Dirac Delta: {dirac_disc_normal}")
    sample_dirac = dirac_disc_normal.sample(5)
    rprint(f"Samples from Dirac Delta: {sample_dirac}")

    # Discrete Histogram
    hist_values = (1.0, 2.5, 5.0)
    hist_probs = (0.2, 0.5, 0.3)
    disc_hist = DiscreteHistogramDistribution(
        values=hist_values, probabilities=hist_probs
    )
    rprint(f"\nDiscrete Histogram: {disc_hist}")
    rprint(f"Nominal Value: {disc_hist.nominal_value}")
    rprint(f"Samples (10): {disc_hist.sample(10)}")

    # 3. Categorical Distributions
    rprint("\n[bold green]3. Categorical Distributions[/bold green]")

    categories = ("Low", "Medium", "High", "Very High")

    # Categorical Uniform
    cat_uniform = CategoricalUniformDistribution(
        categories=categories, nominal_category="High"
    )
    rprint(f"Categorical Uniform: {cat_uniform}")
    rprint(f"Nominal Value: {cat_uniform.nominal_value}")
    rprint(f"Samples (5): {cat_uniform.sample(5)}")
    rprint(f"Nominal Index: {cat_uniform.nominal_index}")

    # Categorical Histogram
    cat_probs = (0.1, 0.3, 0.2, 0.4)
    cat_hist = CategoricalHistogramDistribution(
        categories=categories, probabilities=cat_probs
    )
    rprint(f"\nCategorical Histogram: {cat_hist}")
    rprint(f"Nominal Value: {cat_hist.nominal_value}")
    rprint(f"Samples (10): {cat_hist.sample(10)}")
    rprint(f"Nominal Index: {cat_hist.nominal_index}")

    # Categorical Normal (centered around 'Medium')
    cat_normal = CategoricalNormalDistribution(
        categories=categories, spread=1.5, nominal_category="High"
    )
    rprint(f"\nCategorical Normal: {cat_normal}")
    rprint(f"Nominal Value: {cat_normal.nominal_value}")
    rprint(f"Samples (10): {cat_normal.sample(10)}")
    rprint(f"Nominal Index: {cat_normal.nominal_index}")

    # 4. Helper Functions
    rprint("\n[bold green]4. Helper Functions[/bold green]")
    rprint(f"Is Normal Continuous? {DistributionChecker.is_continuous(normal_dist)}")
    rprint(
        f"Is Discrete Normal Discrete? {DistributionChecker.is_discrete(disc_normal)}"
    )
    rprint(
        f"Is Categorical Uniform Categorical? {DistributionChecker.is_categorical(cat_uniform)}"
    )
    rprint(f"Is Uniform Bounded? {DistributionChecker.is_bounded(uniform_dist)}")

    # sample_from_unit demonstration and integration with sampling methodologies like LHS and Sobol
    # Define a problem for SALib to generate samples in the unit interval
    problem = {"num_vars": 1, "names": ["u"], "bounds": [[0, 1]]}

    # Generate 8 Sobol samples
    unit_samples = sobol.sample(problem, 8).flatten()
    rprint(f"\n[bold]Generated Sobol unit samples:[/bold]\n{unit_samples}")

    # --- Test with Continuous Distribution ---
    rprint("\n[bold green]1. Continuous (Normal) Distribution[/bold green]")
    rprint(f"Using: {normal_dist}")
    continuous_samples = normal_dist.sample_from_unit(unit_samples)
    rprint(f"Transformed samples:\n{[f'{s:.2f}' for s in continuous_samples]}")

    # --- Test with Discrete Distribution ---
    rprint("\n[bold green]2. Discrete (Uniform) Distribution[/bold green]")
    disc_uniform = DiscreteUniformDistribution(lower=100, upper=200)
    rprint(f"Using: {disc_uniform}")
    discrete_samples = disc_uniform.sample_from_unit(unit_samples)
    rprint(f"Transformed samples:\n{discrete_samples}")

    # --- Test with Categorical Distribution ---
    rprint("\n[bold green]3. Categorical (Histogram) Distribution[/bold green]")
    rprint(f"Using: {cat_hist}")
    categorical_samples = cat_hist.sample_from_unit(unit_samples)
    rprint(f"Transformed samples:\n{categorical_samples}")


if __name__ == "__main__":
    main()
