"""Tests for distribution behaviour: empirical CDFs, to_dict, validation."""

import json

import numpy as np
import pytest

from hydroforge.uncertainty.distributions import (
    CategoricalHistogramDistribution,
    CategoricalNormalDistribution,
    CategoricalUniformDistribution,
    NormalDistribution,
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


def test_empirical_categorical_cdf_unknown_category_is_zero():
    distribution = _make("histogram")
    result = distribution.cdf("nope", empirical=True, n_samples=100, random_state=5)
    assert result == pytest.approx(0.0)


def test_empirical_numeric_cdf_still_works():
    distribution = NormalDistribution(mean=0.0, std_dev=1.0)
    result = distribution.cdf(0.0, empirical=True, n_samples=2000, random_state=3)
    assert abs(float(result) - 0.5) < 0.05


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
