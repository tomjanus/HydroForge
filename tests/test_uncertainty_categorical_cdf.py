"""Tests for empirical CDFs of categorically ordered parameters."""

import numpy as np
import pytest

from hydroforge.uncertainty import (
    BinaryStateFlipUncertainty,
    CategoricalReplacementUncertainty,
    CategoricalHistogramDistribution,
    CategoricalRandomReplacementUncertainty,
    ContinuousDiracDeltaDistribution,
    Parameter,
    ParameterType,
)
from hydroforge.uncertainty.common import CDFNotAvailable
from hydroforge.uncertainty.uncertainties import NoUncertainty


def test_ordered_categorical_parameter_cdf_uses_declared_category_order():
    distribution = CategoricalHistogramDistribution(
        categories=("zeta", "alpha", "mu"),
        probabilities=(0.2, 0.3, 0.5),
    )
    parameter = Parameter(
        name="material",
        nominal_value="zeta",
        uncertainty=CategoricalRandomReplacementUncertainty(distribution),
        type=ParameterType.CATEGORICAL,
    )
    categories = ["zeta", "alpha", "mu"]

    result = parameter.cdf(
        categories,
        empirical=True,
        n_samples=500,
        random_state=13,
    )
    expected = distribution.cdf(
        categories,
        empirical=True,
        n_samples=500,
        random_state=13,
    )

    assert result.shape == (3,)
    assert result.dtype == np.float64
    np.testing.assert_array_equal(result, expected)


def test_binary_parameter_cdf_uses_declared_state_order():
    states = ("OPEN", "CLOSED")
    uncertainty = BinaryStateFlipUncertainty(flip_prob=0.35, states=states)
    parameter = Parameter(
        name="valve",
        nominal_value="OPEN",
        uncertainty=uncertainty,
        type=ParameterType.BINARY,
    )
    n_samples = 400
    rng = np.random.default_rng(7)
    samples = uncertainty.apply(
        np.full(n_samples, "OPEN", dtype=object),
        u=rng.random(n_samples),
    )
    sample_indices = np.asarray([states.index(sample) for sample in samples])
    expected = np.asarray(
        [
            np.mean(sample_indices <= category_index)
            for category_index in range(len(states))
        ],
        dtype=np.float64,
    )

    result = parameter.cdf(
        list(states),
        empirical=True,
        n_samples=n_samples,
        random_state=7,
    )

    np.testing.assert_array_equal(result, expected)
    scalar = parameter.cdf(
        "OPEN",
        empirical=True,
        n_samples=n_samples,
        random_state=7,
    )
    assert scalar.shape == ()
    assert scalar.dtype == np.float64


def test_categorical_replacement_uses_its_declared_order_when_nominal_is_in_order():
    categories = ("OPEN", "CLOSED")
    replacement = CategoricalHistogramDistribution(
        categories=categories,
        probabilities=(0.25, 0.75),
    )
    uncertainty = CategoricalReplacementUncertainty(
        flip_distribution=ContinuousDiracDeltaDistribution(value=0.5),
        replacement_distribution=replacement,
    )
    parameter = Parameter(
        name="valve",
        nominal_value="OPEN",
        uncertainty=uncertainty,
        type=ParameterType.CATEGORICAL,
    )
    n_samples = 400
    rng = np.random.default_rng(11)
    rng.random(n_samples)  # The flip-probability Dirac ignores these values.
    replacement_samples = replacement.sample_from_unit(rng.random(n_samples))
    flips = rng.random(n_samples) < 0.5
    samples = np.full(n_samples, "OPEN", dtype=object)
    samples[flips] = replacement_samples[flips]
    sample_indices = np.asarray([categories.index(sample) for sample in samples])
    expected = np.asarray(
        [
            np.mean(sample_indices <= category_index)
            for category_index in range(len(categories))
        ],
        dtype=np.float64,
    )

    result = parameter.cdf(
        list(categories),
        empirical=True,
        n_samples=n_samples,
        random_state=11,
    )

    np.testing.assert_array_equal(result, expected)


def test_unordered_categorical_parameter_cdf_remains_unavailable():
    parameter = Parameter(
        name="material",
        nominal_value="PVC",
        uncertainty=NoUncertainty(),
        type=ParameterType.CATEGORICAL,
    )

    with pytest.raises(CDFNotAvailable, match="explicit category order"):
        parameter.cdf("PVC", empirical=True, random_state=3)


def test_binary_parameter_without_order_bearing_uncertainty_is_unavailable():
    parameter = Parameter(
        name="flag",
        nominal_value=True,
        uncertainty=NoUncertainty(),
        type=ParameterType.BINARY,
    )

    with pytest.raises(CDFNotAvailable, match="explicit category order"):
        parameter.cdf(True, empirical=True, random_state=3)
