"""Stage 2 guarantee tests (#41): full failure matrix, JSON Schema, round-trips.

Validation completeness for the parameter layer: every failure mode reports a
dotted path with collect-all semantics, the envelope schema covers parameters,
and the ADR-0002 round-trip guarantees hold for every registry entry.
"""

from __future__ import annotations

import json
from enum import Enum

import numpy as np
import pytest

from test_uncertainty_specification_catalog import VALID_UNCERTAINTIES

from hydroforge.uncertainty.specification import (
    UncertaintySpecification,
    load_specification,
    save_specification,
)
from hydroforge.uncertainty.specification.exceptions import (
    SpecificationValidationError,
)

PARAMETERS_ONLY = {
    "schema_version": "1.0",
    "parameters": {
        "p1": {
            "nominal_value": 1.0,
            "uncertainty": {
                "type": "Additive",
                "parameters": {
                    "distribution": {
                        "type": "Normal",
                        "parameters": {"mean": 0.0, "std_dev": 1.0},
                    }
                },
            },
        }
    },
}


def _mutate(**path_value) -> dict:
    """Deep-copy PARAMETERS_ONLY and set ``path_value`` along a dotted path."""
    document = json.loads(json.dumps(PARAMETERS_ONLY))
    dotted, value = next(iter(path_value.items()))
    node = document
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value
    return document


def _errors(document) -> set[str]:
    with pytest.raises(SpecificationValidationError) as exc:
        UncertaintySpecification.from_dict(document)
    return {issue.path for issue in exc.value.errors}


# ---------------------------------------------------------------
# Failure matrix with dotted paths (spec #36 success criteria)
# ---------------------------------------------------------------


def test_missing_schema_version_reports_path():
    document = json.loads(json.dumps(PARAMETERS_ONLY))
    del document["schema_version"]
    assert _errors(document) == {"schema_version"}


def test_unknown_top_level_key_reported_with_parameter_paths():
    document = _mutate(**{"extra_section": {"x": 1}})
    paths = _errors(document)
    assert "extra_section" in paths


def test_non_string_parameter_name_reported():
    document = _mutate(**{"parameters": {2: {"nominal_value": 1.0}}})
    assert "parameters.2" in _errors(document)


def test_parameter_entry_must_be_mapping():
    assert _errors(_mutate(**{"parameters": {"p1": [1, 2]}})) == {"parameters.p1"}


def test_nominal_value_missing():
    document = _mutate(**{"parameters": {"p1": {"type": "NUMERICAL"}}})
    assert "parameters.p1.nominal_value" in _errors(document)


def test_enum_nominal_value_is_not_documentable():
    class Mode(Enum):
        HIGH = 1

    document = _mutate(**{"parameters": {"p1": {"nominal_value": Mode.HIGH}}})
    assert "parameters.p1.nominal_value" in _errors(document)


def test_numpy_scalar_nominal_value_is_accepted():
    document = _mutate(**{"parameters": {"p1": {"nominal_value": np.float64(2.5)}}})
    spec = UncertaintySpecification.from_dict(document)
    assert spec.create_parameter("p1").nominal_value == pytest.approx(2.5)


def test_generator_object_cannot_stand_in_for_nested_definition():
    document = _mutate(
        **{
            "parameters": {
                "p1": {
                    "nominal_value": 1.0,
                    "uncertainty": {
                        "type": "Additive",
                        "parameters": {"distribution": np.random.default_rng(1)},
                    },
                }
            }
        }
    )
    assert "parameters.p1.uncertainty.parameters.distribution" in _errors(document)


def test_nested_unknown_parameter_and_missing_required_paths():
    document = _mutate(
        **{
            "parameters": {
                "p1": {
                    "nominal_value": 1.0,
                    "uncertainty": {
                        "type": "Normal",  # wrong family: not an uncertainty
                        "parameters": {},
                    },
                }
            }
        }
    )
    assert "parameters.p1.uncertainty.type" in _errors(document)


def test_rtol_is_unknown_everywhere_it_cannot_be_a_field():
    document = _mutate(
        **{
            "parameters": {
                "p1": {
                    "nominal_value": 1.0,
                    "uncertainty": {
                        "type": "Additive",
                        "parameters": {
                            "distribution": {
                                "type": "DiscreteHistogram",
                                "parameters": {
                                    "values": [1.0],
                                    "probabilities": [1.0],
                                    "rtol": 1e-9,
                                },
                            }
                        },
                    },
                }
            }
        }
    )
    assert (
        "parameters.p1.uncertainty.parameters.distribution.parameters.rtol"
        in _errors(document)
    )


def test_model_section_shape_checked_as_dict():
    document = _mutate(**{"model": ["not", "a", "mapping"]})
    assert "model" in _errors(document)


def test_problems_across_sections_are_collected_together():
    document = {
        "schema_version": "2.0",
        "sensors": {"s1": {"type": "Nope", "parameters": {}}},
        "parameters": {"p1": {"nominal_value": [1]}},
        "bogus": 1,
    }
    paths = _errors(document)
    assert "schema_version" in paths
    assert "sensors.s1.type" in paths
    assert "parameters.p1.nominal_value" in paths
    assert "bogus" in paths


def test_semantic_rules_are_never_applied_at_load_time():
    document = _mutate(
        **{
            "parameters": {
                "p1": {
                    "nominal_value": 1.0,
                    "uncertainty": {
                        "type": "Additive",
                        "parameters": {
                            "distribution": {
                                "type": "Normal",
                                "parameters": {"mean": 0.0, "std_dev": 0.0},
                            }
                        },
                    },
                }
            }
        }
    )
    spec = UncertaintySpecification.from_dict(document)  # shape-valid
    with pytest.raises(ValueError):
        spec.create_parameter("p1")


# ---------------------------------------------------------------
# JSON Schema coverage
# ---------------------------------------------------------------


def test_json_schema_covers_parameters_section():
    schema = UncertaintySpecification.json_schema()

    assert "parameters" in schema["properties"]
    definitions = schema["$defs"]
    assert "ParameterDefinition" in definitions
    parameter_schema = definitions["ParameterDefinition"]
    assert "nominal_value" in parameter_schema["required"]
    assert set(parameter_schema["properties"]) == {
        "nominal_value",
        "uncertainty",
        "type",
        "infer_type_from_data",
        "metadata",
    }
    # sensors remain covered as well
    assert "SensorDefinition" in definitions


def test_json_schema_is_json_serializable():
    json.dumps(UncertaintySpecification.json_schema())


# ---------------------------------------------------------------
# Round-trip guarantees for every uncertainty registry entry
# ---------------------------------------------------------------


def _parameter_document(uncertainty_type: str, parameters: dict) -> dict:
    return {
        "schema_version": "1.0",
        "parameters": {
            "p1": {
                "nominal_value": 1.0,
                "uncertainty": {"type": uncertainty_type, "parameters": parameters},
            },
        },
    }


@pytest.mark.parametrize("uncertainty_type", sorted(VALID_UNCERTAINTIES))
def test_round_trip_guarantees_across_dict_json_and_yaml(uncertainty_type, tmp_path):
    spec = UncertaintySpecification.from_dict(
        _parameter_document(uncertainty_type, VALID_UNCERTAINTIES[uncertainty_type])
    )

    # load -> object -> dict -> object is equality-stable
    payload = spec.to_dict()
    assert UncertaintySpecification.from_dict(payload) == spec

    # file round-trips and byte stability from the first canonical save
    for suffix in (".json", ".yaml"):
        path = tmp_path / f"spec{suffix}"
        save_specification(spec, path)
        reloaded = load_specification(path)
        assert reloaded == spec
        first = path.read_bytes()
        save_specification(reloaded, path)
        assert path.read_bytes() == first


@pytest.mark.parametrize("uncertainty_type", sorted(VALID_UNCERTAINTIES))
def test_every_round_tripped_definition_still_constructs(uncertainty_type):
    spec = UncertaintySpecification.from_dict(
        _parameter_document(uncertainty_type, VALID_UNCERTAINTIES[uncertainty_type])
    )

    original = spec.create_parameter("p1")
    reloaded = UncertaintySpecification.from_dict(spec.to_dict())
    rebuilt = reloaded.create_parameter("p1")

    assert type(original.uncertainty) is type(rebuilt.uncertainty)
    assert original.nominal_value == rebuilt.nominal_value
    assert original.metadata == rebuilt.metadata
