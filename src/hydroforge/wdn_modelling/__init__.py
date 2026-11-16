"""WDN / EPANET-specific modelling package.

This package contains all HydroForge code that depends on EPANET / WDN
concepts (WNTR models, ``.inp`` files, ``EPANETNetworkGraph``). It sits on
top of the generic packages
(``hydroforge.auxiliary``, ``hydroforge.uncertainty``,
``hydroforge.sampling``, ``hydroforge.measurements``) and may import from
them, but the reverse is never allowed: top-level generic packages must
never import from ``hydroforge.wdn_modelling``.

Subpackages
-----------
backends
    Simulation backend facade (WNTR, TSNet, TSNetPlus, PTSNet).
epanetfile_io
    Typed EPANET ``.inp`` parse / edit / write.
graphs
    ``EPANETNetworkGraph`` and visualization.
modifiers
    WNTR model and graph modifiers.
networks
    ``JunctionLeaks`` and WNTR component selectors.
measurement_placement
    Sensor placement and the sensor-network graph (depends on :mod:`graphs`).
"""

from .backends import Backend, BackendName, get_backend
from .epanetfile_io import EPANETNetworkModelIO
from .graphs import EPANETNetworkGraph

__all__ = [
    "Backend",
    "BackendName",
    "get_backend",
    "EPANETNetworkGraph",
    "EPANETNetworkModelIO",
]
