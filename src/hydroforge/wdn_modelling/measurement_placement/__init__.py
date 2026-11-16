"""Sensor placement and sensor-network graph for WDN models.

This package depends on :mod:`hydroforge.wdn_modelling.graphs` and is part of
the WDN / EPANET-specific modelling layer. Top-level generic packages must
never import from here.
"""

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

__all__ = [
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
