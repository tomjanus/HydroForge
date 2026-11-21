"""Tests for distribution behaviour: empirical CDFs, to_dict, validation."""

import json
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from hydroforge.uncertainty.distributions import (
    CategoricalHistogramDistribution,
    CategoricalNormalDistribution,
    CategoricalUniformDistribution,
    DiscreteHistogramDistribution,
    DiscreteNormalDistribution,
    DiscreteUniformDistribution,
    NormalDistribution,
    UniformDistribution,
)

_ORDERED_CATEGORICAL = {
    "histogram": lambda: CategoricalHistogramDistribution(
        categories=("CLOSED", "HALF", "OPEN"),
        probabilities=(0.2, 0.3, 0.5),
    ),
    "uniform": lambda: CategoricalUniformDistribution(
        categories=("A", "B", "C", "D", "E"),
        nominal_category="C",
    ),
    "normal": lambda: CategoricalNormalDistribution(
        categories=("low", "mid", "high"),
        spread=1.0,
        nominal_category="mid",
    ),
}


def _make(name: str):
    return _ORDERED_CATEGORICAL[name]()


# ---------------------------------------------------------------
# Empirical categorical CDF (#31, finding C1)
# ---------------------------------------------------------------


@pytest.mark.parametrize("family", sorted(_ORDERED_CATEGORICAL))
def test_empirical_categorical_cdf_works_on_first_call(family):
    distribution = _make(family)
    result = distribution.cdf(distribution.nominal_value, empirical=True)
    assert 0.0 <= float(result) <= 1.0


@pytest.mark.parametrize("family", sorted(_ORDERED_CATEGORICAL))
def test_empirical_categorical_cdf_shape_and_dtype(family):
    distribution = _make(family)
    nominal = distribution.nominal_value
    scalar = distribution.cdf(nominal, empirical=True, n_samples=500, random_state=7)
    assert scalar.shape == ()
    assert scalar.dtype == np.float64
    vector = distribution.cdf([nominal, nominal], empirical=True, n_samples=500)
    assert vector.shape == (2,)
    assert vector.dtype == np.float64


@pytest.mark.parametrize("family", sorted(_ORDERED_CATEGORICAL))
def test_empirical_categorical_cdf_converges_to_theoretical(family):
    distribution = _make(family)
    x = list(distribution.categories)
    theoretical = distribution.cdf(x)
    empirical = distribution.cdf(x, empirical=True, n_samples=20_000, random_state=42)
    np.testing.assert_allclose(empirical, theoretical, atol=0.02)


@pytest.mark.parametrize("family", sorted(_ORDERED_CATEGORICAL))
@pytest.mark.parametrize("n_samples", [0, -10])
def test_empirical_categorical_cdf_rejects_nonpositive_n_samples(family, n_samples):
    distribution = _make(family)
    with pytest.raises(ValueError, match="greater than zero"):
        distribution.cdf(
            distribution.nominal_value, empirical=True, n_samples=n_samples
        )


def test_empirical_categorical_cdf_nonpositive_n_samples_after_cache_populated():
    """The n_samples check must run before any cache lookup (C1 bypass)."""
    distribution = _make("histogram")
    distribution.cdf("OPEN", empirical=True, n_samples=100, random_state=1)
    with pytest.raises(ValueError, match="greater than zero"):
        distribution.cdf("OPEN", empirical=True, n_samples=0, random_state=1)


def test_empirical_categorical_cdf_is_repeatable_for_same_random_state():
    distribution = _make("histogram")
    x = ["CLOSED", "HALF", "OPEN"]
    first = distribution.cdf(x, empirical=True, n_samples=400, random_state=123)
    second = distribution.cdf(x, empirical=True, n_samples=400, random_state=123)
    np.testing.assert_array_equal(first, second)


def test_empirical_categorical_cdf_none_reuses_first_draw_for_sample_count():
    distribution = _make("histogram")
    categories = list(distribution.categories)
    first = distribution.cdf(categories, empirical=True, n_samples=128)
    second = distribution.cdf(categories, empirical=True, n_samples=128)

    np.testing.assert_array_equal(first, second)


def test_empirical_categorical_cdf_uses_current_generator_state():
    distribution = _make("histogram")
    categories = list(distribution.categories)
    n_samples = 64
    rng = np.random.default_rng(23)

    distribution.cdf(
        categories,
        empirical=True,
        n_samples=n_samples,
        random_state=rng,
    )
    rng.random(n_samples)
    result = distribution.cdf(
        categories,
        empirical=True,
        n_samples=n_samples,
        random_state=rng,
    )

    reference_rng = np.random.default_rng(23)
    reference_rng.random(n_samples)
    reference_rng.random(n_samples)
    samples = distribution.sample_from_unit(reference_rng.random(n_samples))
    sample_indices = np.asarray([categories.index(sample) for sample in samples])
    expected = np.asarray(
        [
            np.mean(sample_indices <= category_index)
            for category_index in range(len(categories))
        ],
        dtype=np.float64,
    )

    np.testing.assert_array_equal(result, expected)
    assert rng.bit_generator.state == reference_rng.bit_generator.state


def test_empirical_categorical_cdf_unknown_category_is_zero():
    distribution = _make("histogram")
    result = distribution.cdf("nope", empirical=True, n_samples=100, random_state=5)
    assert result == pytest.approx(0.0)


def test_empirical_numeric_cdf_still_works():
    distribution = NormalDistribution(mean=0.0, std_dev=1.0)
    result = distribution.cdf(0.0, empirical=True, n_samples=2000, random_state=3)
    assert abs(float(result) - 0.5) < 0.05


def test_empirical_numeric_cdf_uses_current_generator_state():
    distribution = UniformDistribution(lower=0.0, upper=1.0)
    n_samples = 64
    points = np.linspace(0.0, 1.0, 33)
    rng = np.random.default_rng(17)

    distribution.cdf(points, empirical=True, n_samples=n_samples, random_state=rng)
    rng.random(n_samples)
    result = distribution.cdf(
        points,
        empirical=True,
        n_samples=n_samples,
        random_state=rng,
    )

    reference_rng = np.random.default_rng(17)
    reference_rng.random(n_samples)
    reference_rng.random(n_samples)
    expected_samples = np.sort(
        distribution.sample_from_unit(reference_rng.random(n_samples))
    )
    expected = np.searchsorted(expected_samples, points, side="right") / n_samples

    np.testing.assert_array_equal(result, expected)
    assert rng.bit_generator.state == reference_rng.bit_generator.state


def test_empirical_numeric_cdf_integer_seed_is_reproducible():
    points = np.linspace(0.0, 1.0, 17)
    first = UniformDistribution(0.0, 1.0).cdf(
        points,
        empirical=True,
        n_samples=128,
        random_state=41,
    )
    second = UniformDistribution(0.0, 1.0).cdf(
        points,
        empirical=True,
        n_samples=128,
        random_state=41,
    )

    np.testing.assert_array_equal(first, second)


def test_empirical_numeric_cdf_none_reuses_first_draw_for_sample_count():
    distribution = UniformDistribution(0.0, 1.0)
    points = np.linspace(0.0, 1.0, 17)
    first = distribution.cdf(points, empirical=True, n_samples=128)
    second = distribution.cdf(points, empirical=True, n_samples=128)

    np.testing.assert_array_equal(first, second)


def test_empirical_numeric_cdf_concurrent_cache_reads_are_consistent():
    distribution = UniformDistribution(0.0, 1.0)
    points = np.linspace(0.0, 1.0, 17)

    def evaluate(_: int) -> np.ndarray:
        return distribution.cdf(
            points,
            empirical=True,
            n_samples=128,
            random_state=53,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(evaluate, range(16)))

    for result in results[1:]:
        np.testing.assert_array_equal(result, results[0])


def test_empirical_numeric_cdf_concurrent_calls_use_independent_generators():
    distribution = UniformDistribution(0.0, 1.0)
    points = np.linspace(0.0, 1.0, 17)
    seeds = list(range(8))
    generators = [np.random.default_rng(seed) for seed in seeds]

    def evaluate(generator: np.random.Generator) -> np.ndarray:
        return distribution.cdf(
            points,
            empirical=True,
            n_samples=128,
            random_state=generator,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(evaluate, generators))

    expected = [
        UniformDistribution(0.0, 1.0).cdf(
            points,
            empirical=True,
            n_samples=128,
            random_state=seed,
        )
        for seed in seeds
    ]
    for result, expected_result in zip(results, expected):
        np.testing.assert_array_equal(result, expected_result)


# ---------------------------------------------------------------
# to_dict internal-state leakage (#32, finding A1)
# ---------------------------------------------------------------


def test_to_dict_returns_only_constructor_fields():
    assert NormalDistribution(mean=0.0, std_dev=1.0).to_dict() == {
        "mean": 0.0,
        "std_dev": 1.0,
    }


@pytest.mark.parametrize("family", sorted(_ORDERED_CATEGORICAL))
def test_to_dict_excludes_internal_category_and_cache_fields(family):
    payload = _make(family).to_dict()
    assert "_empirical_cache" not in payload
    assert "_cat_to_num" not in payload
    assert "_num_to_cat" not in payload


def test_to_dict_is_json_serializable_after_empirical_cdf_calls():
    """Tuple ndarray cache keys used to break json.dumps(to_dict()) (A1)."""
    distribution = _make("histogram")
    distribution.cdf("OPEN", empirical=True, n_samples=100, random_state=1)
    payload = distribution.to_dict()
    json.dumps(payload)


def test_to_dict_recursive_excludes_non_init_fields():
    distribution = _make("histogram")
    payload = distribution.to_dict(recursive=True)
    assert "_empirical_cache" not in payload
    assert payload["categories"] == ("CLOSED", "HALF", "OPEN")


def test_to_dict_honours_serialize_metadata_optout():
    from dataclasses import dataclass, field
    from typing import ClassVar

    from hydroforge.uncertainty.distributions import (
        ContinuousDiracDeltaDistribution,
        Distribution,
        DistributionBoundsType,
        DistributionDomain,
        DistributionFamily,
        DistributionProperties,
    )

    @dataclass
    class ProbeDistribution(Distribution[float]):
        """Minimal concrete distribution probing to_dict field filtering."""

        alpha: float = 1.0
        hidden: float = field(default=2.0, metadata={"serialize": False})
        properties: ClassVar[DistributionProperties] = DistributionProperties(
            family=DistributionFamily.OTHER,
            bounds_type=DistributionBoundsType.SEMI_BOUNDED,
            domain=DistributionDomain.CONTINUOUS,
        )

        @property
        def nominal_value(self) -> float:
            return self.alpha

        def reduce(self) -> ContinuousDiracDeltaDistribution:
            return ContinuousDiracDeltaDistribution(value=self.alpha)

        def sample_from_unit(self, u):
            raise NotImplementedError

        def _theoretical_cdf(self, x):
            raise NotImplementedError

    payload = ProbeDistribution(alpha=3.5).to_dict()
    assert payload == {"alpha": 3.5}
    assert "hidden" not in payload
    assert "_empirical_cache" not in payload


# ---------------------------------------------------------------
# Construction validation of numeric distributions (#34, finding V6)
# ---------------------------------------------------------------


@pytest.mark.parametrize("bad_std_dev", [float("inf"), float("-inf"), float("nan")])
def test_normal_distribution_rejects_non_finite_std_dev(bad_std_dev):
    with pytest.raises(ValueError, match="finite"):
        NormalDistribution(mean=0.0, std_dev=bad_std_dev)


@pytest.mark.parametrize("bad_mean", [float("inf"), float("nan")])
def test_normal_distribution_rejects_non_finite_mean(bad_mean):
    with pytest.raises(ValueError, match="finite"):
        NormalDistribution(mean=bad_mean, std_dev=1.0)


@pytest.mark.parametrize("bad_mean", ["0", True, False])
def test_normal_distribution_rejects_non_numeric_mean(bad_mean):
    with pytest.raises(TypeError):
        NormalDistribution(mean=bad_mean, std_dev=1.0)


def test_normal_distribution_rejects_non_positive_std_dev():
    with pytest.raises(ValueError):
        NormalDistribution(mean=0.0, std_dev=0.0)
    with pytest.raises(ValueError):
        NormalDistribution(mean=0.0, std_dev=-1.0)


@pytest.mark.parametrize("value", [3, 3.0, np.float64(3.0), np.int64(3)])
def test_normal_distribution_accepts_numeric_types_and_normalises(value):
    distribution = NormalDistribution(mean=value, std_dev=2)
    assert isinstance(distribution.mean, float)
    assert isinstance(distribution.std_dev, float)
    assert distribution.mean == pytest.approx(3.0)


def test_numeric_strings_are_not_coerced():
    with pytest.raises(TypeError):
        UniformDistribution(lower="1", upper="2")


@pytest.mark.parametrize("lower,upper", [(float("nan"), 1.0), (0.0, float("inf"))])
def test_uniform_distribution_rejects_non_finite_bounds(lower, upper):
    with pytest.raises(ValueError, match="finite"):
        UniformDistribution(lower=lower, upper=upper)


@pytest.mark.parametrize("bad_std_dev", [float("inf"), float("nan")])
def test_discrete_normal_rejects_non_finite_std_dev(bad_std_dev):
    with pytest.raises(ValueError, match="finite"):
        DiscreteNormalDistribution(mean=0, std_dev=bad_std_dev)


@pytest.mark.parametrize("bad_mean", ["0", 2.5, True])
def test_discrete_normal_rejects_bad_mean(bad_mean):
    with pytest.raises((TypeError, ValueError)):
        DiscreteNormalDistribution(mean=bad_mean, std_dev=1.0)


@pytest.mark.parametrize("bad_bound", [float("nan"), float("inf")])
def test_discrete_uniform_rejects_non_finite_bounds(bad_bound):
    with pytest.raises(ValueError, match="finite"):
        DiscreteUniformDistribution(lower=0, upper=bad_bound)


@pytest.mark.parametrize("bad_prob", [float("nan"), float("inf")])
def test_discrete_histogram_rejects_non_finite_probabilities(bad_prob):
    with pytest.raises(ValueError, match="finite"):
        DiscreteHistogramDistribution(values=(1.0, 2.0), probabilities=(0.5, bad_prob))


def test_discrete_histogram_rejects_non_numeric_values():
    with pytest.raises(TypeError):
        DiscreteHistogramDistribution(values=("1", "2"), probabilities=(0.5, 0.5))


@pytest.mark.parametrize("bad_prob", [float("nan"), float("inf")])
def test_categorical_histogram_rejects_non_finite_probabilities(bad_prob):
    with pytest.raises(ValueError, match="finite"):
        CategoricalHistogramDistribution(
            categories=("A", "B"), probabilities=(0.5, bad_prob)
        )


@pytest.mark.parametrize("bad_std_dev", [True, False, "1.0", None])
def test_normal_distribution_rejects_non_numeric_std_dev(bad_std_dev):
    with pytest.raises(TypeError):
        NormalDistribution(mean=0.0, std_dev=bad_std_dev)


@pytest.mark.parametrize("bad_bound", [True, False, "1", None])
def test_uniform_distribution_rejects_non_numeric_bounds(bad_bound):
    with pytest.raises(TypeError):
        UniformDistribution(lower=bad_bound, upper=2.0)
    with pytest.raises(TypeError):
        UniformDistribution(lower=0.0, upper=bad_bound)


@pytest.mark.parametrize("bad_mean", [float("inf"), float("nan"), np.inf, np.nan])
def test_discrete_normal_rejects_non_finite_mean(bad_mean):
    with pytest.raises(ValueError, match="finite"):
        DiscreteNormalDistribution(mean=bad_mean, std_dev=1.0)


@pytest.mark.parametrize("bad_bound", [float("nan"), float("inf")])
def test_discrete_uniform_rejects_non_finite_lower_bound(bad_bound):
    with pytest.raises(ValueError, match="finite"):
        DiscreteUniformDistribution(lower=bad_bound, upper=5)


@pytest.mark.parametrize("bad_bound", [True, "0"])
def test_discrete_uniform_rejects_non_integer_type_bounds(bad_bound):
    with pytest.raises(TypeError):
        DiscreteUniformDistribution(lower=bad_bound, upper=5)
    with pytest.raises(TypeError):
        DiscreteUniformDistribution(lower=0, upper=bad_bound)


@pytest.mark.parametrize("bad_probability", [True, "0.5"])
def test_discrete_histogram_rejects_non_numeric_probabilities(bad_probability):
    with pytest.raises(TypeError):
        DiscreteHistogramDistribution(
            values=(1.0, 2.0), probabilities=(0.5, bad_probability)
        )
