"""Tests for unit variates passed to binary state flips."""

import numpy as np
import pytest

from hydroforge.uncertainty import BinaryStateFlipUncertainty


@pytest.mark.parametrize(
    ("flip_prob", "u", "expected"),
    [
        (0.0, 0.0, "OPEN"),
        (1.0, 1.0, "OPEN"),
        (1.0, 0.0, "CLOSED"),
        (0.5, 0.5, "OPEN"),
    ],
)
def test_scalar_flip_uses_strict_unit_interval_comparison(flip_prob, u, expected):
    uncertainty = BinaryStateFlipUncertainty(flip_prob=flip_prob)

    assert uncertainty.apply("OPEN", u=u) == expected


def test_scalar_unit_variate_broadcasts_to_array_values():
    uncertainty = BinaryStateFlipUncertainty(flip_prob=0.5)

    result = uncertainty.apply(["OPEN", "CLOSED"], u=0.25)

    np.testing.assert_array_equal(result, ["CLOSED", "OPEN"])


def test_array_unit_variates_must_match_value_shape():
    uncertainty = BinaryStateFlipUncertainty(flip_prob=0.5)

    with pytest.raises(ValueError, match="shape"):
        uncertainty.apply(["OPEN", "CLOSED"], u=[0.25])


def test_vector_unit_variate_is_rejected_for_scalar_value():
    uncertainty = BinaryStateFlipUncertainty(flip_prob=0.5)

    with pytest.raises(ValueError, match="scalar"):
        uncertainty.apply("OPEN", u=[0.25])


@pytest.mark.parametrize("u", [-0.01, 1.01, float("nan"), float("inf"), "invalid"])
def test_unit_variates_outside_closed_unit_interval_are_rejected(u):
    uncertainty = BinaryStateFlipUncertainty(flip_prob=0.5)

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        uncertainty.apply("OPEN", u=u)


def test_seeded_instance_generator_drives_the_no_u_path():
    first = BinaryStateFlipUncertainty(
        flip_prob=0.5,
        rng=np.random.default_rng(41),
    )
    second = BinaryStateFlipUncertainty(
        flip_prob=0.5,
        rng=np.random.default_rng(41),
    )
    values = ["OPEN", "CLOSED"] * 8

    np.testing.assert_array_equal(first.apply(values), second.apply(values))
