"""Tests for the generic Stage 3 model mapping runtime."""

import copy

import pytest

from hydroforge.sampling import Scenario
from hydroforge.uncertainty.specification import UncertaintySpecification
from hydroforge.wdn_modelling.mapping import (
    GenericModelMapper,
    SimulationResult,
)


def _specification() -> UncertaintySpecification:
    return UncertaintySpecification.from_dict(
        {
            "schema_version": "1.0",
            "parameters": {"sigma": {"nominal_value": 0.5}},
            "sensors": {
                "sensor": {
                    "type": "Offset",
                    "parameters": {"offset": {"$parameter": "sigma"}},
                }
            },
        }
    )


def test_realize_does_not_mutate_reusable_baseline():
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    baseline = {"value": 1}

    def apply_parameters(model, scenario, spec):
        model["value"] = scenario.values["x"]

    def run_model(model):
        return {"raw": model["value"]}

    mapper = GenericModelMapper(
        clone_model=copy.deepcopy,
        apply_parameters=apply_parameters,
        run_model=run_model,
    )
    uncertain_model = mapper.map(specification, baseline)

    first = uncertain_model.realize(Scenario(values={"x": 2}, id="first"))
    second = uncertain_model.realize(Scenario(values={"x": 3}, id="second"))

    assert baseline == {"value": 1}
    assert first.run().raw_results == {"raw": 2}
    assert second.run().raw_results == {"raw": 3}
    assert baseline == {"value": 1}


def test_run_preserves_raw_results_and_reports_measured_outputs_and_provenance():
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    baseline = {"value": 5}

    def run_model(model):
        return {"raw": model["value"]}

    def measure(model, raw_results, scenario, spec, definitions):
        return {"measured": raw_results["raw"] + 1}

    mapper = GenericModelMapper(
        clone_model=copy.deepcopy,
        run_model=run_model,
        measure_sensors=measure,
    )
    instance = mapper.map(specification, baseline).realize(
        Scenario(values={}, id="scenario-1", metadata={"effective_seed": 9})
    )

    result = instance.run()

    assert isinstance(result, SimulationResult)
    assert result.raw_results == {"raw": 5}
    assert result.measured_outputs == {"measured": 6}
    assert result.provenance["scenario_id"] == "scenario-1"
    assert result.provenance["metadata"] == {"effective_seed": 9}


def test_sensor_parameter_reference_resolves_from_realization_values():
    specification = _specification()

    def run_model(model):
        return {"raw": 1}

    def measure(model, raw_results, scenario, spec, definitions):
        assert definitions["sensor"].parameters["offset"] == scenario.values["sigma"]
        sensor = definitions["sensor"].create_sensor()
        assert sensor.offset == scenario.values["sigma"]
        return {"sensor": sensor.offset}

    mapper = GenericModelMapper(
        clone_model=copy.deepcopy,
        run_model=run_model,
        measure_sensors=measure,
        sensor_definitions=specification.sensors,
    )
    instance = mapper.map(specification, {"value": 1}).realize(
        Scenario(values={"sigma": 0.25}, id="scenario")
    )

    assert instance.run().measured_outputs == {"sensor": 0.25}


def test_unresolved_sensor_parameter_reference_fails_before_run():
    specification = _specification()
    applied = {"called": False}

    def apply_parameters(model, scenario, spec):
        applied["called"] = True
        model["value"] = scenario.values.get("x")

    mapper = GenericModelMapper(
        clone_model=copy.deepcopy,
        apply_parameters=apply_parameters,
        run_model=lambda model: {"raw": 1},
        sensor_definitions=specification.sensors,
    )
    with pytest.raises(ValueError, match="unresolved"):
        mapper.map(specification, {"value": 1}).realize(
            Scenario(values={}, id="scenario")
        )
    assert applied["called"] is False


def test_each_measurement_constructs_a_fresh_sensor_instance():
    specification = _specification()
    created_ids: list[int] = []

    def run_model(model):
        return {"raw": 1}

    def measure(model, raw_results, scenario, spec, definitions):
        first = definitions["sensor"].create_sensor()
        second = definitions["sensor"].create_sensor()
        created_ids.extend([id(first), id(second)])
        return {"first": first.offset, "second": second.offset}

    mapper = GenericModelMapper(
        clone_model=copy.deepcopy,
        run_model=run_model,
        measure_sensors=measure,
        sensor_definitions=specification.sensors,
    )
    instance = mapper.map(specification, {"value": 1}).realize(
        Scenario(values={"sigma": 0.5}, id="scenario")
    )

    instance.run()

    assert len(created_ids) == 2
    assert created_ids[0] != created_ids[1]
