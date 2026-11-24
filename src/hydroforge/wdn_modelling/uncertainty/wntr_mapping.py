"""WNTR implementation of the Stage 3 model mapper."""

from __future__ import annotations

import copy
import hashlib
from typing import Any, Callable, Mapping, Sequence, cast

import numpy as np
from wntr.network import WaterNetworkModel as WNTRModel

from hydroforge.wdn_modelling.backends.wntr import WNTRSimulator
from hydroforge.wdn_modelling.backends.wntr.results import WNTRSimulationResults
from hydroforge.wdn_modelling.mapping import (
    GenericModelMapper,
    UncertainModel,
    resolve_sensor_parameter_references,
)
from hydroforge.uncertainty.specification import (
    SensorDefinition,
    UncertaintySpecification,
)
from .parameters import (
    WNTRParameterAdapter,
    WNTRParameterBinding,
)
from .sensors import WNTRSensorAdapter, WNTRSensorBinding


class WNTRModelMapper(GenericModelMapper[WNTRModel, WNTRSimulationResults]):
    """Map one sampled scenario to a fresh WNTR model."""

    def __init__(
        self,
        parameter_bindings: Sequence[WNTRParameterBinding] = (),
        bindings: Sequence[WNTRParameterBinding] = (),
        sensor_bindings: Sequence[WNTRSensorBinding] = (),
        sensor_definitions: Mapping[str, SensorDefinition] | None = None,
        simulator: Any | None = None,
        clone_model: Callable[[WNTRModel], WNTRModel] | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_bindings = tuple(
            parameter_bindings or bindings or kwargs.get("bindings", ())
        )
        self.parameter_bindings = resolved_bindings
        self.sensor_bindings = tuple(sensor_bindings)
        self._sensor_definitions = dict(sensor_definitions or {})
        self._simulator = simulator
        self._parameter_adapter = WNTRParameterAdapter(self.parameter_bindings)
        self._sensor_adapter = (
            WNTRSensorAdapter(self.sensor_bindings, self._sensor_definitions)
            if self.sensor_bindings or self._sensor_definitions
            else None
        )

        def apply(
            model: WNTRModel, scenario: Any, specification: UncertaintySpecification
        ) -> None:
            values = getattr(scenario, "values", scenario)
            self._parameter_adapter.apply(model, values)

        def run(model: WNTRModel) -> WNTRSimulationResults:
            active_simulator = self._simulator
            if active_simulator is None:
                active_simulator = WNTRSimulator()
            return active_simulator.run(model)

        def measure(
            model: WNTRModel,
            raw_results: WNTRSimulationResults,
            scenario: Any,
            specification: UncertaintySpecification | None,
            definitions: Mapping[str, SensorDefinition],
        ) -> dict[str, Any]:
            if self._sensor_adapter is None:
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
            adapter = WNTRSensorAdapter(self.sensor_bindings, resolved_definitions)
            return cast(dict[str, Any], adapter.apply(model, raw_results))

        def sensor_seeds(
            model: WNTRModel,
            raw_results: WNTRSimulationResults,
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
        model: WNTRModel,
    ) -> UncertainModel[WNTRModel, WNTRSimulationResults]:
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


def _derive_seed(realization_seed: int | None, sensor_name: str) -> int | None:
    if realization_seed is None:
        return None
    state = np.random.SeedSequence(
        [int(realization_seed), _stable_hash(sensor_name)]
    ).generate_state(1)
    return int(state[0])


def _stable_hash(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest(), 16)


def _derive_sensor_seeds(
    definition: SensorDefinition,
    realization_seed: int | None,
    sensor_name: str,
) -> SensorDefinition:
    if definition.type == "RandomNoise":
        parameters = dict(definition.parameters)
        if parameters.get("seed") is None:
            derived = _derive_seed(realization_seed, sensor_name)
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


__all__ = [
    "WNTRModel",
    "WNTRModelMapper",
]
