"""Tests for seeded direct sampling strategies."""

import numpy as np
import pytest

from hydroforge.sampling import (
    ConditionalLayer,
    ConditionalMonteCarloSampler,
    DeterministicHashGenerator,
    GibbsSampler,
    LatinHypercubeSampler,
    MonteCarloSampler,
    MixedStrategySampler,
    NestedMonteCarloSampler,
    NestedSamplingSpec,
    ParameterGroup,
    ScenarioTreeNode,
    ScenarioTreeSampler,
    SamplingStrategy,
    SobolSampler,
    StratifiedSampler,
    Stratum,
)
from hydroforge.uncertainty import (
    AdditiveUncertainty,
    BinaryStateFlipUncertainty,
    CategoricalRandomReplacementUncertainty,
    CategoricalUniformDistribution,
    CategoricalHistogramDistribution,
    CategoricalReplacementUncertainty,
    ContinuousDiracDeltaDistribution,
    DiscreteNormalDistribution,
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


@pytest.mark.parametrize(
    "strategy",
    ["conditional", "nested", "mixed", "stratified"],
)
def test_composite_sampler_seed_repeats_complete_scenarios(strategy):
    n_samples = _composite_sample_count(strategy)
    first = list(_make_composite_sampler(strategy, 41).generate(n_samples))
    second = list(_make_composite_sampler(strategy, 41).generate(n_samples))

    assert first == second
    assert all(
        scenario.metadata is not None and scenario.metadata["effective_seed"] == 41
        for scenario in first
    )


@pytest.mark.parametrize(
    "strategy",
    ["conditional", "nested", "mixed", "stratified"],
)
def test_composite_sampler_different_seeds_change_stochastic_draws(strategy):
    n_samples = _composite_sample_count(strategy)
    first = list(_make_composite_sampler(strategy, 41).generate(n_samples))
    second = list(_make_composite_sampler(strategy, 42).generate(n_samples))

    assert [scenario.values for scenario in first] != [
        scenario.values for scenario in second
    ]


@pytest.mark.parametrize(
    "strategy",
    ["conditional", "nested", "mixed", "stratified"],
)
def test_composite_sampler_omitted_seed_metadata_replays_run(strategy):
    n_samples = _composite_sample_count(strategy)
    scenarios = list(_make_composite_sampler(strategy, None).generate(n_samples))

    metadata = scenarios[0].metadata
    assert metadata is not None
    effective_seed = metadata["effective_seed"]
    replay = list(_make_composite_sampler(strategy, effective_seed).generate(n_samples))

    assert replay == scenarios


@pytest.mark.parametrize(
    "strategy",
    ["conditional", "nested", "mixed", "stratified"],
)
def test_composite_sampler_preserves_global_numpy_rng_state(strategy):
    global_state = np.random.get_state()
    try:
        list(
            _make_composite_sampler(strategy, 43).generate(
                _composite_sample_count(strategy)
            )
        )
        state_after_sampling = np.random.get_state()
    finally:
        np.random.set_state(global_state)

    assert _same_legacy_rng_state(global_state, state_after_sampling)


def test_nested_and_mixed_samplers_derive_distinct_child_seed_streams():
    nested = list(_make_composite_sampler("nested", 47).generate(3))
    nested_seeds = {
        scenario.metadata["inner_sampler_seed"]
        for scenario in nested
        if scenario.metadata is not None
    }
    assert len(nested_seeds) == 3

    mixed = list(_make_composite_sampler("mixed", 47).generate(2))
    mixed_metadata = mixed[0].metadata
    assert mixed_metadata is not None
    child_seeds = mixed_metadata["child_seeds"]
    assert len(child_seeds) == 2
    assert len(set(child_seeds)) == 2


def test_stratified_sampler_derives_distinct_child_seed_streams_per_stratum():
    scenarios = list(_make_composite_sampler("stratified", 53).generate(8))
    seed_pairs = {
        (
            scenario.metadata["base_sampler_seed"],
            scenario.metadata["unit_rng_seed"],
        )
        for scenario in scenarios
        if scenario.metadata is not None
    }

    assert len(seed_pairs) == 2
    assert len({base_seed for base_seed, _ in seed_pairs}) == 2
    assert len({unit_seed for _, unit_seed in seed_pairs}) == 2


def test_composite_samplers_reject_child_seed_overrides():
    with pytest.raises(ValueError, match="inner_sampler_kwargs"):
        NestedMonteCarloSampler(
            NestedSamplingSpec(
                outer_parameters=[_make_parameter("outer")],
                inner_parameters=[_make_parameter("inner")],
                inner_sampler_kwargs={"seed": 99},
            ),
            seed=59,
        )

    with pytest.raises(ValueError, match="sampler_kwargs"):
        MixedStrategySampler(
            [
                ParameterGroup(
                    [_make_parameter()],
                    SamplingStrategy.MONTE_CARLO,
                    sampler_kwargs={"seed": 99},
                )
            ],
            seed=59,
        )


def _make_mixed_domain_parameters():
    """Create one continuous, discrete, categorical, and binary parameter."""
    return [
        Parameter(
            name="diameter",
            nominal_value=100.0,
            uncertainty=AdditiveUncertainty(NormalDistribution(0.0, 1.0)),
        ),
        Parameter(
            name="count",
            nominal_value=5,
            uncertainty=AdditiveUncertainty(DiscreteNormalDistribution(5, 1.0)),
        ),
        Parameter(
            name="material",
            nominal_value="PVC",
            uncertainty=CategoricalRandomReplacementUncertainty(
                CategoricalUniformDistribution(
                    categories=("PVC", "Steel"), nominal_category="PVC"
                )
            ),
        ),
        Parameter(
            name="status",
            nominal_value="OPEN",
            uncertainty=BinaryStateFlipUncertainty(
                flip_prob=0.3, states=("OPEN", "CLOSED")
            ),
        ),
    ]


@pytest.mark.parametrize("sampler_class", [LatinHypercubeSampler, SobolSampler])
def test_mixed_domain_sampling_is_deterministic_and_domain_valid(sampler_class):
    parameters = _make_mixed_domain_parameters()
    global_state = np.random.get_state()
    try:
        first = list(sampler_class(parameters, seed=17).generate(8))
        state_after_sampling = np.random.get_state()
    finally:
        np.random.set_state(global_state)

    assert global_state[0] == state_after_sampling[0]
    assert np.array_equal(global_state[1], state_after_sampling[1])
    assert global_state[2] == state_after_sampling[2]
    assert global_state[3] == state_after_sampling[3]
    assert global_state[4] == state_after_sampling[4]

    second_parameters = _make_mixed_domain_parameters()
    second = list(sampler_class(second_parameters, seed=17).generate(8))

    assert [scenario.values for scenario in first] == [
        scenario.values for scenario in second
    ]
    assert all(
        scenario.metadata is not None and scenario.metadata.get("effective_seed") == 17
        for scenario in first
    )

    for scenario in first:
        values = scenario.values
        assert isinstance(values["diameter"], (int, float, np.integer, np.floating))
        assert not isinstance(values["diameter"], (bool, np.bool_))
        assert isinstance(values["count"], (int, np.integer))
        assert not isinstance(values["count"], (bool, np.bool_))
        assert values["material"] in ("PVC", "Steel")
        assert values["status"] in ("OPEN", "CLOSED")
