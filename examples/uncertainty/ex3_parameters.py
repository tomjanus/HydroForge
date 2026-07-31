""" """
import numpy as np
from rich import print as rprint
from hydroforge.uncertainty.distributions import (
    NormalDistribution,
    UniformDistribution,
    CategoricalUniformDistribution,
    DiscreteUniformDistribution
)
from hydroforge.uncertainty.uncertainties import (
    AdditiveUncertainty,
    MultiplicativeUncertainty,
    CategoricalRandomReplacementUncertainty,
    BinaryStateFlipUncertainty
)
from hydroforge.uncertainty.parameters import Parameter, ParameterType

def main() -> None:
    """ """
    rprint("[bold blue]=== Parameter Class Demonstration ===[/bold blue]")

    # 1. Numeric Parameter with Additive Uncertainty
    rprint("\n[bold green]1. Numeric Parameter (Additive Uncertainty)[/bold green]")
    
    normal_dist = NormalDistribution(mean=0.0, std_dev=0.1)
    add_unc = AdditiveUncertainty(distribution=normal_dist)
    
    p_num_add = Parameter(
        name="Pipe Diameter",
        nominal_value=100.0,
        uncertainty=add_unc,
        type=ParameterType.NUMERICAL,
        metadata={"unit": "mm", "material": "PVC"}
    )
    
    rprint(f"Parameter: {p_num_add}")
    rprint(f"Metadata: {p_num_add.metadata}")
    rprint(f"Nominal Value: {p_num_add.nominal()}")
    
    # Sampling behavior (Locking)
    s1 = p_num_add.sample()
    s2 = p_num_add.sample()
    rprint(f"Sample 1: {s1:.4f}")
    rprint(f"Sample 2 (locked): {s2:.4f}")
    
    p_num_add.reset()
    s3 = p_num_add.sample()
    rprint(f"Sample 3 (reset): {s3:.4f}")
    
    # Float conversion
    rprint(f"Float conversion: {float(p_num_add):.4f}")

    # 2. Numeric Parameter with Multiplicative Uncertainty
    rprint("\n[bold green]2. Numeric Parameter (Multiplicative Uncertainty)[/bold green]")
    
    uniform_dist = UniformDistribution(lower=-0.1, upper=0.1) # +/- 10%
    mult_unc = MultiplicativeUncertainty(distribution=uniform_dist)
    
    p_num_mult = Parameter(
        name="Roughness",
        nominal_value=100.0,
        uncertainty=mult_unc,
        type=ParameterType.NUMERICAL
    )
    
    rprint(f"Parameter: {p_num_mult}")
    rprint(f"Sampled (approx 90-110): {p_num_mult.sample():.4f}")

    # 3. Discrete Parameter
    rprint("\n[bold green]3. Discrete Parameter (Integer constraints)[/bold green]")
    
    disc_dist = DiscreteUniformDistribution(lower=-2, upper=2)
    add_unc_disc = AdditiveUncertainty(distribution=disc_dist)
    
    p_disc = Parameter(
        name="Pump Count",
        nominal_value=5,
        uncertainty=add_unc_disc,
        type=ParameterType.DISCRETE
    )
    
    rprint(f"Parameter: {p_disc}")
    rprint(f"Sampled: {p_disc.sample()}")
    
    # Allowed arithmetic
    p_disc.reset()
    rprint(f"Multiplication by int (5 * 2): {p_disc * 2}")
    
    # Disallowed arithmetic
    try:
        rprint(f"Division (5 / 2): {p_disc / 2}")
    except TypeError as e:
        rprint(f"[red]Expected Error on Division:[/red] {e}")
        
    try:
        rprint(f"Multiplication by float (5 * 2.5): {p_disc * 2.5}")
    except TypeError as e:
        rprint(f"[red]Expected Error on Float Mult:[/red] {e}")

    # 4. Arithmetic Operations & NumPy
    rprint("\n[bold green]4. Arithmetic Operations & NumPy[/bold green]")
    
    p_len = Parameter(
        name="Length",
        nominal_value=50.0,
        uncertainty=AdditiveUncertainty(distribution=NormalDistribution(0, 1)),
        type=ParameterType.NUMERICAL
    )
    
    p_num_add.reset()
    p_len.reset()
    
    sum_p = p_num_add + p_len
    rprint(f"Sum ({p_num_add.name} + {p_len.name}): {sum_p:.4f}")
    
    arr_p = np.array([p_num_add, p_len])
    rprint(f"NumPy Array (sampled): {arr_p}")
    rprint(f"Mean: {np.mean([p_num_add, p_len]):.4f}")

    # 2. Arithmetic Operations 2
    rprint("\n[bold green]2. Arithmetic Operations (2)[/bold green]")

    p1 = Parameter(
        name="Pipe Diameter",
        nominal_value=100.0,
        uncertainty=add_unc,
        type=ParameterType.NUMERICAL
    )
    p1.reset()
        
    p2 = Parameter(
        name="Length",
        nominal_value=50.0,
        uncertainty=AdditiveUncertainty(distribution=NormalDistribution(0, 1)),
        type=ParameterType.NUMERICAL
    )
    
    # Reset both to ensure fresh samples
    p1.reset()
    p2.reset()
    
    # Operations
    sum_p = p1 + p2
    prod_p = p1 * 2
    
    rprint(f"p1 ({p1.sample():.2f}) + p2 ({p2.sample():.2f}) = {sum_p:.2f}")
    rprint(f"p1 ({p1.sample():.2f}) * 2 = {prod_p:.2f}")
    
    # Numpy compatibility
    arr_p = np.array([p1, p2])
    rprint(f"NumPy Array of Parameters (sampled): {arr_p}")
    rprint(f"Mean of Parameters: {np.mean([p1, p2]):.2f}")

    # 5. Categorical Parameter
    rprint("\n[bold green]5. Categorical Parameter[/bold green]")
    
    categories = ("Steel", "PVC", "Iron")
    cat_dist = CategoricalUniformDistribution(categories=categories)
    cat_unc = CategoricalRandomReplacementUncertainty(distribution=cat_dist)
    
    p_cat = Parameter(
        name="Material",
        nominal_value="Steel",
        uncertainty=cat_unc,
        type=ParameterType.CATEGORICAL
    )
    
    rprint(f"Parameter: {p_cat}")
    rprint(f"Sampled: {p_cat.sample()}")
    
    try:
        p_cat + 1
    except TypeError as e:
        rprint(f"[red]Expected Error on Arithmetic:[/red] {e}")

    # 6. Binary Parameter
    rprint("\n[bold green]6. Binary Parameter[/bold green]")
    
    flip_unc = BinaryStateFlipUncertainty(flip_prob=0.5, states=("OPEN", "CLOSED"))
    p_bin = Parameter(
        name="Valve Status",
        nominal_value="OPEN",
        uncertainty=flip_unc,
        type=ParameterType.CATEGORICAL
    )
    
    rprint(f"Parameter: {p_bin}")
    samples = []
    for _ in range(10):
        p_bin.reset()
        samples.append(p_bin.sample())
    rprint(f"10 Samples (50% flip chance): {samples}")
    
    
if __name__ == "__main__":
    main()
