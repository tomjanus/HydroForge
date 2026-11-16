"""Sensor modeling, placement, and analysis for water distribution networks.

.. deprecated:: 1.0.0
    ``hydroforge.sensors`` is a backwards-compatibility shim. Its contents
    have moved:

    * Generic sensor / measurement imperfection models
      (``Sensor``, ``RandomNoiseSensor``, ``WindowAverager``, ...):
      :mod:`hydroforge.measurements`
    * WDN-specific sensor placement and the sensor-network graph:
      :mod:`hydroforge.wdn_modelling.measurement_placement`

    Top-level generic packages (``hydroforge.measurements``,
    ``hydroforge.auxiliary``, ``hydroforge.uncertainty``,
    ``hydroforge.sampling``) never import from :mod:`hydroforge.wdn_modelling`.
"""

import warnings

from hydroforge.measurements import (
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
    BaseWindowAverager,
    WindowAverager,
    MovingWindowAverager,
)

from hydroforge.wdn_modelling.measurement_placement import (
    SourceFinder,
    GreedySensorPlacement,
    KCentreSensorPlacement,
    RandomSensorPlacement,
    CentralityBasedSensorPlacement,
    CoverageBasedSensorPlacement,
    DominatingSetBasedSensorPlacement,
    FixedLocationSensorPlacement,
    SensorPlacer,
    SensorNetworkGraph,
)

warnings.warn(
    "hydroforge.sensors is a deprecated compatibility shim; import sensor "
    "models from hydroforge.measurements and placement / sensor-network code "
    "from hydroforge.wdn_modelling.measurement_placement instead.",
    DeprecationWarning,
    stacklevel=2,
)

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
    "SourceFinder",
    "GreedySensorPlacement",
    "KCentreSensorPlacement",
    "RandomSensorPlacement",
    "CentralityBasedSensorPlacement",
    "CoverageBasedSensorPlacement",
    "DominatingSetBasedSensorPlacement",
    "FixedLocationSensorPlacement",
    "SensorPlacer",
    "SensorNetworkGraph",
]
