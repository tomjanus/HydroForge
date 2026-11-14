"""Sampling strategies for uncertainty quantification.

This module provides various sampling strategies for generating scenarios
from uncertain parameters, including:

- Monte Carlo (MC): Random sampling
- Latin Hypercube Sampling (LHS): Stratified sampling
- Sobol sequences: Quasi-random low-discrepancy sequences
- Halton sequences: Alternative quasi-random sequences
- Conditional/Hierarchical Monte Carlo: Sequential sampling with dependencies
- Nested Monte Carlo: Inner-outer sampling for multilevel uncertainty
- Stratified sampling: Layered sampling with controlled coverage
- `GibbsSampler`: legacy independent marginal resampling; not MCMC
- Scenario trees: Discretized branching for decision analysis
- Mixed strategies: Different sampling methods for different parameter groups
"""

from typing import Protocol, Any, Mapping, Optional, Sequence, Callable, cast
from typing import Generator
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid
import hashlib
import json
import numpy as np
from SALib.sample import sobol as salib_sobol
from SALib.sample import latin as salib_latin
from ..uncertainty.parameters import Parameter


class SamplingStrategy(Enum):
    """Enumeration of available sampling strategies."""

    MONTE_CARLO = auto()
    LATIN_HYPERCUBE = auto()
    SOBOL = auto()
    HALTON = auto()
    MIXED = auto()
    CONDITIONAL_MC = auto()
    NESTED_MC = auto()
    STRATIFIED = auto()
    GIBBS = auto()
    SCENARIO_TREE = auto()


class IDGenerator(Protocol):
    """Protocol for unique ID generators."""

    def generate(self) -> str:
        """Generate a new unique ID."""


@dataclass
class UUIDGenerator:
    """Generates unique scenario IDs."""

    prefix: str = "scenario"

    def generate(self) -> str:
        """Generate a new unique ID."""
        return f"{self.prefix}-{uuid.uuid4().hex}"


@dataclass
class DeterministicHashGenerator:
    """Generates unique scenario IDs based on parameter values."""

    scenario: Mapping[str, Any]
    prefix: str = "scenario"
    hash_len: int = 10

    def __post_init__(self):
        if self.scenario is None:
            raise ValueError(f"scenario must be provided for {self.__class__.__name__}")

    def generate(self) -> str:
        """Generate a new unique ID based on parameter values."""
        # Serialize the values to a JSON string with sorted keys
        payload = json.dumps(
            self.scenario,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{self.prefix}-{digest[:self.hash_len]}"


@dataclass(frozen=True)
class Scenario:
    """One sampled realization of all parameters."""

    values: dict[str, Any]  # parameter name → sampled value
    id: str  # scenario id
    metadata: dict[str, Any] | None = field(default=None)


# ================================================================
#  Base Sampler Class
# ================================================================


class Sampler(ABC):
    """Base class for all sampling strategies.

    Provides an interface for sampling scenarios given a set of parameters.
    Each sampling strategy must implement the `generate` method.

    Attributes:
        parameters: List of Parameter objects to sample from
        id_generator: Strategy for generating scenario IDs (can be an instance or class)

    Raises:
        ValueError: If parameters list is empty in subclass methods
    """

    def __init__(
        self,
        parameters: Parameter | Sequence[Parameter],
        id_generator: IDGenerator | type[IDGenerator] | None = None,
    ):
        if isinstance(parameters, Parameter):
            self.parameters = [parameters]
        else:
            self.parameters = list(parameters)
        self.id_generator = id_generator or UUIDGenerator()

        if not self.parameters:
            warnings.warn("Sampler initialized with empty parameter list", UserWarning)

    @abstractmethod
    def generate(self, n: int) -> Generator[Scenario, None, None]:
        """Generate n scenarios.

        Args:
            n: Number of scenarios to generate

        Yields:
            Scenario objects with sampled parameter values
        """

    def _reset_parameters(self):
        """Reset all parameters to allow new sampling."""
        for p in self.parameters:
            p.reset()

    def _create_scenario_id(self, scenario_values: dict[str, Any]) -> str:
        """Create a scenario ID using the configured ID generator.

        Args:
            scenario_values: Dictionary of parameter names to values

        Returns:
            Generated scenario ID string
        """
        if isinstance(self.id_generator, type):
            if issubclass(self.id_generator, DeterministicHashGenerator):
                id_gen: Any = self.id_generator(scenario=scenario_values)
            else:
                id_gen = self.id_generator()
            return id_gen.generate()
        return self.id_generator.generate()


# ================================================================
#  Monte Carlo Sampler
# ================================================================


class MonteCarloSampler(Sampler):
    """Monte Carlo sampling strategy using random sampling.

    This is the simplest sampling strategy where each parameter is sampled
    independently using its own distribution with random u values.
    """

    def generate(self, n: int) -> Generator[Scenario, None, None]:
        """Generate n scenarios using Monte Carlo sampling."""
        if n <= 0:
            raise ValueError(f"Number of samples must be positive, got {n}")

        for _ in range(n):
            self._reset_parameters()
            scenario_values = {p.name: p.sample() for p in self.parameters}
            scenario_id = self._create_scenario_id(scenario_values)
            yield Scenario(values=scenario_values, id=scenario_id)


# ================================================================
#  Latin Hypercube Sampler
# ================================================================


class LatinHypercubeSampler(Sampler):
    """Latin Hypercube Sampling (LHS) strategy.

    LHS ensures better space-filling properties by dividing the sample space
    into equally probable intervals and sampling once from each interval.
    """

    def generate(self, n: int) -> Generator[Scenario, None, None]:
        """Generate n scenarios using Latin Hypercube Sampling."""
        if n <= 0:
            raise ValueError(f"Number of samples must be positive, got {n}")

        n_params = len(self.parameters)
        if n_params == 0:
            raise ValueError("No parameters provided for sampling")

        # Generate LHS samples in [0, 1]^d space
        problem = {
            "num_vars": n_params,
            "names": [p.name for p in self.parameters],
            "bounds": [[0, 1]] * n_params,
        }

        # SALib's latin.sample returns shape (n, n_params)
        unit_samples = salib_latin.sample(problem, n)

        # Convert unit samples to parameter values
        for i in range(n):
            self._reset_parameters()
            scenario_values: dict[str, Any] = {}
            for j, param in enumerate(self.parameters):
                u = unit_samples[i, j]
                scenario_values[param.name] = param.sample_from_unit(u)

            scenario_id = self._create_scenario_id(scenario_values)
            yield Scenario(values=scenario_values, id=scenario_id)


# ================================================================
#  Sobol Sampler
# ================================================================


class SobolSampler(Sampler):
    """Sobol sequence sampler for quasi-random low-discrepancy sampling.

    Sobol sequences provide better coverage of the parameter space than
    random sampling, especially for sensitivity analysis.

    Attributes:
        calc_second_order: If True, generate samples for second-order indices
        skip_values: Number of initial sequence values to skip (improves quality)
    """

    def __init__(
        self,
        parameters: Sequence[Parameter],
        id_generator: IDGenerator | type[IDGenerator] | None = None,
        calc_second_order: bool = False,
        skip_values: int = 0,
    ):
        super().__init__(parameters, id_generator)
        if not parameters:
            raise ValueError("SobolSampler requires at least one parameter")
        self.calc_second_order = calc_second_order
        self.skip_values = skip_values

    def generate(self, n: int) -> Generator[Scenario, None, None]:
        """Generate n scenarios using Sobol sequences."""
        if n <= 0:
            raise ValueError(f"Number of samples must be positive, got {n}")

        n_params = len(self.parameters)
        if n_params == 0:
            raise ValueError("No parameters provided for sampling")

        # Generate Sobol samples in [0, 1]^d space
        problem = {
            "num_vars": n_params,
            "names": [p.name for p in self.parameters],
            "bounds": [[0, 1]] * n_params,
        }

        # SALib's sobol.sample returns shape (n, n_params)
        unit_samples = salib_sobol.sample(
            problem,
            n,
            calc_second_order=self.calc_second_order,
            skip_values=self.skip_values,
        )

        # Convert unit samples to parameter values
        for i in range(n):
            self._reset_parameters()
            scenario_values: dict[str, Any] = {}
            for j, param in enumerate(self.parameters):
                u = unit_samples[i, j]
                scenario_values[param.name] = param.sample_from_unit(u)

            scenario_id = self._create_scenario_id(scenario_values)
            yield Scenario(values=scenario_values, id=scenario_id)


# ================================================================
#  Halton Sampler
# ================================================================


class HaltonSampler(Sampler):
    """Halton sequence sampler for quasi-random sampling.

    Halton sequences are another type of low-discrepancy sequence,
    often used as an alternative to Sobol sequences.

    Attributes:
        skip_values: Number of initial sequence values to skip
        primes: List of prime numbers to use as bases (one per parameter)
    """

    def __init__(
        self,
        parameters: Sequence[Parameter],
        id_generator: IDGenerator | type[IDGenerator] | None = None,
        skip_values: int = 0,
        primes: Optional[Sequence[int]] = None,
    ):
        super().__init__(parameters, id_generator)
        if not parameters:
            raise ValueError("HaltonSampler requires at least one parameter")
        self.skip_values = skip_values
        # Use default primes if not provided
        default_primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
        self.primes = primes or default_primes[: len(parameters)]

        if len(self.primes) < len(parameters):
            raise ValueError(
                f"Need at least {len(parameters)} primes for Halton sequence, "
                f"but only {len(self.primes)} provided"
            )

    def _halton_sequence(self, index: int, base: int) -> float:
        """Generate a single value from Halton sequence."""
        result = 0.0
        f = 1.0 / base
        i = index
        while i > 0:
            result += f * (i % base)
            i //= base
            f /= base
        return result

    def generate(self, n: int) -> Generator[Scenario, None, None]:
        """Generate n scenarios using Halton sequences."""
        if n <= 0:
            raise ValueError(f"Number of samples must be positive, got {n}")

        for i in range(self.skip_values, self.skip_values + n):
            self._reset_parameters()
            scenario_values: dict[str, Any] = {}

            for j, param in enumerate(self.parameters):
                u = self._halton_sequence(i, self.primes[j])
                scenario_values[param.name] = param.sample_from_unit(u)

            scenario_id = self._create_scenario_id(scenario_values)
            yield Scenario(values=scenario_values, id=scenario_id)


# ================================================================
#  Conditional/Hierarchical Monte Carlo Sampler
# ================================================================


@dataclass
class ConditionalLayer:
    """Defines a layer in conditional/hierarchical sampling.

    Attributes:
        parameters: Parameters to sample in this layer
        condition_func: Optional function to compute values based on previous layers
                       Signature: condition_func(previous_values: dict) -> dict
                       Returns dict mapping parameter names to conditional values
    """

    parameters: Sequence[Parameter]
    condition_func: Optional[Callable[[dict], dict]] = None


class ConditionalMonteCarloSampler(Sampler):
    """Conditional/Hierarchical Monte Carlo sampling.

    Samples parameters in layers where later layers can depend on earlier ones.
    This implements p(X₁)p(X₂|X₁)p(X₃|X₁,X₂)...

    Example:
        # Layer 1: Sample climate regime
        # Layer 2: Sample temperature conditional on regime
        # Layer 3: Sample demand conditional on temperature

    Attributes:
        layers: Ordered sequence of ConditionalLayer objects
    """

    def __init__(
        self,
        layers: Sequence[ConditionalLayer],
        id_generator: IDGenerator | type[IDGenerator] | None = None,
    ):
        # Collect all parameters from all layers
        all_parameters: list[Parameter] = []
        for layer in layers:
            all_parameters.extend(layer.parameters)

        if not all_parameters:
            raise ValueError(
                "ConditionalMonteCarloSampler requires at least one parameter across all layers"
            )

        super().__init__(all_parameters, id_generator)
        self.layers = list(layers)

    def generate(self, n: int) -> Generator[Scenario, None, None]:
        """Generate n scenarios using conditional sampling."""
        if n <= 0:
            raise ValueError(f"Number of samples must be positive, got {n}")

        for _ in range(n):
            self._reset_parameters()
            scenario_values: dict[str, Any] = {}

            # Sample layer by layer
            for layer in self.layers:
                # Apply conditioning if provided
                if layer.condition_func is not None:
                    conditional_values = layer.condition_func(scenario_values)
                    # Update nominal values or apply transformations
                    for param in layer.parameters:
                        if param.name in conditional_values:
                            # Store the conditional value
                            scenario_values[param.name] = conditional_values[param.name]
                            continue

                # Sample parameters in this layer
                for param in layer.parameters:
                    if param.name not in scenario_values:
                        scenario_values[param.name] = param.sample()

            scenario_id = self._create_scenario_id(scenario_values)
            yield Scenario(values=scenario_values, id=scenario_id)


# ================================================================
#  Nested Monte Carlo Sampler
# ================================================================


@dataclass
class NestedSamplingSpec:
    """Specification for nested (inner-outer) sampling.

    Attributes:
        outer_parameters: Parameters for outer loop (macro-level uncertainties)
        inner_parameters: Parameters for inner loop (conditional uncertainties)
        n_inner: Number of inner samples per outer sample
        inner_sampler_class: Sampler class for inner loop (default: MonteCarloSampler)
        inner_sampler_kwargs: Additional kwargs for inner sampler
    """

    outer_parameters: Sequence[Parameter]
    inner_parameters: Sequence[Parameter]
    n_inner: int = 10
    inner_sampler_class: type[Sampler] | None = None
    inner_sampler_kwargs: dict[str, Any] = field(default_factory=dict)


class NestedMonteCarloSampler(Sampler):
    """Nested Monte Carlo sampling (inner-outer sampling).

    Useful for evaluating E_X[E_{Y|X}[f(X,Y)]]:
    - Outer loop: sample macro-level uncertainties (e.g., climate scenarios)
    - Inner loop: sample conditional uncertainties (e.g., operational outcomes)

    Each outer sample generates n_inner inner samples.

    Attributes:
        spec: NestedSamplingSpec defining the nested structure
    """

    def __init__(
        self,
        spec: NestedSamplingSpec,
        id_generator: IDGenerator | type[IDGenerator] | None = None,
    ):
        all_parameters = list(spec.outer_parameters) + list(spec.inner_parameters)
        super().__init__(all_parameters, id_generator)
        self.spec = spec

        # Set default inner sampler
        if spec.inner_sampler_class is None:
            self.spec.inner_sampler_class = MonteCarloSampler

        # Validate n_inner
        if spec.n_inner <= 0:
            raise ValueError(f"n_inner must be positive, got {spec.n_inner}")

    def generate(self, n: int) -> Generator[Scenario, None, None]:
        """Generate scenarios using nested sampling.

        Args:
            n: Number of outer loop samples

        Yields:
            Scenarios with metadata indicating outer/inner indices
        """
        if n <= 0:
            raise ValueError(f"Number of outer samples must be positive, got {n}")

        for outer_idx in range(n):
            # Sample outer parameters
            self._reset_parameters()
            outer_values = {}
            for param in self.spec.outer_parameters:
                param.reset()
                outer_values[param.name] = param.sample()

            # Create inner sampler
            inner_sampler = cast(type[Sampler], self.spec.inner_sampler_class)(
                self.spec.inner_parameters,
                id_generator=None,
                **self.spec.inner_sampler_kwargs,
            )

            # Generate inner samples
            for inner_idx, inner_scenario in enumerate(
                inner_sampler.generate(self.spec.n_inner)
            ):
                # Combine outer and inner values
                combined_values = {**outer_values, **inner_scenario.values}

                # Create scenario with nested structure metadata
                scenario_id = self._create_scenario_id(combined_values)
                metadata = {
                    "outer_index": outer_idx,
                    "inner_index": inner_idx,
                    "outer_values": outer_values,
                    "inner_values": inner_scenario.values,
                }

                yield Scenario(
                    values=combined_values,
                    id=f"{scenario_id}-o{outer_idx}-i{inner_idx}",
                    metadata=metadata,
                )


# ================================================================
#  Stratified Sampler
# ================================================================


@dataclass(frozen=True)
class Stratum:
    """Definition of a stratum in the parameter space.

    A stratum defines a region of the parameter space from which scenarios are
    sampled. Bounds are interpreted as value-space bounds and sampling within a
    bounded parameter is performed from the parameter's conditional distribution
    within those bounds.

    Parameters
    ----------
    name
        Unique name identifying the stratum.
    bounds
        Mapping from parameter names to ``(lower, upper)`` bounds.
        Parameters not included in ``bounds`` retain their original distribution.
    weight
        Relative probability assigned to the stratum when ``n_samples`` is not
        specified. Weights are normalized across all weighted strata.
    n_samples
        Fixed number of samples to generate from the stratum. If specified,
        ``weight`` is ignored for sample allocation.

    Notes
    -----
    For a parameter ``X`` with CDF ``F`` and stratum bounds ``(L, U)``, sampling is performed according to
    .. math:: X \\mid L \\leq X \\leq U
    using the transformation
    .. math:: X = F^{-1}\\left[ F(L) + u\\{F(U)-F(L)\\} \\right],
    where ``u ~ Uniform(0, 1)``. This preserves the original parameter distribution conditional
    on the stratum rather than replacing it with a uniform distribution.
    """

    name: str
    bounds: dict[str, tuple[float, float]]
    weight: float = 1.0
    n_samples: Optional[int] = None


def __post_init__(self) -> None:
    """Validate the stratum definition."""
    if not self.name:
        raise ValueError("Stratum name must not be empty.")
    if self.weight < 0:
        raise ValueError(
            f"Stratum '{self.name}' has negative weight: " f"{self.weight}."
        )
    if self.n_samples is not None and self.n_samples < 0:
        raise ValueError(
            f"Stratum '{self.name}' has negative n_samples: " f"{self.n_samples}."
        )
    for parameter_name, bounds in self.bounds.items():
        if len(bounds) != 2:
            raise ValueError(
                f"Bounds for parameter '{parameter_name}' in stratum "
                f"'{self.name}' must contain exactly two values."
            )
        lower, upper = bounds
        if not np.isfinite(lower) or not np.isfinite(upper):
            raise ValueError(
                f"Bounds for parameter '{parameter_name}' in stratum "
                f"'{self.name}' must be finite."
            )
        if lower > upper:
            raise ValueError(
                f"Invalid bounds for parameter '{parameter_name}' "
                f"in stratum '{self.name}': "
                f"lower={lower} > upper={upper}."
            )


class StratifiedSampler(Sampler):
    """Generate scenarios using stratified sampling.

    The parameter space is divided into user-defined strata. Samples are
    generated independently within each stratum, with sample allocation
    controlled either by fixed sample counts or relative stratum weights.

    Parameters
    ----------
    parameters
        Parameters to sample.
    strata
        Sequence of :class:`Stratum` definitions.
    base_sampler_class
        Sampler used to generate the underlying unit-space design. The
        default is :class:`MonteCarloSampler`.
    id_generator
        Generator used to create scenario identifiers.

    Notes
    -----
    A stratum does not simply clip or rescale samples produced by the base
    sampler. For bounded parameters, the original parameter distribution is
    conditioned on the specified bounds.

    Parameters not explicitly bounded by a stratum are sampled according to
    their original distributions.

    Examples
    --------
    >>> strata = [
    ...     Stratum(
    ...         name="low",
    ...         bounds={"flow": (0.0, 30.0)},
    ...         weight=0.2,
    ...     ),
    ...     Stratum(
    ...         name="normal",
    ...         bounds={"flow": (30.0, 70.0)},
    ...         weight=0.6,
    ...     ),
    ...     Stratum(
    ...         name="peak",
    ...         bounds={"flow": (70.0, 100.0)},
    ...         weight=0.2,
    ...     ),
    ... ]

    >>> sampler = StratifiedSampler(parameters, strata)
    >>> scenarios = list(sampler.generate(100))
    """

    def __init__(
        self,
        parameters: Sequence[Parameter],
        strata: Sequence[Stratum],
        base_sampler_class: type[Sampler] | None = None,
        id_generator: IDGenerator | type[IDGenerator] | None = None,
    ) -> None:
        super().__init__(parameters, id_generator)
        if not strata:
            raise ValueError("StratifiedSampler requires at least one stratum.")
        self.strata = list(strata)
        self.base_sampler_class = base_sampler_class or MonteCarloSampler
        self._validate_strata()

    def _validate_strata(self) -> None:
        """Validate the collection of strata and check CDF availability.

        Raises
        ------
        ValueError
            If stratum names are not unique, if strata reference unknown parameters,
            if weights are invalid, or if stratified sampling is impossible.
        CDFNotAvailable
            If a parameter used in stratum bounds does not support CDF evaluation.
        """
        from hydroforge.uncertainty.common import CDFNotAvailable

        names = [stratum.name for stratum in self.strata]

        if len(names) != len(set(names)):
            raise ValueError("Stratum names must be unique.")

        parameter_names = {parameter.name for parameter in self.parameters}

        for stratum in self.strata:
            unknown_parameters = set(stratum.bounds) - parameter_names

            if unknown_parameters:
                names_str = ", ".join(sorted(unknown_parameters))
                raise ValueError(
                    f"Stratum '{stratum.name}' defines bounds for unknown "
                    f"parameter(s): {names_str}."
                )

            # Check that bounded parameters support CDF evaluation
            for param_name in stratum.bounds:
                param = next(p for p in self.parameters if p.name == param_name)
                try:
                    # Test CDF with a sample value to check availability
                    param.cdf(param.nominal_value)
                except CDFNotAvailable as e:
                    raise CDFNotAvailable(
                        f"Cannot use stratified sampling with parameter '{param_name}': {str(e)}"
                    ) from e

        weighted_strata = [
            stratum for stratum in self.strata if stratum.n_samples is None
        ]

        if weighted_strata:
            total_weight = sum(stratum.weight for stratum in weighted_strata)

            if total_weight <= 0:
                raise ValueError(
                    "The total weight of strata without fixed sample counts "
                    "must be greater than zero."
                )

    def _allocate_samples(self, n: int) -> dict[str, int]:
        """Allocate ``n`` samples among the strata.

        Fixed ``n_samples`` values are allocated first. Remaining samples are
        allocated proportionally to the weights using the largest-remainder
        method so that the final allocation sums exactly to ``n``.
        """
        allocation = {stratum.name: 0 for stratum in self.strata}

        fixed_total = sum(
            stratum.n_samples
            for stratum in self.strata
            if stratum.n_samples is not None
        )

        if fixed_total > n:
            raise ValueError(
                "The sum of fixed stratum sample counts "
                f"({fixed_total}) exceeds the requested number "
                f"of samples ({n})."
            )

        for stratum in self.strata:
            if stratum.n_samples is not None:
                allocation[stratum.name] = stratum.n_samples

        remaining = n - fixed_total

        weighted_strata = [
            stratum for stratum in self.strata if stratum.n_samples is None
        ]

        if not weighted_strata or remaining == 0:
            return allocation

        total_weight = sum(stratum.weight for stratum in weighted_strata)

        if total_weight <= 0:
            raise ValueError(
                "The total weight of weighted strata must be greater " "than zero."
            )

        # Compute ideal allocations.
        ideal = {
            stratum.name: (remaining * stratum.weight / total_weight)
            for stratum in weighted_strata
        }

        # Allocate integer parts first.
        for stratum in weighted_strata:
            allocation[stratum.name] = int(np.floor(ideal[stratum.name]))

        # Distribute the remaining samples according to largest remainders.
        allocated = sum(allocation[stratum.name] for stratum in weighted_strata)

        remainder = remaining - allocated

        ranked = sorted(
            weighted_strata,
            key=lambda stratum: (ideal[stratum.name] - allocation[stratum.name]),
            reverse=True,
        )

        for stratum in ranked[:remainder]:
            allocation[stratum.name] += 1

        return allocation

    @staticmethod
    def _conditional_unit_interval(
        parameter: Parameter,
        lower: float,
        upper: float,
        u: float,
    ) -> float:
        """Map a unit sample to the CDF interval defined by bounds.

        Parameters
        ----------
        parameter
            Parameter whose distribution is being sampled.
        lower, upper
            Bounds defining the stratum.
        u
            Unit-interval sample.

        Returns
        -------
        float
            Unit-interval value corresponding to the conditional
            distribution within ``[lower, upper]``.

        Raises
        ------
        CDFNotAvailable
            If the parameter's CDF cannot be evaluated (e.g., categorical parameters).
        ValueError
            If the CDF values are invalid or the stratum bounds are inconsistent.
        """
        from hydroforge.uncertainty.common import CDFNotAvailable

        try:
            # Evaluate CDF at stratum bounds
            lower_cdf = float(parameter.cdf(lower))
            upper_cdf = float(parameter.cdf(upper))
        except CDFNotAvailable as e:
            raise CDFNotAvailable(
                f"Cannot perform stratified sampling on parameter '{parameter.name}': {str(e)}"
            ) from e

        if not 0.0 <= lower_cdf <= 1.0:
            raise ValueError(
                f"CDF evaluated at lower bound {lower} returned "
                f"{lower_cdf} for parameter '{parameter.name}'. "
                f"CDF values must be in [0, 1]."
            )
        if not 0.0 <= upper_cdf <= 1.0:
            raise ValueError(
                f"CDF evaluated at upper bound {upper} returned "
                f"{upper_cdf} for parameter '{parameter.name}'. "
                f"CDF values must be in [0, 1]."
            )
        if upper_cdf < lower_cdf:
            raise ValueError(
                f"Invalid CDF interval for parameter '{parameter.name}': "
                f"F({lower})={lower_cdf} > F({upper})={upper_cdf}. "
                f"Check that lower < upper and parameter is properly configured."
            )

        return lower_cdf + u * (upper_cdf - lower_cdf)

    def _sample_stratum(
        self, stratum: Stratum, n: int
    ) -> Generator[dict[str, object], None, None]:
        """Generate parameter values for one stratum.

        Samples from the conditional distribution within the stratum bounds.
        For bounded parameters, CDFs are used to map unit-interval samples
        to the conditional distribution.

        Parameters
        ----------
        stratum : Stratum
            Stratum definition with bounds and allocation.
        n : int
            Number of samples to generate from this stratum.

        Yields
        ------
        dict[str, object]
            Parameter values sampled from the stratum.

        Raises
        ------
        CDFNotAvailable
            If a bounded parameter does not support CDF evaluation.
        ValueError
            If parameter bounds are invalid or inconsistent.
        """
        from hydroforge.uncertainty.common import CDFNotAvailable

        if n <= 0:
            return

        # Generate an underlying sample design.
        base_sampler = self.base_sampler_class(
            self.parameters,
            id_generator=None,
        )
        parameter_by_name = {parameter.name: parameter for parameter in self.parameters}

        for scenario in base_sampler.generate(n):
            values = dict(scenario.values)
            for parameter_name, (
                lower,
                upper,
            ) in stratum.bounds.items():
                parameter = parameter_by_name[parameter_name]

                # Obtain a unit-space representation of the existing
                # sample. This requires the base sampler to expose its
                # unit-space values. If it does not, generate the unit
                # values independently below.
                #
                # For Monte Carlo this should ideally come directly from
                # the RNG rather than from an already transformed value.
                if hasattr(scenario, "unit_values"):
                    u = float(scenario.unit_values[parameter_name])
                else:
                    # Fall back to a direct uniform draw. This preserves
                    # the conditional-distribution interpretation, although
                    # it means that the base sampler's design is not used
                    # for bounded parameters.
                    u = float(np.random.random())

                try:
                    conditional_u = self._conditional_unit_interval(
                        parameter,
                        lower,
                        upper,
                        u,
                    )
                except (CDFNotAvailable, ValueError) as e:
                    # Re-raise with additional context
                    raise type(e)(
                        f"Error sampling stratum '{stratum.name}' for parameter '{parameter_name}': {str(e)}"
                    ) from e

                values[parameter_name] = parameter.sample_from_unit(conditional_u)
            yield values

    def generate(self, n: int) -> Generator[Scenario, None, None]:
        """Generate ``n`` scenarios using stratified sampling.

        Parameters
        ----------
        n
            Total number of scenarios to generate.

        Yields
        ------
        Scenario
            Generated scenario with stratum information stored in metadata.

        Raises
        ------
        ValueError
            If ``n`` is not positive or the stratum configuration is invalid.
        """
        if n <= 0:
            raise ValueError(f"Number of samples must be positive, got {n}.")
        allocation = self._allocate_samples(n)

        for stratum in self.strata:
            n_stratum = allocation[stratum.name]
            if n_stratum <= 0:
                continue
            for values in self._sample_stratum(stratum, n_stratum):
                scenario_id = self._create_scenario_id(values)
                yield Scenario(
                    values=values,
                    id=f"{scenario_id}-{stratum.name}",
                    metadata={
                        "stratum": stratum.name,
                    },
                )


# ================================================================
#  Legacy independent resampling (`GibbsSampler`)
# ================================================================


class GibbsSampler(Sampler):
    """Legacy independent marginal resampler with a misleading class name.

    Each parameter is sampled independently from its marginal distribution.
    This implementation does not use conditional distributions and does not
    implement Gibbs sampling or a Markov chain Monte Carlo (MCMC) method.

    Attributes:
        n_burn_in: Number of initial independent draws to discard.
        n_thin: Keep every ``n_thin``-th independent draw.
        initial_values: Initial values accepted for compatibility; they do not
            affect the independent draws.
    """

    def __init__(
        self,
        parameters: Sequence[Parameter],
        id_generator: IDGenerator | type[IDGenerator] | None = None,
        n_burn_in: int = 100,
        n_thin: int = 1,
        initial_values: Optional[dict[str, Any]] = None,
    ):
        super().__init__(parameters, id_generator)
        if n_burn_in < 0:
            raise ValueError(f"n_burn_in must be non-negative, got {n_burn_in}")
        if n_thin <= 0:
            raise ValueError(f"n_thin must be positive, got {n_thin}")
        self.n_burn_in = n_burn_in
        self.n_thin = n_thin
        self.initial_values = initial_values or {}

    def generate(self, n: int) -> Generator[Scenario, None, None]:
        """Generate ``n`` scenarios using independent marginal draws.

        ``n_burn_in`` and ``n_thin`` control how many independent draws are
        discarded. They do not define MCMC burn-in or thinning.
        """
        if n <= 0:
            raise ValueError(f"Number of samples must be positive, got {n}")
        if self.n_thin <= 0:
            raise ValueError(f"Thinning parameter must be positive, got {self.n_thin}")

        # Initialize compatibility state; values do not condition later draws.
        current_values = {}
        for param in self.parameters:
            if param.name in self.initial_values:
                current_values[param.name] = self.initial_values[param.name]
            else:
                # Use nominal value as initial state
                current_values[param.name] = param.nominal_value

        iteration = 0
        samples_generated = 0

        # Total iterations needed

        while samples_generated < n:
            # Draw each parameter independently from its marginal distribution.
            for param in self.parameters:
                param.reset()
                # In a full implementation, we'd pass current_values to inform
                # the conditional distribution. For now, just sample.
                current_values[param.name] = param.sample()

            iteration += 1

            # Skip burn-in period
            if iteration <= self.n_burn_in:
                continue

            # Apply thinning
            if (iteration - self.n_burn_in) % self.n_thin != 0:
                continue

            # Keep this sample
            scenario_id = self._create_scenario_id(current_values)
            metadata = {"iteration": iteration, "chain_position": samples_generated}

            yield Scenario(
                values=current_values.copy(),
                id=f"{scenario_id}-iter{iteration}",
                metadata=metadata,
            )

            samples_generated += 1


# ================================================================
#  Scenario Tree Sampler
# ================================================================


@dataclass
class ScenarioTreeNode:
    """Node in a scenario tree.

    Attributes:
        name: Node identifier
        probability: Probability of this branch (conditional on parent)
        parameter_values: Fixed parameter values at this node
        children: Child nodes (sub-scenarios)
        level: Tree level (0 = root)
    """

    name: str
    probability: float
    parameter_values: dict[str, Any] = field(default_factory=dict)
    children: list["ScenarioTreeNode"] = field(default_factory=list)
    level: int = 0

    def add_child(self, child: "ScenarioTreeNode"):
        """Add a child node."""
        child.level = self.level + 1
        self.children.append(child)

    def get_paths(self) -> list[list["ScenarioTreeNode"]]:
        """Get all paths from this node to leaves."""
        if not self.children:
            return [[self]]

        all_paths = []
        for child in self.children:
            child_paths = child.get_paths()
            for path in child_paths:
                all_paths.append([self] + path)

        return all_paths


class ScenarioTreeSampler(Sampler):
    """Scenario tree sampling for sequential decision problems.

    Discretizes uncertainty into a tree structure where:
    - Each node represents a state/decision point
    - Branches represent alternative scenarios
    - Probabilities are assigned to branches

    Common in:
    - Stochastic programming
    - Energy/water system planning
    - Multi-stage decision analysis

    Attributes:
        root: Root node of the scenario tree
    """

    def __init__(
        self,
        parameters: Sequence[Parameter],
        root: ScenarioTreeNode,
        id_generator: IDGenerator | type[IDGenerator] | None = None,
    ):
        super().__init__(parameters, id_generator)
        if root is None:
            raise ValueError("ScenarioTreeSampler requires a root node")
        self.root = root

    def generate(self, n: Optional[int] = None) -> Generator[Scenario, None, None]:
        """Generate scenarios by traversing tree paths.

        Args:
            n: Optional limit on number of scenarios. If None, generates all paths.

        Yields:
            One scenario per tree path from root to leaf
        """
        if n is not None and n <= 0:
            raise ValueError(f"Number of samples must be positive, got {n}")

        # Get all paths from root to leaves
        paths = self.root.get_paths()

        if not paths:
            raise ValueError(
                "Scenario tree has no paths (tree is empty or has no leaf nodes)"
            )

        # Optionally sample a subset of paths
        if n is not None and n < len(paths):
            # Sample paths based on their probabilities
            path_probs = []
            for path in paths:
                prob = 1.0
                for node in path:
                    prob *= node.probability
                path_probs.append(prob)

            # Normalize probabilities
            total_prob = sum(path_probs)
            path_probs = [p / total_prob for p in path_probs]

            # Sample paths
            indices = np.random.choice(len(paths), size=n, replace=True, p=path_probs)
            paths = [paths[i] for i in indices]

        # Generate scenario for each path
        for path_idx, path in enumerate(paths):
            self._reset_parameters()

            # Combine parameter values along the path
            scenario_values: dict[str, Any] = {}
            path_probability = 1.0
            path_names = []

            for node in path:
                scenario_values.update(node.parameter_values)
                path_probability *= node.probability
                path_names.append(node.name)

            # Sample any parameters not specified in tree
            for param in self.parameters:
                if param.name not in scenario_values:
                    scenario_values[param.name] = param.sample()

            scenario_id = self._create_scenario_id(scenario_values)
            path_str = "->".join(path_names)

            metadata = {
                "path": path_str,
                "path_probability": path_probability,
                "tree_depth": len(path) - 1,
            }

            yield Scenario(
                values=scenario_values,
                id=f"{scenario_id}-{path_str}",
                metadata=metadata,
            )


# ================================================================
#  Mixed Strategy Sampler
# ================================================================


@dataclass
class ParameterGroup:
    """Group of parameters sharing the same sampling strategy.

    Attributes:
        parameters: List of parameters in this group
        strategy: Sampling strategy for this group
        sampler_kwargs: Additional arguments for the sampler
    """

    parameters: Sequence[Parameter]
    strategy: SamplingStrategy
    sampler_kwargs: dict[str, Any] = field(default_factory=dict)


class MixedStrategySampler(Sampler):
    """Sampler that uses different strategies for different parameter groups.

    This allows combining multiple sampling strategies, for example:
    - Use Sobol sequences for continuous parameters
    - Use Monte Carlo for categorical parameters
    - Use LHS for discrete parameters

    Attributes:
        groups: List of ParameterGroup objects defining sampling strategies
    """

    def __init__(
        self,
        groups: Sequence[ParameterGroup],
        id_generator: IDGenerator | type[IDGenerator] | None = None,
    ):
        # Collect all parameters from all groups
        all_parameters: list[Parameter] = []
        for group in groups:
            all_parameters.extend(group.parameters)

        if not all_parameters:
            raise ValueError(
                "MixedStrategySampler requires at least one parameter across all groups"
            )

        super().__init__(all_parameters, id_generator)
        self.groups = list(groups)

        # Create sub-samplers for each group
        self.sub_samplers = []
        for group in self.groups:
            sampler_class = self._get_sampler_class(group.strategy)
            sub_sampler = sampler_class(
                group.parameters,
                id_generator=None,  # Don't generate IDs for sub-samplers
                **group.sampler_kwargs,
            )
            self.sub_samplers.append(sub_sampler)

    def _get_sampler_class(self, strategy: SamplingStrategy) -> type[Sampler]:
        """Get the sampler class for a given strategy."""
        mapping: dict[SamplingStrategy, type[Sampler]] = {
            SamplingStrategy.MONTE_CARLO: MonteCarloSampler,
            SamplingStrategy.LATIN_HYPERCUBE: LatinHypercubeSampler,
            SamplingStrategy.SOBOL: SobolSampler,
            SamplingStrategy.HALTON: HaltonSampler,
        }
        return mapping[strategy]

    def generate(self, n: int) -> Generator[Scenario, None, None]:
        """Generate n scenarios using mixed sampling strategies."""
        if n <= 0:
            raise ValueError(f"Number of samples must be positive, got {n}")

        # Generate samples from each sub-sampler
        sub_generators = [sub_sampler.generate(n) for sub_sampler in self.sub_samplers]

        # Combine samples from each group
        for _ in range(n):
            self._reset_parameters()
            scenario_values: dict[str, Any] = {}

            for sub_gen in sub_generators:
                sub_scenario = next(sub_gen)
                scenario_values.update(sub_scenario.values)

            scenario_id = self._create_scenario_id(scenario_values)
            yield Scenario(values=scenario_values, id=scenario_id)
