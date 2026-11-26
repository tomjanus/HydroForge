"""Persistence for Stage 3 WNTR realization bundles."""

from __future__ import annotations

import dataclasses
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping, cast

import wntr

from hydroforge.sampling import Scenario
from hydroforge.uncertainty.specification import (
    SensorDefinition,
    UncertaintySpecification,
)
from hydroforge.wdn_modelling.mapping import SimulationInstance
from hydroforge.wdn_modelling.backends.wntr import WNTRSimulator
from hydroforge.wdn_modelling.backends.wntr.results import WNTRSimulationResults
from hydroforge.wdn_modelling.uncertainty.parameters import WNTRParameterBinding
from hydroforge.wdn_modelling.uncertainty.sensors import WNTRSensorBinding
from hydroforge.wdn_modelling.uncertainty.sensors import WNTRSensorAdapter
from hydroforge.wdn_modelling.mapping import resolve_sensor_parameter_references


_REQUIRED_MANIFEST_KEYS = {
    "manifest_version",
    "backend",
    "specification",
    "scenario",
    "sampled_values",
    "model_artifact",
}


def _as_path(value: Any) -> Path:
    return value if isinstance(value, Path) else Path(value)


def _is_instance(value: Any) -> bool:
    return hasattr(value, "run") and hasattr(value, "model")


def _normalize_save_args(instance: Any, directory: Any) -> tuple[Any, Path]:
    if _is_instance(directory) and not _is_instance(instance):
        instance, directory = directory, instance
    return instance, _as_path(directory)


def _binding_to_dict(binding: Any) -> dict[str, Any]:
    if dataclasses.is_dataclass(binding):
        return dataclasses.asdict(cast(Any, binding))
    if isinstance(binding, Mapping):
        return dict(binding)
    return {
        "component_id": getattr(binding, "component_id", None),
        "property": getattr(binding, "property", None),
        "parameter_key": getattr(binding, "parameter_key", None),
        "point_id": getattr(binding, "point_id", None),
        "sensor_key": getattr(binding, "sensor_key", None),
        "variable": getattr(binding, "variable", None),
    }


def _backend_name(instance: Any, model: Any) -> str:
    explicit = getattr(instance, "backend", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    explicit = getattr(model, "backend", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    module = type(model).__module__.lower()
    class_name = type(model).__name__.lower()
    if "tsnetplus" in module or "tsnetplus" in class_name:
        return "tsnetplus"
    if "ptsnet" in module or "ptsnet" in class_name:
        return "ptsnet"
    return "wntr"


def _save_model_artifact(model: Any, model_path: Path) -> None:
    for attribute in ("inpfile", "_inpfile"):
        source = getattr(model, attribute, None)
        if isinstance(source, (str, Path)):
            source_path = Path(source)
            if source_path.is_file():
                import shutil

                shutil.copyfile(source_path, model_path)
                return
    writer = getattr(model, "write_inpfile", None)
    if callable(writer):
        writer(str(model_path))
        return
    try:
        import wntr

        wntr.network.io.write_inpfile(model, str(model_path))
        return
    except Exception as exc:
        raise ValueError(f"could not save a native model artifact: {exc}") from exc


def save_realization(
    instance: Any,
    directory: Any = None,
    *,
    overwrite: bool = False,
    **kwargs: Any,
) -> Path:
    """Save one WNTR realization as a directory bundle."""
    instance, directory = _normalize_save_args(instance, directory)
    if directory.exists() and any(directory.iterdir()) and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing bundle: {directory}")
    directory.mkdir(parents=True, exist_ok=True)

    specification = getattr(instance, "specification", None)
    if not isinstance(specification, UncertaintySpecification):
        raise TypeError("instance must carry an UncertaintySpecification")

    scenario = getattr(instance, "scenario", None)
    if not isinstance(scenario, Scenario):
        raise TypeError("instance must carry a Scenario")

    model = getattr(instance, "model", None)
    if model is None:
        raise TypeError("instance must carry a model")
    backend = _backend_name(instance, model)

    model_artifact = "model.inp"
    model_path = directory / model_artifact
    _save_model_artifact(model, model_path)

    parameter_bindings = getattr(instance, "parameter_bindings", None)
    if parameter_bindings is None:
        parameter_bindings = kwargs.get("parameter_bindings", [])
    sensor_bindings = getattr(instance, "sensor_bindings", None)
    if sensor_bindings is None:
        sensor_bindings = kwargs.get("sensor_bindings", [])
    wave_speed_bindings = getattr(instance, "wave_speed_bindings", None)
    if wave_speed_bindings is None:
        wave_speed_bindings = kwargs.get("wave_speed_bindings", [])
    surge_bindings = getattr(instance, "surge_bindings", None)
    if surge_bindings is None:
        surge_bindings = getattr(instance, "surge_protection_bindings", None)
    if surge_bindings is None:
        surge_bindings = getattr(instance, "surge_tank_bindings", None)
    if surge_bindings is None:
        surge_bindings = kwargs.get("surge_bindings", [])
    interior_bindings = getattr(instance, "interior_bindings", None)
    if interior_bindings is None:
        interior_bindings = kwargs.get("interior_bindings", [])

    sensor_definitions = getattr(instance, "sensor_definitions", {}) or {}
    resolved_sensor_definitions = {}
    for name, definition in sensor_definitions.items():
        resolved_sensor_definitions[name] = resolve_sensor_parameter_references(
            definition, getattr(scenario, "values", {}) or {}
        )

    backend_settings = kwargs.get("backend_settings")
    if backend_settings is None and backend == "ptsnet":
        configured_settings = getattr(model, "_hydroforge_config_settings", None)
        if isinstance(configured_settings, Mapping):
            backend_settings = dict(configured_settings)
        else:
            settings = getattr(model, "settings", None)
            settings_to_dict = getattr(settings, "to_dict", None)
            if callable(settings_to_dict):
                backend_settings = settings_to_dict(simplified=True)
                backend_settings.setdefault("parallel", False)
                backend_settings.setdefault("gpu", False)
    if backend_settings is None:
        backend_settings = {}
    if not isinstance(backend_settings, Mapping):
        raise ValueError("backend_settings must be a mapping")

    manifest = {
        "manifest_version": "1.0",
        "backend": backend,
        "schema_version": specification.schema_version,
        "specification": specification.to_dict(),
        "scenario": {
            "id": getattr(scenario, "id", None),
            "values": getattr(scenario, "values", None),
            "metadata": getattr(scenario, "metadata", None),
        },
        "sampled_values": getattr(scenario, "values", None),
        "effective_seed": (
            (getattr(scenario, "metadata", None) or {}).get("effective_seed")
            if isinstance(getattr(scenario, "metadata", None), Mapping)
            else None
        ),
        "mapping": {
            "parameter_bindings": [
                _binding_to_dict(binding) for binding in (parameter_bindings or [])
            ],
            "sensor_bindings": [
                _binding_to_dict(binding) for binding in (sensor_bindings or [])
            ],
            "wave_speed_bindings": [
                _binding_to_dict(binding) for binding in (wave_speed_bindings or [])
            ],
            "surge_bindings": [
                _binding_to_dict(binding) for binding in (surge_bindings or [])
            ],
            "interior_bindings": [
                _binding_to_dict(binding) for binding in (interior_bindings or [])
            ],
        },
        "backend_settings": dict(backend_settings),
        "sensor_setup": {
            "definitions": {
                name: definition.to_dict()
                for name, definition in (sensor_definitions or {}).items()
            },
            "bindings": [
                _binding_to_dict(binding) for binding in (sensor_bindings or [])
            ],
        },
        "model_artifact": model_artifact,
    }

    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return directory


def _apply_dynamic_configuration(backend, model, manifest):
    if backend not in {"tsnetplus", "ptsnet"}:
        return
    values = manifest.get("sampled_values", {})
    if not isinstance(values, Mapping):
        values = {}
    mapping = manifest.get("mapping", {})
    if not isinstance(mapping, Mapping):
        mapping = {}

    if backend == "tsnetplus":
        for binding in mapping.get("wave_speed_bindings", []) or []:
            if not isinstance(binding, Mapping):
                continue
            key = binding.get("parameter_key")
            if key in values:
                pipes = binding.get("pipes")
                if hasattr(model, "set_wavespeed"):
                    if pipes is None:
                        model.set_wavespeed(values[key])
                    else:
                        model.set_wavespeed(values[key], pipes=list(pipes))
                settings = getattr(model, "settings", None)
                if settings is not None and pipes is None:
                    try:
                        settings.default_wave_speed = float(values[key])
                    except (TypeError, ValueError):
                        pass
        for binding in mapping.get("surge_bindings", []) or []:
            if not isinstance(binding, Mapping):
                continue
            node_id = binding.get("node_id")
            tank_type = binding.get("tank_type", "open")
            shape = list(binding.get("shape", (1.0,)))
            if binding.get("area_key") in values:
                if shape:
                    shape[0] = values[binding["area_key"]]
            if tank_type == "closed":
                if binding.get("height_key") in values and len(shape) > 1:
                    shape[1] = values[binding["height_key"]]
                if binding.get("level_key") in values and len(shape) >= 3:
                    shape[2] = values[binding["level_key"]]
            if hasattr(model, "add_surge_tank"):
                model.add_surge_tank(node_id, tuple(shape), tank_type)
        for binding in mapping.get("interior_bindings", []) or []:
            if not isinstance(binding, Mapping):
                continue
            if not callable(getattr(model, "add_pipe_output", None)):
                raise RuntimeError(
                    "interior-output persistence requires the backend "
                    "add_pipe_output API"
                )
            output_name = binding.get("name") or binding.get("sensor_key")
            position = (
                binding.get("fraction")
                if binding.get("fraction") is not None
                else binding.get("index")
            )
            position_type = (
                "fraction" if binding.get("fraction") is not None else "index"
            )
            quantity = binding.get("quantity", "head")
            model.add_pipe_output(
                output_name,
                binding.get("pipe_id"),
                position,
                position_type,
                variables=(quantity,),
            )

    if backend == "ptsnet":
        for binding in mapping.get("wave_speed_bindings", []) or []:
            if not isinstance(binding, Mapping):
                continue
            key = binding.get("parameter_key")
            if key in values:
                ss = getattr(model, "ss", None)
                if isinstance(ss, Mapping) and "pipe" in ss:
                    wave_speed = getattr(ss["pipe"], "wave_speed", None)
                    pipes = binding.get("pipes")
                    if wave_speed is not None:
                        if pipes is None:
                            wave_speed[:] = float(values[key])
                        else:
                            for pipe in pipes:
                                wave_speed[pipe] = float(values[key])
                        model._hydroforge_wave_speed_overridden = True
                settings = getattr(model, "settings", None)
                if settings is not None and binding.get("pipes") is None:
                    try:
                        settings.default_wave_speed = float(values[key])
                    except Exception:
                        pass
        for binding in mapping.get("surge_bindings", []) or []:
            if not isinstance(binding, Mapping):
                continue
            node_id = binding.get("node_id")
            protection_type = binding.get("protection_type", "open")
            area = binding.get("tank_area", 1.0)
            if binding.get("area_key") in values:
                area = values[binding["area_key"]]
            height = binding.get("tank_height")
            if binding.get("height_key") in values:
                height = values[binding["height_key"]]
            level = binding.get("water_level")
            if binding.get("level_key") in values:
                level = values[binding["level_key"]]
            if hasattr(model, "add_surge_protection"):
                if protection_type == "closed":
                    model.add_surge_protection(
                        node_id,
                        protection_type,
                        area,
                        tank_height=height,
                        water_level=level,
                    )
                else:
                    model.add_surge_protection(node_id, protection_type, area)

        for binding in mapping.get("interior_bindings", []) or []:
            if not isinstance(binding, Mapping):
                continue
            if not callable(getattr(model, "add_pipe_output", None)):
                raise RuntimeError(
                    "PTSNet interior-output persistence requires add_pipe_output; "
                    "install the PTSNet feature branch with interior output support"
                )
            output_name = binding.get("name") or binding.get("sensor_key")
            position = (
                binding.get("fraction")
                if binding.get("fraction") is not None
                else binding.get("index")
            )
            position_type = (
                "fraction" if binding.get("fraction") is not None else "index"
            )
            quantity = binding.get("quantity", "head")
            model.add_pipe_output(
                output_name,
                binding.get("pipe_id"),
                position,
                position_type,
                variables=(quantity,),
            )


def _ptsnet_mapper_from_manifest(
    mapping: Mapping[str, Any],
    sensor_definitions: Mapping[str, SensorDefinition],
    backend_settings: Mapping[str, Any],
):
    """Rebuild PTSNet bindings and measurement callbacks from a bundle."""
    from hydroforge.wdn_modelling.uncertainty import ptsnet_mapping

    config_type = ptsnet_mapping.PTSNetConfig
    if config_type is None or ptsnet_mapping.PTSNetSimulator is None:
        raise RuntimeError(
            "PTSNet persistence requires the PTSNet backend and simulator API"
        )

    def binding_list(key: str) -> list[Mapping[str, Any]]:
        items = mapping.get(key, []) or []
        if not isinstance(items, list) or any(
            not isinstance(item, Mapping) for item in items
        ):
            raise ValueError(f"manifest mapping {key!r} must be a list of mappings")
        return items

    def required_text(binding: Mapping[str, Any], key: str) -> str:
        value = binding.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"PTSNet binding {key!r} must be a non-empty string")
        return value

    wave_bindings = []
    for item in binding_list("wave_speed_bindings"):
        parameter_key = required_text(item, "parameter_key")
        pipes = item.get("pipes")
        if pipes is not None and (
            not isinstance(pipes, (list, tuple))
            or any(not isinstance(pipe, str) or not pipe for pipe in pipes)
        ):
            raise ValueError("PTSNet wave-speed pipes must be a sequence of names")
        wave_bindings.append(
            ptsnet_mapping.PTSNetWaveSpeedBinding(parameter_key, pipes)
        )

    surge_bindings = []
    for item in binding_list("surge_bindings"):
        node_id = required_text(item, "node_id")
        protection_type = item.get("protection_type", "open")
        if protection_type not in {"open", "closed"}:
            raise ValueError("PTSNet protection_type must be 'open' or 'closed'")
        for key in ("area_key", "height_key", "level_key"):
            if item.get(key) is not None and not isinstance(item[key], str):
                raise ValueError(f"PTSNet surge binding {key} must be a string")
        surge_bindings.append(
            ptsnet_mapping.PTSNetSurgeProtectionBinding(
                node_id=node_id,
                protection_type=protection_type,
                tank_area=float(item.get("tank_area", 1.0)),
                tank_height=(
                    None
                    if item.get("tank_height") is None
                    else float(item["tank_height"])
                ),
                water_level=(
                    None
                    if item.get("water_level") is None
                    else float(item["water_level"])
                ),
                area_key=item.get("area_key"),
                height_key=item.get("height_key"),
                level_key=item.get("level_key"),
            )
        )

    sensor_bindings = []
    for item in binding_list("sensor_bindings"):
        node_id = required_text(item, "node_id")
        sensor_key = required_text(item, "sensor_key")
        variable = item.get("variable", "head")
        if variable not in {"head", "emitter_discharge", "demand_discharge"}:
            raise ValueError(f"unsupported PTSNet node sensor variable: {variable!r}")
        sensor_bindings.append(
            ptsnet_mapping.PTSNetSensorBinding(node_id, sensor_key, variable)
        )

    interior_bindings = []
    for item in binding_list("interior_bindings"):
        pipe_id = required_text(item, "pipe_id")
        sensor_key = required_text(item, "sensor_key")
        quantity = item.get("quantity", "head")
        name = item.get("name")
        if name is not None and (not isinstance(name, str) or not name):
            raise ValueError("PTSNet interior output name must be a non-empty string")
        fraction = item.get("fraction")
        index = item.get("index")
        if fraction is not None and (
            isinstance(fraction, bool) or not isinstance(fraction, (int, float))
        ):
            raise ValueError("PTSNet interior fraction must be numeric")
        if index is not None and (
            isinstance(index, bool) or not isinstance(index, int)
        ):
            raise ValueError("PTSNet interior index must be an integer")
        try:
            interior_bindings.append(
                ptsnet_mapping.PTSNetInteriorSensorBinding(
                    pipe_id=pipe_id,
                    sensor_key=sensor_key,
                    quantity=quantity,
                    name=name,
                    fraction=fraction,
                    index=index,
                )
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid PTSNet interior binding: {exc}") from exc

    allowed_settings = set(getattr(config_type, "__dataclass_fields__", {}))
    unknown_settings = set(backend_settings).difference(allowed_settings)
    if unknown_settings:
        raise ValueError(
            f"unsupported PTSNet backend settings: {sorted(unknown_settings)}"
        )
    config = config_type(**dict(backend_settings))
    mapper = ptsnet_mapping.PTSNetModelMapper(
        wave_speed_bindings=wave_bindings,
        surge_protection_bindings=surge_bindings,
        sensor_bindings=sensor_bindings,
        interior_sensor_bindings=interior_bindings,
        sensor_definitions=sensor_definitions,
        simulator_config=config,
    )
    return mapper, wave_bindings, surge_bindings, sensor_bindings, interior_bindings


def load_realization(directory: Any) -> SimulationInstance:
    """Load a saved WNTR realization bundle."""
    directory = _as_path(directory)
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    missing = _REQUIRED_MANIFEST_KEYS - set(manifest)
    if missing:
        raise ValueError(f"incomplete manifest; missing: {sorted(missing)}")

    if manifest.get("manifest_version") not in {None, "1.0"}:
        raise ValueError(
            f"unsupported manifest version: {manifest.get('manifest_version')!r}"
        )

    backend = manifest.get("backend")
    if backend not in {"wntr", "tsnetplus", "ptsnet"}:
        raise ValueError(f"unsupported or missing backend: {backend!r}")
    backend_settings = manifest.get("backend_settings", {})
    if not isinstance(backend_settings, Mapping):
        raise ValueError("manifest backend_settings must be a mapping")

    manifest_mapping = manifest.get("mapping", {})
    if not isinstance(manifest_mapping, Mapping):
        raise ValueError("manifest mapping must be a mapping")

    spec_document = manifest.get("specification")
    if not isinstance(spec_document, dict):
        raise ValueError("manifest specification must be a mapping")
    specification = UncertaintySpecification.from_dict(spec_document)

    artifact_name = manifest.get("model_artifact")
    if not isinstance(artifact_name, str) or not artifact_name:
        raise ValueError("manifest model_artifact must be a non-empty string")
    artifact_path = Path(artifact_name)
    if artifact_path.is_absolute() or len(artifact_path.parts) != 1:
        raise ValueError("manifest model_artifact must be a bundle-local file name")
    model_path = directory / artifact_path.name
    try:
        resolved_directory = directory.resolve(strict=True)
        resolved_model = model_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"invalid model artifact path: {exc}") from exc
    if resolved_model.parent != resolved_directory:
        raise ValueError(
            "manifest model_artifact must remain inside the bundle directory"
        )
    if not resolved_model.is_file():
        raise FileNotFoundError(f"missing model artifact: {model_path}")
    ptsnet_source_directory = None
    if backend == "wntr":
        model = wntr.network.io.read_inpfile(str(model_path))
    elif backend == "tsnetplus":
        try:
            from hydroforge.wdn_modelling.backends.tsnetplus_backend import (
                TSNetPlusBackend,
            )
        except Exception as exc:
            raise RuntimeError("TSNetPlus is not installed") from exc
        model = TSNetPlusBackend().load_model(model_path)
    elif backend == "ptsnet":
        try:
            from hydroforge.wdn_modelling.backends.ptsnet_backend import PTSNetBackend
        except Exception as exc:
            raise RuntimeError("PTSNet is not installed") from exc
        ptsnet_source_directory = tempfile.TemporaryDirectory(
            prefix="hydroforge_ptsnet_model_"
        )
        isolated_model_path = Path(ptsnet_source_directory.name) / artifact_path.name
        shutil.copyfile(model_path, isolated_model_path)
        model = PTSNetBackend().load_model(
            isolated_model_path,
            settings=dict(backend_settings),
            workspace_name=f"{directory.name}_loaded_{uuid.uuid4().hex}",
        )
    else:
        raise ValueError(f"unsupported backend: {backend!r}")

    sampled_values = manifest.get("sampled_values")
    if sampled_values is None:
        sampled_values = (
            manifest.get("scenario", {}).get("values", {})
            if isinstance(manifest.get("scenario"), dict)
            else {}
        )
    if not isinstance(sampled_values, Mapping):
        raise ValueError("manifest sampled_values must be a mapping")
    scenario_document = manifest.get("scenario", {})
    if not isinstance(scenario_document, dict):
        raise ValueError("manifest scenario must be a mapping")
    scenario = Scenario(
        values=dict(sampled_values),
        id=scenario_document.get("id", directory.name),
        metadata=scenario_document.get("metadata"),
    )

    sensor_setup = manifest.get("sensor_setup", {})
    if not isinstance(sensor_setup, Mapping):
        raise ValueError("manifest sensor_setup must be a mapping")
    raw_definitions = sensor_setup.get("definitions", {})
    if not isinstance(raw_definitions, Mapping):
        raise ValueError("manifest sensor definitions must be a mapping")
    sensor_definitions = {}
    for name, raw_definition in raw_definitions.items():
        definition = SensorDefinition.model_validate(raw_definition)
        sensor_definitions[name] = resolve_sensor_parameter_references(
            definition, getattr(scenario, "values", {}) or {}
        )

    sensor_bindings = []
    for raw_binding in sensor_setup.get("bindings", []) or []:
        if not isinstance(raw_binding, Mapping):
            raise ValueError("sensor binding must be a mapping")
        if "point_id" not in raw_binding:
            continue
        point_id = raw_binding.get("point_id")
        sensor_key = raw_binding.get("sensor_key")
        variable = raw_binding.get("variable", "pressure")
        if not isinstance(point_id, str) or not point_id:
            raise ValueError("sensor binding point_id must be a non-empty string")
        if not isinstance(sensor_key, str) or not sensor_key:
            raise ValueError("sensor binding sensor_key must be a non-empty string")
        if not isinstance(variable, str) or variable not in {"pressure", "flowrate"}:
            raise ValueError("sensor binding variable must be 'pressure' or 'flowrate'")
        sensor_bindings.append(
            WNTRSensorBinding(
                point_id=point_id,
                sensor_key=sensor_key,
                variable=variable,
            )
        )

    parameter_bindings = []
    for raw_binding in manifest_mapping.get("parameter_bindings", []) or []:
        if not isinstance(raw_binding, Mapping):
            raise ValueError("parameter binding must be a mapping")
        component_id = raw_binding.get("component_id")
        property_name = raw_binding.get("property")
        parameter_key = raw_binding.get("parameter_key")
        if not isinstance(component_id, str) or not component_id:
            raise ValueError(
                "parameter binding component_id must be a non-empty string"
            )
        if property_name not in {
            "diameter",
            "diameter_multiplier",
            "roughness",
            "base_demand",
            "valve_setting",
            "initial_status",
        }:
            raise ValueError(f"invalid parameter binding property: {property_name!r}")
        if not isinstance(parameter_key, str) or not parameter_key:
            raise ValueError(
                "parameter binding parameter_key must be a non-empty string"
            )
        parameter_bindings.append(
            WNTRParameterBinding(
                component_id=component_id,
                property=property_name,
                parameter_key=parameter_key,
            )
        )

    ptsnet_mapper = None
    ptsnet_wave_bindings = []
    ptsnet_surge_bindings = []
    ptsnet_sensor_bindings = []
    ptsnet_interior_bindings = []
    if backend == "ptsnet":
        (
            ptsnet_mapper,
            ptsnet_wave_bindings,
            ptsnet_surge_bindings,
            ptsnet_sensor_bindings,
            ptsnet_interior_bindings,
        ) = _ptsnet_mapper_from_manifest(
            manifest_mapping, sensor_definitions, backend_settings
        )

    _apply_dynamic_configuration(backend, model, manifest)

    def run(loaded_model: Any) -> Any:
        if backend == "wntr":
            return WNTRSimulator().run(loaded_model)
        if backend == "tsnetplus":
            from hydroforge.wdn_modelling.backends.tsnetplus import TSNetSPlusSimulator
            from hydroforge.wdn_modelling.backends.tsnetplus.config import (
                TSNetPlusConfig,
            )

            simulator = TSNetSPlusSimulator(
                config=TSNetPlusConfig(duration=0.0), inplace=True
            )
            return simulator.run(loaded_model)
        if backend == "ptsnet":
            if ptsnet_mapper is None:
                raise RuntimeError("PTSNet mapper configuration was not restored")
            return ptsnet_mapper._run(loaded_model)
        raise RuntimeError(f"unsupported backend: {backend}")

    def measure(
        loaded_model: Any,
        raw_results: WNTRSimulationResults,
        loaded_scenario: Any,
        specification: UncertaintySpecification | None,
        definitions: Mapping[str, SensorDefinition],
    ) -> dict[str, Any]:
        if backend == "ptsnet":
            if ptsnet_mapper is None:
                raise RuntimeError("PTSNet mapper configuration was not restored")
            return ptsnet_mapper._measure(
                loaded_model,
                raw_results,
                loaded_scenario,
                specification,
                definitions,
            )
        if not sensor_bindings or not definitions:
            return {}
        adapter = WNTRSensorAdapter(sensor_bindings, definitions)
        return adapter.apply(loaded_model, raw_results)

    ptsnet_sensor_seed_callback = None
    if backend == "ptsnet":
        if ptsnet_mapper is None:
            raise RuntimeError("PTSNet mapper configuration was not restored")
        ptsnet_sensor_seed_callback = ptsnet_mapper._sensor_seeds

    return SimulationInstance(
        model=model,
        scenario=scenario,
        specification=specification,
        run=run,
        measure=measure,
        parameter_bindings=parameter_bindings,
        sensor_bindings=(
            ptsnet_sensor_bindings if backend == "ptsnet" else sensor_bindings
        ),
        sensor_definitions=sensor_definitions,
        sensor_seeds=ptsnet_sensor_seed_callback,
        wave_speed_bindings=ptsnet_wave_bindings,
        surge_bindings=ptsnet_surge_bindings,
        interior_bindings=ptsnet_interior_bindings,
        ptsnet_source_directory=ptsnet_source_directory,
    )


# Aliases for likely public names.
save_simulation_instance = save_realization
load_simulation_instance = load_realization
save_bundle = save_realization
load_bundle = load_realization
save_uncertain_model = save_realization
load_uncertain_model = load_realization


__all__ = [
    "load_realization",
    "load_simulation_instance",
    "load_bundle",
    "load_uncertain_model",
    "save_realization",
    "save_simulation_instance",
    "save_bundle",
    "save_uncertain_model",
]
