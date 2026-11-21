"""Tests for applying generic sensor definitions to WNTR result columns."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import wntr

from hydroforge.uncertainty.specification import SensorDefinition
from hydroforge.wdn_modelling.backends.wntr.results import WNTRSimulationResults
from hydroforge.wdn_modelling.backends.wntr.simulator import WNTRSimulator
from hydroforge.wdn_modelling.uncertainty import (
    SensorApplicationError,
    WNTRSensorAdapter,
    WNTRSensorBinding,
)

BASE_NETWORK = Path(__file__).parent / "base_networks" / "Net1_with_prv.inp"


@pytest.fixture
def simulated_network():
    model = wntr.network.WaterNetworkModel(BASE_NETWORK)
    model.options.time.duration = 0
    results = WNTRSimulator().run(model)
    return model, results


def _binding(
    point_id: str,
    sensor_key: str,
    variable: str,
) -> WNTRSensorBinding:
    return WNTRSensorBinding(
        point_id=point_id,
        sensor_key=sensor_key,
        variable=variable,
    )


def _definitions(**definitions: SensorDefinition) -> dict[str, SensorDefinition]:
    return definitions


def _apply(
    model,
    results: WNTRSimulationResults,
    bindings: list[WNTRSensorBinding],
    definitions: dict[str, SensorDefinition],
):
    return WNTRSensorAdapter(bindings, definitions).apply(model, results)


def _assert_application_error(
    model,
    results: WNTRSimulationResults,
    binding: WNTRSensorBinding,
    definitions: dict[str, SensorDefinition],
    path: str,
) -> None:
    with pytest.raises(SensorApplicationError) as exc_info:
        _apply(model, results, [binding], definitions)

    assert exc_info.value.path == path


def test_applies_sensors_only_to_bound_pressure_and_flow_columns(simulated_network):
    model, results = simulated_network
    node_id = model.junction_name_list[0]
    tank_id = model.tank_name_list[0]
    pipe_id = model.pipe_name_list[0]
    pump_id = model.pump_name_list[0]
    valve_id = model.valve_name_list[0]
    original_node = results.raw.node["pressure"].copy(deep=True)
    original_link = results.raw.link["flowrate"].copy(deep=True)
    definitions = _definitions(
        offset=SensorDefinition(type="Offset", parameters={"offset": 2.0}),
        exact=SensorDefinition(type="Perfect"),
    )

    measured = _apply(
        model,
        results,
        [
            _binding(node_id, "offset", "pressure"),
            _binding(tank_id, "exact", "pressure"),
            _binding(pipe_id, "offset", "flowrate"),
            _binding(pump_id, "exact", "flowrate"),
            _binding(valve_id, "exact", "flowrate"),
        ],
        definitions,
    )

    assert set(measured) == {"pressure", "flowrate"}
    assert list(measured["pressure"].columns) == [node_id, tank_id]
    assert list(measured["flowrate"].columns) == [pipe_id, pump_id, valve_id]
    assert measured["pressure"].index.equals(original_node.index)
    assert measured["flowrate"].index.equals(original_link.index)
    pd.testing.assert_series_equal(
        measured["pressure"][node_id],
        original_node[node_id] + 2.0,
        check_names=False,
    )
    pd.testing.assert_series_equal(
        measured["flowrate"][pipe_id],
        original_link[pipe_id] + 2.0,
        check_names=False,
    )
    pd.testing.assert_frame_equal(results.raw.node["pressure"], original_node)
    pd.testing.assert_frame_equal(results.raw.link["flowrate"], original_link)


def test_each_binding_gets_a_fresh_live_sensor(simulated_network):
    model, results = simulated_network
    node_ids = model.junction_name_list[:2]
    definitions = _definitions(
        drift=SensorDefinition(
            type="Drift",
            parameters={"offset_rate": 0.25},
        )
    )
    original = results.raw.node["pressure"].copy(deep=True)

    measured = _apply(
        model,
        results,
        [_binding(node_id, "drift", "pressure") for node_id in node_ids],
        definitions,
    )["pressure"]

    for node_id in node_ids:
        pd.testing.assert_series_equal(
            measured[node_id],
            original[node_id] + 0.25,
            check_names=False,
        )


def test_seeded_definition_starts_each_point_with_a_fresh_rng(simulated_network):
    model, results = simulated_network
    node_ids = model.junction_name_list[:2]
    definitions = _definitions(
        noise=SensorDefinition(
            type="RandomNoise",
            parameters={"sigma": 0.5, "seed": 17},
        )
    )
    original = results.raw.node["pressure"].copy(deep=True)

    measured = _apply(
        model,
        results,
        [_binding(node_id, "noise", "pressure") for node_id in node_ids],
        definitions,
    )["pressure"]

    first_noise = measured[node_ids[0]] - original[node_ids[0]]
    second_noise = measured[node_ids[1]] - original[node_ids[1]]
    pd.testing.assert_series_equal(first_noise, second_noise, check_names=False)


def test_sensor_definition_location_must_match_external_binding(simulated_network):
    model, results = simulated_network
    point_id = model.junction_name_list[0]

    _assert_application_error(
        model,
        results,
        _binding(point_id, "located", "pressure"),
        _definitions(
            located=SensorDefinition(
                type="Perfect",
                location=model.junction_name_list[1],
            )
        ),
        "sensor_definitions['located'].location",
    )


def test_matching_sensor_definition_location_is_accepted(simulated_network):
    model, results = simulated_network
    point_id = model.junction_name_list[0]

    measured = _apply(
        model,
        results,
        [_binding(point_id, "located", "pressure")],
        _definitions(
            located=SensorDefinition(type="Perfect", location=point_id),
        ),
    )

    assert list(measured["pressure"].columns) == [point_id]


@pytest.mark.parametrize(
    ("binding", "definitions", "path"),
    [
        (
            _binding("missing-point", "perfect", "pressure"),
            _definitions(perfect=SensorDefinition(type="Perfect")),
            "bindings[0].point_id",
        ),
        (
            _binding("9", "perfect", "pressure"),
            _definitions(perfect=SensorDefinition(type="Perfect")),
            "bindings[0].point_id",
        ),
        (
            _binding("10", "perfect", "velocity"),
            _definitions(perfect=SensorDefinition(type="Perfect")),
            "bindings[0].variable",
        ),
        (
            _binding("10", "absent", "pressure"),
            {},
            "bindings[0].sensor_key",
        ),
    ],
)
def test_invalid_sensor_binding_has_actionable_path(
    simulated_network,
    binding,
    definitions,
    path,
):
    model, results = simulated_network

    _assert_application_error(model, results, binding, definitions, path)


def test_duplicate_point_and_variable_binding_is_rejected(simulated_network):
    model, results = simulated_network
    point_id = model.junction_name_list[0]
    definitions = _definitions(perfect=SensorDefinition(type="Perfect"))

    with pytest.raises(SensorApplicationError) as exc_info:
        WNTRSensorAdapter(
            [
                _binding(point_id, "perfect", "pressure"),
                _binding(point_id, "perfect", "pressure"),
            ],
            definitions,
        ).apply(model, results)

    assert exc_info.value.path == "bindings[1]"


def test_result_data_must_contain_bound_point_and_variable(simulated_network):
    model, results = simulated_network
    results_without_column = WNTRSimulationResults(deepcopy(results.raw))
    del results_without_column.raw.node["pressure"][model.junction_name_list[0]]

    _assert_application_error(
        model,
        results_without_column,
        _binding(model.junction_name_list[0], "perfect", "pressure"),
        _definitions(perfect=SensorDefinition(type="Perfect")),
        f"results.node.pressure[{model.junction_name_list[0]!r}]",
    )


def test_empty_bindings_return_no_measured_variables(simulated_network):
    model, results = simulated_network

    assert _apply(model, results, [], {}) == {}


def test_power_pump_flowrate_is_supported():
    model = wntr.network.WaterNetworkModel()
    model.add_reservoir("R1", base_head=30.0)
    model.add_junction("J1")
    model.add_pump(
        "PUMP",
        "R1",
        "J1",
        pump_type="POWER",
        pump_parameter=50.0,
    )
    time_index = pd.Index([0], name="time")
    raw = SimpleNamespace(
        node={"pressure": pd.DataFrame({"J1": [10.0]}, index=time_index)},
        link={"flowrate": pd.DataFrame({"PUMP": [2.0]}, index=time_index)},
    )
    results = WNTRSimulationResults(raw)

    measured = _apply(
        model,
        results,
        [_binding("PUMP", "perfect", "flowrate")],
        _definitions(perfect=SensorDefinition(type="Perfect")),
    )

    assert measured["flowrate"].loc[0, "PUMP"] == 2.0


def test_flowrate_binding_rejects_node_components(simulated_network):
    model, results = simulated_network
    node_id = next(
        node_id
        for node_id in model.node_name_list
        if node_id not in model.link_name_list
    )

    _assert_application_error(
        model,
        results,
        _binding(node_id, "perfect", "flowrate"),
        _definitions(perfect=SensorDefinition(type="Perfect")),
        "bindings[0].point_id",
    )


def test_reservoir_pressure_is_explicitly_rejected(simulated_network):
    model, results = simulated_network

    with pytest.raises(SensorApplicationError, match="reservoir pressure") as exc_info:
        _apply(
            model,
            results,
            [_binding(model.reservoir_name_list[0], "perfect", "pressure")],
            _definitions(perfect=SensorDefinition(type="Perfect")),
        )

    assert exc_info.value.path == "bindings[0].point_id"


def test_pump_velocity_is_not_a_supported_measurement_variable(simulated_network):
    model, results = simulated_network

    _assert_application_error(
        model,
        results,
        _binding(model.pump_name_list[0], "perfect", "velocity"),
        _definitions(perfect=SensorDefinition(type="Perfect")),
        "bindings[0].variable",
    )
