"""Allow-listed registries mapping type names to sensor, uncertainty, and
distribution classes.

The registries are the only supported way to turn a serialised type name into
a class. Documents can never import arbitrary classes.
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
from hydroforge.uncertainty.distributions import (
    CategoricalDiracDeltaDistribution,
    CategoricalHistogramDistribution,
    CategoricalNormalDistribution,
    CategoricalUniformDistribution,
    ContinuousDiracDeltaDistribution,
    DiscreteDiracDeltaDistribution,
    DiscreteHistogramDistribution,
    DiscreteNormalDistribution,
    DiscreteUniformDistribution,
    Distribution,
    NormalDistribution,
    UniformDistribution,
)
from hydroforge.uncertainty.uncertainties import (
    AdditiveUncertainty,
    BinaryStateFlipUncertainty,
    BiasUncertainty,
    CategoricalRandomReplacementUncertainty,
    CategoricalReplacementUncertainty,
    MultiplicativeUncertainty,
    NoUncertainty,
    Uncertainty,
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


class _ClassRegistry:
    """A name -> class allow-list with short and full-name spellings.

    Canonical short names (e.g. ``Normal``) are the documented spelling and
    the only names :meth:`names` returns; full class names (e.g.
    ``NormalDistribution``) are accepted by :meth:`lookup` as input aliases.
    """

    def __init__(self, kind: str, suffix: str, classes: tuple[type, ...]) -> None:
        self._kind = kind
        self._suffix = suffix
        self._by_name: dict[str, type] = {}
        for cls in classes:
            self._by_name[cls.__name__] = cls
            self._by_name[cls.__name__.removesuffix(suffix)] = cls

    def lookup(self, name: str) -> type | None:
        """Return the registered class for ``name``, or ``None``."""
        return self._by_name.get(name)

    def resolve(self, name: str) -> type:
        """Return the registered class for ``name``.

        Raises
        ------
        SpecificationValidationError
            If ``name`` is not registered.
        """
        cls = self.lookup(name)
        if cls is None:
            raise SpecificationValidationError(
                [
                    SpecificationIssue(
                        path="type",
                        message=(
                            f"unknown {self._kind} type {name!r}; "
                            f"supported types: {self.names()}"
                        ),
                    )
                ]
            )
        return cls

    def canonical_name(self, name: str) -> str | None:
        """Return the canonical short name for ``name``, or ``None``."""
        cls = self._by_name.get(name)
        if cls is None:
            return None
        return cls.__name__.removesuffix(self._suffix)

    def names(self) -> list[str]:
        """Return the sorted canonical short names this registry accepts."""
        return sorted(
            cls.__name__.removesuffix(self._suffix)
            for cls in set(self._by_name.values())
        )


# Registries hold every concrete class. The generic DiracDeltaDistribution is
# deliberately absent: without a type tag its document form is ambiguous and
# its CDF is undefined (ADR-0002 decision 2).
_DISTRIBUTION_CLASSES: tuple[type[Distribution], ...] = (
    NormalDistribution,
    UniformDistribution,
    ContinuousDiracDeltaDistribution,
    DiscreteDiracDeltaDistribution,
    CategoricalDiracDeltaDistribution,
    DiscreteNormalDistribution,
    DiscreteUniformDistribution,
    DiscreteHistogramDistribution,
    CategoricalNormalDistribution,
    CategoricalUniformDistribution,
    CategoricalHistogramDistribution,
)

_UNCERTAINTY_CLASSES: tuple[type[Uncertainty], ...] = (
    NoUncertainty,
    AdditiveUncertainty,
    MultiplicativeUncertainty,
    BiasUncertainty,
    CategoricalRandomReplacementUncertainty,
    CategoricalReplacementUncertainty,
    BinaryStateFlipUncertainty,
)

_DISTRIBUTION_REGISTRY = _ClassRegistry(
    kind="distribution",
    suffix="Distribution",
    classes=_DISTRIBUTION_CLASSES,
)

_UNCERTAINTY_REGISTRY = _ClassRegistry(
    kind="uncertainty",
    suffix="Uncertainty",
    classes=_UNCERTAINTY_CLASSES,
)


def lookup_distribution_type(name: str) -> type[Distribution] | None:
    """Return the distribution class registered under ``name``, or ``None``."""
    return _DISTRIBUTION_REGISTRY.lookup(name)


def resolve_distribution_type(name: str) -> type[Distribution]:
    """Return the distribution class registered under ``name``."""
    return _DISTRIBUTION_REGISTRY.resolve(name)


def canonical_distribution_type_name(name: str) -> str | None:
    """Return the canonical distribution short name for ``name``."""
    return _DISTRIBUTION_REGISTRY.canonical_name(name)


def distribution_type_names() -> list[str]:
    """Return the sorted canonical distribution type names."""
    return _DISTRIBUTION_REGISTRY.names()


def lookup_uncertainty_type(name: str) -> type[Uncertainty] | None:
    """Return the uncertainty class registered under ``name``, or ``None``."""
    return _UNCERTAINTY_REGISTRY.lookup(name)


def resolve_uncertainty_type(name: str) -> type[Uncertainty]:
    """Return the uncertainty class registered under ``name``."""
    return _UNCERTAINTY_REGISTRY.resolve(name)


def canonical_uncertainty_type_name(name: str) -> str | None:
    """Return the canonical uncertainty short name for ``name``."""
    return _UNCERTAINTY_REGISTRY.canonical_name(name)


def uncertainty_type_names() -> list[str]:
    """Return the sorted canonical uncertainty type names."""
    return _UNCERTAINTY_REGISTRY.names()
