"""Tests for WNTR realization bundle persistence."""

import json

import pytest
import wntr

from hydroforge.sampling import Scenario
from hydroforge.uncertainty.specification import UncertaintySpecification
from hydroforge.wdn_modelling.persistence import load_realization, save_realization
from hydroforge.wdn_modelling.uncertainty import (
    WNTRModelMapper,
    WNTRParameterBinding,
)


def _make_model():
    model = wntr.network.WaterNetworkModel()
    model.add_reservoir("R1", base_head=30.0)
    model.add_junction("J1", base_demand=2.0, elevation=10.0)
    model.add_pipe("P1", "R1", "J1", length=100.0, diameter=0.2, roughness=100.0)
    return model


def test_save_and_load_realization_round_trips_and_reruns(tmp_path):
    model = _make_model()
    mapper = WNTRModelMapper(
        parameter_bindings=[WNTRParameterBinding("P1", "diameter", "diameter")]
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    scenario = Scenario(
        values={"diameter": 0.35}, id="scenario-1", metadata={"effective_seed": 7}
    )
    instance = mapper.map(specification, model).realize(scenario)

    bundle = tmp_path / "bundle"
    save_realization(instance, bundle)
    assert (bundle / "manifest.json").is_file()
    assert (bundle / "model.inp").is_file()

    import json

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sampled_values"] == {"diameter": 0.35}

    loaded = load_realization(bundle)
    assert loaded.model.get_link("P1").diameter == pytest.approx(0.35)
    result = loaded.run()
    assert result.raw_results is not None
    assert loaded.scenario.id == "scenario-1"


def test_save_refuses_overwrite(tmp_path):
    model = _make_model()
    mapper = WNTRModelMapper(parameter_bindings=[])
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    instance = mapper.map(specification, model).realize(
        Scenario(values={}, id="scenario")
    )

    bundle = tmp_path / "bundle"
    save_realization(instance, bundle)
    with pytest.raises(FileExistsError):
        save_realization(instance, bundle)


def test_incomplete_manifest_fails(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        load_realization(bundle)


def test_load_rejects_path_traversal_artifact(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(
        '{"manifest_version":"1.0","specification":{"schema_version":"1.0","sensors":{}},'
        '"scenario":{"id":"x","values":{},"metadata":null},"sampled_values":{},'
        '"model_artifact":"../secret.inp"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_realization(bundle)


def test_load_rejects_absolute_artifact(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(
        '{"manifest_version":"1.0","specification":{"schema_version":"1.0","sensors":{}},'
        '"scenario":{"id":"x","values":{},"metadata":null},"sampled_values":{},'
        '"model_artifact":"/tmp/secret.inp"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_realization(bundle)


def test_load_rejects_malformed_parameter_binding(tmp_path):
    import json

    model = _make_model()
    from hydroforge.wdn_modelling.uncertainty import WNTRModelMapper

    mapper = WNTRModelMapper(parameter_bindings=[])
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    instance = mapper.map(specification, model).realize(
        Scenario(values={}, id="scenario")
    )
    bundle = tmp_path / "bundle"
    save_realization(instance, bundle)

    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["mapping"]["parameter_bindings"] = [
        {"component_id": 1, "property": "diameter", "parameter_key": "x"}
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError):
        load_realization(bundle)


def test_load_rejects_malformed_sensor_binding(tmp_path):
    import json

    model = _make_model()
    mapper = WNTRModelMapper(parameter_bindings=[])
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    instance = mapper.map(specification, model).realize(
        Scenario(values={}, id="scenario")
    )
    bundle = tmp_path / "bundle"
    save_realization(instance, bundle)

    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sensor_setup"]["bindings"] = [
        {"point_id": 1, "sensor_key": "s", "variable": "pressure"}
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError):
        load_realization(bundle)


def test_dynamic_backend_artifact_dispatch_and_config_round_trip(tmp_path, monkeypatch):
    source = tmp_path / "source.inp"
    source.write_text("data", encoding="utf-8")

    class FakeModel:
        def __init__(self):
            self._inpfile = str(source)
            self.settings = type(
                "Settings",
                (),
                {"default_wave_speed": 1000.0, "time_step": 0.1, "duration": 0.0},
            )()
            self.ss = {"pipe": type("PipeTable", (), {"wave_speed": {}})()}
            self.surge_calls = []
            self.pipe_output_requests = []
            self.interior_results = {}

        def set_wavespeed(self, value, pipes=None):
            if pipes is None:
                self.settings.default_wave_speed = float(value)
                self.ss["pipe"].wave_speed = float(value)
            else:
                for pipe in pipes:
                    self.ss["pipe"].wave_speed[pipe] = float(value)

        def set_time(self, tf, dt=None):
            self.settings.duration = tf
            self.settings.time_step = dt if dt is not None else self.settings.time_step

        def add_surge_tank(self, *args, **kwargs):
            self.surge_calls.append((args, kwargs))

        def add_pipe_output(self, *args, **kwargs):
            self.pipe_output_requests.append((args, kwargs))

    class FakeBackend:
        def load_model(self, path):
            model = FakeModel()
            model.loaded_from = str(path)
            return model

    monkeypatch.setattr(
        "hydroforge.wdn_modelling.backends.tsnetplus_backend.TSNetPlusBackend",
        FakeBackend,
    )
    monkeypatch.setattr(
        "hydroforge.wdn_modelling.backends.tsnetplus.TSNetSPlusSimulator",
        lambda config=None, inplace=True: type(
            "FakeSimulator", (), {"run": lambda self, model: model}
        )(),
    )
    monkeypatch.setattr(
        "hydroforge.wdn_modelling.backends.ptsnet_backend.PTSNetBackend",
        FakeBackend,
    )

    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import UncertaintySpecification
    from hydroforge.wdn_modelling.mapping import SimulationInstance

    model = FakeModel()
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    instance = SimulationInstance(
        model=model,
        scenario=Scenario(values={"wave_speed": 1100.0}, id="scenario"),
        specification=specification,
        run=lambda loaded_model: loaded_model,
        wave_speed_bindings=[{"parameter_key": "wave_speed", "pipes": None}],
        surge_bindings=[
            {
                "node_id": "N1",
                "tank_type": "open",
                "tank_area": 2.0,
                "shape": (2.0,),
            }
        ],
        interior_bindings=[
            {
                "pipe_id": "P1",
                "sensor_key": "interior",
                "quantity": "head",
                "fraction": 0.25,
                "name": "interior",
            }
        ],
    )
    instance.backend = "tsnetplus"

    bundle = tmp_path / "bundle"
    save_realization(instance, bundle)
    assert (bundle / "model.inp").read_text(encoding="utf-8") == "data"
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["backend"] == "tsnetplus"
    assert manifest["mapping"]["wave_speed_bindings"]

    loaded = load_realization(bundle)
    assert loaded.model.loaded_from.endswith("model.inp")
    assert loaded.model.settings.default_wave_speed == 1100.0
    assert loaded.model.pipe_output_requests
    # Re-running does not reapply dynamic configuration.
    before = (
        loaded.model.settings.default_wave_speed,
        list(loaded.model.pipe_output_requests),
    )
    loaded.run()
    after = (
        loaded.model.settings.default_wave_speed,
        list(loaded.model.pipe_output_requests),
    )
    assert before == after


def test_load_rejects_malformed_mapping(tmp_path):
    import json

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "model.inp").write_text("data", encoding="utf-8")
    manifest = {
        "manifest_version": "1.0",
        "backend": "wntr",
        "schema_version": "2.0",
        "specification": {"schema_version": "2.0", "sensors": {}},
        "scenario": {"id": "x", "values": {}, "metadata": None},
        "sampled_values": {},
        "model_artifact": "model.inp",
        "mapping": "bad",
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="mapping"):
        load_realization(bundle)
