"""Tests for WNTR realization bundle persistence."""

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
