"""Apply generic sensor definitions to explicitly bound WNTR result columns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence, TypeAlias

import pandas as pd
import wntr

from hydroforge.measurements import Sensor
from hydroforge.uncertainty.specification import SensorDefinition

from ..backends.wntr.results import WNTRSimulationResults

WNTRSensorVariable: TypeAlias = Literal["pressure", "flowrate"]
_SUPPORTED_VARIABLES = frozenset({"pressure", "flowrate"})


class SensorApplicationError(ValueError):
    """An invalid WNTR sensor binding or result column.

    ``path`` identifies the binding, definition, or results entry responsible
    for the error, allowing callers to diagnose configuration failures without
    parsing the message text.
    """

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        super().__init__(f"{path}: {message}")


@dataclass(frozen=True, slots=True)
class WNTRSensorBinding:
    """Bind one WNTR sensing point and result variable to a named sensor."""

    point_id: str
    sensor_key: str
    variable: WNTRSensorVariable


@dataclass(frozen=True, slots=True)
class _PreparedSensor:
    binding: WNTRSensorBinding
    definition: SensorDefinition
    values: pd.Series
    path: str


class WNTRSensorAdapter:
    """Measure selected WNTR result columns using fresh generic sensors.

    This adapter only reads the supplied WNTR model and result wrapper. It
    does not run a backend, modify raw results, or share mutable sensor state
    between sensing-point bindings.
    """

    def __init__(
        self,
        bindings: Sequence[WNTRSensorBinding],
        sensor_definitions: Mapping[str, SensorDefinition],
    ) -> None:
        self.bindings = tuple(bindings)
        self.sensor_definitions = sensor_definitions

    def apply(
        self,
        model: wntr.network.WaterNetworkModel,
        results: WNTRSimulationResults,
    ) -> dict[WNTRSensorVariable, pd.DataFrame]:
        """Return measured DataFrames for the configured sensing points.

        Each result DataFrame retains the WNTR time index and contains only
        bound point IDs, in binding order. A new live sensor is constructed
        for every binding.

        Raises
        ------
        SensorApplicationError
            If a binding, sensor definition, component, or result column is
            invalid, or a sensor does not preserve its input Series shape and
            index.
        """
        if not isinstance(model, wntr.network.WaterNetworkModel):
            raise SensorApplicationError("model", "expected a WNTR WaterNetworkModel")
        if not isinstance(self.sensor_definitions, Mapping):
            raise SensorApplicationError(
                "sensor_definitions", "expected a mapping of sensor keys to definitions"
            )
        if not isinstance(results, WNTRSimulationResults):
            raise SensorApplicationError(
                "results", "expected WNTRSimulationResults from a completed run"
            )

        prepared = self._preflight(model, results)
        measured_columns: dict[WNTRSensorVariable, list[pd.Series]] = {}
        for operation in prepared:
            sensor: Sensor = operation.definition.create_sensor()
            try:
                measured = sensor.measure(operation.values.copy(deep=True))
            except Exception as exc:
                raise SensorApplicationError(
                    f"{operation.path}.sensor_key",
                    f"sensor measurement failed: {exc}",
                ) from exc

            if not isinstance(measured, pd.Series):
                raise SensorApplicationError(
                    f"{operation.path}.sensor_key",
                    "sensor must return a pandas Series when given a result column",
                )
            if len(measured) != len(operation.values) or not measured.index.equals(
                operation.values.index
            ):
                raise SensorApplicationError(
                    f"{operation.path}.sensor_key",
                    "sensor must preserve the input Series shape and time index",
                )

            measured = measured.copy(deep=True)
            measured.name = operation.binding.point_id
            measured_columns.setdefault(operation.binding.variable, []).append(measured)

        return {
            variable: pd.concat(columns, axis=1)
            for variable, columns in measured_columns.items()
        }

    def _preflight(
        self,
        model: wntr.network.WaterNetworkModel,
        results: WNTRSimulationResults,
    ) -> list[_PreparedSensor]:
        prepared: list[_PreparedSensor] = []
        seen_targets: dict[tuple[str, str], int] = {}

        for index, binding in enumerate(self.bindings):
            path = f"bindings[{index}]"
            if not isinstance(binding, WNTRSensorBinding):
                raise SensorApplicationError(path, "expected a WNTRSensorBinding")
            if not isinstance(binding.point_id, str) or not binding.point_id:
                raise SensorApplicationError(
                    f"{path}.point_id", "expected a non-empty component ID"
                )
            if not isinstance(binding.sensor_key, str) or not binding.sensor_key:
                raise SensorApplicationError(
                    f"{path}.sensor_key", "expected a non-empty sensor key"
                )
            if not isinstance(binding.variable, str) or (
                binding.variable not in _SUPPORTED_VARIABLES
            ):
                raise SensorApplicationError(
                    f"{path}.variable",
                    f"unsupported WNTR measurement variable {binding.variable!r}; "
                    "supported variables are 'pressure' and 'flowrate'",
                )

            target = (binding.variable, binding.point_id)
            if target in seen_targets:
                raise SensorApplicationError(
                    path,
                    f"duplicates the point/variable target from "
                    f"bindings[{seen_targets[target]}]",
                )
            seen_targets[target] = index

            if binding.sensor_key not in self.sensor_definitions:
                raise SensorApplicationError(
                    f"{path}.sensor_key",
                    f"{binding.sensor_key!r} is missing from sensor_definitions",
                )
            definition = self.sensor_definitions[binding.sensor_key]
            if not isinstance(definition, SensorDefinition):
                raise SensorApplicationError(
                    f"sensor_definitions[{binding.sensor_key!r}]",
                    "expected a generic SensorDefinition",
                )
            if (
                definition.location is not None
                and definition.location != binding.point_id
            ):
                raise SensorApplicationError(
                    f"sensor_definitions[{binding.sensor_key!r}].location",
                    f"{definition.location!r} does not match bound point "
                    f"{binding.point_id!r}",
                )

            self._validate_component(model, binding, path)
            result_table = self._result_table(results, binding)
            if binding.point_id not in result_table.columns:
                raise SensorApplicationError(
                    self._result_column_path(binding),
                    f"simulation results contain no column for "
                    f"{binding.point_id!r}",
                )
            prepared.append(
                _PreparedSensor(
                    binding=binding,
                    definition=definition,
                    values=result_table[binding.point_id].copy(deep=True),
                    path=path,
                )
            )

        return prepared

    @staticmethod
    def _validate_component(
        model: wntr.network.WaterNetworkModel,
        binding: WNTRSensorBinding,
        path: str,
    ) -> None:
        point_id = binding.point_id
        if binding.variable == "pressure":
            if point_id in model.junction_name_list or point_id in model.tank_name_list:
                return
            if point_id in model.reservoir_name_list:
                raise SensorApplicationError(
                    f"{path}.point_id",
                    "WNTR reservoir pressure is a zero placeholder; "
                    "reservoir pressure measurements are unsupported",
                )
            if point_id in model.link_name_list:
                raise SensorApplicationError(
                    f"{path}.point_id",
                    f"{point_id!r} is a link; pressure requires a junction or tank",
                )
        else:
            if (
                point_id in model.pipe_name_list
                or point_id in model.pump_name_list
                or point_id in model.valve_name_list
            ):
                return
            if point_id in model.node_name_list:
                raise SensorApplicationError(
                    f"{path}.point_id",
                    f"{point_id!r} is a node; flowrate requires a pipe, pump, or valve",
                )
            if point_id in model.link_name_list:
                raise SensorApplicationError(
                    f"{path}.point_id",
                    f"flowrate is unsupported for link {point_id!r}",
                )

        raise SensorApplicationError(
            f"{path}.point_id", f"unknown WNTR component {point_id!r}"
        )

    @staticmethod
    def _result_table(
        results: WNTRSimulationResults,
        binding: WNTRSensorBinding,
    ) -> pd.DataFrame:
        table_path = (
            "results.node.pressure"
            if binding.variable == "pressure"
            else "results.link.flowrate"
        )
        try:
            if binding.variable == "pressure":
                tables = results.raw.node
            else:
                tables = results.raw.link
            table = tables[binding.variable]
        except (AttributeError, KeyError, TypeError) as exc:
            raise SensorApplicationError(
                table_path, "simulation results do not contain this variable"
            ) from exc
        if not isinstance(table, pd.DataFrame):
            raise SensorApplicationError(
                table_path, "expected a pandas DataFrame in simulation results"
            )
        return table

    @staticmethod
    def _result_column_path(binding: WNTRSensorBinding) -> str:
        table_path = (
            "results.node.pressure"
            if binding.variable == "pressure"
            else "results.link.flowrate"
        )
        return f"{table_path}[{binding.point_id!r}]"


__all__ = [
    "SensorApplicationError",
    "WNTRSensorAdapter",
    "WNTRSensorBinding",
    "WNTRSensorVariable",
]
