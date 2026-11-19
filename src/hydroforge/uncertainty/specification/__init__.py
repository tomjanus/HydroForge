"""Generic uncertainty specification models, registry, and I/O.

This package is domain-agnostic: it has no EPANET / WDN dependence and must
not import :mod:`hydroforge.wdn_modelling`.
"""

from .exceptions import (
    SpecificationError,
    SpecificationFormatError,
    SpecificationIssue,
    SpecificationValidationError,
)
from .io import load_specification, save_specification
from .models import ParameterDefinition, SensorDefinition, UncertaintySpecification
from .registry import lookup_sensor_type, resolve_sensor_type, sensor_type_names

__all__ = [
    "SensorDefinition",
    "ParameterDefinition",
    "UncertaintySpecification",
    "SpecificationError",
    "SpecificationFormatError",
    "SpecificationIssue",
    "SpecificationValidationError",
    "load_specification",
    "save_specification",
    "lookup_sensor_type",
    "resolve_sensor_type",
    "sensor_type_names",
]
