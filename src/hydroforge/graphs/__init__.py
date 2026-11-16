"""EPANET network graph analysis and visualization.

.. deprecated:: 1.0.0
    ``hydroforge.graphs`` is a backwards-compatibility shim that re-exports
    from :mod:`hydroforge.wdn_modelling.graphs`. New code should import from
    :mod:`hydroforge.wdn_modelling.graphs` directly.
"""

import warnings

from hydroforge.wdn_modelling.graphs import EPANETNetworkGraph
from hydroforge.wdn_modelling.graphs.visualization import EPANETGraphPlotter

warnings.warn(
    "hydroforge.graphs is a deprecated compatibility shim; import from "
    "hydroforge.wdn_modelling.graphs instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "EPANETNetworkGraph",
    "EPANETGraphPlotter",
]
