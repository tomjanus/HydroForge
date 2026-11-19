"""Tests for uncertain parameter behaviour (type inference, arithmetic rules)."""

import numpy as np
import pytest

from hydroforge.uncertainty import (
    BinaryStateFlipUncertainty,
    NoUncertainty,
    Parameter,
    ParameterType,
)


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
