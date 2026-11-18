"""Tests for constructing live sensors from uncertainty specifications."""

import pytest

from hydroforge.measurements import (
    CompositeSensor,
    DeadBandSensor,
    DriftSensor,
    FixedPrecisionSensor,
    OffsetSensor,
    PerfectSensor,
    RandomNoiseSensor,
    SaturationSensor,
    SensitivityErrorSensor,
)
from hydroforge.uncertainty.specification import (
    SpecificationValidationError,
    UncertaintySpecification,
)


def _spec(sensor_type, parameters, **extra):
    return UncertaintySpecification.from_dict(
        {
            "schema_version": "1.0",
            "sensors": {
                "sensor1": {"type": sensor_type, "parameters": parameters, **extra}
            },
        }
    )


def test_create_sensor_from_single_fixed_precision_definition():
    spec = _spec("FixedPrecision", {"delta_y": 0.1})

    sensor = spec.create_sensor("sensor1")

    assert type(sensor) is FixedPrecisionSensor
    assert sensor.delta_y == 0.1


@pytest.mark.parametrize(
    ("sensor_type", "parameters", "expected_type", "expected_attributes"),
    [
        ("Perfect", {}, PerfectSensor, {}),
        ("FixedPrecision", {"delta_y": 0.1}, FixedPrecisionSensor, {"delta_y": 0.1}),
        (
            "RandomNoise",
            {"sigma": 0.05, "seed": 42},
            RandomNoiseSensor,
            {"sigma": 0.05},
        ),
        ("Offset", {"offset": 0.2}, OffsetSensor, {"offset": 0.2}),
        (
            "SensitivityError",
            {"scale": 1.05},
            SensitivityErrorSensor,
            {"scale": 1.05},
        ),
        ("DeadBand", {"threshold": 0.05}, DeadBandSensor, {"threshold": 0.05}),
        (
            "Saturation",
            {"min_val": 0.0, "max_val": 1.5},
            SaturationSensor,
            {"min_val": 0.0, "max_val": 1.5},
        ),
        ("Drift", {"offset_rate": 0.01}, DriftSensor, {"offset_rate": 0.01}),
    ],
)
def test_create_sensor_for_each_registered_type(
    sensor_type, parameters, expected_type, expected_attributes
):
    spec = _spec(sensor_type, parameters)

    sensor = spec.create_sensor("sensor1")

    assert type(sensor) is expected_type
    for name, value in expected_attributes.items():
        assert getattr(sensor, name) == value


def test_full_class_name_constructs_same_sensor():
    spec = _spec("FixedPrecisionSensor", {"delta_y": 0.25})

    sensor = spec.create_sensor("sensor1")

    assert type(sensor) is FixedPrecisionSensor
    assert sensor.delta_y == 0.25


def test_composite_definition_constructs_composite_sensor():
    spec = UncertaintySpecification.from_dict(
        {
            "schema_version": "1.0",
            "sensors": {
                "sensor1": {
                    "type": "Composite",
                    "parameters": {
                        "sensors": [
                            {"type": "FixedPrecision", "parameters": {"delta_y": 0.1}},
                            {"type": "Offset", "parameters": {"offset": 0.5}},
                        ]
                    },
                }
            },
        }
    )

    sensor = spec.create_sensor("sensor1")

    assert type(sensor) is CompositeSensor
    assert [type(item) for item in sensor.sensors] == [
        FixedPrecisionSensor,
        OffsetSensor,
    ]
    assert sensor.sensors[0].delta_y == 0.1
    assert sensor.sensors[1].offset == 0.5


def test_composite_rejects_invalid_nested_definition():
    spec = {
        "schema_version": "1.0",
        "sensors": {
            "sensor1": {
                "type": "Composite",
                "parameters": {
                    "sensors": [{"type": "FixedPrecision", "parameters": {}}]
                },
            }
        },
    }

    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(spec)

    assert (
        exc.value.errors[0].path
        == "sensors.sensor1.parameters.sensors.0.parameters.delta_y"
    )


def test_composite_rejects_unknown_parameter():
    spec = {
        "schema_version": "1.0",
        "sensors": {
            "sensor1": {
                "type": "Composite",
                "parameters": {"components": []},
            }
        },
    }

    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(spec)

    assert exc.value.errors[0].path == "sensors.sensor1.parameters.components"


def test_location_is_preserved_through_load_and_serialisation():
    spec = _spec("FixedPrecision", {"delta_y": 0.1}, location="J1")

    serialised = spec.to_dict()

    assert spec.sensors["sensor1"].location == "J1"
    assert serialised["sensors"]["sensor1"]["location"] == "J1"


def test_internal_state_fields_are_not_valid_parameters():
    with pytest.raises(SpecificationValidationError) as exc:
        _spec("Drift", {"offset_rate": 0.01, "current_offset": 1.0})
    assert exc.value.errors[0].path == "sensors.sensor1.parameters.current_offset"

    with pytest.raises(SpecificationValidationError) as exc:
        _spec("RandomNoise", {"sigma": 0.1, "_rng": 123})
    assert exc.value.errors[0].path == "sensors.sensor1.parameters._rng"


def test_unknown_sensor_name_raises_specification_error():
    from hydroforge.uncertainty.specification import SpecificationError

    spec = _spec("FixedPrecision", {"delta_y": 0.1})

    with pytest.raises(SpecificationError):
        spec.create_sensor("missing")
