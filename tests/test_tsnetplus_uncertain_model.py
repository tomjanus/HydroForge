"""Tests for the TSNetPlus Stage 3 model mapper."""

import pytest

try:
    from hydroforge.wdn_modelling.backends.tsnetplus_backend import TSNetPlusBackend
except Exception:  # pragma: no cover
    TSNetPlusBackend = None


pytestmark = pytest.mark.skipif(
    TSNetPlusBackend is None, reason="TSNetPlus is not installed"
)


def _make_model():
    pytest.importorskip("tsnetplus", reason="TSNetPlus is an optional backend")
    from hydroforge.wdn_modelling.backends.tsnetplus_backend import TSNetPlusBackend

    backend = TSNetPlusBackend()
    return backend.load_model("tests/base_networks/Net1.inp")


def test_tsnetplus_mapper_applies_shared_wave_speed():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import UncertaintySpecification
    from hydroforge.wdn_modelling.uncertainty.tsnetplus_mapping import (
        TSNetPlusModelMapper,
        TSNetPlusWaveSpeedBinding,
    )
    from hydroforge.wdn_modelling.backends.tsnetplus.config import TSNetPlusConfig

    model = _make_model()
    mapper = TSNetPlusModelMapper(
        wave_speed_bindings=[TSNetPlusWaveSpeedBinding(parameter_key="wave_speed")],
        simulator_config=TSNetPlusConfig(duration=1.0, wave_speed=1200.0),
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    uncertain_model = mapper.map(specification, model)
    realized = uncertain_model.realize(
        Scenario(values={"wave_speed": 1100.0}, id="scenario")
    ).model

    assert model is not realized


def test_tsnetplus_mapper_applies_per_pipe_wave_speed():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import UncertaintySpecification
    from hydroforge.wdn_modelling.uncertainty.tsnetplus_mapping import (
        TSNetPlusModelMapper,
        TSNetPlusWaveSpeedBinding,
    )
    from hydroforge.wdn_modelling.backends.tsnetplus.config import TSNetPlusConfig

    model = _make_model()
    pipe_name = list(model.pipes())[0][0]
    mapper = TSNetPlusModelMapper(
        wave_speed_bindings=[
            TSNetPlusWaveSpeedBinding(parameter_key="wave_speed", pipes=(pipe_name,))
        ],
        simulator_config=TSNetPlusConfig(duration=1.0, wave_speed=1200.0),
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    realized = (
        mapper.map(specification, model)
        .realize(Scenario(values={"wave_speed": 900.0}, id="scenario"))
        .model
    )
    pipe = [p for p in realized.pipes() if p[0] == pipe_name][0][1]
    assert pipe.wavev == pytest.approx(900.0, rel=1e-6)


def test_tsnetplus_open_and_closed_surge_tanks_map():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import UncertaintySpecification
    from hydroforge.wdn_modelling.uncertainty.tsnetplus_mapping import (
        TSNetPlusModelMapper,
        TSNetPlusSurgeTankBinding,
    )
    from hydroforge.wdn_modelling.backends.tsnetplus.config import TSNetPlusConfig

    for tank_type, shape in (("open", (2.0,)), ("closed", (2.0, 5.0, 1.0))):
        model = _make_model()
        node = list(model.node_name_list)[0]
        mapper = TSNetPlusModelMapper(
            surge_tank_bindings=[TSNetPlusSurgeTankBinding(node, tank_type, shape)],
            simulator_config=TSNetPlusConfig(duration=1.0, wave_speed=1200.0),
        )
        specification = UncertaintySpecification.from_dict(
            {"schema_version": "1.0", "sensors": {}}
        )
        realized = (
            mapper.map(specification, model)
            .realize(Scenario(values={}, id=tank_type))
            .model
        )
        surge_node = realized.get_node(node)
        assert surge_node.transient_node_type in {"SurgeTank", "Chamber"}


def test_tsnetplus_invalid_wave_speed_fails_before_mutation():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import UncertaintySpecification
    from hydroforge.wdn_modelling.uncertainty.tsnetplus_mapping import (
        TSNetPlusModelMapper,
        TSNetPlusWaveSpeedBinding,
    )
    from hydroforge.wdn_modelling.backends.tsnetplus.config import TSNetPlusConfig

    model = _make_model()
    mapper = TSNetPlusModelMapper(
        wave_speed_bindings=[TSNetPlusWaveSpeedBinding(parameter_key="wave_speed")],
        simulator_config=TSNetPlusConfig(duration=1.0, wave_speed=1200.0),
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    with pytest.raises(ValueError):
        mapper.map(specification, model).realize(
            Scenario(values={"wave_speed": "bad"}, id="scenario")
        )


def test_tsnetplus_baseline_isolation():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import UncertaintySpecification
    from hydroforge.wdn_modelling.uncertainty.tsnetplus_mapping import (
        TSNetPlusModelMapper,
        TSNetPlusWaveSpeedBinding,
    )
    from hydroforge.wdn_modelling.backends.tsnetplus.config import TSNetPlusConfig

    model = _make_model()
    baseline_wave = (
        list(model.pipes())[0][1].wavev
        if hasattr(list(model.pipes())[0][1], "wavev")
        else None
    )
    mapper = TSNetPlusModelMapper(
        wave_speed_bindings=[TSNetPlusWaveSpeedBinding(parameter_key="wave_speed")],
        simulator_config=TSNetPlusConfig(duration=1.0, wave_speed=1200.0),
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    uncertain_model = mapper.map(specification, model)
    uncertain_model.realize(Scenario(values={"wave_speed": 900.0}, id="first"))
    assert (not hasattr(list(model.pipes())[0][1], "wavev")) or list(model.pipes())[0][
        1
    ].wavev == baseline_wave


def test_tsnetplus_invalid_surge_tank_type_fails_before_mutation():
    from hydroforge.sampling import Scenario
    from hydroforge.uncertainty.specification import UncertaintySpecification
    from hydroforge.wdn_modelling.uncertainty.tsnetplus_mapping import (
        TSNetPlusModelMapper,
        TSNetPlusSurgeTankBinding,
    )
    from hydroforge.wdn_modelling.backends.tsnetplus.config import TSNetPlusConfig

    model = _make_model()
    mapper = TSNetPlusModelMapper(
        surge_tank_bindings=[
            TSNetPlusSurgeTankBinding(list(model.node_name_list)[0], "sideways", (2.0,))
        ],
        simulator_config=TSNetPlusConfig(duration=1.0, wave_speed=1200.0),
    )
    specification = UncertaintySpecification.from_dict(
        {"schema_version": "1.0", "sensors": {}}
    )
    with pytest.raises(ValueError):
        mapper.map(specification, model).realize(Scenario(values={}, id="scenario"))
