"""PTSNet implementation of the Stage 3 model mapper."""

from __future__ import annotations

import copy
import os
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import numpy as np

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


@dataclass
class PTSNetInteriorSensorBinding:
    pipe_id: str
    sensor_key: str
    quantity: str = "head"
    name: str | None = None
    fraction: float | None = None
    index: int | None = None

    def __post_init__(self) -> None:
        if self.quantity not in {"head", "flowrate"}:
            raise ValueError(
                "PTSNet interior quantity must be 'head' or 'flowrate', "
                f"got {self.quantity!r}"
            )
        if self.fraction is None and self.index is None:
            raise ValueError("an interior sensor needs a fraction or mesh index")
        if self.fraction is not None and self.index is not None:
            raise ValueError("use either a fraction or a mesh index, not both")


class PTSNetModelMapper(GenericModelMapper[PTSNetModel, PTSNetSimulationResults]):
    """Map one sampled scenario to a fresh PTSNet model."""

    def __init__(
        self,
        wave_speed_bindings: Sequence[PTSNetWaveSpeedBinding] = (),
        surge_protection_bindings: Sequence[PTSNetSurgeProtectionBinding] = (),
        sensor_bindings: Sequence[PTSNetSensorBinding] = (),
        interior_sensor_bindings: Sequence[PTSNetInteriorSensorBinding] = (),
        sensor_definitions: Mapping[str, SensorDefinition] | None = None,
        simulator_config: Any | None = None,
        simulator: Any | None = None,
        clone_model: Callable[[PTSNetModel], PTSNetModel] | None = None,
        **kwargs: Any,
    ) -> None:
        self.wave_speed_bindings = tuple(wave_speed_bindings)
        self.surge_protection_bindings = tuple(surge_protection_bindings)
        self.sensor_bindings = tuple(sensor_bindings)
        self.interior_sensor_bindings = tuple(interior_sensor_bindings)
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

            # Register configured interior capture locations before simulation.
            for binding in self.interior_sensor_bindings:
                if not hasattr(model, "add_pipe_output"):
                    raise RuntimeError(
                        "PTSNet interior capture requires add_pipe_output; "
                        "install a PTSNet version that supports it"
                    )
                output_name = binding.name or binding.sensor_key
                position = (
                    binding.fraction if binding.fraction is not None else binding.index
                )
                position_type = "fraction" if binding.fraction is not None else "index"
                model.add_pipe_output(
                    output_name,
                    binding.pipe_id,
                    position,
                    position_type,
                    variables=(binding.quantity,),
                )

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
                        if isinstance(wave_speed, np.ndarray):
                            wave_speed[:] = float(value)
                            model._hydroforge_wave_speed_overridden = True
                else:
                    ss = getattr(model, "ss", None)
                    if isinstance(ss, Mapping) and "pipe" in ss:
                        wave_speed = getattr(ss["pipe"], "wave_speed", None)
                        if wave_speed is not None:
                            for pipe in pipes:
                                wave_speed[pipe] = float(value)
                            model._hydroforge_wave_speed_overridden = True

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
                config = self._simulator_config or PTSNetConfig()
                active_simulator = PTSNetSimulator(config=config)
            return active_simulator.run(model)

        def measure(
            model: PTSNetModel,
            raw_results: PTSNetSimulationResults,
            scenario: Any,
            specification: UncertaintySpecification | None,
            definitions: Mapping[str, SensorDefinition],
        ) -> dict[str, Any]:
            if not self.sensor_bindings and not self.interior_sensor_bindings:
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
                series = _ptsnet_node_series(
                    raw_results, binding.variable, binding.node_id
                )
                if series is None:
                    raise ValueError(
                        f"PTSNet results contain no column for {binding.node_id!r}"
                    )
                measured_series = sensor.measure(series.copy())
                measured.setdefault(binding.variable, {})[
                    binding.node_id
                ] = measured_series

            interior_results = getattr(raw_results, "interior_results", None)
            if interior_results is None and isinstance(raw_results, Mapping):
                interior_results = raw_results.get("interior_results")
            if interior_results is None:
                interior_results = getattr(
                    getattr(raw_results, "model", None), "interior_results", {}
                )
            for interior_binding in self.interior_sensor_bindings:
                if interior_binding.sensor_key not in resolved_definitions:
                    raise ValueError(
                        f"missing PTSNet sensor definition {interior_binding.sensor_key!r}"
                    )
                definition = resolved_definitions[interior_binding.sensor_key]
                sensor = definition.create_sensor()
                output_name = interior_binding.name or interior_binding.sensor_key
                if (
                    not isinstance(interior_results, Mapping)
                    or output_name not in interior_results
                ):
                    raise ValueError(
                        f"PTSNet results contain no interior output for {output_name!r}"
                    )
                quantity_results = interior_results[output_name]
                if interior_binding.quantity not in quantity_results:
                    raise ValueError(
                        f"PTSNet interior output {output_name!r} has no {interior_binding.quantity!r}"
                    )
                values = quantity_results[interior_binding.quantity]
                timestamps = _ptsnet_timestamps(raw_results)
                if timestamps is None:
                    raise ValueError("PTSNet results do not expose a time_stamps axis")
                if len(timestamps) != len(np.asarray(values)):
                    raise ValueError(
                        "PTSNet timestamps and interior output have different lengths"
                    )
                import pandas as pd

                series = pd.Series(
                    np.asarray(values, dtype=float),
                    index=pd.Index(timestamps, name="time"),
                    name=output_name,
                )
                measured_series = sensor.measure(series.copy())
                measured.setdefault(interior_binding.quantity, {})[
                    output_name
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

        def _clone(model: PTSNetModel) -> PTSNetModel:
            if clone_model is not None:
                return clone_model(model)

            inpfile = getattr(model, "inpfile", None) or getattr(
                model, "_inpfile", None
            )
            if inpfile is None:
                return copy.deepcopy(model)

            try:
                inpfile_path = os.fspath(inpfile)
            except TypeError as exc:
                raise ValueError(
                    "PTSNet model inpfile must be a filesystem path"
                ) from exc
            if not inpfile_path:
                raise ValueError("PTSNet model inpfile cannot be empty")

            if PTSNetConfig is None:
                raise RuntimeError("PTSNet is required to clone this model")
            from ptsnet.simulation.sim import PTSNETSimulation

            config = self._simulator_config
            if config is None and self._simulator is not None:
                config = getattr(self._simulator, "config", None)
            if config is None:
                config = PTSNetConfig()
            settings_factory = getattr(config, "_to_settings", None)
            if not callable(settings_factory):
                raise TypeError(
                    "PTSNet simulator config must provide a _to_settings() method"
                )

            workspace = getattr(model, "workspace_name", "hydroforge")
            unique_workspace = f"{workspace}_realization_{uuid.uuid4().hex}"
            settings = settings_factory()
            cloned = PTSNETSimulation(
                workspace_name=unique_workspace,
                inpfile=inpfile_path,
                settings=settings,
            )
            cloned._hydroforge_config_settings = settings
            return cloned

        super().__init__(
            clone_model=_clone,
            apply_parameters=apply,
            run_model=run,
            measure_sensors=measure,
            sensor_seeds=sensor_seeds,
            wave_speed_bindings=self.wave_speed_bindings,
            surge_bindings=self.surge_protection_bindings,
            interior_bindings=self.interior_sensor_bindings,
            sensor_bindings=self.sensor_bindings,
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


def _ptsnet_node_series(raw_results: Any, variable: str, node_id: str) -> Any:
    """Return a node result series from a wrapper, raw model, or raw table dict."""
    model = getattr(raw_results, "model", None)
    results = None
    if isinstance(raw_results, Mapping):
        if "node" in raw_results:
            results = raw_results
        elif isinstance(raw_results.get("results"), Mapping):
            results = raw_results["results"]
            model = raw_results.get("model", model)
    if results is None:
        if model is None:
            model = raw_results
        results = getattr(model, "results", None)

    if isinstance(results, Mapping) and "node" in results:
        table = results["node"]
        try:
            values = np.asarray(getattr(table, variable))
            labels = list(getattr(table, "labels", []))
            if node_id not in labels:
                return None
            timestamps = _ptsnet_timestamps(raw_results)
            if timestamps is None:
                timestamps = range(values.shape[1] if values.ndim == 2 else len(values))
            import pandas as pd

            frame = pd.DataFrame(
                values.T if values.ndim == 2 else values.reshape(-1, 1),
                index=pd.Index(timestamps, name="time"),
                columns=labels,
            )
            if node_id in frame.columns:
                return frame[node_id]
        except Exception:
            return None
    return None


def _ptsnet_timestamps(raw_results: Any) -> Any:
    """Return the native PTSNet time axis, when available."""
    model = getattr(raw_results, "model", raw_results)
    for attribute in ("time_stamps", "simulation_timestamps", "time"):
        timestamps = getattr(model, attribute, None)
        if timestamps is not None:
            return timestamps
    if isinstance(raw_results, Mapping):
        for key in ("time_stamps", "simulation_timestamps", "time"):
            timestamps = raw_results.get(key)
            if timestamps is not None:
                return timestamps
        nested_model = raw_results.get("model")
        if nested_model is not None:
            for attribute in ("time_stamps", "simulation_timestamps", "time"):
                timestamps = getattr(nested_model, attribute, None)
                if timestamps is not None:
                    return timestamps
    return None


__all__ = [
    "PTSNetModel",
    "PTSNetModelMapper",
    "PTSNetSensorBinding",
    "PTSNetSurgeProtectionBinding",
    "PTSNetWaveSpeedBinding",
]
