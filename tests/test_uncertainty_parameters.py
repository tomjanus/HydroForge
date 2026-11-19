"""Tests for uncertain parameter behaviour (type inference, arithmetic rules)."""

import numpy as np
import pytest

from hydroforge.uncertainty import (
    AdditiveUncertainty,
    BinaryStateFlipUncertainty,
    NoUncertainty,
    NormalDistribution,
    Parameter,
    ParameterType,
)
from hydroforge.uncertainty.uncertainties import Uncertainty


def _binary_parameter(name: str = "valve") -> Parameter:
    """Binary parameter that always samples its nominal state (flip_prob=0)."""
    return Parameter(
        name=name,
        nominal_value="OPEN",
        uncertainty=BinaryStateFlipUncertainty(flip_prob=0.0),
        type=ParameterType.BINARY,
    )


# ---------------------------------------------------------------
# BINARY arithmetic policy (#29, finding C3)
# ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("dunder", "operand"),
    [
        (name, operand)
        for name in ("__add__", "__sub__", "__mul__", "__truediv__")
        for operand in (2, 2.0, np.int64(2))
    ],
)
def test_binary_parameter_rejects_all_arithmetic_with_values(dunder, operand):
    parameter = _binary_parameter()
    with pytest.raises(TypeError, match="[Bb]inary"):
        getattr(parameter, dunder)(operand)


@pytest.mark.parametrize("operation", ["radd", "rsub", "rmul", "rtruediv"])
def test_binary_parameter_rejects_all_reflected_arithmetic_with_values(operation):
    parameter = _binary_parameter()
    with pytest.raises(TypeError, match="[Bb]inary"):
        getattr(parameter, f"__{operation}__")(2)


def test_binary_times_integer_is_silent_string_repetition_regression():
    """`BINARY * 2` used to return 'OPENOPEN' instead of raising (C3)."""
    parameter = _binary_parameter()
    with pytest.raises(TypeError, match="[Bb]inary"):
        _ = parameter * 2


def test_binary_plus_one_raises_policy_error_not_string_concatenation():
    """`BINARY + 1` used to leak the built-in str-concatenation error (C3)."""
    parameter = _binary_parameter()
    with pytest.raises(TypeError) as exc:
        _ = parameter + 1
    assert "concatenate" not in str(exc.value)


def test_binary_parameter_operand_rejected_in_right_position():
    binary = _binary_parameter()
    numerical = Parameter(
        name="demand",
        nominal_value=1.0,
        uncertainty=NoUncertainty(),
        type=ParameterType.NUMERICAL,
    )
    with pytest.raises(TypeError, match="[Bb]inary"):
        _ = numerical + binary
    with pytest.raises(TypeError, match="[Bb]inary"):
        _ = numerical * binary


# ---------------------------------------------------------------
# Type inference for boolean nominal values (#30, finding C2)
# ---------------------------------------------------------------


@pytest.mark.parametrize("nominal_value", [True, False, np.bool_(True)])
def test_boolean_nominal_value_infers_binary_type(nominal_value):
    parameter = Parameter(name="flag", nominal_value=nominal_value)
    assert parameter.type is ParameterType.BINARY


def test_numeric_and_string_inference_are_unchanged():
    assert Parameter(name="p", nominal_value=1).type is ParameterType.NUMERICAL
    assert Parameter(name="p", nominal_value=1.5).type is ParameterType.NUMERICAL
    assert Parameter(name="p", nominal_value="PVC").type is ParameterType.CATEGORICAL


def test_binary_uncertainty_still_infers_binary():
    from hydroforge.uncertainty import BinaryStateFlipUncertainty

    parameter = Parameter(
        name="valve",
        nominal_value="OPEN",
        uncertainty=BinaryStateFlipUncertainty(flip_prob=0.0),
    )
    assert parameter.type is ParameterType.BINARY


def test_explicit_type_is_never_overridden_by_inference():
    parameter = Parameter(name="flag", nominal_value=True, type=ParameterType.NUMERICAL)
    assert parameter.type is ParameterType.NUMERICAL


# ---------------------------------------------------------------
# Existing policy regressions (categorical / discrete / numerical)
# ---------------------------------------------------------------


def test_categorical_parameter_rejects_all_arithmetic():
    parameter = Parameter(
        name="material",
        nominal_value="PVC",
        uncertainty=NoUncertainty(),
        type=ParameterType.CATEGORICAL,
    )
    with pytest.raises(TypeError, match="[Cc]ategorical"):
        _ = parameter + 1


def test_numerical_and_discrete_rules_are_unchanged():
    numerical = Parameter(
        name="diameter",
        nominal_value=100.0,
        uncertainty=NoUncertainty(),
        type=ParameterType.NUMERICAL,
    )
    discrete = Parameter(
        name="count",
        nominal_value=10,
        uncertainty=NoUncertainty(),
        type=ParameterType.DISCRETE,
    )
    assert numerical * 2 == pytest.approx(200.0)
    assert discrete * 2 == pytest.approx(20)
    with pytest.raises(TypeError, match="integer multiplier"):
        _ = discrete * 2.5
    with pytest.raises(TypeError, match="Division not allowed"):
        _ = discrete / 2.0


# ---------------------------------------------------------------
# Locked sampling behaviour (#33, finding T1)
# ---------------------------------------------------------------


class _CountingUncertainty(Uncertainty):
    """Uncertainty model that counts how often ``apply`` draws a new sample."""

    def __init__(self):
        self.calls = 0

    def apply(self, value, u=None):
        self.calls += 1
        return float(value) + self.calls


def test_sample_is_locked_until_reset():
    uncertainty = _CountingUncertainty()
    parameter = Parameter(
        name="x",
        nominal_value=1.0,
        uncertainty=uncertainty,
        type=ParameterType.NUMERICAL,
    )
    first = parameter.sample()
    second = parameter.sample()
    assert first == second
    assert uncertainty.calls == 1
    parameter.reset()
    third = parameter.sample()
    assert uncertainty.calls == 2
    assert third != first


def test_repeated_operand_uses_one_sample():
    """The README claims `p + p` uses the same sample for both operands."""
    parameter = Parameter(
        name="x",
        nominal_value=100.0,
        uncertainty=AdditiveUncertainty(NormalDistribution(mean=0.0, std_dev=1.0)),
        type=ParameterType.NUMERICAL,
    )
    assert parameter + parameter == 2 * parameter.sample()


def test_binary_parameter_rejects_infix_arithmetic_syntax():
    """Reflected dunders must work through interpreter dispatch, not just direct calls."""
    parameter = _binary_parameter()
    for expression in (
        lambda: 2 + parameter,
        lambda: 2 - parameter,
        lambda: 2 * parameter,
        lambda: 2 / parameter,
        lambda: parameter + 2,
        lambda: parameter * 2,
    ):
        with pytest.raises(TypeError, match="[Bb]inary"):
            expression()


# ---------------------------------------------------------------
# Symmetric discrete arithmetic operand rules (#37, ADR-0002 decision 7)
# ---------------------------------------------------------------


def _discrete_parameter(value=10, uncertainty=None):
    return Parameter(
        name="count",
        nominal_value=value,
        uncertainty=uncertainty or NoUncertainty(),
        type=ParameterType.DISCRETE,
    )


def _numerical_parameter(value=100.0):
    return Parameter(
        name="demand",
        nominal_value=value,
        uncertainty=NoUncertainty(),
        type=ParameterType.NUMERICAL,
    )


def test_discrete_operand_blocks_division_from_either_side():
    discrete = _discrete_parameter()
    numerical = _numerical_parameter()
    # left operand discrete already raised before this change
    with pytest.raises(TypeError, match="Division not allowed"):
        _ = discrete / numerical
    # right operand discrete must now raise too (the C4 gap)
    with pytest.raises(TypeError, match="Division not allowed"):
        _ = numerical / discrete


def test_discrete_operand_multiplication_requires_integer_partner():
    # a discrete parameter used as an operand must respect the integer rule
    discrete = _discrete_parameter()
    numerical = _numerical_parameter(2.0)  # samples to float 2.0
    with pytest.raises(TypeError, match="integer multiplier"):
        _ = numerical * discrete
    with pytest.raises(TypeError, match="integer multiplier"):
        _ = discrete * numerical


def test_integer_parameter_products_remain_allowed():
    discrete_a = _discrete_parameter(value=6)
    discrete_b = _discrete_parameter(value=3)
    assert discrete_a * discrete_b == pytest.approx(18)


def test_integral_valued_float_partner_still_rejected_in_discrete_product():
    """Pinned reading of #37: the multiplier must be Integral-typed.

    A float like 10.0 is mathematically integral but not an integer
    multiplier: the rule protects the discrete invariant against silent
    type widening, so a float operand raises regardless of its value.
    """
    discrete = _discrete_parameter()
    numerical_integral_float = _numerical_parameter(10.0)
    with pytest.raises(TypeError, match="integer multiplier"):
        _ = numerical_integral_float * discrete
    with pytest.raises(TypeError, match="integer multiplier"):
        _ = discrete * numerical_integral_float


@pytest.mark.parametrize("nominal_value", [np.int64(5), np.float32(2.5)])
def test_numpy_integer_and_float_nominal_values_infer_numerical(nominal_value):
    """NumPy integer scalars (np.float32 included) are real numbers (ADR-0002 §4)."""
    parameter = Parameter(name="p", nominal_value=nominal_value)
    assert parameter.type is ParameterType.NUMERICAL


def test_value_operand_discrete_rules_unchanged():
    discrete = _discrete_parameter()
    assert discrete * 2 == pytest.approx(20)
    assert discrete + 2 == pytest.approx(12)
    with pytest.raises(TypeError, match="integer multiplier"):
        _ = discrete * 2.5
