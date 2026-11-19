"""Pydantic models for the uncertainty specification document.

The models are deliberately declarative: a specification stores sensor type
names and parameter values, not live sensor instances, and parameter,
uncertainty, and distribution definitions, not live runtime objects. Use
:meth:`SensorDefinition.create_sensor` and :meth:`ParameterDefinition.create_parameter`
to construct live objects from definitions.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from dataclasses import dataclass
from typing import Any, Union

import numpy as np
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
from hydroforge.uncertainty.distributions import Distribution
from hydroforge.uncertainty.parameters import Parameter, ParameterType
from hydroforge.uncertainty.uncertainties import NoUncertainty, Uncertainty

from .exceptions import (
    SpecificationError,
    SpecificationIssue,
    SpecificationValidationError,
)
from .registry import (
    canonical_distribution_type_name,
    canonical_sensor_type_name,
    canonical_uncertainty_type_name,
    distribution_type_names,
    lookup_distribution_type,
    lookup_sensor_type,
    lookup_uncertainty_type,
    resolve_sensor_type,
    sensor_type_names,
    uncertainty_type_names,
)

SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0"})

# Constructor fields that hold internal state rather than user configuration.
_NON_SPEC_PARAMETER_FIELDS: frozenset[str] = frozenset({"_rng", "current_offset"})

# Keys permitted inside a sensor definition (also used for nested composite
# entries, which are validated by this layer rather than by Pydantic).
_SENSOR_DEFINITION_KEYS: frozenset[str] = frozenset({"type", "parameters", "location"})

# Keys permitted inside a nested uncertainty/distribution definition.
_NESTED_DEFINITION_KEYS: frozenset[str] = frozenset({"type", "parameters"})

# Keys permitted inside a parameter definition.
_PARAMETER_DEFINITION_KEYS: frozenset[str] = frozenset(
    {"nominal_value", "uncertainty", "type", "infer_type_from_data", "metadata"}
)

# Document name replacing a live ``numpy.random.Generator`` constructor field
# (ADR-0002 decision 5); the adapter builds the generator at construction.
_GENERATOR_SEED_FIELD = "seed"

_PARAMETER_TYPE_NAMES: frozenset[str] = frozenset(
    member.name for member in ParameterType
)

# Keys permitted at the top level of a specification document. ``measurements``
# is a legacy input alias for ``sensors`` (see ADR-0001); ``parameters`` holds
# Stage 2 parameter definitions (see ADR-0002); ``model`` remains a reserved,
# verbatim pass-through section interpreted by scenario generation, not here.
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
    if origin in (tuple, list):
        return "a list"
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
    if annotation is type(None):
        return value is None
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
    if origin is tuple:
        # documents carry JSON arrays where Python tuples are accepted
        # (ADR-0002 decision 4); fixed-length tuples also fix the length
        if not isinstance(value, (list, tuple)):
            return False
        args = typing.get_args(annotation)
        if len(args) == 2 and args[1] is Ellipsis:
            return all(_annotation_allows(item, args[0]) for item in value)
        return len(value) == len(args) and all(
            _annotation_allows(item, arg) for item, arg in zip(value, args)
        )
    if origin is list:
        if not isinstance(value, list):
            return False
        args = typing.get_args(annotation)
        return (
            all(_annotation_allows(item, args[0]) for item in value) if args else True
        )
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


@dataclass(frozen=True)
class _DefinitionField:
    """A constructor field of a registered uncertainty/distribution class.

    Attributes
    ----------
    name : str
        Constructor field name.
    doc_name : str
        Document-visible name; generator fields appear as ``seed`` instead.
    kind : str
        ``"scalar"``, ``"nested_distribution"``, or ``"generator"``.
    annotation : Any
        Resolved type annotation of the constructor field.
    required : bool
        Whether the constructor field has no default.
    """

    name: str
    doc_name: str
    kind: str
    annotation: Any
    required: bool


def _is_distribution_annotation(annotation: Any) -> bool:
    """Return whether ``annotation`` describes a nested distribution slot."""
    origin = typing.get_origin(annotation)
    target = origin if origin is not None else annotation
    return isinstance(target, type) and issubclass(target, Distribution)


def _is_generator_annotation(annotation: Any) -> bool:
    """Return whether ``annotation`` requires a live ``numpy`` generator."""
    if annotation is np.random.Generator or (
        isinstance(annotation, type) and issubclass(annotation, np.random.Generator)
    ):
        return True
    origin = typing.get_origin(annotation)
    if origin in (Union, types.UnionType):
        return any(_is_generator_annotation(arg) for arg in typing.get_args(annotation))
    return False


def _definition_fields(cls: type) -> dict[str, _DefinitionField]:
    """Classify the specification-visible constructor fields of ``cls``."""
    if not dataclasses.is_dataclass(cls):
        return {}
    try:
        hints = typing.get_type_hints(cls)
    except Exception:  # pragma: no cover - defensive for unusual annotations
        hints = {}
    result: dict[str, _DefinitionField] = {}
    for field in dataclasses.fields(cls):
        if (
            not field.init
            or field.name.startswith("_")
            or field.name in _NON_SPEC_PARAMETER_FIELDS
        ):
            continue
        annotation = hints.get(field.name, field.type)
        required = (
            field.default is dataclasses.MISSING
            and field.default_factory is dataclasses.MISSING
        )
        if _is_distribution_annotation(annotation):
            kind = "nested_distribution"
        elif _is_generator_annotation(annotation):
            kind = "generator"
        else:
            kind = "scalar"
        doc_name = _GENERATOR_SEED_FIELD if kind == "generator" else field.name
        result[field.name] = _DefinitionField(
            name=field.name,
            doc_name=doc_name,
            kind=kind,
            annotation=annotation,
            required=required,
        )
    return result


def _validate_definition_body(
    fields: dict[str, _DefinitionField], parameters: dict[str, Any], path: str
) -> list[SpecificationIssue]:
    """Validate a ``parameters`` mapping against classified constructor fields.

    Shape and type rules only: semantic constraints live in the runtime
    ``__post_init__`` methods and fire at construction (ADR-0002 decision 15).
    """
    issues: list[SpecificationIssue] = []
    allowed = {field.doc_name for field in fields.values()}

    for key in parameters:
        if key not in allowed:
            issues.append(
                SpecificationIssue(
                    path=_join(path, key),
                    message=f"unknown parameter; allowed: {sorted(allowed)}",
                )
            )

    for definition_field in fields.values():
        value_present = definition_field.doc_name in parameters
        if definition_field.kind == "generator":
            if value_present and not _annotation_allows(
                parameters[definition_field.doc_name], int | None
            ):
                issues.append(
                    SpecificationIssue(
                        path=_join(path, definition_field.doc_name),
                        message="expected an integer or null",
                    )
                )
            continue
        if definition_field.required and not value_present:
            issues.append(
                SpecificationIssue(
                    path=_join(path, definition_field.doc_name),
                    message="missing required parameter",
                )
            )
        elif not value_present:
            continue
        elif definition_field.kind == "nested_distribution":
            issues.extend(
                _validate_distribution_mapping(
                    parameters[definition_field.doc_name],
                    _join(path, definition_field.doc_name),
                )
            )
        elif not _annotation_allows(
            parameters[definition_field.doc_name], definition_field.annotation
        ):
            issues.append(
                SpecificationIssue(
                    path=_join(path, definition_field.doc_name),
                    message=(
                        f"expected {_describe(definition_field.annotation)}, "
                        f"got {type(parameters[definition_field.doc_name]).__name__}"
                    ),
                )
            )
    return issues


def _validate_nested_mapping(
    raw: Any, path: str, kind: str
) -> list[SpecificationIssue]:
    """Check the shared shape of a tagged ``{type, parameters}`` definition."""
    if not isinstance(raw, dict):
        return [
            SpecificationIssue(
                path=path, message=f"expected a {kind} definition mapping"
            )
        ]
    issues = [
        SpecificationIssue(
            path=_join(path, str(key)),
            message=f"unknown key; allowed: {sorted(_NESTED_DEFINITION_KEYS)}",
        )
        for key in raw
        if key not in _NESTED_DEFINITION_KEYS
    ]
    return issues


def _validate_distribution_mapping(raw: Any, path: str) -> list[SpecificationIssue]:
    """Validate a raw distribution definition located at ``path``."""
    issues = _validate_nested_mapping(raw, path, "distribution")
    if issues or not isinstance(raw, dict):
        return issues
    type_name = raw.get("type")
    if not isinstance(type_name, str):
        return issues + [
            SpecificationIssue(
                path=_join(path, "type"), message="missing or invalid distribution type"
            )
        ]
    cls = lookup_distribution_type(type_name)
    if cls is None:
        return issues + [
            SpecificationIssue(
                path=_join(path, "type"),
                message=(
                    f"unknown distribution type {type_name!r}; "
                    f"supported types: {distribution_type_names()}"
                ),
            )
        ]
    parameters = raw.get("parameters", {})
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict):
        return issues + [
            SpecificationIssue(
                path=_join(path, "parameters"),
                message="expected a mapping of parameter names to values",
            )
        ]
    issues.extend(
        _validate_definition_body(
            _definition_fields(cls), parameters, _join(path, "parameters")
        )
    )
    return issues


def _validate_uncertainty_mapping(raw: Any, path: str) -> list[SpecificationIssue]:
    """Validate a raw uncertainty definition located at ``path``."""
    issues = _validate_nested_mapping(raw, path, "uncertainty")
    if issues or not isinstance(raw, dict):
        return issues
    type_name = raw.get("type")
    if not isinstance(type_name, str):
        return issues + [
            SpecificationIssue(
                path=_join(path, "type"), message="missing or invalid uncertainty type"
            )
        ]
    cls = lookup_uncertainty_type(type_name)
    if cls is None:
        return issues + [
            SpecificationIssue(
                path=_join(path, "type"),
                message=(
                    f"unknown uncertainty type {type_name!r}; "
                    f"supported types: {uncertainty_type_names()}"
                ),
            )
        ]
    parameters = raw.get("parameters", {})
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict):
        return issues + [
            SpecificationIssue(
                path=_join(path, "parameters"),
                message="expected a mapping of parameter names to values",
            )
        ]
    issues.extend(
        _validate_definition_body(
            _definition_fields(cls), parameters, _join(path, "parameters")
        )
    )
    return issues


def _validate_parameter_mapping(raw: Any, path: str) -> list[SpecificationIssue]:
    """Validate a raw parameter-definition mapping located at ``path``."""
    if isinstance(raw, ParameterDefinition):
        return []
    if not isinstance(raw, dict):
        return [
            SpecificationIssue(path=path, message="expected a parameter definition")
        ]

    issues: list[SpecificationIssue] = []
    for key in raw:
        if key not in _PARAMETER_DEFINITION_KEYS:
            issues.append(
                SpecificationIssue(
                    path=_join(path, str(key)),
                    message=(
                        f"unknown key; allowed: {sorted(_PARAMETER_DEFINITION_KEYS)}"
                    ),
                )
            )

    if "nominal_value" not in raw:
        issues.append(
            SpecificationIssue(
                path=_join(path, "nominal_value"),
                message="missing required field 'nominal_value'",
            )
        )
    else:
        nominal = raw["nominal_value"]
        if not isinstance(nominal, (str, int, float, bool)):
            issues.append(
                SpecificationIssue(
                    path=_join(path, "nominal_value"),
                    message=(
                        "expected a string, number, or boolean, "
                        f"got {type(nominal).__name__}"
                    ),
                )
            )

    type_name = raw.get("type")
    if type_name is not None and (
        not isinstance(type_name, str) or type_name not in _PARAMETER_TYPE_NAMES
    ):
        issues.append(
            SpecificationIssue(
                path=_join(path, "type"),
                message=(
                    f"unknown parameter type {type_name!r}; "
                    f"supported types: {sorted(_PARAMETER_TYPE_NAMES)}"
                ),
            )
        )

    infer = raw.get("infer_type_from_data")
    if infer is not None and not isinstance(infer, bool):
        issues.append(
            SpecificationIssue(
                path=_join(path, "infer_type_from_data"), message="expected a boolean"
            )
        )

    metadata = raw.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        issues.append(
            SpecificationIssue(
                path=_join(path, "metadata"), message="expected a mapping"
            )
        )

    uncertainty = raw.get("uncertainty")
    if uncertainty is not None:
        issues.extend(
            _validate_uncertainty_mapping(uncertainty, _join(path, "uncertainty"))
        )
    return issues


def _canonicalise_nested_definition(raw: Any) -> Any:
    """Map full uncertainty/distribution class names to canonical short names."""
    if not isinstance(raw, dict):
        return raw
    document = dict(raw)
    type_name = document.get("type")
    if isinstance(type_name, str):
        canonical = canonical_uncertainty_type_name(type_name)
        if canonical is not None:
            document["type"] = canonical
    parameters = document.get("parameters")
    if isinstance(parameters, dict):
        canonicalised = dict(parameters)
        for key, value in parameters.items():
            if isinstance(value, dict) and "type" in value:
                nested_type = value["type"]
                if isinstance(nested_type, str):
                    distribution_name = canonical_distribution_type_name(nested_type)
                    if distribution_name is not None:
                        updated = dict(value)
                        updated["type"] = distribution_name
                        canonicalised[key] = updated
        document["parameters"] = canonicalised
    return document


def _build_registry_object(cls: type, parameters: dict[str, Any]) -> Any:
    """Construct one live object from classified fields and document values.

    Nested distribution slots are built recursively; generator fields receive
    a ``numpy.random.default_rng`` built from the document ``seed``
    (ADR-0002 decision 5). Runtime validation (``__post_init__``) fires here
    and its exceptions propagate unwrapped (ADR-0002 decision 15).
    """
    kwargs: dict[str, Any] = {}
    for definition_field in _definition_fields(cls).values():
        if definition_field.kind == "generator":
            kwargs[definition_field.name] = np.random.default_rng(
                parameters.get(_GENERATOR_SEED_FIELD)
            )
        elif definition_field.kind == "nested_distribution":
            kwargs[definition_field.name] = _build_distribution(
                parameters[definition_field.doc_name]
            )
        elif definition_field.doc_name in parameters:
            kwargs[definition_field.name] = parameters[definition_field.doc_name]
    return cls(**kwargs)


def _build_distribution(raw: dict[str, Any]) -> Distribution:
    """Internal: construct a live distribution from a validated definition."""
    cls = resolve_registered_type(raw.get("type"), "distribution")
    parameters = raw.get("parameters") or {}
    return _build_registry_object(cls, parameters)


def _build_uncertainty(raw: dict[str, Any] | None) -> Uncertainty:
    """Internal: construct a live uncertainty from a validated definition."""
    if raw is None:
        return NoUncertainty()
    cls = resolve_registered_type(raw.get("type"), "uncertainty")
    parameters = raw.get("parameters") or {}
    return _build_registry_object(cls, parameters)


def resolve_registered_type(type_name: Any, kind: str) -> type:
    """Resolve a nested definition ``type`` through its registry.

    Raises
    ------
    SpecificationValidationError
        If the name is not registered.
    """
    lookup = (
        lookup_distribution_type if kind == "distribution" else lookup_uncertainty_type
    )
    names = (
        distribution_type_names if kind == "distribution" else uncertainty_type_names
    )
    cls = lookup(type_name) if isinstance(type_name, str) else None
    if cls is None:
        raise SpecificationValidationError(
            [
                SpecificationIssue(
                    path="type",
                    message=(
                        f"unknown {kind} type {type_name!r}; "
                        f"supported types: {names()}"
                    ),
                )
            ]
        )
    return cls


class ParameterDefinition(BaseModel):
    """A named parameter configuration in an uncertainty specification.

    The document mapping key becomes the live parameter's ``name`` at
    construction time and is therefore not a field of the definition itself.

    Parameters
    ----------
    nominal_value : str | int | float | bool
        The base (unperturbed) value. Booleans are legitimate and infer a
        ``BINARY`` parameter (ADR-0002 decision 14).
    uncertainty : dict, optional
        Nested tagged uncertainty definition; ``None`` means
        ``NoUncertainty``.
    type : str, optional
        ``ParameterType`` member name. Absent means construction-time
        inference; explicit values are honoured.
    infer_type_from_data : bool, optional
        Passed through to the runtime constructor; defaults to ``True``.
    metadata : dict, optional
        Accepted verbatim; not interpreted by this layer.
    """

    model_config = ConfigDict(extra="forbid")

    nominal_value: Any
    uncertainty: dict[str, Any] | None = None
    type: str | None = None
    infer_type_from_data: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _reject_unknown_keys(cls, document: Any) -> Any:
        """Reject unknown keys inside the public exception family."""
        if isinstance(document, dict):
            unknown = [key for key in document if key not in _PARAMETER_DEFINITION_KEYS]
            if unknown:
                raise SpecificationValidationError(
                    [
                        SpecificationIssue(
                            path=str(key),
                            message=(
                                "unknown key; allowed: "
                                f"{sorted(_PARAMETER_DEFINITION_KEYS)}"
                            ),
                        )
                        for key in unknown
                    ]
                )
        return document

    @field_validator("uncertainty", mode="before")
    @classmethod
    def _canonicalise_uncertainty(cls, value: Any) -> Any:
        """Map full uncertainty/distribution class names to short names."""
        return _canonicalise_nested_definition(value)

    @model_validator(mode="after")
    def _validate_against_registries(self) -> "ParameterDefinition":
        issues = _validate_parameter_mapping(
            {
                "nominal_value": self.nominal_value,
                "uncertainty": self.uncertainty,
                "type": self.type,
                "infer_type_from_data": self.infer_type_from_data,
                "metadata": self.metadata,
            },
            path="",
        )
        if issues:
            raise SpecificationValidationError(issues)
        return self

    def create_parameter(self, name: str) -> Parameter:
        """Construct a live parameter from this definition.

        Parameters
        ----------
        name : str
            The document mapping key, used as the parameter name.

        Returns
        -------
        Parameter
            A live ``hydroforge.uncertainty.Parameter``. Runtime semantic
            validation fires in the constructors and propagates unwrapped.

        Raises
        ------
        SpecificationValidationError
            If a nested type is not registered (defensive; load validates first).
        """
        parameter_type = (
            ParameterType[self.type]
            if self.type is not None
            else ParameterType.UNDEFINED
        )
        return Parameter(
            name=name,
            nominal_value=self.nominal_value,
            uncertainty=_build_uncertainty(self.uncertainty),
            type=parameter_type,
            infer_type_from_data=self.infer_type_from_data,
            metadata=dict(self.metadata),
        )

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
        Reserved pass-through section; interpreted by scenario generation,
        not by this layer (ADR-0002 decision 11).
    parameters : dict[str, ParameterDefinition], optional
        Named parameter definitions (Stage 2); validated and interpreted.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str
    sensors: dict[str, SensorDefinition] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("sensors", "measurements"),
    )
    model: dict[str, Any] | None = None
    parameters: dict[str, ParameterDefinition] | None = None

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

        raw_parameters = document.get("parameters")
        if raw_parameters is not None and not isinstance(raw_parameters, dict):
            issues.append(
                SpecificationIssue(
                    path="parameters",
                    message="expected a mapping of parameter names to definitions",
                )
            )
        elif isinstance(raw_parameters, dict):
            for name, raw in raw_parameters.items():
                if not isinstance(name, str):
                    issues.append(
                        SpecificationIssue(
                            path=f"parameters.{name}",
                            message="parameter names must be strings",
                        )
                    )
                    continue
                issues.extend(_validate_parameter_mapping(raw, f"parameters.{name}"))

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

    def create_parameter(self, name: str) -> Parameter:
        """Construct a live uncertain parameter by name.

        Parameters
        ----------
        name : str
            Key of the parameter definition in the ``parameters`` section.

        Returns
        -------
        Parameter
            A live ``hydroforge.uncertainty.Parameter`` built from the
            definition, including its nested uncertainty and distribution
            objects. Semantic validation runs in the runtime constructors and
            propagates unwrapped (ADR-0002 decision 15).

        Raises
        ------
        SpecificationError
            If no parameter is defined under ``name``.
        """
        if self.parameters is None or name not in self.parameters:
            raise SpecificationError(
                f"unknown parameter {name!r}; defined parameters: "
                f"{sorted(self.parameters or {})}"
            )
        return self.parameters[name].create_parameter(name=name)

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
