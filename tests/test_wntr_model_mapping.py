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
    model.add_valve("V1", "R1", "J1", valve_type="PBV", initial_setting="OPEN")
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
