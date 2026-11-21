"""Tests for atomic, WNTR-specific parameter application."""

from pathlib import Path

import pytest
import wntr

from hydroforge.wdn_modelling.uncertainty import (
    ParameterApplicationError,
    WNTRParameterAdapter,
    WNTRParameterBinding,
)

BASE_NETWORKS = Path(__file__).parent / "base_networks"


def _make_model() -> wntr.network.WaterNetworkModel:
    model = wntr.network.WaterNetworkModel()
    model.add_reservoir("R1", base_head=30.0)
    model.add_junction("J1", base_demand=2.0, elevation=10.0)
    model.add_junction("J2", base_demand=4.0, elevation=10.0)
    model.add_pipe(
        "P1",
        "R1",
        "J1",
        length=100.0,
        diameter=0.2,
        roughness=100.0,
    )
    model.add_pipe(
        "P2",
        "R1",
        "J2",
        length=100.0,
        diameter=0.3,
        roughness=110.0,
    )
    return model


def _binding(
    component_id: str,
    property: str,
    parameter_key: str,
) -> WNTRParameterBinding:
    return WNTRParameterBinding(
        component_id=component_id,
        property=property,
        parameter_key=parameter_key,
    )


def _assert_error_path(
    model: wntr.network.WaterNetworkModel,
    bindings: list[WNTRParameterBinding],
    values: dict[str, object],
    path: str,
) -> None:
    with pytest.raises(ParameterApplicationError) as exc_info:
        WNTRParameterAdapter(bindings).apply(model, values)

    assert exc_info.value.path == path


def test_applies_pipe_and_single_demand_properties_in_binding_order():
    model = _make_model()
    bindings = [
        _binding("P1", "diameter", "new_diameter"),
        _binding("P2", "diameter_multiplier", "diameter_factor"),
        _binding("P1", "roughness", "new_roughness"),
        _binding("J1", "base_demand", "new_demand"),
    ]

    report = WNTRParameterAdapter(bindings).apply(
        model,
        {
            "new_diameter": 0.25,
            "diameter_factor": 1.5,
            "new_roughness": 125.0,
            "new_demand": 3.5,
            "unused": 99.0,
        },
    )

    assert model.get_link("P1").diameter == 0.25
    assert model.get_link("P2").diameter == pytest.approx(0.45)
    assert model.get_link("P1").roughness == 125.0
    assert model.get_node("J1").demand_timeseries_list[0].base_value == 3.5
    assert [
        (
            operation.operation_index,
            operation.component_id,
            operation.property,
            operation.parameter_key,
            operation.old_value,
            operation.realized_value,
            operation.new_value,
        )
        for operation in report.operations
    ] == [
        (0, "P1", "diameter", "new_diameter", 0.2, 0.25, 0.25),
        (
            1,
            "P2",
            "diameter_multiplier",
            "diameter_factor",
            0.3,
            1.5,
            pytest.approx(0.45),
        ),
        (2, "P1", "roughness", "new_roughness", 100.0, 125.0, 125.0),
        (3, "J1", "base_demand", "new_demand", 2.0, 3.5, 3.5),
    ]


def test_diameter_set_and_multiplier_follow_declared_operation_order():
    model = _make_model()
    report = WNTRParameterAdapter(
        [
            _binding("P1", "diameter", "diameter"),
            _binding("P1", "diameter_multiplier", "factor"),
        ]
    ).apply(model, {"diameter": 0.4, "factor": 2.0})

    assert model.get_link("P1").diameter == pytest.approx(0.8)
    assert report.operations[1].old_value == pytest.approx(0.4)
    assert report.operations[1].new_value == pytest.approx(0.8)


def test_invalid_later_binding_leaves_earlier_valid_target_unchanged():
    model = _make_model()
    original_diameter = model.get_link("P1").diameter
    original_demand = model.get_node("J1").demand_timeseries_list[0].base_value

    _assert_error_path(
        model,
        [
            _binding("P1", "diameter", "new_diameter"),
            _binding("missing-pipe", "roughness", "new_roughness"),
        ],
        {"new_diameter": 0.25, "new_roughness": 120.0},
        "bindings[1].component_id",
    )

    assert model.get_link("P1").diameter == original_diameter
    assert model.get_node("J1").demand_timeseries_list[0].base_value == original_demand


@pytest.mark.parametrize(
    ("binding", "values", "path"),
    [
        (_binding("missing", "diameter", "d"), {"d": 0.2}, "bindings[0].component_id"),
        (_binding("J1", "diameter", "d"), {"d": 0.2}, "bindings[0].component_id"),
        (_binding("P1", "base_demand", "d"), {"d": 0.2}, "bindings[0].component_id"),
        (_binding("P1", "unsupported", "d"), {"d": 0.2}, "bindings[0].property"),
        (_binding("P1", "diameter", "absent"), {}, "bindings[0].parameter_key"),
    ],
)
def test_invalid_binding_has_actionable_path_and_does_not_mutate(
    binding: WNTRParameterBinding,
    values: dict[str, object],
    path: str,
):
    model = _make_model()
    original_diameter = model.get_link("P1").diameter

    _assert_error_path(model, [binding], values, path)

    assert model.get_link("P1").diameter == original_diameter


def test_junction_with_multiple_demand_timeseries_is_rejected_atomically():
    model = _make_model()
    junction = model.get_node("J1")
    junction.add_demand(5.0, None, category="second")
    original_demand = junction.demand_timeseries_list[0].base_value

    _assert_error_path(
        model,
        [
            _binding("P1", "diameter", "d"),
            _binding("J1", "base_demand", "demand"),
        ],
        {"d": 0.25, "demand": 10.0},
        "bindings[1].component_id",
    )

    assert model.get_link("P1").diameter == 0.2
    assert junction.demand_timeseries_list[0].base_value == original_demand


@pytest.mark.parametrize("invalid_value", [True, "0.25", float("nan"), float("inf")])
def test_non_finite_or_non_numeric_values_are_rejected_before_mutation(invalid_value):
    model = _make_model()

    _assert_error_path(
        model,
        [
            _binding("P1", "diameter", "valid"),
            _binding("J1", "base_demand", "invalid"),
        ],
        {"valid": 0.25, "invalid": invalid_value},
        "realized_values['invalid']",
    )

    assert model.get_link("P1").diameter == 0.2


def test_duplicate_component_property_binding_is_rejected():
    model = _make_model()

    _assert_error_path(
        model,
        [
            _binding("P1", "diameter", "first"),
            _binding("P1", "diameter", "second"),
        ],
        {"first": 0.25, "second": 0.3},
        "bindings[1]",
    )

    assert model.get_link("P1").diameter == 0.2


def test_applies_values_to_a_loaded_wntr_network_fixture():
    model = wntr.network.WaterNetworkModel(BASE_NETWORKS / "Net1_shortened.inp")
    pipe_id = model.pipe_name_list[0]
    junction_id = model.junction_name_list[0]
    old_diameter = model.get_link(pipe_id).diameter
    old_demand = model.get_node(junction_id).demand_timeseries_list[0].base_value

    report = WNTRParameterAdapter(
        [
            _binding(pipe_id, "diameter", "diameter"),
            _binding(junction_id, "base_demand", "demand"),
        ]
    ).apply(model, {"diameter": 0.125, "demand": 0.75})

    assert model.get_link(pipe_id).diameter == 0.125
    assert model.get_node(junction_id).demand_timeseries_list[0].base_value == 0.75
    assert report.operations[0].old_value == old_diameter
    assert report.operations[1].old_value == old_demand
