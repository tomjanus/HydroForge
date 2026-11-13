"""Sensor modeling, placement, and analysis for water distribution networks.

Submodules
----------
sensors
    Sensor models simulating measurement error and noise (e.g., fixed
    precision, random noise, offset, drift) plus window-averaging helpers.
sensor_network
    `SensorNetworkGraph`, a graph representation of a sensor network built
    on top of a NetworkX graph.
sensor_placement
    Sensor placement strategies (greedy, K-center, random, centrality-based,
    coverage-based, dominating set, fixed location) and the `SensorPlacer`
    orchestrator class.
"""

from .sensors import (
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

from .placement import (
    SourceFinder,
    GreedySensorPlacement,
    KCentreSensorPlacement,
    RandomSensorPlacement,
    CentralityBasedSensorPlacement,
    CoverageBasedSensorPlacement,
    DominatingSetBasedSensorPlacement,
    FixedLocationSensorPlacement,
    SensorPlacer,
)

from .sensor_network import SensorNetworkGraph

__doc____ = (
    """Sensor modeling, placement, and analysis for water distribution networks."""
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
