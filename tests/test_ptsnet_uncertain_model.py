"""Tests for the PTSNet Stage 3 model mapper."""

import pandas as pd
import pytest

from hydroforge.sampling import Scenario
from hydroforge.uncertainty.specification import UncertaintySpecification
from hydroforge.wdn_modelling.uncertainty.ptsnet_mapping import (
    PTSNetModelMapper,
    PTSNetSensorBinding,
    PTSNetSurgeProtectionBinding,
    PTSNetWaveSpeedBinding,
)


class _FakePipeTable:
    def __init__(self):
        self.wave_speed = {}


class _FakeSettings:
    def __init__(self):
        self.default_wave_speed = 1000.0


class _FakeModel:
    def __init__(self):
        self.settings = _FakeSettings()
        self.ss = {"pipe": _FakePipeTable()}
        self.node_name_list = ["N1"]
        self.surge_calls = []

    def pipes(self):
        return [("P1", self)]

    def get_node(self, name):
        return self

    def add_surge_protection(
        self, node_name, protection_type, tank_area, tank_height=None, water_level=None
    ):
        self.surge_calls.append(
            (node_name, protection_type, tank_area, tank_height, water_level)
        )


class _FakeResults:
    def get_node_variable(self, variable, nodes, as_dataframe=False):
        return pd.DataFrame({"N1": [1.0, 2.0]}, index=[0, 1])


def _make_mapper(**kwargs):
    return PTSNetModelMapper(simulator_config=None, **kwargs)


def test_ptsnet_shared_wave_speed_applies_to_all_pipes():
    model = _FakeModel()
    mapper = _make_mapper(
        wave_speed_bindings=[PTSNetWaveSpeedBinding(parameter_key="wave_speed")]
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    uncertain_model = mapper.map(specification, model)
    realized = uncertain_model.realize(
        Scenario(values={"wave_speed": 1234.0}, id="scenario")
    ).model

    assert realized.settings.default_wave_speed == 1234.0
    assert realized.ss["pipe"].wave_speed == {}
    assert model.settings.default_wave_speed == 1000.0


def test_ptsnet_per_pipe_wave_speed_applies_to_selected_pipe():
    model = _FakeModel()
    mapper = _make_mapper(
        wave_speed_bindings=[
            PTSNetWaveSpeedBinding(parameter_key="wave_speed", pipes=("P1",))
        ]
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    realized = (
        mapper.map(specification, model)
        .realize(Scenario(values={"wave_speed": 999.0}, id="scenario"))
        .model
    )

    assert realized.ss["pipe"].wave_speed["P1"] == 999.0


def test_ptsnet_open_and_closed_surge_protection_map():
    for protection_type, kwargs in (
        ("open", {"tank_area": 2.0}),
        ("closed", {"tank_area": 2.0, "tank_height": 5.0, "water_level": 1.0}),
    ):
        model = _FakeModel()
        mapper = _make_mapper(
            surge_protection_bindings=[
                PTSNetSurgeProtectionBinding("N1", protection_type, **kwargs)
            ]
        )
        specification = UncertaintySpecification.from_dict(
            {"schema_version": "1.0", "sensors": {}}
        )
        mapper.map(specification, model).realize(
            Scenario(values={}, id=protection_type)
        )
        assert model.surge_calls == []
        realized_model = (
            mapper.map(specification, model)
            .realize(Scenario(values={}, id=protection_type))
            .model
        )
        assert realized_model.surge_calls == [
            (
                "N1",
                protection_type,
                kwargs["tank_area"],
                kwargs.get("tank_height"),
                kwargs.get("water_level"),
            )
        ]


def test_ptsnet_node_measurement_preserves_raw_results_and_time_index():
    model = _FakeModel()
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    # Sensor definitions must be supplied for measurement; use a generic Offset-like definition.
    from hydroforge.uncertainty.specification import SensorDefinition

    mapper2 = _make_mapper(
        sensor_bindings=[PTSNetSensorBinding("N1", "sensor", "head")],
        sensor_definitions={
            "sensor": SensorDefinition(type="Offset", parameters={"offset": 0.5})
        },
    )
    mapper2._run = lambda model: _FakeResults()
    uncertain_model = mapper2.map(specification, model)
    result = uncertain_model.realize(Scenario(values={}, id="scenario")).run()

    assert result.raw_results is not None
    assert result.measured_outputs["head"]["N1"].index.equals(pd.Index([0, 1]))
    assert result.provenance["scenario_id"] == "scenario"


def test_ptsnet_baseline_isolation():
    model = _FakeModel()
    mapper = _make_mapper(
        wave_speed_bindings=[PTSNetWaveSpeedBinding(parameter_key="wave_speed")]
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    uncertain_model = mapper.map(specification, model)
    uncertain_model.realize(Scenario(values={"wave_speed": 900.0}, id="first"))
    assert model.settings.default_wave_speed == 1000.0
    assert model.ss["pipe"].wave_speed == {}


def test_ptsnet_invalid_wave_speed_fails_before_mutation():
    model = _FakeModel()
    mapper = _make_mapper(
        wave_speed_bindings=[PTSNetWaveSpeedBinding(parameter_key="wave_speed")]
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    with pytest.raises(ValueError):
        mapper.map(specification, model).realize(
            Scenario(values={"wave_speed": "bad"}, id="scenario")
        )


def test_ptsnet_invalid_surge_protection_type_fails_before_mutation():
    model = _FakeModel()
    mapper = _make_mapper(
        surge_protection_bindings=[PTSNetSurgeProtectionBinding("N1", "sideways", 2.0)]
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    with pytest.raises(ValueError):
        mapper.map(specification, model).realize(Scenario(values={}, id="scenario"))


def test_ptsnet_missing_wave_speed_value_fails_before_mutation():
    model = _FakeModel()
    mapper = _make_mapper(
        wave_speed_bindings=[PTSNetWaveSpeedBinding(parameter_key="wave_speed")]
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    with pytest.raises(ValueError):
        mapper.map(specification, model).realize(Scenario(values={}, id="scenario"))


try:
    import ptsnet  # noqa: F401
except Exception:  # pragma: no cover
    ptsnet = None


def _ptsnet_integration_available():
    if ptsnet is None:
        return False
    import importlib.util

    return importlib.util.find_spec("tqdm") is not None


if _ptsnet_integration_available():

    def test_ptsnet_optional_integration_smoke():
        pytest.importorskip("tqdm")
        from hydroforge.wdn_modelling.backends.ptsnet_backend import PTSNetBackend

        backend = PTSNetBackend()
        model = backend.load_model("tests/base_networks/Net1.inp")
        assert model is not None
