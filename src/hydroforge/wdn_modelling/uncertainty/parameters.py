"""Apply already-realized parameter values to a live WNTR model."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Literal, Mapping, Sequence, TypeAlias, cast

import wntr
from wntr.network.base import LinkStatus
from wntr.network.elements import Junction, Pipe, Valve

WNTRParameterProperty: TypeAlias = Literal[
    "diameter",
    "diameter_multiplier",
    "roughness",
    "base_demand",
    "valve_setting",
]

_PIPE_PROPERTIES = frozenset({"diameter", "diameter_multiplier", "roughness"})
_SUPPORTED_PROPERTIES = _PIPE_PROPERTIES | {"base_demand", "valve_setting"}
_CONTINUOUS_VALVE_TYPES = frozenset({"PRV", "PSV", "FCV", "TCV"})
_SUPPORTED_VALVE_TYPES = _CONTINUOUS_VALVE_TYPES | {"GPV", "PBV"}


class ParameterApplicationError(ValueError):
    """A WNTR parameter binding or realized value is invalid.

    ``path`` identifies the binding or value entry responsible for the error,
    allowing callers to report configuration failures without parsing the
    message text.
    """

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        super().__init__(f"{path}: {message}")


@dataclass(frozen=True, slots=True)
class WNTRParameterBinding:
    """Bind one WNTR component property to a named realized parameter value."""

    component_id: str
    property: WNTRParameterProperty
    parameter_key: str


@dataclass(frozen=True, slots=True)
class ParameterApplicationRecord:
    """Audit record for one successfully applied WNTR property update."""

    operation_index: int
    component_id: str
    property: WNTRParameterProperty
    parameter_key: str
    old_value: object
    realized_value: object
    new_value: object


@dataclass(frozen=True, slots=True)
class ParameterApplicationReport:
    """Deterministic, ordered audit report returned after application."""

    operations: tuple[ParameterApplicationRecord, ...]


@dataclass(frozen=True, slots=True)
class _PreparedOperation:
    binding: WNTRParameterBinding
    target: Pipe | Junction | Valve
    old_value: object
    realized_value: object
    new_value: object


class WNTRParameterAdapter:
    """Preflight and apply named scalar values to supported WNTR properties.

    Bindings are evaluated in the order supplied. The adapter does not sample
    values, inspect generic scenario objects, or modify anything until every
    binding and referenced value has passed preflight validation.
    """

    def __init__(self, bindings: Sequence[WNTRParameterBinding]) -> None:
        self.bindings = tuple(bindings)

    def apply(
        self,
        model: wntr.network.WaterNetworkModel,
        realized_values: Mapping[str, object],
    ) -> ParameterApplicationReport:
        """Apply the binding set to ``model`` in place and return its audit.

        Parameters
        ----------
        model
            Live WNTR network model owned by the caller.
        realized_values
            Mapping from parameter key to an already-realized scalar value.

        Raises
        ------
        ParameterApplicationError
            If a binding, component, or value is invalid. Validation failures
            occur before model mutation.
        """
        if not isinstance(realized_values, Mapping):
            raise ParameterApplicationError(
                "realized_values", "expected a mapping of parameter keys to values"
            )

        prepared = self._preflight(model, realized_values)
        self._apply_prepared(prepared)
        return ParameterApplicationReport(
            operations=tuple(
                ParameterApplicationRecord(
                    operation_index=index,
                    component_id=operation.binding.component_id,
                    property=operation.binding.property,
                    parameter_key=operation.binding.parameter_key,
                    old_value=operation.old_value,
                    realized_value=operation.realized_value,
                    new_value=operation.new_value,
                )
                for index, operation in enumerate(prepared)
            )
        )

    def _preflight(
        self,
        model: wntr.network.WaterNetworkModel,
        realized_values: Mapping[str, object],
    ) -> list[_PreparedOperation]:
        prepared: list[_PreparedOperation] = []
        seen_targets: dict[tuple[str, str], int] = {}
        current_values: dict[tuple[str, str], object] = {}

        for index, binding in enumerate(self.bindings):
            path = f"bindings[{index}]"
            if not isinstance(binding, WNTRParameterBinding):
                raise ParameterApplicationError(path, "expected a WNTRParameterBinding")
            if not isinstance(binding.component_id, str) or not binding.component_id:
                raise ParameterApplicationError(
                    f"{path}.component_id", "expected a non-empty component ID"
                )
            if not isinstance(binding.property, str):
                raise ParameterApplicationError(
                    f"{path}.property", "expected a supported property name"
                )
            if binding.property not in _SUPPORTED_PROPERTIES:
                raise ParameterApplicationError(
                    f"{path}.property",
                    f"unsupported property {binding.property!r}",
                )
            if not isinstance(binding.parameter_key, str) or not binding.parameter_key:
                raise ParameterApplicationError(
                    f"{path}.parameter_key", "expected a non-empty parameter key"
                )

            target_key = (binding.component_id, binding.property)
            if target_key in seen_targets:
                first_index = seen_targets[target_key]
                raise ParameterApplicationError(
                    path,
                    f"duplicates the target from bindings[{first_index}]",
                )
            seen_targets[target_key] = index

            if binding.parameter_key not in realized_values:
                raise ParameterApplicationError(
                    f"{path}.parameter_key",
                    f"{binding.parameter_key!r} is missing from realized_values",
                )
            target = self._resolve_target(model, binding, path)
            storage_key = (
                binding.component_id,
                self._storage_property(binding.property),
            )
            old_value = current_values.get(
                storage_key,
                self._read_value(target, binding.property),
            )
            value_path = f"realized_values[{binding.parameter_key!r}]"
            if binding.property == "valve_setting":
                realized_value, new_value = self._validate_valve_setting(
                    model,
                    cast(Valve, target),
                    realized_values[binding.parameter_key],
                    value_path,
                )
            else:
                realized_value = self._coerce_realized_value(
                    realized_values[binding.parameter_key],
                    value_path,
                )
                new_value = self._calculate_new_value(
                    binding.property,
                    cast(float, old_value),
                    realized_value,
                    value_path,
                )
            current_values[storage_key] = new_value
            prepared.append(
                _PreparedOperation(
                    binding=binding,
                    target=target,
                    old_value=old_value,
                    realized_value=realized_value,
                    new_value=new_value,
                )
            )

        return prepared

    @staticmethod
    def _coerce_realized_value(value: object, path: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ParameterApplicationError(path, "expected a real numeric scalar")
        try:
            result = float(value)
        except (OverflowError, TypeError, ValueError) as exc:
            raise ParameterApplicationError(
                path, "value cannot be represented"
            ) from exc
        if not isfinite(result):
            raise ParameterApplicationError(path, "value must be finite")
        return result

    @staticmethod
    def _resolve_target(
        model: wntr.network.WaterNetworkModel,
        binding: WNTRParameterBinding,
        path: str,
    ) -> Pipe | Junction | Valve:
        component_id = binding.component_id
        if binding.property == "valve_setting":
            if component_id in model.valve_name_list:
                return model.get_link(component_id)
            if component_id in model.link_name_list:
                component = model.get_link(component_id)
                raise ParameterApplicationError(
                    f"{path}.component_id",
                    f"{component_id!r} is a {type(component).__name__}, expected Valve",
                )
            if component_id in model.node_name_list:
                component = model.get_node(component_id)
                raise ParameterApplicationError(
                    f"{path}.component_id",
                    f"{component_id!r} is a {type(component).__name__}, expected Valve",
                )
            raise ParameterApplicationError(
                f"{path}.component_id",
                f"unknown WNTR component {component_id!r}",
            )

        if binding.property in _PIPE_PROPERTIES:
            if component_id in model.pipe_name_list:
                return model.get_link(component_id)
            if component_id in model.link_name_list:
                component = model.get_link(component_id)
                raise ParameterApplicationError(
                    f"{path}.component_id",
                    f"{component_id!r} is a {type(component).__name__}, expected Pipe",
                )
            if component_id in model.node_name_list:
                component = model.get_node(component_id)
                raise ParameterApplicationError(
                    f"{path}.component_id",
                    f"{component_id!r} is a {type(component).__name__}, expected Pipe",
                )
        else:
            if component_id in model.junction_name_list:
                junction = model.get_node(component_id)
                if len(junction.demand_timeseries_list) != 1:
                    raise ParameterApplicationError(
                        f"{path}.component_id",
                        f"junction {component_id!r} must have exactly one demand "
                        "timeseries entry",
                    )
                return junction
            if component_id in model.node_name_list:
                component = model.get_node(component_id)
                raise ParameterApplicationError(
                    f"{path}.component_id",
                    f"{component_id!r} is a {type(component).__name__}, "
                    "expected Junction",
                )
            if component_id in model.link_name_list:
                component = model.get_link(component_id)
                raise ParameterApplicationError(
                    f"{path}.component_id",
                    f"{component_id!r} is a {type(component).__name__}, "
                    "expected Junction",
                )

        raise ParameterApplicationError(
            f"{path}.component_id",
            f"unknown WNTR component {component_id!r}",
        )

    @staticmethod
    def _storage_property(property_name: WNTRParameterProperty) -> str:
        if property_name == "diameter_multiplier":
            return "diameter"
        return property_name

    @staticmethod
    def _read_value(
        target: Pipe | Junction | Valve,
        property_name: WNTRParameterProperty,
    ) -> object:
        if property_name in {"diameter", "diameter_multiplier"}:
            return float(target.diameter)
        if property_name == "roughness":
            return float(target.roughness)
        if property_name == "valve_setting":
            assert isinstance(target, Valve)
            return WNTRParameterAdapter._read_valve_setting(target)
        assert isinstance(target, Junction)
        return float(target.demand_timeseries_list[0].base_value)

    @staticmethod
    def _read_valve_setting(valve: Valve) -> object:
        valve_type = valve.valve_type.upper()
        if valve_type in _CONTINUOUS_VALVE_TYPES:
            return float(valve.initial_setting)
        if valve_type == "GPV":
            return valve.headloss_curve_name
        if valve_type == "PBV":
            status = valve.initial_status.name.upper()
            return "OPEN" if status in {"OPEN", "OPENED"} else status
        return valve.initial_setting

    @staticmethod
    def _validate_valve_setting(
        model: wntr.network.WaterNetworkModel,
        valve: Valve,
        value: object,
        path: str,
    ) -> tuple[object, object]:
        valve_type = valve.valve_type.upper()
        if valve_type not in _SUPPORTED_VALVE_TYPES:
            raise ParameterApplicationError(
                path,
                f"unsupported WNTR valve type {valve_type!r}",
            )

        if valve_type in _CONTINUOUS_VALVE_TYPES:
            setting = WNTRParameterAdapter._coerce_realized_value(value, path)
            is_invalid = setting < 0.0 if valve_type == "TCV" else setting <= 0.0
            if is_invalid:
                comparator = "non-negative" if valve_type == "TCV" else "positive"
                raise ParameterApplicationError(
                    path,
                    f"{valve_type} setting must be {comparator}",
                )
            return setting, setting

        if valve_type == "GPV":
            if not isinstance(value, str) or not value:
                raise ParameterApplicationError(
                    path, "GPV setting must be a non-empty headloss curve ID"
                )
            if value not in model.curve_name_list:
                raise ParameterApplicationError(
                    path, f"unknown GPV headloss curve {value!r}"
                )
            curve_type = model.get_curve(value).curve_type
            if curve_type is not None and curve_type.upper() != "HEADLOSS":
                raise ParameterApplicationError(
                    path,
                    f"curve {value!r} has type {curve_type!r}; GPV requires a "
                    "HEADLOSS curve",
                )
            return value, value

        if not isinstance(value, str):
            raise ParameterApplicationError(
                path, "PBV setting must be 'OPEN' or 'CLOSED'"
            )
        status = value.strip().upper()
        if status not in {"OPEN", "CLOSED"}:
            raise ParameterApplicationError(
                path,
                f"invalid PBV status {value!r}; expected 'OPEN' or 'CLOSED'",
            )
        return status, status

    @staticmethod
    def _calculate_new_value(
        property_name: WNTRParameterProperty,
        old_value: float,
        realized_value: float,
        path: str,
    ) -> float:
        if property_name == "diameter_multiplier":
            if realized_value <= 0.0:
                raise ParameterApplicationError(
                    path, "diameter multiplier must be positive"
                )
            new_value = old_value * realized_value
        else:
            new_value = realized_value

        if (
            property_name in {"diameter", "diameter_multiplier", "roughness"}
            and new_value <= 0.0
        ):
            raise ParameterApplicationError(path, f"{property_name} must be positive")
        if not isfinite(new_value):
            raise ParameterApplicationError(path, "resulting value must be finite")
        return new_value

    @staticmethod
    def _write_value(operation: _PreparedOperation, value: object) -> None:
        property_name = operation.binding.property
        target = operation.target
        if property_name == "valve_setting":
            assert isinstance(target, Valve)
            valve_type = target.valve_type.upper()
            if valve_type in _CONTINUOUS_VALVE_TYPES:
                target.initial_setting = value
            elif valve_type == "GPV":
                target.headloss_curve_name = value
            elif valve_type == "PBV":
                status_values = {
                    "OPEN": LinkStatus.Opened,
                    "CLOSED": LinkStatus.Closed,
                    "ACTIVE": LinkStatus.Active,
                }
                if not isinstance(value, str):
                    raise TypeError("preflighted PBV status must be a string")
                target.initial_status = status_values[value]
            else:
                raise ValueError(f"Unsupported WNTR valve type {valve_type!r}")
        elif property_name in {"diameter", "diameter_multiplier"}:
            assert isinstance(target, Pipe)
            target.diameter = value
        elif property_name == "roughness":
            assert isinstance(target, Pipe)
            target.roughness = value
        else:
            assert isinstance(target, Junction)
            target.demand_timeseries_list[0].base_value = value

    @classmethod
    def _apply_prepared(cls, operations: Sequence[_PreparedOperation]) -> None:
        applied: list[_PreparedOperation] = []
        try:
            for operation in operations:
                applied.append(operation)
                cls._write_value(operation, operation.new_value)
        except Exception as exc:
            for operation in reversed(applied):
                cls._write_value(operation, operation.old_value)
            raise ParameterApplicationError(
                "model", "update failed; previous updates were rolled back"
            ) from exc


__all__ = [
    "ParameterApplicationError",
    "ParameterApplicationRecord",
    "ParameterApplicationReport",
    "WNTRParameterAdapter",
    "WNTRParameterBinding",
    "WNTRParameterProperty",
]
