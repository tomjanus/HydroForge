"""Sampling strategies for uncertainty quantification.

This module provides various sampling strategies for generating scenarios
from uncertain parameters, including:

**Basic Strategies:**
- Monte Carlo (MC): Random sampling
- Latin Hypercube Sampling (LHS): Stratified sampling
- Sobol sequences: Quasi-random low-discrepancy sequences
- Halton sequences: Alternative quasi-random sequences

**Advanced Strategies:**
- Conditional/Hierarchical Monte Carlo: Sequential sampling with dependencies
- Nested Monte Carlo: Inner-outer sampling for multilevel uncertainty
- Stratified sampling: Layered sampling with controlled coverage
- Gibbs sampling: MCMC for conditional distributions
- Scenario trees: Discretized branching for decision analysis

**Composite Strategies:**
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
from hydroforge.uncertainty.parameters import Parameter, ParameterKind


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
        parameters: Sequence[Parameter],
        id_generator: IDGenerator | type[IDGenerator] | None = None,
    ):
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
        else:
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

    def generate(self, n_outer: int) -> Generator[Scenario, None, None]:
        """Generate scenarios using nested sampling.

        Args:
            n_outer: Number of outer loop samples

        Yields:
            Scenarios with metadata indicating outer/inner indices
        """
        if n_outer <= 0:
            raise ValueError(f"Number of outer samples must be positive, got {n_outer}")

        for outer_idx in range(n_outer):
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


@dataclass
class Stratum:
    """Defines a stratum for stratified sampling.

    Attributes:
        name: Identifier for this stratum
        bounds: Dict mapping parameter names to (lower, upper) bounds for this stratum
        weight: Sampling weight/probability for this stratum
        n_samples: Number of samples to draw from this stratum (overrides weight if set)
    """

    name: str
    bounds: dict[str, tuple[float, float]]
    weight: float = 1.0
    n_samples: Optional[int] = None


class StratifiedSampler(Sampler):
    """Stratified sampling with custom strata definitions.

    Divides the parameter space into strata and samples from each,
    ensuring coverage across important regions.

    This is more flexible than LHS as you can define custom strata
    based on domain knowledge (e.g., operating regimes, climate zones).

    Attributes:
        strata: List of Stratum definitions
        base_sampler_class: Sampler to use within each stratum
    """

    def __init__(
        self,
        parameters: Sequence[Parameter],
        strata: Sequence[Stratum],
        base_sampler_class: type | None = None,
        id_generator: IDGenerator | type[IDGenerator] | None = None,
    ):
        super().__init__(parameters, id_generator)
        if not strata:
            raise ValueError("StratifiedSampler requires at least one stratum")
        self.strata = list(strata)
        self.base_sampler_class = base_sampler_class or MonteCarloSampler

        # Normalize weights if n_samples not specified
        total_weight = sum(s.weight for s in self.strata if s.n_samples is None)
        self._normalized_weights = {}
        for stratum in self.strata:
            if stratum.n_samples is None and total_weight > 0:
                self._normalized_weights[stratum.name] = stratum.weight / total_weight
            else:
                self._normalized_weights[stratum.name] = 0.0

    def generate(self, n: int) -> Generator[Scenario, None, None]:
        """Generate n scenarios using stratified sampling."""
        if n <= 0:
            raise ValueError(f"Number of samples must be positive, got {n}")

        # Allocate samples to strata
        sample_allocation = {}
        remaining = n

        # First allocate fixed n_samples
        for stratum in self.strata:
            if stratum.n_samples is not None:
                sample_allocation[stratum.name] = stratum.n_samples
                remaining -= stratum.n_samples

        # Then allocate remaining based on weights
        for stratum in self.strata:
            if stratum.n_samples is None:
                sample_allocation[stratum.name] = int(
                    remaining * self._normalized_weights[stratum.name]
                )

        # Generate samples from each stratum
        for stratum in self.strata:
            n_stratum = sample_allocation[stratum.name]
            if n_stratum <= 0:
                continue

            # Create sampler for this stratum
            stratum_sampler = self.base_sampler_class(
                self.parameters, id_generator=None
            )

            for scenario in stratum_sampler.generate(n_stratum):
                # Transform samples to fit stratum bounds
                adjusted_values = {}
                for param_name, value in scenario.values.items():
                    if param_name in stratum.bounds:
                        lower, upper = stratum.bounds[param_name]
                        # Map value to stratum bounds (simple rescaling)
                        # This is a simplification; more sophisticated mapping may be needed
                        adjusted_values[param_name] = value
                    else:
                        adjusted_values[param_name] = value

                scenario_id = self._create_scenario_id(adjusted_values)
                metadata = {"stratum": stratum.name}

                yield Scenario(
                    values=adjusted_values,
                    id=f"{scenario_id}-{stratum.name}",
                    metadata=metadata,
                )


# ================================================================
#  Gibbs Sampler (MCMC)
# ================================================================


class GibbsSampler(Sampler):
    """Gibbs sampling (Markov Chain Monte Carlo).

    Samples parameters one at a time from conditional distributions:
    - X^(t+1) ~ p(X | Y^(t), Z^(t))
    - Y^(t+1) ~ p(Y | X^(t+1), Z^(t))
    - Z^(t+1) ~ p(Z | X^(t+1), Y^(t+1))

    Useful when:
    - Joint distribution is hard to sample from
    - Conditional distributions are easy to sample from
    - Parameters have complex dependencies

    Attributes:
        n_burn_in: Number of initial samples to discard (burn-in period)
        n_thin: Keep every n_thin samples (thinning to reduce autocorrelation)
        initial_values: Starting values for the chain (optional)
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
        """Generate n scenarios using Gibbs sampling.

        Note: n samples after burn-in and thinning. Total iterations will be
        n_burn_in + n * n_thin.
        """
        if n <= 0:
            raise ValueError(f"Number of samples must be positive, got {n}")
        if self.n_thin <= 0:
            raise ValueError(f"Thinning parameter must be positive, got {self.n_thin}")

        # Initialize chain
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
            # Update each parameter conditioned on others
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
        mapping = {
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


# ================================================================
#  Legacy Compatibility - Keep old MonteCarloSampler signature
# ================================================================


if __name__ == "__main__":
    from rich import print as rprint
    from rich.table import Table
    from hydroforge.uncertainty.distributions import (
        NormalDistribution,
        UniformDistribution,
        CategoricalUniformDistribution,
        DiscreteUniformDistribution,
    )
    from hydroforge.uncertainty.uncertainties import (
        AdditiveUncertainty,
        MultiplicativeUncertainty,
        CategoricalRandomReplacementUncertainty,
    )

    rprint("[bold blue]=== Sampling Strategies Demonstration ===[/bold blue]")

    # 1. Define test parameters
    test_parameters = [
        Parameter(
            name="diameter",
            nominal_value=150.0,
            uncertainty=AdditiveUncertainty(NormalDistribution(0, 5)),
            kind=ParameterKind.NUMERICAL,
            metadata={"unit": "mm", "group": "continuous"},
        ),
        Parameter(
            name="roughness",
            nominal_value=0.1,
            uncertainty=MultiplicativeUncertainty(UniformDistribution(-0.2, 0.2)),
            kind=ParameterKind.NUMERICAL,
            metadata={"unit": "mm", "group": "continuous"},
        ),
        Parameter(
            name="sensor_count",
            nominal_value=10,
            uncertainty=AdditiveUncertainty(DiscreteUniformDistribution(-2, 2)),
            kind=ParameterKind.DISCRETE,
            metadata={"unit": "count", "group": "discrete"},
        ),
        Parameter(
            name="material",
            nominal_value="PVC",
            uncertainty=CategoricalRandomReplacementUncertainty(
                CategoricalUniformDistribution(categories=("PVC", "Iron", "Steel"))
            ),
            kind=ParameterKind.CATEGORICAL,
            metadata={"group": "categorical"},
        ),
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
            str(scenario.values["sensor_count"]),
            scenario.values["material"],
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
            str(scenario.values["sensor_count"]),
            scenario.values["material"],
        )
    rprint(table)

    # 4. Sobol Sequence Sampling
    rprint("\n[bold green]3. Sobol Sequence Sampling[/bold green]")
    rprint(
        "Quasi-random low-discrepancy sequences - excellent for sensitivity analysis"
    )
    sobol_sampler = SobolSampler(test_parameters, skip_values=100)

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
            str(scenario.values["sensor_count"]),
            scenario.values["material"],
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
            str(scenario.values["sensor_count"]),
            scenario.values["material"],
        )
    rprint(table)

    # 6. Mixed Strategy Sampling
    rprint("\n[bold green]5. Mixed Strategy Sampling[/bold green]")
    rprint("Different strategies for different parameter groups")

    # Separate parameters into groups
    continuous_params = [
        p for p in test_parameters if p.metadata.get("group") == "continuous"
    ]
    discrete_params = [
        p for p in test_parameters if p.metadata.get("group") == "discrete"
    ]
    categorical_params = [
        p for p in test_parameters if p.metadata.get("group") == "categorical"
    ]

    # Create parameter groups with different strategies
    groups = [
        ParameterGroup(
            parameters=continuous_params,
            strategy=SamplingStrategy.SOBOL,
            sampler_kwargs={"skip_values": 100},
        ),
        ParameterGroup(
            parameters=discrete_params, strategy=SamplingStrategy.LATIN_HYPERCUBE
        ),
        ParameterGroup(
            parameters=categorical_params, strategy=SamplingStrategy.MONTE_CARLO
        ),
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
            str(scenario.values["sensor_count"]),
            scenario.values["material"],
        )
    rprint(table)

    # 7. Demonstrate deterministic hash IDs
    rprint("\n[bold green]6. Deterministic Hash IDs[/bold green]")
    rprint("IDs based on parameter values - reproducible across runs")
    mc_sampler_hash = MonteCarloSampler(
        test_parameters[:2],  # Use fewer params for clarity
        id_generator=DeterministicHashGenerator,
    )

    table = Table(title="Hash-based IDs")
    table.add_column("Scenario ID", style="cyan")
    table.add_column("Diameter", style="green")
    table.add_column("Roughness", style="green")

    for scenario in mc_sampler_hash.generate(3):
        table.add_row(
            scenario.id,
            f"{scenario.values['diameter']:.2f}",
            f"{scenario.values['roughness']:.4f}",
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
    rprint("\n[bold green]7. Conditional Monte Carlo[/bold green]")
    rprint("Sequential sampling with dependencies: climate → temperature → demand")

    # Define climate regime parameter
    from hydroforge.uncertainty.distributions import CategoricalUniformDistribution

    climate_param = Parameter(
        name="climate_regime",
        nominal_value="normal",
        uncertainty=CategoricalRandomReplacementUncertainty(
            CategoricalUniformDistribution(categories=("dry", "normal", "wet"))
        ),
        kind=ParameterKind.CATEGORICAL,
    )

    temp_param = Parameter(
        name="temperature",
        nominal_value=20.0,
        uncertainty=AdditiveUncertainty(NormalDistribution(0, 3)),
        kind=ParameterKind.NUMERICAL,
    )

    demand_param = Parameter(
        name="demand",
        nominal_value=100.0,
        uncertainty=MultiplicativeUncertainty(UniformDistribution(-0.1, 0.1)),
        kind=ParameterKind.NUMERICAL,
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
            parameters=[temp_param, demand_param], condition_func=condition_on_climate
        ),
    ]

    conditional_sampler = ConditionalMonteCarloSampler(layers)

    table = Table(title="Conditional MC Samples")
    table.add_column("Climate", style="cyan")
    table.add_column("Temperature", style="yellow")
    table.add_column("Demand", style="magenta")

    for scenario in conditional_sampler.generate(5):
        table.add_row(
            scenario.values["climate_regime"],
            f"{scenario.values['temperature']:.1f}°C",
            f"{scenario.values['demand']:.1f}",
        )
    rprint(table)

    # 9b. Nested Monte Carlo
    rprint("\n[bold green]8. Nested Monte Carlo[/bold green]")
    rprint("Outer: climate scenarios | Inner: daily operations (2 inner per outer)")

    # Outer: climate
    outer_params = [climate_param]

    # Inner: operational variables
    inner_params = [
        Parameter(
            name="daily_flow",
            nominal_value=50.0,
            uncertainty=MultiplicativeUncertainty(UniformDistribution(-0.2, 0.2)),
            kind=ParameterKind.NUMERICAL,
        )
    ]

    nested_spec = NestedSamplingSpec(
        outer_parameters=outer_params, inner_parameters=inner_params, n_inner=2
    )

    nested_sampler = NestedMonteCarloSampler(nested_spec)

    table = Table(title="Nested MC Samples")
    table.add_column("Outer", style="cyan")
    table.add_column("Inner", style="cyan")
    table.add_column("Climate", style="yellow")
    table.add_column("Daily Flow", style="magenta")

    for scenario in nested_sampler.generate(n_outer=3):
        table.add_row(
            str(cast(dict[str, Any], scenario.metadata)["outer_index"]),
            str(cast(dict[str, Any], scenario.metadata)["inner_index"]),
            scenario.values["climate_regime"],
            f"{scenario.values['daily_flow']:.1f}",
        )
    rprint(table)

    # 9c. Scenario Tree
    rprint("\n[bold green]9. Scenario Tree[/bold green]")
    rprint("Tree: Root → (Low/High demand) → (Normal/Peak usage)")

    # Build scenario tree
    root = ScenarioTreeNode(name="Root", probability=1.0, parameter_values={})

    # Stage 1: Demand level
    low_demand = ScenarioTreeNode(
        name="LowDemand", probability=0.4, parameter_values={"demand_level": 80.0}
    )
    high_demand = ScenarioTreeNode(
        name="HighDemand", probability=0.6, parameter_values={"demand_level": 120.0}
    )
    root.add_child(low_demand)
    root.add_child(high_demand)

    # Stage 2: Usage pattern (conditional on demand)
    normal_usage_low = ScenarioTreeNode(
        name="Normal", probability=0.7, parameter_values={"usage_factor": 1.0}
    )
    peak_usage_low = ScenarioTreeNode(
        name="Peak", probability=0.3, parameter_values={"usage_factor": 1.3}
    )
    low_demand.add_child(normal_usage_low)
    low_demand.add_child(peak_usage_low)

    normal_usage_high = ScenarioTreeNode(
        name="Normal", probability=0.5, parameter_values={"usage_factor": 1.0}
    )
    peak_usage_high = ScenarioTreeNode(
        name="Peak", probability=0.5, parameter_values={"usage_factor": 1.5}
    )
    high_demand.add_child(normal_usage_high)
    high_demand.add_child(peak_usage_high)

    # Create parameters that can be used with tree
    tree_params = [
        Parameter(
            name="demand_level",
            nominal_value=100.0,
            uncertainty=AdditiveUncertainty(NormalDistribution(0, 5)),
            kind=ParameterKind.NUMERICAL,
        ),
        Parameter(
            name="usage_factor",
            nominal_value=1.0,
            uncertainty=MultiplicativeUncertainty(UniformDistribution(-0.05, 0.05)),
            kind=ParameterKind.NUMERICAL,
        ),
    ]

    tree_sampler = ScenarioTreeSampler(tree_params, root)

    table = Table(title="Scenario Tree Paths")
    table.add_column("Path", style="cyan")
    table.add_column("Probability", style="yellow")
    table.add_column("Demand", style="green")
    table.add_column("Usage", style="magenta")

    for scenario in tree_sampler.generate():
        table.add_row(
            cast(dict[str, Any], scenario.metadata)["path"],
            f"{cast(dict[str, Any], scenario.metadata)['path_probability']:.2%}",
            f"{scenario.values['demand_level']:.1f}",
            f"{scenario.values['usage_factor']:.2f}",
        )
    rprint(table)

    rprint(
        "\n[bold cyan]✓ All sampling strategies demonstrated successfully![/bold cyan]"
    )
