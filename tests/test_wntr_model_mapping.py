"""Tests for the WNTR Stage 3 model mapper."""

import pytest
import wntr

from hydroforge.sampling import Scenario
from hydroforge.uncertainty.specification import UncertaintySpecification
from hydroforge.wdn_modelling.uncertainty import (
    WNTRModelMapper,
)


def _make_model() -> wntr.network.WaterNetworkModel:
    model = wntr.network.WaterNetworkModel()
    model.add_reservoir("R1", base_head=30.0)
    model.add_junction("J1", base_demand=2.0, elevation=10.0)
    model.add_pipe("P1", "R1", "J1", length=100.0, diameter=0.2, roughness=100.0)
    pass
    return model


def test_wntr_mapper_applies_realized_values_to_fresh_model():
    model = _make_model()
    from hydroforge.wdn_modelling.uncertainty.parameters import WNTRParameterBinding

    bindings = [
        WNTRParameterBinding("P1", "diameter", "diameter"),
        WNTRParameterBinding("P1", "initial_status", "status"),
    ]
    mapper = WNTRModelMapper(parameter_bindings=bindings)
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )

    uncertain_model = mapper.map(specification, model)
    realized = uncertain_model.realize(
        Scenario(values={"diameter": 0.35, "status": "CLOSED"}, id="scenario")
    ).model

    assert realized.get_link("P1").diameter == pytest.approx(0.35)
    assert realized.get_link("P1").initial_status.name.upper() == "CLOSED"
    assert model.get_link("P1").diameter == pytest.approx(0.2)
    assert model.get_link("P1").initial_status.name.upper() == "OPEN"


def test_wntr_mapper_realizations_are_isolated_and_order_independent():
    model = _make_model()
    from hydroforge.wdn_modelling.uncertainty.parameters import WNTRParameterBinding

    bindings = [WNTRParameterBinding("P1", "diameter", "diameter")]
    mapper = WNTRModelMapper(parameter_bindings=bindings)
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    uncertain_model = mapper.map(specification, model)

    first_values = [0.25, 0.4]
    second_values = [0.4, 0.25]
    first_results = [
        uncertain_model.realize(
            Scenario(values={"diameter": value}, id=f"first-{value}")
        )
        .model.get_link("P1")
        .diameter
        for value in first_values
    ]
    second_results = [
        uncertain_model.realize(
            Scenario(values={"diameter": value}, id=f"second-{value}")
        )
        .model.get_link("P1")
        .diameter
        for value in second_values
    ]

    assert first_results == pytest.approx(first_values)
    assert second_results == pytest.approx(second_values)
    assert model.get_link("P1").diameter == pytest.approx(0.2)


def test_initial_status_open_and_closed_are_applied():
    model = _make_model()
    from hydroforge.wdn_modelling.uncertainty.parameters import WNTRParameterBinding

    bindings = [WNTRParameterBinding("P1", "initial_status", "status")]
    mapper = WNTRModelMapper(parameter_bindings=bindings)
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    uncertain_model = mapper.map(specification, model)

    for status in ("OPEN", "CLOSED"):
        realized = uncertain_model.realize(
            Scenario(values={"status": status}, id=status)
        ).model
        assert realized.get_link("P1").initial_status.name.upper() == status
    assert model.get_link("P1").initial_status.name.upper() == "OPEN"


def test_malformed_binding_raises_before_mutation():
    model = _make_model()
    from hydroforge.wdn_modelling.uncertainty.parameters import (
        ParameterApplicationError,
        WNTRParameterAdapter,
    )

    adapter = WNTRParameterAdapter([object()])  # type: ignore[list-item]
    with pytest.raises(ParameterApplicationError):
        adapter.apply(model, {})
    assert model.get_link("P1").initial_status.name.upper() == "OPEN"


def test_protocol_conforming_binding_is_accepted():
    model = _make_model()
    from dataclasses import dataclass

    from hydroforge.wdn_modelling.uncertainty.parameters import (
        WNTRParameterAdapter,
    )

    @dataclass
    class ProtocolBinding:
        component_id: str
        property: str
        parameter_key: str

    binding = ProtocolBinding("P1", "diameter", "diameter")
    adapter = WNTRParameterAdapter([binding])  # type: ignore[list-item]
    adapter.apply(model, {"diameter": 0.3})
    assert model.get_link("P1").diameter == pytest.approx(0.3)


def test_binding_with_missing_or_wrong_typed_attributes_raises():
    model = _make_model()
    from hydroforge.wdn_modelling.uncertainty.parameters import (
        ParameterApplicationError,
        WNTRParameterAdapter,
    )

    class MissingAttributeBinding:
        component_id = "P1"
        property = "diameter"

    class WrongTypedBinding:
        component_id = 1
        property = "diameter"
        parameter_key = "diameter"

    for binding in (MissingAttributeBinding(), WrongTypedBinding()):
        adapter = WNTRParameterAdapter([binding])  # type: ignore[list-item]
        with pytest.raises(ParameterApplicationError):
            adapter.apply(model, {"diameter": 0.3})
    assert model.get_link("P1").diameter == pytest.approx(0.2)


def test_initial_status_invalid_value_fails_before_mutation():
    model = _make_model()
    from hydroforge.wdn_modelling.uncertainty.parameters import (
        ParameterApplicationError,
        WNTRParameterAdapter,
        WNTRParameterBinding,
    )

    adapter = WNTRParameterAdapter(
        [WNTRParameterBinding("P1", "initial_status", "status")]
    )
    with pytest.raises(ParameterApplicationError):
        adapter.apply(model, {"status": "ACTIVE"})
    assert model.get_link("P1").initial_status.name.upper() == "OPEN"


def test_duplicate_initial_status_target_fails_before_mutation():
    model = _make_model()
    from hydroforge.wdn_modelling.uncertainty.parameters import (
        ParameterApplicationError,
        WNTRParameterAdapter,
        WNTRParameterBinding,
    )

    adapter = WNTRParameterAdapter(
        [
            WNTRParameterBinding("P1", "initial_status", "first"),
            WNTRParameterBinding("P1", "initial_status", "second"),
        ]
    )
    with pytest.raises(ParameterApplicationError, match="duplicates"):
        adapter.apply(model, {"first": "OPEN", "second": "CLOSED"})
    assert model.get_link("P1").initial_status.name.upper() == "OPEN"


def _mapper_with_random_noise():
    from hydroforge.wdn_modelling.uncertainty import WNTRModelMapper, WNTRSensorBinding

    model = _make_model()
    node = model.junction_name_list[0]
    pipe = model.pipe_name_list[0]
    spec = UncertaintySpecification.from_dict(
        {
            "schema_version": "1.0",
            "parameters": {"sigma": {"nominal_value": 0.1}},
            "sensors": {
                "noise": {
                    "type": "RandomNoise",
                    "parameters": {"sigma": {"$parameter": "sigma"}},
                },
                "composite": {
                    "type": "Composite",
                    "parameters": {
                        "sensors": [
                            {
                                "type": "RandomNoise",
                                "parameters": {"sigma": {"$parameter": "sigma"}},
                            }
                        ]
                    },
                },
            },
        }
    )
    bindings = [
        WNTRSensorBinding(node, "noise", "pressure"),
        WNTRSensorBinding(pipe, "composite", "flowrate"),
    ]
    mapper = WNTRModelMapper(sensor_bindings=bindings, sensor_definitions=spec.sensors)
    return model, spec, mapper, node, pipe


def test_random_noise_seeds_derive_from_realization_seed_and_sensor_name():
    model, spec, mapper, node, pipe = _mapper_with_random_noise()
    from hydroforge.sampling import Scenario

    scenario = Scenario(
        values={"sigma": 0.1}, id="scenario", metadata={"effective_seed": 7}
    )
    uncertain_model = mapper.map(spec, model)
    result = uncertain_model.realize(scenario).run()

    seeds = result.provenance["sensor_seeds"]
    assert set(seeds) == {"noise", "composite"}
    # Reproducibility: same seed gives same derived seeds.
    scenario2 = Scenario(
        values={"sigma": 0.1}, id="scenario2", metadata={"effective_seed": 7}
    )
    result2 = mapper.map(spec, model).realize(scenario2).run()
    assert result2.provenance["sensor_seeds"] == seeds
    # Independent sensor names get distinct derived seeds.
    assert seeds["noise"] != seeds["composite"]


def test_explicit_random_noise_seed_overrides_derivation():
    model, spec, mapper, node, pipe = _mapper_with_random_noise()
    spec.sensors["noise"].parameters["seed"] = 99
    from hydroforge.sampling import Scenario

    scenario = Scenario(
        values={"sigma": 0.1}, id="scenario", metadata={"effective_seed": 7}
    )
    uncertain_model = mapper.map(spec, model)
    result = uncertain_model.realize(scenario).run()

    assert result.provenance["sensor_seeds"]["noise"] == 99


def test_nested_composite_random_noise_seed_is_derived():
    model, spec, mapper, node, pipe = _mapper_with_random_noise()
    from hydroforge.sampling import Scenario

    scenario = Scenario(
        values={"sigma": 0.1}, id="scenario", metadata={"effective_seed": 11}
    )
    uncertain_model = mapper.map(spec, model)
    result = uncertain_model.realize(scenario).run()

    composite_seed = result.provenance["sensor_seeds"]["composite"]
    assert isinstance(composite_seed, list)
    assert composite_seed[0] is not None


def test_each_measurement_uses_a_fresh_sensor_instance():
    model, spec, mapper, node, pipe = _mapper_with_random_noise()
    from hydroforge.sampling import Scenario

    captured: list[int] = []

    def measure(model, raw_results, scenario, spec, definitions):
        first = definitions["noise"].create_sensor()
        second = definitions["noise"].create_sensor()
        captured.extend([id(first), id(second)])
        return {}

    mapper._measure = measure  # type: ignore[attr-defined]
    mapper.map(spec, model).realize(
        Scenario(values={"sigma": 0.1}, id="scenario", metadata={"effective_seed": 1})
    ).run()
    assert len(captured) == 2
    assert captured[0] != captured[1]


def test_wntr_mapper_run_preserves_raw_results_and_provenance():
    model, spec, mapper, node, pipe = _mapper_with_random_noise()
    from hydroforge.sampling import Scenario

    scenario = Scenario(
        values={"sigma": 0.1}, id="scenario", metadata={"effective_seed": 5}
    )
    uncertain_model = mapper.map(spec, model)
    instance = uncertain_model.realize(scenario)
    result = instance.run()

    assert result.raw_results is not None
    assert set(result.measured_outputs) == {"pressure", "flowrate"}
    for frame in result.measured_outputs.values():
        assert frame.index.equals(
            result.raw_results.raw.node["pressure"].index
        ) or frame.index.equals(result.raw_results.raw.link["flowrate"].index)
    assert result.provenance["scenario_id"] == "scenario"
    assert result.provenance["metadata"] == {"effective_seed": 5}
    assert "sensor_seeds" in result.provenance
