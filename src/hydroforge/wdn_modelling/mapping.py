"""Generic typed mapping runtime for Stage 3 uncertain models.

This module defines the small common boundary that maps a generic
``UncertaintySpecification`` and a backend model to an ``UncertainModel``.
Backend-specific cloning, application, simulation, and sensor measurement
are supplied through callables or subclasses; this module contains no
WNTR, TSNetPlus, or PTSNET implementation.
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Generic,
    Mapping,
    Protocol,
    TypeVar,
    cast,
    runtime_checkable,
)

import numpy as np

from hydroforge.uncertainty.specification import (
    SensorDefinition,
    UncertaintySpecification,
)

ModelT = TypeVar("ModelT")
ResultT = TypeVar("ResultT")


def derive_deterministic_seed(realization_seed: int | None, name: str) -> int | None:
    """Derive a deterministic integer seed from a realization seed and name."""
    if realization_seed is None:
        return None
    state = np.random.SeedSequence(
        [
            int(realization_seed),
            int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16),
        ]
    ).generate_state(1)
    return int(state[0])


def _scenario_values(scenario: Any) -> Mapping[str, Any]:
    values = getattr(scenario, "values", None)
    if isinstance(values, Mapping):
        return values
    if isinstance(scenario, Mapping):
        return scenario
    return {}


def _is_parameter_reference(value: Any) -> bool:
    return isinstance(value, dict) and len(value) == 1 and "$parameter" in value


def resolve_sensor_parameter_references(
    definition: SensorDefinition,
    scenario_values: Mapping[str, Any],
) -> SensorDefinition:
    """Return a copy of ``definition`` with ``$parameter`` references resolved.

    The returned definition contains no unresolved references and can be
    used to construct a fresh live sensor for the realization.
    """

    def _resolve(value: Any) -> Any:
        if _is_parameter_reference(value):
            name = value["$parameter"]
            if not isinstance(name, str):
                raise ValueError("a $parameter reference must name a string parameter")
            if name not in scenario_values:
                raise ValueError(
                    f"unresolved sensor parameter reference {name!r}; "
                    "realization values do not contain it"
                )
            return scenario_values[name]
        if isinstance(value, dict):
            return {key: _resolve(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            resolved = [_resolve(item) for item in value]
            return tuple(resolved) if isinstance(value, tuple) else resolved
        return value

    resolved_parameters = _resolve(dict(definition.parameters))
    return SensorDefinition(type=definition.type, parameters=resolved_parameters)


@runtime_checkable
class ModelMapper(Protocol[ModelT]):
    """Typed boundary for mapping a specification and baseline model."""

    def map(
        self,
        specification: UncertaintySpecification,
        model: ModelT,
    ) -> "UncertainModel[ModelT, Any]":
        """Return an uncertain-model wrapper for ``model``."""


@dataclass
class SimulationResult(Generic[ModelT, ResultT]):
    """Typed result returned by ``SimulationInstance.run``."""

    raw_results: ResultT
    measured_outputs: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def raw(self) -> ResultT:
        return self.raw_results

    @property
    def sensor_outputs(self) -> dict[str, Any]:
        return self.measured_outputs

    @property
    def scenario(self) -> Any:
        return self.provenance.get("scenario")

    @property
    def measured(self) -> dict[str, Any]:
        return self.measured_outputs


class SimulationInstance(Generic[ModelT, ResultT]):
    """One realized, simulation-ready backend instance."""

    def __init__(
        self,
        model: ModelT,
        scenario: Any,
        specification: UncertaintySpecification | None = None,
        *,
        run: Callable[[ModelT], ResultT] | None = None,
        run_model: Callable[[ModelT], ResultT] | None = None,
        runner: Callable[[ModelT], ResultT] | None = None,
        measure: (
            Callable[
                [
                    ModelT,
                    ResultT,
                    Any,
                    UncertaintySpecification | None,
                    Mapping[str, SensorDefinition],
                ],
                Any,
            ]
            | None
        ) = None,
        measure_sensors: (
            Callable[
                [
                    ModelT,
                    ResultT,
                    Any,
                    UncertaintySpecification | None,
                    Mapping[str, SensorDefinition],
                ],
                Any,
            ]
            | None
        ) = None,
        sensor_definitions: Mapping[str, SensorDefinition] | None = None,
        resolved_sensor_definitions: Mapping[str, SensorDefinition] | None = None,
        sensor_seeds: (
            Callable[
                [
                    ModelT,
                    ResultT,
                    Any,
                    UncertaintySpecification | None,
                    Mapping[str, SensorDefinition],
                ],
                Any,
            ]
            | None
        ) = None,
        parameter_bindings: Any = None,
        sensor_bindings: Any = None,
        **kwargs: Any,
    ) -> None:
        self.model = model
        self.scenario = scenario
        self.specification = specification
        self._run = run or run_model or runner
        self._measure = measure or measure_sensors
        self._sensor_seeds = sensor_seeds
        self.parameter_bindings = parameter_bindings
        self.sensor_bindings = sensor_bindings
        self.sensor_definitions = dict(
            resolved_sensor_definitions or sensor_definitions or {}
        )
        self.extra = kwargs

    def run(self) -> SimulationResult[ModelT, ResultT]:
        """Run the instance and preserve raw results, measurements, and provenance."""
        if not callable(self._run):
            raise TypeError("SimulationInstance requires a run callable")
        raw_results = self._run(self.model)
        scenario_values = _scenario_values(self.scenario)
        resolved_definitions = {
            key: resolve_sensor_parameter_references(definition, scenario_values)
            for key, definition in self.sensor_definitions.items()
        }
        measured_outputs: dict[str, Any] = {}
        if callable(self._measure):
            measured = self._measure(
                self.model,
                raw_results,
                self.scenario,
                self.specification,
                resolved_definitions,
            )
            if isinstance(measured, Mapping):
                measured_outputs = dict(measured)
            else:
                measured_outputs = {"measured_outputs": measured}
        sensor_seed_values: dict[str, Any] = {}
        if callable(self._sensor_seeds):
            seeds = self._sensor_seeds(
                self.model,
                raw_results,
                self.scenario,
                self.specification,
                resolved_definitions,
            )
            if isinstance(seeds, Mapping):
                sensor_seed_values = dict(seeds)
        provenance = {
            "scenario": self.scenario,
            "scenario_id": getattr(self.scenario, "id", None),
            "values": getattr(self.scenario, "values", None),
            "metadata": getattr(self.scenario, "metadata", None),
            "sensor_seeds": sensor_seed_values,
        }
        return SimulationResult(
            raw_results=raw_results,
            measured_outputs=measured_outputs,
            provenance=provenance,
        )


class UncertainModel(Generic[ModelT, ResultT]):
    """Wrapper that realizes one scenario at a time from a baseline model."""

    def __init__(
        self,
        specification: UncertaintySpecification,
        model: ModelT | None = None,
        baseline_model: ModelT | None = None,
        baseline: ModelT | None = None,
        *,
        clone: Callable[[ModelT], ModelT] | None = None,
        clone_model: Callable[[ModelT], ModelT] | None = None,
        apply: Callable[[ModelT, Any, UncertaintySpecification], None] | None = None,
        apply_parameters: (
            Callable[[ModelT, Any, UncertaintySpecification], None] | None
        ) = None,
        apply_values: (
            Callable[[ModelT, Any, UncertaintySpecification], None] | None
        ) = None,
        run: Callable[[ModelT], ResultT] | None = None,
        run_model: Callable[[ModelT], ResultT] | None = None,
        runner: Callable[[ModelT], ResultT] | None = None,
        measure: (
            Callable[
                [
                    ModelT,
                    ResultT,
                    Any,
                    UncertaintySpecification | None,
                    Mapping[str, SensorDefinition],
                ],
                Any,
            ]
            | None
        ) = None,
        measure_sensors: (
            Callable[
                [
                    ModelT,
                    ResultT,
                    Any,
                    UncertaintySpecification | None,
                    Mapping[str, SensorDefinition],
                ],
                Any,
            ]
            | None
        ) = None,
        sensor_seeds: (
            Callable[
                [
                    ModelT,
                    ResultT,
                    Any,
                    UncertaintySpecification | None,
                    Mapping[str, SensorDefinition],
                ],
                Any,
            ]
            | None
        ) = None,
        parameter_bindings: Any = None,
        sensor_bindings: Any = None,
        sensor_definitions: Mapping[str, SensorDefinition] | None = None,
        **kwargs: Any,
    ) -> None:
        if model is None and baseline_model is None and baseline is None:
            raise TypeError("UncertainModel requires a baseline model")
        self.specification = specification
        self.baseline_model = (
            model
            if model is not None
            else (baseline_model if baseline_model is not None else baseline)
        )
        self._clone = clone or clone_model or copy.deepcopy
        self._apply = apply or apply_parameters or apply_values
        self._run = run or run_model or runner
        self._measure = measure or measure_sensors
        self._sensor_seeds = sensor_seeds
        self.parameter_bindings = parameter_bindings
        self.sensor_bindings = sensor_bindings
        self.sensor_definitions = dict(sensor_definitions or {})
        self.extra = kwargs

    @property
    def model(self) -> ModelT:
        return cast(ModelT, self.baseline_model)

    def realize(self, scenario: Any) -> SimulationInstance[ModelT, ResultT]:
        """Create a fresh simulation instance from ``scenario``."""
        resolved_definitions = {
            key: resolve_sensor_parameter_references(
                definition, _scenario_values(scenario)
            )
            for key, definition in self.sensor_definitions.items()
        }
        realized_model = self._clone(cast(ModelT, self.baseline_model))
        if callable(self._apply):
            self._apply(realized_model, scenario, self.specification)
        return SimulationInstance(
            model=realized_model,
            scenario=scenario,
            specification=self.specification,
            run=self._run,
            measure=self._measure,
            sensor_seeds=self._sensor_seeds,
            parameter_bindings=self.parameter_bindings,
            sensor_bindings=self.sensor_bindings,
            sensor_definitions=resolved_definitions,
        )


class GenericModelMapper(ModelMapper[ModelT], Generic[ModelT, ResultT]):
    """Small callable-backed implementation of ``ModelMapper``."""

    def __init__(
        self,
        *,
        clone: Callable[[ModelT], ModelT] | None = None,
        clone_model: Callable[[ModelT], ModelT] | None = None,
        apply: Callable[[ModelT, Any, UncertaintySpecification], None] | None = None,
        apply_parameters: (
            Callable[[ModelT, Any, UncertaintySpecification], None] | None
        ) = None,
        run: Callable[[ModelT], ResultT] | None = None,
        run_model: Callable[[ModelT], ResultT] | None = None,
        measure: (
            Callable[
                [
                    ModelT,
                    ResultT,
                    Any,
                    UncertaintySpecification | None,
                    Mapping[str, SensorDefinition],
                ],
                Any,
            ]
            | None
        ) = None,
        measure_sensors: (
            Callable[
                [
                    ModelT,
                    ResultT,
                    Any,
                    UncertaintySpecification | None,
                    Mapping[str, SensorDefinition],
                ],
                Any,
            ]
            | None
        ) = None,
        sensor_definitions: Mapping[str, SensorDefinition] | None = None,
        sensor_seeds: (
            Callable[
                [
                    ModelT,
                    ResultT,
                    Any,
                    UncertaintySpecification | None,
                    Mapping[str, SensorDefinition],
                ],
                Any,
            ]
            | None
        ) = None,
        parameter_bindings: Any = None,
        sensor_bindings: Any = None,
        validate: Callable[[UncertaintySpecification, ModelT], None] | None = None,
    ) -> None:
        self._clone = clone or clone_model or copy.deepcopy
        self._apply = apply or apply_parameters
        self._run = run or run_model
        self._measure = measure or measure_sensors
        self._sensor_seeds = sensor_seeds
        self._parameter_bindings = parameter_bindings
        self._sensor_bindings = sensor_bindings
        self._sensor_definitions = dict(sensor_definitions or {})
        self._validate = validate

    def map(
        self,
        specification: UncertaintySpecification,
        model: ModelT,
    ) -> UncertainModel[ModelT, ResultT]:
        if callable(self._validate):
            self._validate(specification, model)
        return UncertainModel(
            specification=specification,
            model=model,
            clone=self._clone,
            apply=self._apply,
            run=self._run,
            measure=self._measure,
            sensor_seeds=self._sensor_seeds,
            parameter_bindings=self._parameter_bindings,
            sensor_bindings=self._sensor_bindings,
            sensor_definitions=self._sensor_definitions,
        )


__all__ = [
    "GenericModelMapper",
    "ModelMapper",
    "SimulationInstance",
    "SimulationResult",
    "UncertainModel",
    "derive_deterministic_seed",
    "resolve_sensor_parameter_references",
]
