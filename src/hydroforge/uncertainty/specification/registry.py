"""Allow-listed registry mapping sensor type names to sensor classes.

The registry is the only supported way to turn a serialised sensor type name
into a sensor class. Documents can never import arbitrary classes.
"""

from __future__ import annotations

from hydroforge.measurements import (
    CompositeSensor,
    DeadBandSensor,
    DriftSensor,
    FixedPrecisionSensor,
    OffsetSensor,
    PerfectSensor,
    RandomNoiseSensor,
    SaturationSensor,
    SensitivityErrorSensor,
    Sensor,
)

from .exceptions import SpecificationIssue, SpecificationValidationError

_SENSOR_CLASSES: tuple[type[Sensor], ...] = (
    PerfectSensor,
    FixedPrecisionSensor,
    RandomNoiseSensor,
    OffsetSensor,
    SensitivityErrorSensor,
    DeadBandSensor,
    SaturationSensor,
    DriftSensor,
    CompositeSensor,
)

# Canonical short names (e.g. ``FixedPrecision``) are the documented spelling
# for specifications; full class names (e.g. ``FixedPrecisionSensor``) are
# accepted as input aliases but never emitted.
_SENSOR_TYPES: dict[str, type[Sensor]] = {}
for _cls in _SENSOR_CLASSES:
    _SENSOR_TYPES[_cls.__name__] = _cls
    _SENSOR_TYPES[_cls.__name__.removesuffix("Sensor")] = _cls
del _cls


def lookup_sensor_type(name: str) -> type[Sensor] | None:
    """Return the sensor class registered under ``name``, or ``None``.

    Both the short name (``FixedPrecision``) and the full class name
    (``FixedPrecisionSensor``) are registered.
    """
    return _SENSOR_TYPES.get(name)


def resolve_sensor_type(name: str) -> type[Sensor]:
    """Return the sensor class registered under ``name``.

    Raises
    ------
    SpecificationValidationError
        If ``name`` is not registered.
    """
    cls = lookup_sensor_type(name)
    if cls is None:
        raise SpecificationValidationError(
            [
                SpecificationIssue(
                    path="type",
                    message=(
                        f"unknown sensor type {name!r}; "
                        f"supported types: {sensor_type_names()}"
                    ),
                )
            ]
        )
    return cls


def canonical_sensor_type_name(name: str) -> str | None:
    """Return the canonical short name for ``name``, or ``None`` if unknown."""
    cls = _SENSOR_TYPES.get(name)
    if cls is None:
        return None
    return cls.__name__.removesuffix("Sensor")


def sensor_type_names() -> list[str]:
    """Return the sorted canonical sensor type names.

    These are the names specifications should use. Full class names are
    accepted by :func:`lookup_sensor_type` as input aliases but are not
    listed here.
    """
    return sorted(cls.__name__.removesuffix("Sensor") for cls in _SENSOR_CLASSES)
