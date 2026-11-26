"""Tests for uncertainty specification validation."""

import pytest

from hydroforge.uncertainty.specification import (
    SensorDefinition,
    SpecificationValidationError,
    UncertaintySpecification,
)

BASE = {
    "schema_version": "1.0",
    "sensors": {"sensor1": {"type": "FixedPrecision", "parameters": {"delta_y": 0.1}}},
}


def test_valid_minimal_specification_loads():
    spec = UncertaintySpecification.from_dict(BASE)

    assert spec.schema_version == "2.0"
    assert set(spec.sensors) == {"sensor1"}


def test_missing_schema_version_is_reported():
    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict({"sensors": {}})

    assert exc.value.errors[0].path == "schema_version"


def test_unsupported_schema_version_is_reported():
    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict({"schema_version": "3.0", "sensors": {}})

    assert exc.value.errors[0].path == "schema_version"


def test_both_alias_keys_are_rejected():
    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(
            {"schema_version": "1.0", "sensors": {}, "measurements": {}}
        )

    assert any(issue.path == "sensors" for issue in exc.value.errors)


def test_unknown_sensor_type_lists_supported_types():
    data = {
        "schema_version": "1.0",
        "sensors": {"sensor1": {"type": "Nope", "parameters": {}}},
    }

    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(data)

    assert exc.value.errors[0].path == "sensors.sensor1.type"
    assert "FixedPrecision" in exc.value.errors[0].message


def test_missing_required_parameter_is_reported():
    data = {
        "schema_version": "1.0",
        "sensors": {"sensor1": {"type": "FixedPrecision", "parameters": {}}},
    }

    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(data)

    assert exc.value.errors[0].path == "sensors.sensor1.parameters.delta_y"


def test_unknown_parameter_lists_allowed_parameters():
    data = {
        "schema_version": "1.0",
        "sensors": {
            "sensor1": {
                "type": "FixedPrecision",
                "parameters": {"delta_y": 0.1, "foo": 1},
            }
        },
    }

    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(data)

    assert exc.value.errors[0].path == "sensors.sensor1.parameters.foo"
    assert "delta_y" in exc.value.errors[0].message


def test_wrong_parameter_type_is_rejected():
    data = {
        "schema_version": "1.0",
        "sensors": {
            "sensor1": {"type": "FixedPrecision", "parameters": {"delta_y": "high"}}
        },
    }

    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(data)

    assert exc.value.errors[0].path == "sensors.sensor1.parameters.delta_y"


def test_boolean_is_rejected_for_numeric_parameter():
    data = {
        "schema_version": "1.0",
        "sensors": {
            "sensor1": {"type": "FixedPrecision", "parameters": {"delta_y": True}}
        },
    }

    with pytest.raises(SpecificationValidationError):
        UncertaintySpecification.from_dict(data)


def test_integer_is_accepted_for_float_parameter():
    data = {
        "schema_version": "1.0",
        "sensors": {
            "sensor1": {"type": "FixedPrecision", "parameters": {"delta_y": 1}}
        },
    }

    spec = UncertaintySpecification.from_dict(data)

    assert spec.sensors["sensor1"].parameters["delta_y"] == 1


def test_unknown_sensor_key_is_rejected():
    data = {
        "schema_version": "1.0",
        "sensors": {
            "sensor1": {
                "type": "FixedPrecision",
                "parameters": {"delta_y": 0.1},
                "bogus": 1,
            }
        },
    }

    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(data)

    assert exc.value.errors[0].path == "sensors.sensor1.bogus"


def test_unknown_top_level_key_is_rejected():
    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(
            {"schema_version": "1.0", "sensors": {}, "bogus": 1}
        )

    assert exc.value.errors[0].path == "bogus"


def test_multiple_problems_are_collected():
    data = {
        "sensors": {
            "sensor1": {"type": "Nope", "parameters": {"foo": 1}},
            "sensor2": {"type": "FixedPrecision", "parameters": {}},
        }
    }

    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(data)

    assert len(exc.value.errors) >= 3


def test_standalone_sensor_definition_validates():
    with pytest.raises(SpecificationValidationError):
        SensorDefinition(type="FixedPrecision", parameters={})


def test_standalone_sensor_definition_rejects_unknown_key_as_public_error():
    with pytest.raises(SpecificationValidationError):
        SensorDefinition(type="FixedPrecision", parameters={"delta_y": 0.1}, bogus=1)


def test_mixed_structural_and_semantic_problems_are_collected():
    data = {
        "schema_version": "9.9",
        "sensors": {"sensor1": {"type": "Nope", "parameters": {}}},
        "bogus": 1,
    }

    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(data)

    paths = {issue.path for issue in exc.value.errors}
    assert "schema_version" in paths
    assert "sensors.sensor1.type" in paths
    assert "bogus" in paths


def test_sensor_type_names_lists_canonical_types_only():
    from hydroforge.uncertainty.specification import sensor_type_names

    names = sensor_type_names()

    assert len(names) == 9
    assert all(not name.endswith("Sensor") for name in names)
    assert "FixedPrecision" in names
    assert "Composite" in names


def test_json_schema_describes_the_envelope():
    schema = UncertaintySpecification.json_schema()

    assert schema["title"] == "UncertaintySpecification"
    assert "schema_version" in schema["properties"]
    assert "sensors" in schema["properties"]
    assert "SensorDefinition" in schema["$defs"]


def test_json_schema_requires_schema_version():
    schema = UncertaintySpecification.json_schema()

    assert "schema_version" in schema.get("required", [])


def test_single_validation_error_exposes_its_path():
    data = {
        "schema_version": "1.0",
        "sensors": {"sensor1": {"type": "FixedPrecision", "parameters": {}}},
    }

    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(data)

    assert exc.value.path == "sensors.sensor1.parameters.delta_y"


def test_specification_layer_does_not_import_wdn_modelling():
    """The specification layer is generic and must not pull in WDN modelling."""
    import sys

    for module in list(sys.modules):
        if module == "hydroforge.wdn_modelling" or module.startswith(
            "hydroforge.wdn_modelling."
        ):
            del sys.modules[module]

    import hydroforge.uncertainty.specification  # noqa: F401

    assert not any(name.startswith("hydroforge.wdn_modelling") for name in sys.modules)
