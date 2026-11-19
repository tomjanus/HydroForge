"""Stage 2 catalog tests (#40): every registered distribution/uncertainty.

Full catalog loading, construction, alias canonicalization, tuple/list
canonicalization, and the seed-to-generator adapter.
"""

from __future__ import annotations

import json

import pytest

from hydroforge.uncertainty import (
    AdditiveUncertainty,
    BinaryStateFlipUncertainty,
    BiasUncertainty,
    CategoricalRandomReplacementUncertainty,
    CategoricalReplacementUncertainty,
    MultiplicativeUncertainty,
    NoUncertainty,
    Parameter,
    ParameterType,
)
from hydroforge.uncertainty.distributions import (
    CategoricalHistogramDistribution,
    CategoricalNormalDistribution,
    CategoricalUniformDistribution,
    ContinuousDiracDeltaDistribution,
    DiscreteDiracDeltaDistribution,
    CategoricalDiracDeltaDistribution,
    DiscreteHistogramDistribution,
    DiscreteNormalDistribution,
    DiscreteUniformDistribution,
    NormalDistribution,
    UniformDistribution,
)
from hydroforge.uncertainty.specification import (
    SpecificationValidationError,
    UncertaintySpecification,
    save_specification,
)
from hydroforge.uncertainty.specification.registry import (
    distribution_type_names,
    uncertainty_type_names,
)

EXPECTED_DISTRIBUTION_NAMES = [
    "CategoricalHistogram",
    "CategoricalNormal",
    "CategoricalUniform",
    "ContinuousDiracDelta",
    "CategoricalDiracDelta",
    "DiscreteDiracDelta",
    "DiscreteHistogram",
    "DiscreteNormal",
    "DiscreteUniform",
    "Normal",
    "Uniform",
]

EXPECTED_UNCERTAINTY_NAMES = [
    "Additive",
    "Bias",
    "BinaryStateFlip",
    "CategoricalRandomReplacement",
    "CategoricalReplacement",
    "Multiplicative",
    "No",
]

VALID_DISTRIBUTIONS = {
    "Normal": {"mean": 0.0, "std_dev": 1.0},
    "Uniform": {"lower": 0.0, "upper": 1.0},
    "ContinuousDiracDelta": {"value": 1.5},
    "DiscreteDiracDelta": {"value": 3},
    "CategoricalDiracDelta": {"value": "on"},
    "DiscreteNormal": {"mean": 3, "std_dev": 1.0},
    "DiscreteUniform": {"lower": 0, "upper": 5},
    "DiscreteHistogram": {"values": [1.0, 2.0], "probabilities": [0.5, 0.5]},
    "CategoricalNormal": {
        "categories": ["a", "b", "c"],
        "spread": 1.0,
        "nominal_category": "b",
    },
    "CategoricalUniform": {"categories": ["a", "b", "c"], "nominal_category": "b"},
    "CategoricalHistogram": {"categories": ["a", "b"], "probabilities": [0.5, 0.5]},
}

LIVE_DISTRIBUTION_CLASSES = {
    "Normal": NormalDistribution,
    "Uniform": UniformDistribution,
    "ContinuousDiracDelta": ContinuousDiracDeltaDistribution,
    "DiscreteDiracDelta": DiscreteDiracDeltaDistribution,
    "CategoricalDiracDelta": CategoricalDiracDeltaDistribution,
    "DiscreteNormal": DiscreteNormalDistribution,
    "DiscreteUniform": DiscreteUniformDistribution,
    "DiscreteHistogram": DiscreteHistogramDistribution,
    "CategoricalNormal": CategoricalNormalDistribution,
    "CategoricalUniform": CategoricalUniformDistribution,
    "CategoricalHistogram": CategoricalHistogramDistribution,
}

VALID_UNCERTAINTIES = {
    "No": {},
    "Additive": {
        "distribution": {"type": "Normal", "parameters": VALID_DISTRIBUTIONS["Normal"]}
    },
    "Multiplicative": {
        "distribution": {
            "type": "Uniform",
            "parameters": VALID_DISTRIBUTIONS["Uniform"],
        }
    },
    "Bias": {"bias": 0.1},
    "CategoricalRandomReplacement": {
        "distribution": {
            "type": "CategoricalUniform",
            "parameters": VALID_DISTRIBUTIONS["CategoricalUniform"],
        }
    },
    "CategoricalReplacement": {
        "flip_distribution": {
            "type": "Uniform",
            "parameters": VALID_DISTRIBUTIONS["Uniform"],
        },
        "replacement_distribution": {
            "type": "CategoricalUniform",
            "parameters": VALID_DISTRIBUTIONS["CategoricalUniform"],
        },
    },
    "BinaryStateFlip": {
        "flip_prob": 0.5,
        "states": ["OPEN", "CLOSED"],
        "seed": 7,
    },
}

LIVE_UNCERTAINTY_CLASSES = {
    "No": NoUncertainty,
    "Additive": AdditiveUncertainty,
    "Multiplicative": MultiplicativeUncertainty,
    "Bias": BiasUncertainty,
    "CategoricalRandomReplacement": CategoricalRandomReplacementUncertainty,
    "CategoricalReplacement": CategoricalReplacementUncertainty,
    "BinaryStateFlip": BinaryStateFlipUncertainty,
}


def _document(uncertainty_type: str, parameters: dict) -> dict:
    return {
        "schema_version": "1.0",
        "parameters": {
            "p1": {
                "nominal_value": 1.0,
                "uncertainty": {"type": uncertainty_type, "parameters": parameters},
            }
        },
    }


def _spec(uncertainty_type: str, parameters: dict) -> UncertaintySpecification:
    return UncertaintySpecification.from_dict(_document(uncertainty_type, parameters))


# ---------------------------------------------------------------
# Registry inventory
# ---------------------------------------------------------------


def test_distribution_registry_contains_all_concrete_classes():
    names = distribution_type_names()
    assert sorted(names) == sorted(EXPECTED_DISTRIBUTION_NAMES)
    assert "DiracDelta" not in names  # the generic stays unregistered


def test_uncertainty_registry_contains_all_concrete_classes():
    assert sorted(uncertainty_type_names()) == sorted(EXPECTED_UNCERTAINTY_NAMES)


# ---------------------------------------------------------------
# Full catalog: load, construct, round-trip
# ---------------------------------------------------------------


@pytest.mark.parametrize("uncertainty_type", sorted(VALID_UNCERTAINTIES))
def test_every_uncertainty_loads_constructs_and_round_trips(uncertainty_type):
    spec = _spec(
        uncertainty_type,
        {
            key: (
                {"type": value["type"], "parameters": dict(value["parameters"])}
                if isinstance(value, dict)
                else value
            )
            for key, value in VALID_UNCERTAINTIES[uncertainty_type].items()
        },
    )

    parameter = spec.create_parameter("p1")
    assert isinstance(parameter, Parameter)
    assert type(parameter.uncertainty) is LIVE_UNCERTAINTY_CLASSES[uncertainty_type]

    payload = spec.to_dict()
    assert UncertaintySpecification.from_dict(payload) == spec


@pytest.mark.parametrize("distribution_type", sorted(VALID_DISTRIBUTIONS))
def test_every_distribution_loads_constructs_and_round_trips(distribution_type):
    spec = UncertaintySpecification.from_dict(
        {
            "schema_version": "1.0",
            "parameters": {
                "p1": {
                    "nominal_value": 1.0,
                    "uncertainty": {
                        "type": "Additive",
                        "parameters": {
                            "distribution": {
                                "type": distribution_type,
                                "parameters": VALID_DISTRIBUTIONS[distribution_type],
                            }
                        },
                    },
                }
            },
        }
    )

    distribution = spec.create_parameter("p1").uncertainty.distribution
    assert type(distribution) is LIVE_DISTRIBUTION_CLASSES[distribution_type]

    payload = spec.to_dict()
    stored = payload["parameters"]["p1"]["uncertainty"]["parameters"]["distribution"]
    assert stored["type"] == distribution_type
    assert UncertaintySpecification.from_dict(payload) == spec


@pytest.mark.parametrize("distribution_type", sorted(VALID_DISTRIBUTIONS))
def test_distribution_full_class_name_aliases_canonicalise(distribution_type):
    class_name = LIVE_DISTRIBUTION_CLASSES[distribution_type].__name__
    spec = UncertaintySpecification.from_dict(
        {
            "schema_version": "1.0",
            "parameters": {
                "p1": {
                    "nominal_value": 1.0,
                    "uncertainty": {
                        "type": "AdditiveUncertainty",
                        "parameters": {
                            "distribution": {
                                "type": class_name,
                                "parameters": VALID_DISTRIBUTIONS[distribution_type],
                            }
                        },
                    },
                }
            },
        }
    )

    stored = spec.to_dict()["parameters"]["p1"]["uncertainty"]
    assert stored["type"] == "Additive"
    assert stored["parameters"]["distribution"]["type"] == distribution_type


# ---------------------------------------------------------------
# Tuple/list canonicalization (ADR-0002 decision 4)
# ---------------------------------------------------------------


def test_tuple_fields_accept_lists_and_serialize_as_lists():
    spec = _spec("BinaryStateFlip", VALID_UNCERTAINTIES["BinaryStateFlip"])

    payload = spec.to_dict()
    states = payload["parameters"]["p1"]["uncertainty"]["parameters"]["states"]
    assert isinstance(states, list)
    assert states == ["OPEN", "CLOSED"]


def test_scalar_instead_of_list_is_rejected_for_states():
    parameters = dict(VALID_UNCERTAINTIES["BinaryStateFlip"])
    parameters["states"] = "OPEN"

    with pytest.raises(SpecificationValidationError) as exc:
        _spec("BinaryStateFlip", parameters)

    issue = next(
        candidate
        for candidate in exc.value.errors
        if candidate.path == "parameters.p1.uncertainty.parameters.states"
    )
    assert "list" in issue.message


def test_wrong_list_length_is_rejected_for_states():
    parameters = dict(VALID_UNCERTAINTIES["BinaryStateFlip"])
    parameters["states"] = ["OPEN", "CLOSED", "HALF"]

    with pytest.raises(SpecificationValidationError):
        _spec("BinaryStateFlip", parameters)


def test_histogram_values_shuffle_loads_and_live_object_is_sorted():
    parameters = {
        "values": [2.0, 1.0],
        "probabilities": [0.5, 0.5],
    }
    spec = _spec(
        "Additive",
        {"distribution": {"type": "DiscreteHistogram", "parameters": parameters}},
    )

    distribution = spec.create_parameter("p1").uncertainty.distribution
    assert list(distribution.values) == [1.0, 2.0]  # runtime __post_init__ sorts

    payload = spec.to_dict()
    stored = payload["parameters"]["p1"]["uncertainty"]["parameters"]["distribution"][
        "parameters"
    ]
    assert stored["values"] == [2.0, 1.0]  # definitions preserved verbatim
    assert json.dumps(payload)  # document payload is JSON-native


def test_second_save_is_byte_stable(tmp_path):
    spec = _spec(
        "Additive",
        {
            "distribution": {
                "type": "DiscreteHistogram",
                "parameters": {"values": [2.0, 1.0], "probabilities": [0.5, 0.5]},
            }
        },
    )
    path = tmp_path / "spec.yaml"

    save_specification(spec, path)
    first = path.read_bytes()
    from hydroforge.uncertainty.specification import load_specification

    save_specification(load_specification(path), path)
    assert path.read_bytes() == first


# ---------------------------------------------------------------
# Seed adapter (ADR-0002 decision 5)
# ---------------------------------------------------------------


def test_binary_state_flip_seed_is_deterministic():
    spec = _spec("BinaryStateFlip", VALID_UNCERTAINTIES["BinaryStateFlip"])

    first = spec.create_parameter("p1")
    second = spec.create_parameter("p1")
    sequence_a = [first.uncertainty.apply("OPEN") for _ in range(20)]
    sequence_b = [second.uncertainty.apply("OPEN") for _ in range(20)]
    assert sequence_a == sequence_b


def test_binary_state_flip_null_seed_still_constructs():
    parameters = dict(VALID_UNCERTAINTIES["BinaryStateFlip"])
    parameters["seed"] = None
    spec = _spec("BinaryStateFlip", parameters)

    parameter = spec.create_parameter("p1")
    assert isinstance(parameter.uncertainty, BinaryStateFlipUncertainty)


def test_generators_never_appear_in_documents():
    spec = _spec("BinaryStateFlip", VALID_UNCERTAINTIES["BinaryStateFlip"])

    payload = spec.to_dict()
    serialized = json.dumps(payload)  # a generator object would not survive this
    uncertainty_parameters = payload["parameters"]["p1"]["uncertainty"]["parameters"]
    assert "seed" in uncertainty_parameters
    assert "rng" not in uncertainty_parameters
    assert serialized


def test_seed_rejected_for_uncertainties_without_generators():
    with pytest.raises(SpecificationValidationError):
        _spec("Bias", {"bias": 0.1, "seed": 3})


def test_seed_must_be_integer_or_null():
    with pytest.raises(SpecificationValidationError):
        _spec(
            "BinaryStateFlip",
            {**VALID_UNCERTAINTIES["BinaryStateFlip"], "seed": "seven"},
        )


# ---------------------------------------------------------------
# Nested definitions everywhere (CategoricalReplacement double slot)
# ---------------------------------------------------------------


def test_categoricalreplacement_validates_both_nested_slots_deeply():
    parameters = {
        "flip_distribution": {
            "type": "Kernel",
            "parameters": VALID_DISTRIBUTIONS["Uniform"],
        },
        "replacement_distribution": {
            "type": "CategoricalUniform",
            "parameters": VALID_DISTRIBUTIONS["CategoricalUniform"],
        },
    }

    with pytest.raises(SpecificationValidationError) as exc:
        _spec("CategoricalReplacement", parameters)

    assert any(
        issue.path == "parameters.p1.uncertainty.parameters.flip_distribution.type"
        for issue in exc.value.errors
    )


def test_semantic_failures_surface_at_construction_unwrapped():
    # even number of categories without a nominal category: shape-valid,
    # semantically rejected by the runtime constructor
    parameters = {
        "flip_distribution": {
            "type": "Uniform",
            "parameters": VALID_DISTRIBUTIONS["Uniform"],
        },
        "replacement_distribution": {
            "type": "CategoricalUniform",
            "parameters": {"categories": ["a", "b"]},
        },
    }
    spec = _spec("CategoricalReplacement", parameters)

    with pytest.raises(ValueError):
        spec.create_parameter("p1")


# ---------------------------------------------------------------
# Canonical example document
# ---------------------------------------------------------------


def test_canonical_parameters_example_loads_and_constructs():
    from pathlib import Path

    from hydroforge.uncertainty.specification import load_specification

    path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "uncertainty_definitions"
        / "definition_ex2_parameters.json"
    )

    spec = load_specification(path)

    assert sorted(spec.parameters) == [
        "demand_multiplier",
        "pipe_102_diameter",
        "valve_A_state",
    ]
    diameter = spec.create_parameter("pipe_102_diameter")
    assert diameter.type is ParameterType.NUMERICAL
    assert diameter.metadata["unit"] == "mm"
    valve = spec.create_parameter("valve_A_state")
    assert isinstance(valve.uncertainty, BinaryStateFlipUncertainty)
    payload = spec.to_dict()
    # canonical output materializes defaults; the guarantee is that the
    # canonical form is self-stable and semantically equal to the source
    assert UncertaintySpecification.from_dict(payload).to_dict() == payload
    with path.open(encoding="utf-8") as handle:
        source = json.load(handle)
    assert payload["schema_version"] == source["schema_version"]
    for name, definition in source["parameters"].items():
        for key, value in definition.items():
            assert payload["parameters"][name][key] == value
