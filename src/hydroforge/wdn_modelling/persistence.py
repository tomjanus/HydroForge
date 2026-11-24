"""Persistence for Stage 3 WNTR realization bundles."""

from __future__ import annotations

import dataclasses
import json
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

    model_artifact = "model.inp"
    model_path = directory / model_artifact
    wntr.network.io.write_inpfile(model, str(model_path))

    parameter_bindings = getattr(instance, "parameter_bindings", None)
    if parameter_bindings is None:
        parameter_bindings = kwargs.get("parameter_bindings", [])
    sensor_bindings = getattr(instance, "sensor_bindings", None)
    if sensor_bindings is None:
        sensor_bindings = kwargs.get("sensor_bindings", [])

    sensor_definitions = getattr(instance, "sensor_definitions", {}) or {}
    resolved_sensor_definitions = {}
    for name, definition in sensor_definitions.items():
        resolved_sensor_definitions[name] = resolve_sensor_parameter_references(
            definition, getattr(scenario, "values", {}) or {}
        )

    manifest = {
        "manifest_version": "1.0",
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
        },
        "backend_settings": kwargs.get("backend_settings", {}),
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
    model = wntr.network.io.read_inpfile(str(model_path))

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
    for raw_binding in manifest.get("mapping", {}).get("parameter_bindings", []) or []:
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

    def run(loaded_model: Any) -> WNTRSimulationResults:
        return WNTRSimulator().run(loaded_model)

    def measure(
        loaded_model: Any,
        raw_results: WNTRSimulationResults,
        loaded_scenario: Any,
        specification: UncertaintySpecification | None,
        definitions: Mapping[str, SensorDefinition],
    ) -> dict[str, Any]:
        if not sensor_bindings or not definitions:
            return {}
        adapter = WNTRSensorAdapter(sensor_bindings, definitions)
        return adapter.apply(loaded_model, raw_results)

    return SimulationInstance(
        model=model,
        scenario=scenario,
        specification=specification,
        run=run,
        measure=measure,
        parameter_bindings=parameter_bindings,
        sensor_bindings=sensor_bindings,
        sensor_definitions=sensor_definitions,
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
