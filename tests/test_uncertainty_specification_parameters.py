"""Tests for parameter definitions in uncertainty specification documents (#39).

End-to-end single-parameter slice: ``Additive(Normal)`` loads, validates,
round-trips through dict/JSON/YAML, and constructs a live ``Parameter``.
Only ``Normal`` and ``Additive`` are registered at this stage; the full
catalog is #40.
"""

from __future__ import annotations

import pytest

from hydroforge.measurements import FixedPrecisionSensor
from hydroforge.uncertainty import (
    AdditiveUncertainty,
    NoUncertainty,
    NormalDistribution,
    Parameter,
    ParameterType,
)
from hydroforge.uncertainty.specification import (
    ParameterDefinition,
    SpecificationError,
    SpecificationValidationError,
    UncertaintySpecification,
    load_specification,
    save_specification,
)


def _parameter_document(**overrides) -> dict:
    document = {
        "schema_version": "1.0",
        "parameters": {
            "p1": {
                "nominal_value": 100.0,
                "uncertainty": {
                    "type": "Additive",
                    "parameters": {
                        "distribution": {
                            "type": "Normal",
                            "parameters": {"mean": 0.0, "std_dev": 5.0},
                        }
                    },
                },
            }
        },
    }
    document.update(overrides)
    return document


def _definition(**overrides) -> dict:
    definition = {
        "nominal_value": 100.0,
        "uncertainty": {
            "type": "Additive",
            "parameters": {
                "distribution": {
                    "type": "Normal",
                    "parameters": {"mean": 0.0, "std_dev": 5.0},
                }
            },
        },
    }
    definition.update(overrides)
    return definition


# ---------------------------------------------------------------
# End-to-end happy path
# ---------------------------------------------------------------


def test_valid_document_loads_with_parameters_section():
    spec = UncertaintySpecification.from_dict(_parameter_document())

    assert spec.parameters is not None
    assert set(spec.parameters) == {"p1"}
    assert isinstance(spec.parameters["p1"], ParameterDefinition)
    assert spec.parameters["p1"].nominal_value == 100.0


def test_create_parameter_builds_live_object_tree():
    spec = UncertaintySpecification.from_dict(_parameter_document())

    parameter = spec.create_parameter("p1")

    assert isinstance(parameter, Parameter)
    assert parameter.name == "p1"
    assert parameter.nominal_value == 100.0
    assert isinstance(parameter.uncertainty, AdditiveUncertainty)
    assert isinstance(parameter.uncertainty.distribution, NormalDistribution)
    assert parameter.uncertainty.distribution.mean == 0.0
    assert parameter.uncertainty.distribution.std_dev == 5.0
    # construction-time type inference runs in the live object
    assert parameter.type is ParameterType.NUMERICAL


def test_created_parameter_is_functional():
    spec = UncertaintySpecification.from_dict(_parameter_document())
    parameter = spec.create_parameter("p1")

    value = parameter.sample()
    assert isinstance(float(value), float)
    assert 0.0 <= float(parameter.cdf(105.0)) <= 1.0


def test_full_class_names_are_accepted_as_input_aliases():
    document = _parameter_document()
    definition = document["parameters"]["p1"]
    definition["uncertainty"]["type"] = "AdditiveUncertainty"
    definition["uncertainty"]["parameters"]["distribution"][
        "type"
    ] = "NormalDistribution"

    spec = UncertaintySpecification.from_dict(document)

    payload = spec.to_dict()
    stored = payload["parameters"]["p1"]["uncertainty"]
    assert stored["type"] == "Additive"
    assert stored["parameters"]["distribution"]["type"] == "Normal"


def test_round_trip_through_dict_is_equality_stable():
    spec = UncertaintySpecification.from_dict(_parameter_document())

    payload = spec.to_dict()
    reloaded = UncertaintySpecification.from_dict(payload)

    assert reloaded == spec
    assert reloaded.to_dict() == payload


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_round_trip_through_file(tmp_path, suffix):
    spec = UncertaintySpecification.from_dict(_parameter_document())
    path = tmp_path / f"spec{suffix}"

    save_specification(spec, path)
    reloaded = load_specification(path)

    assert reloaded == spec
    # second save is byte-stable
    first_bytes = path.read_bytes()
    save_specification(reloaded, path)
    assert path.read_bytes() == first_bytes


def test_sensors_and_parameters_coexist():
    document = _parameter_document(
        sensors={"sensor1": {"type": "FixedPrecision", "parameters": {"delta_y": 0.1}}}
    )

    spec = UncertaintySpecification.from_dict(document)

    assert type(spec.create_sensor("sensor1")) is FixedPrecisionSensor
    assert isinstance(spec.create_parameter("p1"), Parameter)


def test_model_section_remains_verbatim_pass_through():
    model = {"some": {"nested": [1, 2, "keys"]}, "kept": True}
    document = _parameter_document(model=model)

    spec = UncertaintySpecification.from_dict(document)

    assert spec.model == model
    assert spec.to_dict()["model"] == model


def test_metadata_is_accepted_verbatim_and_preserved():
    metadata = {"unit": "mm", "source": "calibration", "nested": {"a": [1, 2]}}
    document = _parameter_document()
    document["parameters"]["p1"]["metadata"] = metadata

    spec = UncertaintySpecification.from_dict(document)

    assert spec.parameters["p1"].metadata == metadata
    assert spec.to_dict()["parameters"]["p1"]["metadata"] == metadata


# ---------------------------------------------------------------
# ParameterDefinition field contract (ADR-0002 decision 14)
# ---------------------------------------------------------------


def test_uncertainty_absent_defaults_to_no_uncertainty():
    document = _parameter_document()
    document["parameters"]["p1"] = {"nominal_value": 42.0}

    spec = UncertaintySpecification.from_dict(document)
    parameter = spec.create_parameter("p1")

    assert isinstance(parameter.uncertainty, NoUncertainty)


@pytest.mark.parametrize(
    ("nominal_value", "expected_type"),
    [(100.0, ParameterType.NUMERICAL), (True, ParameterType.BINARY)],
)
def test_nominal_value_types_and_inference(nominal_value, expected_type):
    document = _parameter_document()
    document["parameters"]["p1"] = {"nominal_value": nominal_value}

    spec = UncertaintySpecification.from_dict(document)

    assert spec.create_parameter("p1").type is expected_type


def test_explicit_type_is_honoured_on_the_live_object():
    document = _parameter_document()
    document["parameters"]["p1"]["type"] = "DISCRETE"

    spec = UncertaintySpecification.from_dict(document)

    assert spec.create_parameter("p1").type is ParameterType.DISCRETE


def test_create_unknown_parameter_name_raises():
    spec = UncertaintySpecification.from_dict(_parameter_document())

    with pytest.raises(SpecificationError):
        spec.create_parameter("missing")


# ---------------------------------------------------------------
# Validation failures with dotted paths
# ---------------------------------------------------------------


def _first_path(document) -> str:
    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(document)
    return exc.value.errors[0].path


def test_non_mapping_parameters_section_is_rejected():
    document = _parameter_document(parameters=["not", "a", "mapping"])
    with pytest.raises(SpecificationValidationError):
        UncertaintySpecification.from_dict(document)


def test_non_string_parameter_name_is_rejected():
    document = _parameter_document()
    document["parameters"] = {3: _definition()}
    with pytest.raises(SpecificationValidationError):
        UncertaintySpecification.from_dict(document)


def test_parameter_definition_must_be_a_mapping():
    assert _first_path(_parameter_document(parameters={"p1": 5})) == "parameters.p1"


def test_unknown_key_in_parameter_definition_reports_path():
    document = _parameter_document()
    document["parameters"]["p1"]["bogus"] = 1

    assert _first_path(document) == "parameters.p1.bogus"


def test_missing_nominal_value_reports_path():
    document = _parameter_document()
    document["parameters"]["p1"] = {"uncertainty": {"type": "Additive"}}

    assert _first_path(document) == "parameters.p1.nominal_value"


@pytest.mark.parametrize("bad_value", [None, [1, 2], {"a": 1}])
def test_nominal_value_rejects_non_scalar_types(bad_value):
    document = _parameter_document()
    document["parameters"]["p1"]["nominal_value"] = bad_value

    assert _first_path(document) == "parameters.p1.nominal_value"


def test_unknown_parameter_type_name_is_rejected():
    document = _parameter_document()
    document["parameters"]["p1"]["type"] = "INTEGER"

    assert _first_path(document) == "parameters.p1.type"


def test_unknown_uncertainty_type_lists_registered_names():
    document = _parameter_document()
    document["parameters"]["p1"]["uncertainty"]["type"] = "Multiplicative"

    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(document)

    issue = next(
        candidate
        for candidate in exc.value.errors
        if candidate.path == "parameters.p1.uncertainty.type"
    )
    assert "unknown uncertainty type" in issue.message
    assert "Additive" in issue.message  # only entries registered at this stage


def test_unknown_distribution_type_is_rejected_with_path():
    document = _parameter_document()
    document["parameters"]["p1"]["uncertainty"]["parameters"]["distribution"][
        "type"
    ] = "Uniform"

    assert (
        _first_path(document)
        == "parameters.p1.uncertainty.parameters.distribution.type"
    )


def test_generic_dirac_is_not_documentable():
    document = _parameter_document()
    document["parameters"]["p1"]["uncertainty"]["parameters"]["distribution"][
        "type"
    ] = "DiracDelta"

    with pytest.raises(SpecificationValidationError):
        UncertaintySpecification.from_dict(document)


def test_nested_missing_required_parameter_reports_deep_path():
    document = _parameter_document()
    del document["parameters"]["p1"]["uncertainty"]["parameters"]["distribution"][
        "parameters"
    ]["std_dev"]

    assert (
        _first_path(document)
        == "parameters.p1.uncertainty.parameters.distribution.parameters.std_dev"
    )


def test_nested_wrong_value_type_reports_deep_path():
    document = _parameter_document()
    document["parameters"]["p1"]["uncertainty"]["parameters"]["distribution"][
        "parameters"
    ]["std_dev"] = "wide"

    assert (
        _first_path(document)
        == "parameters.p1.uncertainty.parameters.distribution.parameters.std_dev"
    )


def test_nested_unknown_distribution_parameter_reports_deep_path():
    document = _parameter_document()
    document["parameters"]["p1"]["uncertainty"]["parameters"]["distribution"][
        "parameters"
    ]["variance"] = 1.0

    assert (
        _first_path(document)
        == "parameters.p1.uncertainty.parameters.distribution.parameters.variance"
    )


def test_uncertainty_distribution_must_be_nested_definition():
    document = _parameter_document()
    document["parameters"]["p1"]["uncertainty"]["parameters"][
        "distribution"
    ] = "just a string"

    assert _first_path(document) == "parameters.p1.uncertainty.parameters.distribution"


def test_multiple_parameter_problems_are_collected():
    document = _parameter_document()
    document["parameters"]["p2"] = {"nominal_value": None}
    document["parameters"]["p3"] = 7

    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(document)

    paths = {issue.path for issue in exc.value.errors}
    assert "parameters.p2.nominal_value" in paths
    assert "parameters.p3" in paths


def test_semantic_rules_are_not_applied_at_load_time():
    """std_dev=-1 is shape-valid; it fails only at construction (ADR-0002 §15)."""
    document = _parameter_document()
    document["parameters"]["p1"]["uncertainty"]["parameters"]["distribution"][
        "parameters"
    ]["std_dev"] = -1.0

    spec = UncertaintySpecification.from_dict(document)  # loads fine

    with pytest.raises(ValueError):
        spec.create_parameter("p1")


def test_internal_state_fields_are_not_valid_parameters():
    document = _parameter_document()
    document["parameters"]["p1"]["uncertainty"]["parameters"]["distribution"][
        "parameters"
    ]["_empirical_cache"] = {}

    assert (
        _first_path(document)
        == "parameters.p1.uncertainty.parameters.distribution.parameters"
        "._empirical_cache"
    )


def test_rtol_is_not_a_document_parameter():
    """rtol is a ClassVar (ADR-0002 §4): rejected like any unknown field."""
    document = _parameter_document()
    document["parameters"]["p1"]["uncertainty"]["parameters"]["distribution"][
        "parameters"
    ]["rtol"] = 1e-9

    with pytest.raises(SpecificationValidationError):
        UncertaintySpecification.from_dict(document)


def test_importing_parameter_spec_does_not_import_wdn_modelling():
    """The parameter layer is generic; importing it must not pull in WDN code."""
    import sys

    for module in list(sys.modules):
        if module == "hydroforge.wdn_modelling" or module.startswith(
            "hydroforge.wdn_modelling."
        ):
            del sys.modules[module]

    import hydroforge.uncertainty.specification  # noqa: F401

    assert not any(name.startswith("hydroforge.wdn_modelling") for name in sys.modules)
