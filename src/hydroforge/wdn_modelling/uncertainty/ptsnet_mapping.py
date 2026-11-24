"""PTSNet implementation of the Stage 3 model mapper."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

try:
    from hydroforge.wdn_modelling.backends.ptsnet import (
        PTSNetSimulator,
        PTSNetSimulationResults,
    )
    from hydroforge.wdn_modelling.backends.ptsnet.config import PTSNetConfig
    from hydroforge.wdn_modelling.backends.ptsnet.model import PTSNetModel
except Exception:  # pragma: no cover - optional dependency
    PTSNetSimulator = None
    PTSNetSimulationResults = Any
    PTSNetConfig = None
    PTSNetModel = Any

from hydroforge.wdn_modelling.mapping import (
    GenericModelMapper,
    UncertainModel,
    resolve_sensor_parameter_references,
)
from hydroforge.uncertainty.specification import (
    SensorDefinition,
    UncertaintySpecification,
)


@dataclass
class PTSNetWaveSpeedBinding:
    parameter_key: str
    pipes: Sequence[str] | None = None


@dataclass
class PTSNetSurgeProtectionBinding:
    node_id: str
    protection_type: str = "open"
    tank_area: float = 1.0
    tank_height: float | None = None
    water_level: float | None = None
    area_key: str | None = None
    height_key: str | None = None
    level_key: str | None = None


@dataclass
class PTSNetSensorBinding:
    node_id: str
    sensor_key: str
    variable: str = "head"


class PTSNetModelMapper(GenericModelMapper[PTSNetModel, PTSNetSimulationResults]):
    """Map one sampled scenario to a fresh PTSNet model."""

    def __init__(
        self,
        wave_speed_bindings: Sequence[PTSNetWaveSpeedBinding] = (),
        surge_protection_bindings: Sequence[PTSNetSurgeProtectionBinding] = (),
        sensor_bindings: Sequence[PTSNetSensorBinding] = (),
        sensor_definitions: Mapping[str, SensorDefinition] | None = None,
        simulator_config: Any | None = None,
        simulator: Any | None = None,
        clone_model: Callable[[PTSNetModel], PTSNetModel] | None = None,
        **kwargs: Any,
    ) -> None:
        self.wave_speed_bindings = tuple(wave_speed_bindings)
        self.surge_protection_bindings = tuple(surge_protection_bindings)
        self.sensor_bindings = tuple(sensor_bindings)
        self._sensor_definitions = dict(sensor_definitions or {})
        self._simulator = simulator
        self._simulator_config = simulator_config

        def apply(
            model: PTSNetModel, scenario: Any, specification: UncertaintySpecification
        ) -> None:
            values = getattr(scenario, "values", scenario)
            if not isinstance(values, Mapping):
                values = {}

            # Preflight all bindings before mutating the model.
            for wave_binding in self.wave_speed_bindings:
                if wave_binding.parameter_key not in values:
                    raise ValueError(
                        f"missing PTSNet wave-speed value {wave_binding.parameter_key!r}"
                    )
                try:
                    float(values[wave_binding.parameter_key])
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"invalid PTSNet wave-speed value {values[wave_binding.parameter_key]!r}"
                    ) from exc
            for protection in self.surge_protection_bindings:
                if protection.protection_type not in {"open", "closed"}:
                    raise ValueError(
                        f"unsupported PTSNet surge-protection type {protection.protection_type!r}"
                    )
                if protection.protection_type == "closed" and (
                    protection.tank_height is None
                    and protection.height_key is None
                    or protection.water_level is None
                    and protection.level_key is None
                ):
                    raise ValueError(
                        "closed PTSNet surge protection requires height and water level"
                    )
                for key in (
                    protection.area_key,
                    protection.height_key,
                    protection.level_key,
                ):
                    if key is not None and key not in values:
                        raise ValueError(
                            f"missing PTSNet surge-protection value {key!r}"
                        )
                    if key is not None:
                        try:
                            float(values[key])
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                f"invalid PTSNet surge-protection value {values[key]!r}"
                            ) from exc

            # Apply wave speeds.
            for wave_binding in self.wave_speed_bindings:
                value = values[wave_binding.parameter_key]
                pipes = None if wave_binding.pipes is None else list(wave_binding.pipes)
                if pipes is None:
                    if hasattr(model, "settings"):
                        try:
                            model.settings.default_wave_speed = float(value)
                        except Exception:
                            pass
                    ss = getattr(model, "ss", None)
                    if isinstance(ss, Mapping) and "pipe" in ss:
                        wave_speed = getattr(ss["pipe"], "wave_speed", None)
                        if wave_speed is not None:
                            try:
                                wave_speed[:] = float(value)
                            except Exception:
                                pass
                else:
                    ss = getattr(model, "ss", None)
                    if isinstance(ss, Mapping) and "pipe" in ss:
                        wave_speed = getattr(ss["pipe"], "wave_speed", None)
                        if wave_speed is not None:
                            for pipe in pipes:
                                wave_speed[pipe] = float(value)

            # Apply surge protection.
            for protection in self.surge_protection_bindings:
                area = protection.tank_area
                if protection.area_key is not None and protection.area_key in values:
                    area = float(values[protection.area_key])
                height = protection.tank_height
                if (
                    protection.height_key is not None
                    and protection.height_key in values
                ):
                    height = float(values[protection.height_key])
                level = protection.water_level
                if protection.level_key is not None and protection.level_key in values:
                    level = float(values[protection.level_key])
                if protection.protection_type == "closed":
                    if height is None or level is None:
                        raise ValueError(
                            "closed PTSNet surge protection requires height and water level"
                        )
                model.add_surge_protection(
                    protection.node_id,
                    protection.protection_type,
                    area,
                    tank_height=height,
                    water_level=level,
                )

        def run(model: PTSNetModel) -> PTSNetSimulationResults:
            active_simulator = self._simulator
            if active_simulator is None:
                if PTSNetSimulator is None or PTSNetConfig is None:
                    raise RuntimeError("PTSNet is not installed")
                config = self._simulator_config
                if config is None:
                    config = PTSNetConfig()
                active_simulator = PTSNetSimulator(config=config)
            config = getattr(active_simulator, "config", None)
            if config is not None:
                try:
                    config.apply_to(model)
                except Exception:
                    pass
            return active_simulator.run(model)

        def measure(
            model: PTSNetModel,
            raw_results: PTSNetSimulationResults,
            scenario: Any,
            specification: UncertaintySpecification | None,
            definitions: Mapping[str, SensorDefinition],
        ) -> dict[str, Any]:
            if not self.sensor_bindings:
                return {}
            values = getattr(scenario, "values", scenario)
            if not isinstance(values, Mapping):
                values = {}
            resolved_definitions = {
                key: _derive_sensor_seeds(
                    resolve_sensor_parameter_references(definition, values),
                    _realization_seed(scenario),
                    key,
                )
                for key, definition in self._sensor_definitions.items()
            }
            measured: dict[str, Any] = {}
            for binding in self.sensor_bindings:
                if binding.sensor_key not in resolved_definitions:
                    raise ValueError(
                        f"missing PTSNet sensor definition {binding.sensor_key!r}"
                    )
                definition = resolved_definitions[binding.sensor_key]
                sensor = definition.create_sensor()
                series = raw_results.get_node_variable(
                    binding.variable, [binding.node_id], as_dataframe=True
                )
                if binding.node_id not in getattr(series, "columns", []):
                    raise ValueError(
                        f"PTSNet results contain no column for {binding.node_id!r}"
                    )
                measured_series = sensor.measure(series[binding.node_id].copy())
                measured.setdefault(binding.variable, {})[
                    binding.node_id
                ] = measured_series
            result: dict[str, Any] = {}
            for variable, columns in measured.items():
                if isinstance(columns, dict):
                    import pandas as pd

                    result[variable] = pd.DataFrame(columns)
                else:
                    result[variable] = columns
            return result

        def sensor_seeds(
            model: PTSNetModel,
            raw_results: PTSNetSimulationResults,
            scenario: Any,
            specification: UncertaintySpecification | None,
            definitions: Mapping[str, SensorDefinition],
        ) -> dict[str, Any]:
            values = getattr(scenario, "values", scenario)
            if not isinstance(values, Mapping):
                values = {}
            resolved_definitions = {
                key: _derive_sensor_seeds(
                    resolve_sensor_parameter_references(definition, values),
                    _realization_seed(scenario),
                    key,
                )
                for key, definition in self._sensor_definitions.items()
            }
            seeds: dict[str, Any] = {}
            for key, definition in resolved_definitions.items():
                seed = _random_noise_seed(definition)
                if seed is not None:
                    seeds[key] = seed
            return seeds

        super().__init__(
            clone_model=clone_model or copy.deepcopy,
            apply_parameters=apply,
            run_model=run,
            measure_sensors=measure,
            sensor_seeds=sensor_seeds,
            sensor_definitions=self._sensor_definitions,
        )

    def map(
        self,
        specification: UncertaintySpecification,
        model: PTSNetModel,
    ) -> UncertainModel[PTSNetModel, PTSNetSimulationResults]:
        return super().map(specification, model)


def _realization_seed(scenario: Any) -> int | None:
    metadata = getattr(scenario, "metadata", None)
    if isinstance(metadata, Mapping):
        seed = metadata.get("effective_seed")
        if seed is not None:
            try:
                return int(seed)
            except (TypeError, ValueError):
                return None
    seed = getattr(scenario, "seed", None)
    if seed is not None:
        try:
            return int(seed)
        except (TypeError, ValueError):
            return None
    return None


def _sensor_definition_from_raw(raw: Any) -> SensorDefinition:
    if isinstance(raw, SensorDefinition):
        return raw
    return SensorDefinition.model_validate(raw)


def _random_noise_seed(definition: SensorDefinition) -> Any:
    if definition.type == "RandomNoise":
        return definition.parameters.get("seed")
    if definition.type == "Composite":
        parameters = definition.parameters
        nested = parameters.get("sensors")
        if isinstance(nested, list):
            seeds = [
                _random_noise_seed(_sensor_definition_from_raw(item)) for item in nested
            ]
            if any(seed is not None for seed in seeds):
                return seeds
    return None


def _derive_sensor_seeds(
    definition: SensorDefinition,
    realization_seed: int | None,
    sensor_name: str,
) -> SensorDefinition:
    from hydroforge.wdn_modelling.mapping import derive_deterministic_seed

    if definition.type == "RandomNoise":
        parameters = dict(definition.parameters)
        if parameters.get("seed") is None:
            derived = derive_deterministic_seed(realization_seed, sensor_name)
            if derived is not None:
                parameters["seed"] = derived
        return SensorDefinition(type=definition.type, parameters=parameters)

    if definition.type == "Composite":
        parameters = dict(definition.parameters)
        nested = parameters.get("sensors")
        if isinstance(nested, list):
            parameters["sensors"] = [
                _derive_sensor_seeds(
                    _sensor_definition_from_raw(item),
                    realization_seed,
                    f"{sensor_name}.{index}",
                )
                for index, item in enumerate(nested)
            ]
        return SensorDefinition(type=definition.type, parameters=parameters)

    return definition


__all__ = [
    "PTSNetModel",
    "PTSNetModelMapper",
    "PTSNetSensorBinding",
    "PTSNetSurgeProtectionBinding",
    "PTSNetWaveSpeedBinding",
]
