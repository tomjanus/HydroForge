"""TSNetPlus implementation of the Stage 3 model mapper."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

try:
    import tsnetplus
    from hydroforge.wdn_modelling.backends.tsnetplus import (
        TSNetSPlusSimulator,
        TSNetPlusSimulationResults,
    )
    from hydroforge.wdn_modelling.backends.tsnetplus.config import TSNetPlusConfig
    from hydroforge.wdn_modelling.backends.tsnetplus.model import TSNetPlusModel
except Exception:  # pragma: no cover - optional dependency
    tsnetplus = None
    TSNetSPlusSimulator = None
    TSNetPlusSimulationResults = Any
    TSNetPlusConfig = None
    TSNetPlusModel = Any

from hydroforge.wdn_modelling.mapping import (
    GenericModelMapper,
    UncertainModel,
    derive_deterministic_seed,
    resolve_sensor_parameter_references,
)
from hydroforge.uncertainty.specification import (
    SensorDefinition,
    UncertaintySpecification,
)


@dataclass
class TSNetPlusWaveSpeedBinding:
    parameter_key: str
    pipes: Sequence[str] | None = None


@dataclass
class TSNetPlusSurgeTankBinding:
    node_id: str
    tank_type: str = "open"
    shape: Sequence[float] = field(default_factory=lambda: (1.0,))
    area_key: str | None = None
    height_key: str | None = None
    level_key: str | None = None


@dataclass
class TSNetPlusSensorBinding:
    node_id: str
    sensor_key: str
    variable: str = "head"


class TSNetPlusModelMapper(
    GenericModelMapper[TSNetPlusModel, TSNetPlusSimulationResults]
):
    """Map one sampled scenario to a fresh TSNetPlus model."""

    def __init__(
        self,
        wave_speed_bindings: Sequence[TSNetPlusWaveSpeedBinding] = (),
        surge_tank_bindings: Sequence[TSNetPlusSurgeTankBinding] = (),
        sensor_bindings: Sequence[TSNetPlusSensorBinding] = (),
        sensor_definitions: Mapping[str, SensorDefinition] | None = None,
        simulator_config: Any | None = None,
        simulator: Any | None = None,
        clone_model: Callable[[TSNetPlusModel], TSNetPlusModel] | None = None,
        **kwargs: Any,
    ) -> None:
        self.wave_speed_bindings = tuple(wave_speed_bindings)
        self.surge_tank_bindings = tuple(surge_tank_bindings)
        self.sensor_bindings = tuple(sensor_bindings)
        self._sensor_definitions = dict(sensor_definitions or {})
        self._simulator = simulator
        self._simulator_config = simulator_config
        self._sensor_adapter = None

        def apply(
            model: TSNetPlusModel,
            scenario: Any,
            specification: UncertaintySpecification,
        ) -> None:
            values = getattr(scenario, "values", scenario)
            if not isinstance(values, Mapping):
                values = {}

            # Preflight all bindings before mutating the model.
            for wave_binding in self.wave_speed_bindings:
                if wave_binding.parameter_key not in values:
                    raise ValueError(
                        f"missing TSNetPlus wave-speed value {wave_binding.parameter_key!r}"
                    )
                try:
                    float(values[wave_binding.parameter_key])
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"invalid TSNetPlus wave-speed value {values[wave_binding.parameter_key]!r}"
                    ) from exc
            for tank_binding in self.surge_tank_bindings:
                if tank_binding.tank_type not in {"open", "closed"}:
                    raise ValueError(
                        f"unsupported TSNetPlus surge-tank type {tank_binding.tank_type!r}"
                    )
                if tank_binding.tank_type == "open":
                    if len(tank_binding.shape) != 1:
                        raise ValueError(
                            "open TSNetPlus surge-tank shape must be (area,)"
                        )
                else:
                    if len(tank_binding.shape) != 3:
                        raise ValueError(
                            "closed TSNetPlus surge-tank shape must be "
                            "(area, height, initial_water_height)"
                        )
                for key in (
                    tank_binding.area_key,
                    tank_binding.height_key,
                    tank_binding.level_key,
                ):
                    if key is not None and key not in values:
                        raise ValueError(f"missing TSNetPlus surge-tank value {key!r}")
                    if key is not None:
                        try:
                            float(values[key])
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                f"invalid TSNetPlus surge-tank value {values[key]!r}"
                            ) from exc

            for wave_binding in self.wave_speed_bindings:
                if wave_binding.pipes is None:
                    model.set_wavespeed(values[wave_binding.parameter_key])
                else:
                    model.set_wavespeed(
                        values[wave_binding.parameter_key],
                        pipes=list(wave_binding.pipes),
                    )
            for tank_binding in self.surge_tank_bindings:
                shape = list(tank_binding.shape)
                if (
                    tank_binding.area_key is not None
                    and tank_binding.area_key in values
                ):
                    shape[0] = values[tank_binding.area_key]
                if tank_binding.tank_type == "closed":
                    if (
                        tank_binding.height_key is not None
                        and tank_binding.height_key in values
                    ):
                        shape[1] = values[tank_binding.height_key]
                    if (
                        tank_binding.level_key is not None
                        and tank_binding.level_key in values
                    ):
                        shape[2] = values[tank_binding.level_key]
                model.add_surge_tank(
                    tank_binding.node_id, tuple(shape), tank_binding.tank_type
                )

        def run(model: TSNetPlusModel) -> TSNetPlusSimulationResults:
            active_simulator = self._simulator
            if active_simulator is None:
                if TSNetSPlusSimulator is None or TSNetPlusConfig is None:
                    raise RuntimeError("TSNetPlus is not installed")
                config = self._simulator_config
                if config is None:
                    config = TSNetPlusConfig(duration=0.0)
                try:
                    config.wave_speed = [
                        getattr(pipe, "wavev", config.wave_speed)
                        for _, pipe in model.pipes()
                    ]
                except Exception:
                    pass
                active_simulator = TSNetSPlusSimulator(config=config, inplace=True)
            return active_simulator.run(model)

        def measure(
            model: TSNetPlusModel,
            raw_results: TSNetPlusSimulationResults,
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
                        f"missing TSNetPlus sensor definition {binding.sensor_key!r}"
                    )
                definition = resolved_definitions[binding.sensor_key]
                sensor = definition.create_sensor()
                series = raw_results.get_node_variable(
                    binding.variable, [binding.node_id], as_dataframe=True
                )
                if binding.node_id not in series.columns:
                    raise ValueError(
                        f"TSNetPlus results contain no column for {binding.node_id!r}"
                    )
                measured_series = sensor.measure(series[binding.node_id].copy())
                measured.setdefault(binding.variable, {})[
                    binding.node_id
                ] = measured_series
            # Flatten to variable -> DataFrame where possible.
            result: dict[str, Any] = {}
            for variable, columns in measured.items():
                if isinstance(columns, dict):
                    import pandas as pd

                    result[variable] = pd.DataFrame(columns)
                else:
                    result[variable] = columns
            return result

        def sensor_seeds(
            model: TSNetPlusModel,
            raw_results: TSNetPlusSimulationResults,
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
        model: TSNetPlusModel,
    ) -> UncertainModel[TSNetPlusModel, TSNetPlusSimulationResults]:
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
    "TSNetPlusModelMapper",
    "TSNetPlusSensorBinding",
    "TSNetPlusSurgeTankBinding",
    "TSNetPlusWaveSpeedBinding",
]
