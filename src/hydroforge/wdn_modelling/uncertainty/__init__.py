"""WNTR-specific application of generic uncertainty definitions and values."""

from .parameters import (
    ParameterApplicationError,
    ParameterApplicationRecord,
    ParameterApplicationReport,
    WNTRParameterAdapter,
    WNTRParameterBinding,
    WNTRParameterBindingProtocol,
    WNTRParameterProperty,
)
from .sensors import (
    SensorApplicationError,
    WNTRSensorAdapter,
    WNTRSensorBinding,
    WNTRSensorVariable,
)
from .wntr_mapping import WNTRModel, WNTRModelMapper

# TSNetPlus/PTSNET mapping implementations are intentionally not imported here.
# They live in their canonical submodules so importing this generic package does
# not require optional simulation backends:
#   hydroforge.wdn_modelling.uncertainty.tsnetplus_mapping
#   hydroforge.wdn_modelling.uncertainty.ptset_mapping (when added)

__all__ = [
    "ParameterApplicationError",
    "ParameterApplicationRecord",
    "ParameterApplicationReport",
    "WNTRParameterAdapter",
    "WNTRParameterBinding",
    "WNTRParameterBindingProtocol",
    "WNTRParameterProperty",
    "SensorApplicationError",
    "WNTRSensorAdapter",
    "WNTRSensorBinding",
    "WNTRSensorVariable",
    "WNTRModel",
    "WNTRModelMapper",
]
