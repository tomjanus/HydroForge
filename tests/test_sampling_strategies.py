"""Tests for seeded direct sampling strategies."""

import numpy as np
import pytest

from hydroforge.sampling import (
    DeterministicHashGenerator,
    GibbsSampler,
    LatinHypercubeSampler,
    MonteCarloSampler,
    ScenarioTreeNode,
    ScenarioTreeSampler,
    SobolSampler,
)
from hydroforge.uncertainty import (
    AdditiveUncertainty,
    CategoricalHistogramDistribution,
    CategoricalReplacementUncertainty,
    ContinuousDiracDeltaDistribution,
    NormalDistribution,
    Parameter,
    ParameterType,
)


def _make_parameter(name: str = "diameter") -> Parameter:
    """Create a parameter with a continuous random realization."""
    return Parameter(
        name=name,
        nominal_value=100.0,
        uncertainty=AdditiveUncertainty(NormalDistribution(0.0, 1.0)),
    )


def _same_legacy_rng_state(first: tuple, second: tuple) -> bool:
    """Compare NumPy's legacy module-level RNG states."""
    return (
        first[0] == second[0]
        and np.array_equal(first[1], second[1])
        and first[2:] == second[2:]
    )


def _make_direct_sampler(
    strategy: str,
    seed: int | None,
    parameters: list[Parameter] | None = None,
):
    if parameters is None:
        parameters = [_make_parameter()]
    id_generator = DeterministicHashGenerator
    if strategy == "monte_carlo":
        return MonteCarloSampler(parameters, id_generator=id_generator, seed=seed)
    if strategy == "latin_hypercube":
        return LatinHypercubeSampler(parameters, id_generator=id_generator, seed=seed)
    if strategy == "sobol":
        return SobolSampler(parameters, id_generator=id_generator, seed=seed)
    if strategy == "gibbs":
        return GibbsSampler(
            parameters,
            id_generator=id_generator,
            n_burn_in=0,
            n_thin=1,
            seed=seed,
        )
    if strategy == "scenario_tree":
        root = ScenarioTreeNode(name="root", probability=1.0)
        for index in range(4):
            root.add_child(
                ScenarioTreeNode(
                    name=f"leaf-{index}",
                    probability=0.25,
                )
            )
        return ScenarioTreeSampler(
            parameters,
            root,
            id_generator=id_generator,
            seed=seed,
        )
    raise AssertionError(f"Unknown direct sampler: {strategy}")


def _direct_sample_count(strategy: str) -> int:
    return 2 if strategy == "scenario_tree" else 8


def _make_composite_sampler(strategy: str, seed: int | None):
    id_generator = DeterministicHashGenerator
    if strategy == "conditional":
        return ConditionalMonteCarloSampler(
            [
                ConditionalLayer([_make_parameter("outer")]),
                ConditionalLayer([_make_parameter("inner")]),
            ],
            id_generator=id_generator,
            seed=seed,
        )
    if strategy == "nested":
        return NestedMonteCarloSampler(
            NestedSamplingSpec(
                outer_parameters=[_make_parameter("outer")],
                inner_parameters=[_make_parameter("inner")],
                n_inner=3,
            ),
            id_generator=id_generator,
            seed=seed,
        )
    if strategy == "mixed":
        return MixedStrategySampler(
            [
                ParameterGroup(
                    [_make_parameter("diameter")],
                    SamplingStrategy.MONTE_CARLO,
                ),
                ParameterGroup(
                    [_make_parameter("roughness")],
                    SamplingStrategy.LATIN_HYPERCUBE,
                ),
            ],
            id_generator=id_generator,
            seed=seed,
        )
    if strategy == "stratified":
        parameter = _make_parameter("flow")
        return StratifiedSampler(
            [parameter],
            [
                Stratum(name="low", bounds={"flow": (98.0, 100.0)}),
                Stratum(name="high", bounds={"flow": (100.0, 102.0)}),
            ],
            id_generator=id_generator,
            seed=seed,
        )
    raise AssertionError(f"Unknown composite sampler: {strategy}")


def _composite_sample_count(strategy: str) -> int:
    return 8 if strategy in {"mixed", "stratified"} else 3


def _make_categorical_replacement_parameter() -> Parameter:
    """Create a categorical parameter with conditional replacement uncertainty."""
    return Parameter(
        name="valve",
        nominal_value="OPEN",
        uncertainty=CategoricalReplacementUncertainty(
            flip_distribution=ContinuousDiracDeltaDistribution(value=0.5),
            replacement_distribution=CategoricalHistogramDistribution(
                categories=("OPEN", "CLOSED"),
                probabilities=(0.5, 0.5),
            ),
        ),
        type=ParameterType.CATEGORICAL,
    )


def test_monte_carlo_seed_repeats_values_and_records_effective_seed():
    first_sampler = MonteCarloSampler(
        [_make_parameter()],
        id_generator=DeterministicHashGenerator,
        seed=17,
    )
    second_sampler = MonteCarloSampler(
        [_make_parameter()],
        id_generator=DeterministicHashGenerator,
        seed=17,
    )

    first = list(first_sampler.generate(8))
    second = list(second_sampler.generate(8))

    assert [scenario.values for scenario in first] == [
        scenario.values for scenario in second
    ]
    assert [scenario.id for scenario in first] == [scenario.id for scenario in second]
    assert all(
        scenario.metadata is not None and scenario.metadata["effective_seed"] == 17
        for scenario in first
    )


def test_monte_carlo_uses_local_rng_and_omitted_seed_is_replayable():
    global_state = np.random.get_state()
    sampler = MonteCarloSampler([_make_parameter()])
    try:
        scenarios = list(sampler.generate(8))
        state_after_sampling = np.random.get_state()
    finally:
        np.random.set_state(global_state)

    assert _same_legacy_rng_state(global_state, state_after_sampling)
    metadata = scenarios[0].metadata
    assert metadata is not None
    effective_seed = metadata["effective_seed"]
    replay = list(
        MonteCarloSampler([_make_parameter()], seed=effective_seed).generate(8)
    )
    assert [scenario.values for scenario in scenarios] == [
        scenario.values for scenario in replay
    ]


def test_monte_carlo_different_seeds_change_random_realizations():
    first = list(MonteCarloSampler([_make_parameter()], seed=17).generate(8))
    second = list(MonteCarloSampler([_make_parameter()], seed=18).generate(8))

    assert [scenario.values for scenario in first] != [
        scenario.values for scenario in second
    ]


def test_monte_carlo_seeded_draw_preserves_parameter_sample_lock():
    parameter = _make_parameter()
    scenario = next(MonteCarloSampler([parameter], seed=17).generate(1))

    assert parameter.sample() == scenario.values[parameter.name]


@pytest.mark.parametrize(
    "strategy",
    ["monte_carlo", "latin_hypercube", "sobol", "gibbs", "scenario_tree"],
)
def test_direct_stochastic_sampler_repeats_and_records_seed(strategy):
    n_samples = _direct_sample_count(strategy)
    first = list(_make_direct_sampler(strategy, 23).generate(n_samples))
    second = list(_make_direct_sampler(strategy, 23).generate(n_samples))

    assert [scenario.values for scenario in first] == [
        scenario.values for scenario in second
    ]
    assert [scenario.id for scenario in first] == [scenario.id for scenario in second]
    assert all(
        scenario.metadata is not None and scenario.metadata["effective_seed"] == 23
        for scenario in first
    )


@pytest.mark.parametrize(
    "strategy",
    ["monte_carlo", "latin_hypercube", "sobol", "gibbs", "scenario_tree"],
)
def test_direct_stochastic_sampler_preserves_global_numpy_rng_state(strategy):
    global_state = np.random.get_state()
    try:
        list(
            _make_direct_sampler(strategy, 31).generate(_direct_sample_count(strategy))
        )
        state_after_sampling = np.random.get_state()
    finally:
        np.random.set_state(global_state)

    assert _same_legacy_rng_state(global_state, state_after_sampling)


@pytest.mark.parametrize(
    "strategy",
    ["monte_carlo", "latin_hypercube", "sobol", "gibbs", "scenario_tree"],
)
def test_direct_sampler_omitted_seed_is_recorded_and_replayable(strategy):
    n_samples = _direct_sample_count(strategy)
    scenarios = list(_make_direct_sampler(strategy, None).generate(n_samples))

    metadata = scenarios[0].metadata
    assert metadata is not None
    effective_seed = metadata["effective_seed"]
    replay = list(_make_direct_sampler(strategy, effective_seed).generate(n_samples))

    assert [scenario.values for scenario in scenarios] == [
        scenario.values for scenario in replay
    ]
    assert all(
        scenario.metadata is not None
        and scenario.metadata["effective_seed"] == effective_seed
        for scenario in scenarios
    )


@pytest.mark.parametrize(
    "strategy",
    ["monte_carlo", "latin_hypercube", "sobol", "gibbs", "scenario_tree"],
)
def test_direct_sampler_different_seeds_change_random_realizations(strategy):
    n_samples = _direct_sample_count(strategy)
    first = list(_make_direct_sampler(strategy, 17).generate(n_samples))
    second = list(_make_direct_sampler(strategy, 18).generate(n_samples))

    assert [scenario.values for scenario in first] != [
        scenario.values for scenario in second
    ]


@pytest.mark.parametrize(
    "strategy",
    ["monte_carlo", "latin_hypercube", "sobol", "gibbs", "scenario_tree"],
)
def test_direct_samplers_keep_categorical_replacement_off_global_rng(strategy):
    global_state = np.random.get_state()
    try:
        sampler = _make_direct_sampler(
            strategy,
            seed=31,
            parameters=[_make_categorical_replacement_parameter()],
        )
        list(sampler.generate(_direct_sample_count(strategy)))
        state_after_sampling = np.random.get_state()
    finally:
        np.random.set_state(global_state)

    assert _same_legacy_rng_state(global_state, state_after_sampling)
