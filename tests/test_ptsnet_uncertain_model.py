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
        self.pipe_output_requests = []

    def pipes(self):
        return [("P1", self)]

    def add_pipe_output(self, *args, **kwargs):
        self.pipe_output_requests.append((args, kwargs))

    def get_node(self, name):
        return self

    def add_surge_protection(
        self, node_name, protection_type, tank_area, tank_height=None, water_level=None
    ):
        self.surge_calls.append(
            (node_name, protection_type, tank_area, tank_height, water_level)
        )


class _FakeResults:
    def __init__(self):
        self.results = {
            "node": type("NodeTable", (), {"head": [[1.0, 2.0]], "labels": ["N1"]})()
        }
        self.time_stamps = [0.0, 0.01]

    def get_node_variable(self, variable, nodes, as_dataframe=False):
        return pd.DataFrame({"N1": [1.0, 2.0]}, index=self.time_stamps)


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
    assert result.measured_outputs["head"]["N1"].index.equals(
        pd.Index([0.0, 0.01], name="time")
    )
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


# Optional PTSNet integration is unavailable in this environment because the
# native EPANET shared library is missing, so no live integration test runs.


class _FakeInteriorModel:
    def __init__(self):
        self.settings = type("Settings", (), {"default_wave_speed": 1000.0})()
        self.ss = {"pipe": type("PipeTable", (), {"wave_speed": {}})()}
        self.node_name_list = ["N1"]
        self.pipe_output_requests = []
        self.interior_results = {}
        self.time_stamps = [0.0, 0.01]

    def pipes(self):
        return [("P1", self)]

    def get_node(self, name):
        return self

    def add_surge_protection(self, *args, **kwargs):
        return None

    def add_pipe_output(self, name, pipe_name, position, position_type, variables=None):
        self.pipe_output_requests.append(
            (name, pipe_name, position, position_type, tuple(variables or ()))
        )

    def run(self):
        self.interior_results = {
            "interior": {"head": [1.0, 2.0]},
            "interior_idx": {"head": [3.0, 4.0]},
        }


class _FakeInteriorResults:
    def __init__(self, model):
        self.model = model

    def get_node_variable(self, variable, nodes, as_dataframe=False):
        import pandas as pd

        return pd.DataFrame({"N1": [1.0, 2.0]}, index=[0, 1])


def test_ptsnet_interior_fractional_binding_registers_add_pipe_output():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import UncertaintySpecification
    from hydroforge.wdn_modelling.uncertainty.ptsnet_mapping import (
        PTSNetInteriorSensorBinding,
        PTSNetModelMapper,
    )

    model = _FakeInteriorModel()
    mapper = PTSNetModelMapper(
        interior_sensor_bindings=[
            PTSNetInteriorSensorBinding("P1", "interior", "head", fraction=0.25)
        ],
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    realized_model = (
        mapper.map(specification, model)
        .realize(Scenario(values={}, id="scenario"))
        .model
    )
    assert realized_model.pipe_output_requests == [
        ("interior", "P1", 0.25, "fraction", ("head",))
    ]


def test_ptsnet_interior_mesh_index_binding_registers_add_pipe_output():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import UncertaintySpecification
    from hydroforge.wdn_modelling.uncertainty.ptsnet_mapping import (
        PTSNetInteriorSensorBinding,
        PTSNetModelMapper,
    )

    model = _FakeInteriorModel()
    mapper = PTSNetModelMapper(
        interior_sensor_bindings=[
            PTSNetInteriorSensorBinding("P1", "interior_idx", "head", index=1)
        ],
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    realized_model = (
        mapper.map(specification, model)
        .realize(Scenario(values={}, id="scenario"))
        .model
    )
    assert realized_model.pipe_output_requests == [
        ("interior_idx", "P1", 1, "index", ("head",))
    ]


def test_ptsnet_interior_measured_output_preserves_timestamps_and_provenance():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import (
        SensorDefinition,
        UncertaintySpecification,
    )
    from hydroforge.wdn_modelling.uncertainty.ptsnet_mapping import (
        PTSNetInteriorSensorBinding,
        PTSNetModelMapper,
    )

    model = _FakeInteriorModel()
    model.interior_results = {"interior": {"head": [1.0, 2.0]}}
    model.run = lambda: None
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    mapper = PTSNetModelMapper(
        interior_sensor_bindings=[
            PTSNetInteriorSensorBinding(
                "P1", "interior", "head", fraction=0.25, name="interior"
            )
        ],
        sensor_definitions={
            "interior": SensorDefinition(type="Offset", parameters={"offset": 0.5})
        },
    )
    mapper._run = lambda model: _FakeInteriorResults(model)
    uncertain_model = mapper.map(specification, model)
    result = uncertain_model.realize(
        Scenario(values={}, id="scenario", metadata={"effective_seed": 7})
    ).run()

    assert result.raw_results is not None
    assert result.measured_outputs["head"]["interior"].index.tolist() == [0.0, 0.01]
    assert result.provenance["scenario_id"] == "scenario"


def test_ptsnet_missing_interior_output_fails_clearly():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import (
        SensorDefinition,
        UncertaintySpecification,
    )
    from hydroforge.wdn_modelling.uncertainty.ptsnet_mapping import (
        PTSNetInteriorSensorBinding,
        PTSNetModelMapper,
    )

    model = _FakeInteriorModel()
    model.interior_results = {}
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    mapper = PTSNetModelMapper(
        interior_sensor_bindings=[
            PTSNetInteriorSensorBinding(
                "P1", "missing", "head", fraction=0.25, name="missing"
            )
        ],
        sensor_definitions={
            "missing": SensorDefinition(type="Offset", parameters={"offset": 0.0})
        },
        simulator=type(
            "FakeSimulator",
            (),
            {"run": lambda self, candidate: _FakeInteriorResults(candidate)},
        )(),
    )
    uncertain_model = mapper.map(specification, model)
    with pytest.raises(ValueError, match="interior output"):
        uncertain_model.realize(Scenario(values={}, id="scenario")).run()


def test_ptsnet_interior_quantity_validation():
    from hydroforge.wdn_modelling.uncertainty.ptsnet_mapping import (
        PTSNetInteriorSensorBinding,
    )

    with pytest.raises(ValueError):
        PTSNetInteriorSensorBinding("P1", "sensor", "velocity", fraction=0.25)


class _FakeRawResults:
    def __init__(self, node_values, interior_values, timestamps):
        self.model = type(
            "Model",
            (),
            {
                "results": {
                    "node": type(
                        "NodeTable",
                        (),
                        {"head": node_values, "labels": ["N1"]},
                    )()
                },
                "time_stamps": timestamps,
                "interior_results": interior_values,
            },
        )()


def test_ptsnet_fake_raw_node_and_interior_measurement_output():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import (
        SensorDefinition,
        UncertaintySpecification,
    )
    from hydroforge.wdn_modelling.uncertainty.ptsnet_mapping import (
        PTSNetInteriorSensorBinding,
        PTSNetModelMapper,
        PTSNetSensorBinding,
    )

    model = _FakeModel()
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    mapper = PTSNetModelMapper(
        sensor_bindings=[PTSNetSensorBinding("N1", "node_sensor", "head")],
        interior_sensor_bindings=[
            PTSNetInteriorSensorBinding(
                "P1", "interior_sensor", "head", fraction=0.5, name="interior"
            )
        ],
        sensor_definitions={
            "node_sensor": SensorDefinition(type="Offset", parameters={"offset": 0.5}),
            "interior_sensor": SensorDefinition(
                type="Offset", parameters={"offset": 0.5}
            ),
        },
    )
    mapper._run = lambda model: _FakeRawResults(
        [[1.0, 2.0]], {"interior": {"head": [3.0, 4.0]}}, [0.0, 0.01]
    )
    uncertain_model = mapper.map(specification, model)
    result = uncertain_model.realize(Scenario(values={}, id="scenario")).run()

    assert result.raw_results is not None
    assert result.measured_outputs["head"]["N1"].index.tolist() == [0.0, 0.01]
    assert result.measured_outputs["head"]["interior"].index.tolist() == [0.0, 0.01]


def test_ptsnet_fake_raw_missing_interior_output_fails():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import (
        SensorDefinition,
        UncertaintySpecification,
    )
    from hydroforge.wdn_modelling.uncertainty.ptsnet_mapping import (
        PTSNetInteriorSensorBinding,
        PTSNetModelMapper,
    )

    model = _FakeModel()
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    mapper = PTSNetModelMapper(
        interior_sensor_bindings=[
            PTSNetInteriorSensorBinding(
                "P1", "missing", "head", fraction=0.5, name="missing"
            )
        ],
        sensor_definitions={
            "missing": SensorDefinition(type="Offset", parameters={"offset": 0.0})
        },
    )
    mapper._run = lambda model: _FakeRawResults([[1.0, 2.0]], {}, [0, 1])
    uncertain_model = mapper.map(specification, model)
    with pytest.raises(ValueError, match="interior output"):
        uncertain_model.realize(Scenario(values={}, id="scenario")).run()


class _FakeTable:
    def __init__(self, values, labels):
        self.values = values
        self.labels = labels

    @property
    def head(self):
        return self.values

    @property
    def start_node_flowrate(self):
        return self.values


def test_ptsnet_raw_dict_of_tables_measurement_output():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import (
        SensorDefinition,
        UncertaintySpecification,
    )
    from hydroforge.wdn_modelling.uncertainty.ptsnet_mapping import (
        PTSNetInteriorSensorBinding,
        PTSNetModelMapper,
        PTSNetSensorBinding,
    )

    model = _FakeModel()
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    mapper = PTSNetModelMapper(
        sensor_bindings=[PTSNetSensorBinding("N1", "node_sensor", "head")],
        interior_sensor_bindings=[
            PTSNetInteriorSensorBinding(
                "P1", "interior_sensor", "flowrate", fraction=0.5, name="interior"
            )
        ],
        sensor_definitions={
            "node_sensor": SensorDefinition(type="Offset", parameters={"offset": 0.5}),
            "interior_sensor": SensorDefinition(
                type="Offset", parameters={"offset": 0.5}
            ),
        },
    )
    raw_results = {
        "node": _FakeTable([[1.0, 2.0]], ["N1"]),
        "pipe.start": _FakeTable([[3.0, 4.0]], ["P1"]),
        "interior_results": {"interior": {"flowrate": [5.0, 6.0]}},
        "time_stamps": [0.0, 0.01],
    }
    mapper._run = lambda model: raw_results
    uncertain_model = mapper.map(specification, model)
    result = uncertain_model.realize(Scenario(values={}, id="scenario")).run()

    assert result.raw_results is raw_results
    assert result.measured_outputs["head"]["N1"].index.tolist() == [0.0, 0.01]
    assert result.measured_outputs["flowrate"]["interior"].index.tolist() == [0.0, 0.01]


def test_ptsnet_default_simulator_receives_config_and_runs(monkeypatch):
    import hydroforge.wdn_modelling.uncertainty.ptsnet_mapping as ptsnet_mapping

    config = object()
    model = _FakeModel()
    expected = object()
    calls = []

    class RecordingSimulator:
        def __init__(self, config):
            calls.append(("init", config))

        def run(self, candidate):
            calls.append(("run", candidate))
            return expected

    monkeypatch.setattr(ptsnet_mapping, "PTSNetSimulator", RecordingSimulator)
    monkeypatch.setattr(ptsnet_mapping, "PTSNetConfig", object)
    mapper = ptsnet_mapping.PTSNetModelMapper(simulator_config=config)

    assert mapper._run(model) is expected
    assert calls == [("init", config), ("run", model)]


def test_ptsnet_mapper_uses_injected_simulator():
    from hydroforge.wdn_modelling.uncertainty.ptsnet_mapping import PTSNetModelMapper

    model = _FakeModel()
    expected = object()

    class InjectedSimulator:
        def __init__(self):
            self.models = []

        def run(self, candidate):
            self.models.append(candidate)
            return expected

    simulator = InjectedSimulator()
    mapper = PTSNetModelMapper(simulator=simulator)

    assert mapper._run(model) is expected
    assert simulator.models == [model]


def test_ptsnet_clones_pathlike_input_with_unique_workspace_names(
    tmp_path, monkeypatch
):
    import sys
    import types

    import hydroforge.wdn_modelling.uncertainty.ptsnet_mapping as ptsnet_mapping

    class Config:
        @staticmethod
        def _to_settings():
            return {"duration": 2.0, "time_step": 0.1}

    class FakePTSNETSimulation:
        def __init__(self, workspace_name, inpfile, settings):
            self.workspace_name = workspace_name
            self.inpfile = inpfile
            self.settings = settings

    ptsnet_package = types.ModuleType("ptsnet")
    ptsnet_package.__path__ = []
    simulation_package = types.ModuleType("ptsnet.simulation")
    simulation_package.__path__ = []
    simulation_module = types.ModuleType("ptsnet.simulation.sim")
    simulation_module.PTSNETSimulation = FakePTSNETSimulation
    monkeypatch.setitem(sys.modules, "ptsnet", ptsnet_package)
    monkeypatch.setitem(sys.modules, "ptsnet.simulation", simulation_package)
    monkeypatch.setitem(sys.modules, "ptsnet.simulation.sim", simulation_module)
    monkeypatch.setattr(ptsnet_mapping, "PTSNetConfig", Config)

    source = tmp_path / "network.inp"
    model = _FakeModel()
    model.inpfile = source
    model.workspace_name = "network"
    mapper = ptsnet_mapping.PTSNetModelMapper(simulator_config=Config())

    first = mapper._clone(model)
    second = mapper._clone(model)

    assert first.inpfile == str(source)
    assert first.settings == {"duration": 2.0, "time_step": 0.1}
    assert first.workspace_name != second.workspace_name
    assert first.workspace_name.startswith("network_realization_")
