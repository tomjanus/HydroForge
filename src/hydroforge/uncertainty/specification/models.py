"""Pydantic models for the uncertainty specification document.

The models are deliberately declarative: a specification stores sensor type
names and parameter values, not live sensor instances. Use
:meth:`SensorDefinition.create_sensor` to construct a sensor from a definition.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from dataclasses import dataclass
from typing import Any, Union

import pydantic
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from hydroforge.measurements import CompositeSensor, Sensor

from .exceptions import (
    SpecificationError,
    SpecificationIssue,
    SpecificationValidationError,
)
from .registry import (
    canonical_sensor_type_name,
    lookup_sensor_type,
    resolve_sensor_type,
    sensor_type_names,
)

SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0"})

# Constructor fields that hold internal state rather than user configuration.
_NON_SPEC_PARAMETER_FIELDS: frozenset[str] = frozenset({"_rng", "current_offset"})

# Keys permitted inside a sensor definition (also used for nested composite
# entries, which are validated by this layer rather than by Pydantic).
_SENSOR_DEFINITION_KEYS: frozenset[str] = frozenset({"type", "parameters", "location"})

# Keys permitted at the top level of a specification document. ``measurements``
# is a legacy input alias for ``sensors`` (see ADR-0001); ``model`` and
# ``parameters`` are reserved for Stage 2 and are accepted but not interpreted.
_SPECIFICATION_KEYS: frozenset[str] = frozenset(
    {"schema_version", "sensors", "measurements", "model", "parameters"}
)


@dataclass(frozen=True)
class _ParameterField:
    """A sensor constructor field that may appear in a specification."""

    name: str
    annotation: Any
    required: bool


def _join(path: str, key: str) -> str:
    """Append ``key`` to a dotted ``path``."""
    return f"{path}.{key}" if path else key


def _describe(annotation: Any) -> str:
    """Return a short human-readable description of an accepted value."""
    if annotation is float:
        return "a number"
    if annotation is int:
        return "an integer"
    if annotation is str:
        return "a string"
    if annotation is bool:
        return "a boolean"
    origin = typing.get_origin(annotation)
    if origin in (Union, types.UnionType):
        args = typing.get_args(annotation)
        parts = [_describe(arg) for arg in args if arg is not type(None)]
        if type(None) in args:
            parts.append("null")
        return " or ".join(parts)
    return "a valid value"


def _annotation_allows(value: Any, annotation: Any) -> bool:
    """Return whether ``value`` is acceptable for a field annotated ``annotation``.

    This is a deliberately narrow check for the free-form ``parameters``
    mapping, whose keys are matched against arbitrary sensor constructor
    types; Pydantic cannot validate that shape because the schema depends on
    the registry type resolved at validation time (see ADR-0001).
    """
    if annotation is None or annotation is Any:
        return True
    origin = typing.get_origin(annotation)
    if origin in (Union, types.UnionType):
        return any(
            _annotation_allows(value, arg) for arg in typing.get_args(annotation)
        )
    if annotation is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if annotation is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if annotation is str:
        return isinstance(value, str)
    if annotation is bool:
        return isinstance(value, bool)
    return True


def _sensor_parameter_fields(cls: type[Sensor]) -> dict[str, _ParameterField]:
    """Return the specification-visible constructor fields of a sensor class."""
    if not dataclasses.is_dataclass(cls):
        return {}
    try:
        hints = typing.get_type_hints(cls)
    except Exception:  # pragma: no cover - defensive for unusual annotations
        hints = {}
    fields: dict[str, _ParameterField] = {}
    for field in dataclasses.fields(cls):
        if (
            not field.init
            or field.name.startswith("_")
            or field.name in _NON_SPEC_PARAMETER_FIELDS
        ):
            continue
        required = (
            field.default is dataclasses.MISSING
            and field.default_factory is dataclasses.MISSING
        )
        fields[field.name] = _ParameterField(
            name=field.name,
            annotation=hints.get(field.name, field.type),
            required=required,
        )
    return fields


def _validate_parameters(
    cls: type[Sensor], parameters: dict[str, Any], path: str
) -> list[SpecificationIssue]:
    """Validate a ``parameters`` mapping against a sensor class."""
    issues: list[SpecificationIssue] = []

    if cls is CompositeSensor:
        allowed = {"sensors"}
        for key in parameters:
            if key not in allowed:
                issues.append(
                    SpecificationIssue(
                        path=_join(path, key),
                        message=f"unknown parameter; allowed: {sorted(allowed)}",
                    )
                )
        if "sensors" not in parameters:
            issues.append(
                SpecificationIssue(
                    path=_join(path, "sensors"),
                    message="missing required parameter 'sensors'",
                )
            )
        else:
            nested = parameters["sensors"]
            if not isinstance(nested, list):
                issues.append(
                    SpecificationIssue(
                        path=_join(path, "sensors"),
                        message="expected a list of sensor definitions",
                    )
                )
            else:
                for index, item in enumerate(nested):
                    issues.extend(
                        _validate_sensor_mapping(
                            item, _join(_join(path, "sensors"), str(index))
                        )
                    )
        return issues

    fields = _sensor_parameter_fields(cls)
    for key in parameters:
        if key not in fields:
            issues.append(
                SpecificationIssue(
                    path=_join(path, key),
                    message=f"unknown parameter; allowed: {sorted(fields)}",
                )
            )
    for name, parameter_field in fields.items():
        if parameter_field.required and name not in parameters:
            issues.append(
                SpecificationIssue(
                    path=_join(path, name), message="missing required parameter"
                )
            )
        elif name in parameters and not _annotation_allows(
            parameters[name], parameter_field.annotation
        ):
            issues.append(
                SpecificationIssue(
                    path=_join(path, name),
                    message=(
                        f"expected {_describe(parameter_field.annotation)}, "
                        f"got {type(parameters[name]).__name__}"
                    ),
                )
            )
    return issues


def _validate_definition(
    type_name: str,
    parameters: dict[str, Any],
    location: str | None,
    path: str,
) -> list[SpecificationIssue]:
    """Validate one sensor definition located at ``path``."""
    issues: list[SpecificationIssue] = []
    cls = lookup_sensor_type(type_name)
    if cls is None:
        issues.append(
            SpecificationIssue(
                path=_join(path, "type"),
                message=(
                    f"unknown sensor type {type_name!r}; "
                    f"supported types: {sensor_type_names()}"
                ),
            )
        )
        return issues
    if not isinstance(parameters, dict):
        issues.append(
            SpecificationIssue(
                path=_join(path, "parameters"),
                message="expected a mapping of parameter names to values",
            )
        )
        return issues
    issues.extend(_validate_parameters(cls, parameters, _join(path, "parameters")))
    if location is not None and not isinstance(location, str):
        issues.append(
            SpecificationIssue(
                path=_join(path, "location"), message="expected a string or null"
            )
        )
    return issues


def _validate_sensor_mapping(raw: Any, path: str) -> list[SpecificationIssue]:
    """Validate a raw sensor-definition mapping located at ``path``."""
    if isinstance(raw, SensorDefinition):
        return []
    if not isinstance(raw, dict):
        return [
            SpecificationIssue(
                path=path, message="expected a sensor definition mapping"
            )
        ]

    issues: list[SpecificationIssue] = []
    for key in raw:
        if key not in _SENSOR_DEFINITION_KEYS:
            issues.append(
                SpecificationIssue(
                    path=_join(path, str(key)),
                    message=(
                        f"unknown key; allowed: {sorted(_SENSOR_DEFINITION_KEYS)}"
                    ),
                )
            )

    type_name = raw.get("type")
    if not isinstance(type_name, str):
        issues.append(
            SpecificationIssue(
                path=_join(path, "type"), message="missing or invalid sensor type"
            )
        )
        return issues

    parameters = raw.get("parameters", {})
    if parameters is None:
        parameters = {}
    issues.extend(
        _validate_definition(type_name, parameters, raw.get("location"), path)
    )
    return issues


class SensorDefinition(BaseModel):
    """A named sensor model configuration.

    Parameters
    ----------
    type : str
        Sensor type name, either the short name (``FixedPrecision``) or the
        full class name (``FixedPrecisionSensor``).
    parameters : dict[str, Any]
        Constructor arguments for the sensor class.
    location : str, optional
        Network location (node or link id) associated with the observation
        point. It is carried through but not validated against a network.
    """

    model_config = ConfigDict(extra="forbid")

    type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    location: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_unknown_keys(cls, document: Any) -> Any:
        """Reject unknown keys with the public exception family.

        Pydantic's ``extra="forbid"`` would raise a raw ``ValidationError``;
        raising here keeps standalone construction inside the documented
        ``SpecificationError`` hierarchy (ADR-0001).
        """
        if isinstance(document, dict):
            unknown = [key for key in document if key not in _SENSOR_DEFINITION_KEYS]
            if unknown:
                raise SpecificationValidationError(
                    [
                        SpecificationIssue(
                            path=str(key),
                            message=(
                                "unknown key; allowed: "
                                f"{sorted(_SENSOR_DEFINITION_KEYS)}"
                            ),
                        )
                        for key in unknown
                    ]
                )
        return document

    @field_validator("type", mode="before")
    @classmethod
    def _canonicalise_type(cls, value: Any) -> Any:
        """Map full class names to the canonical short type name."""
        if isinstance(value, str):
            canonical = canonical_sensor_type_name(value)
            if canonical is not None:
                return canonical
        return value

    @model_validator(mode="after")
    def _validate_against_registry(self) -> "SensorDefinition":
        issues = _validate_definition(
            self.type, self.parameters, self.location, path=""
        )
        if issues:
            raise SpecificationValidationError(issues)
        return self

    def create_sensor(self) -> Sensor:
        """Construct a live sensor from this definition.

        Returns
        -------
        Sensor
            A sensor from :mod:`hydroforge.measurements`.

        Raises
        ------
        SpecificationValidationError
            If the definition is not valid.
        """
        cls = resolve_sensor_type(self.type)
        if cls is CompositeSensor:
            nested = [
                _build_sensor_definition(item)
                for item in self.parameters.get("sensors", [])
            ]
            return CompositeSensor(*(item.create_sensor() for item in nested))
        return cls(**self.parameters)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-serialisable dictionary for this definition."""
        return self.model_dump(exclude_none=True)


class UncertaintySpecification(BaseModel):
    """An uncertainty specification document.

    Parameters
    ----------
    schema_version : str
        Version of the specification format.
    sensors : dict[str, SensorDefinition]
        Named sensor definitions attached to observation points.
    model : dict[str, Any], optional
        Reserved section for model-component parameters (Stage 2).
    parameters : dict[str, Any], optional
        Reserved section for parameter definitions (Stage 2).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str
    sensors: dict[str, SensorDefinition] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("sensors", "measurements"),
    )
    model: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def _collect_semantic_errors(cls, document: Any) -> Any:
        """Collect all problems in the document before Pydantic builds it.

        Running before field validation lets structural problems (unknown
        top-level keys) and semantic problems (bad schema version, invalid
        sensor definitions) be reported together, so one load reports
        everything the researcher needs to fix.
        """
        if not isinstance(document, dict):
            return document

        issues: list[SpecificationIssue] = []

        for key in document:
            if key not in _SPECIFICATION_KEYS:
                issues.append(
                    SpecificationIssue(
                        path=str(key),
                        message=f"unknown key; allowed: {sorted(_SPECIFICATION_KEYS)}",
                    )
                )

        if "sensors" in document and "measurements" in document:
            issues.append(
                SpecificationIssue(
                    path="sensors",
                    message=(
                        "both 'sensors' and 'measurements' were provided; "
                        "use only 'sensors'"
                    ),
                )
            )

        version = document.get("schema_version")
        if version is None:
            issues.append(
                SpecificationIssue(
                    path="schema_version", message="missing required field"
                )
            )
        elif not isinstance(version, str) or version not in SUPPORTED_SCHEMA_VERSIONS:
            issues.append(
                SpecificationIssue(
                    path="schema_version",
                    message=(
                        f"unsupported schema version {version!r}; "
                        f"supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}"
                    ),
                )
            )

        raw_sensors = document.get("sensors", document.get("measurements"))
        if isinstance(raw_sensors, dict):
            for name, raw in raw_sensors.items():
                if not isinstance(name, str):
                    issues.append(
                        SpecificationIssue(
                            path=f"sensors.{name}",
                            message="sensor names must be strings",
                        )
                    )
                    continue
                issues.extend(_validate_sensor_mapping(raw, f"sensors.{name}"))

        if issues:
            raise SpecificationValidationError(issues)
        return document

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> "UncertaintySpecification":
        """Build a specification from a dictionary, wrapping Pydantic errors.

        Parameters
        ----------
        document : dict
            The parsed specification document.

        Raises
        ------
        SpecificationValidationError
            If the dictionary is not a valid specification.
        """
        try:
            return cls.model_validate(document)
        except pydantic.ValidationError as exc:
            raise _convert_validation_error(exc) from exc

    def create_sensor(self, name: str) -> Sensor:
        """Construct a live sensor by name.

        Raises
        ------
        SpecificationError
            If no sensor is defined under ``name``.
        """
        if name not in self.sensors:
            raise SpecificationError(
                f"unknown sensor {name!r}; defined sensors: {sorted(self.sensors)}"
            )
        return self.sensors[name].create_sensor()

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-serialisable dictionary for this specification."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        """Return the JSON Schema for the specification envelope."""
        return cls.model_json_schema()


def _build_sensor_definition(document: Any) -> SensorDefinition:
    """Validate a raw nested sensor definition through the public exception family.

    Raises
    ------
    SpecificationValidationError
        If the nested document is not a valid sensor definition.
    """
    try:
        return SensorDefinition.model_validate(document)
    except pydantic.ValidationError as exc:
        raise _convert_validation_error(exc) from exc


def _convert_validation_error(
    exc: pydantic.ValidationError,
) -> SpecificationValidationError:
    """Convert a Pydantic validation error into the public exception type."""
    issues = []
    for error in exc.errors():
        path = ".".join(str(part) for part in error["loc"])
        issues.append(SpecificationIssue(path=path, message=error["msg"]))
    return SpecificationValidationError(issues)
