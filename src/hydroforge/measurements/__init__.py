"""Generic sensor / measurement imperfection models.

This package is domain-agnostic: it has no EPANET / WDN dependence and is safe
to import without any WDN dependency. It provides generic sensor models
(``Sensor``, ``RandomNoiseSensor``, etc.) and window-averaging helpers
(``WindowAverager``, ``MovingWindowAverager``).

Sensor placement and the sensor-network graph, which *do* depend on WDN /
graph concepts, live in
:mod:`hydroforge.wdn_modelling.measurement_placement`.
"""

from .models import (
    Sensor,
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
from .window import BaseWindowAverager, WindowAverager, MovingWindowAverager

__all__ = [
    "Sensor",
    "PerfectSensor",
    "FixedPrecisionSensor",
    "RandomNoiseSensor",
    "OffsetSensor",
    "SensitivityErrorSensor",
    "DeadBandSensor",
    "SaturationSensor",
    "DriftSensor",
    "CompositeSensor",
    "BaseWindowAverager",
    "WindowAverager",
    "MovingWindowAverager",
]
