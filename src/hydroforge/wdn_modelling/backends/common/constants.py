"""Core enumerations for HydroForge simulation configuration.

This module defines enumerations used to identify supported hydraulic demand
models and simulation backends in HydroForge.

Classes
-------
DemandModel
    Enumeration of demand modelling approaches supported by HydroForge,
    including demand-driven and pressure-driven formulations.

BackendName
    Enumeration of simulation backends supported by HydroForge, including
    WNTR, TSNet, TSNetPlus, and PTSNet.

Notes
-----
The enumeration values are represented by strings corresponding to the
canonical names used by HydroForge when selecting a demand model or
simulation backend.
"""

import sys
from enum import Enum

if sys.version_info >= (3, 11):
    from enum import StrEnum as _StrEnumBase
else:  # Python 3.10

    class _StrEnumBase(str, Enum):
        """String enum compatibility for Python versions before 3.11."""

        def __str__(self) -> str:
            return str(self.value)


class DemandModel(Enum):
    """Supported demand models for hydraulic simulation.

    Values
    ------
    DD
        Demand-driven model.
    PDD
        Pressure-driven model.
    """

    DD = "DD"  # Demand-Driven
    PDD = "PDD"  # Pressure-Driven


class BackendName(_StrEnumBase):
    """Enumeration of supported HydroForge simulation backends."""

    WNTR = "wntr"
    TSNET = "tsnet"
    TSNETPLUS = "tsnetplus"
    PTSNET = "ptsnet"
