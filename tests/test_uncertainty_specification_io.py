"""Tests for loading and saving uncertainty specifications."""

import json
from pathlib import Path

import pytest

from hydroforge.uncertainty.specification import (
    SpecificationFormatError,
    load_specification,
    save_specification,
)

SPEC = {
    "schema_version": "1.0",
    "sensors": {"sensor1": {"type": "FixedPrecision", "parameters": {"delta_y": 0.1}}},
}


def test_load_from_dict_and_round_trip_through_json(tmp_path):
    spec = load_specification(SPEC)

    path = tmp_path / "spec.json"
    save_specification(spec, path)
    reloaded = load_specification(path)

    assert reloaded == spec
    assert (
        json.loads(path.read_text(encoding="utf-8"))["sensors"]["sensor1"]["type"]
        == "FixedPrecision"
    )


def test_load_from_yaml_and_round_trip(tmp_path):
    spec = load_specification(SPEC)

    path = tmp_path / "spec.yaml"
    save_specification(spec, path)

    assert load_specification(path) == spec


def test_measurements_alias_loads_and_serialises_as_sensors():
    data = {
        "schema_version": "1.0",
        "measurements": {
            "sensor1": {"type": "FixedPrecision", "parameters": {"delta_y": 0.5}}
        },
    }

    spec = load_specification(data)

    assert "sensor1" in spec.sensors
    assert "sensors" in spec.to_dict()
    assert "measurements" not in spec.to_dict()


def test_full_class_name_alias_loads_and_serialises_as_short_name():
    data = {
        "schema_version": "1.0",
        "sensors": {
            "sensor1": {
                "type": "FixedPrecisionSensor",
                "parameters": {"delta_y": 0.5},
            }
        },
    }

    spec = load_specification(data)

    assert spec.to_dict()["sensors"]["sensor1"]["type"] == "FixedPrecision"


def test_unsupported_suffix_raises_format_error(tmp_path):
    with pytest.raises(SpecificationFormatError):
        load_specification(tmp_path / "spec.txt")

    spec = load_specification(SPEC)
    with pytest.raises(SpecificationFormatError):
        save_specification(spec, tmp_path / "spec.txt")


def test_malformed_json_raises_format_error(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(SpecificationFormatError):
        load_specification(path)


def test_malformed_yaml_raises_format_error(tmp_path):
    path = tmp_path / "spec.yaml"
    path.write_text("sensors: [unclosed", encoding="utf-8")

    with pytest.raises(SpecificationFormatError):
        load_specification(path)


def test_non_mapping_document_raises_format_error(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(SpecificationFormatError):
        load_specification(path)


def test_canonical_example_loads():
    example = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "uncertainty_definitions"
        / "definition_ex1.json"
    )

    spec = load_specification(example)

    assert spec.schema_version == "1.0"
    assert set(spec.sensors) == {"pressure_sensor", "flow_sensor"}
    assert spec.sensors["pressure_sensor"].location == "J1"


def test_round_trip_preserves_explicit_none_optional_parameter(tmp_path):
    data = {
        "schema_version": "1.0",
        "sensors": {
            "sensor1": {
                "type": "RandomNoise",
                "parameters": {"sigma": 0.05, "seed": None},
            }
        },
    }

    spec = load_specification(data)

    json_path = tmp_path / "spec.json"
    yaml_path = tmp_path / "spec.yaml"
    save_specification(spec, json_path)
    save_specification(spec, yaml_path)

    assert spec.to_dict()["sensors"]["sensor1"]["parameters"]["seed"] is None
    assert load_specification(json_path) == spec
    assert load_specification(yaml_path) == spec


def test_save_to_missing_directory_raises_format_error(tmp_path):
    spec = load_specification(SPEC)

    with pytest.raises(SpecificationFormatError):
        save_specification(spec, tmp_path / "missing" / "spec.json")
