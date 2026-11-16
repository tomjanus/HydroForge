"""WNTR model and graph modifiers.

.. deprecated:: 1.0.0
    ``hydroforge.modifiers`` is a backwards-compatibility shim that
    re-exports from :mod:`hydroforge.wdn_modelling.modifiers`. New code should
    import from :mod:`hydroforge.wdn_modelling.modifiers` directly.
"""

import warnings

from hydroforge.wdn_modelling.modifiers.network_graph_modifier import (
    NetworkGraphComponentModifier,
    NetworkGraphPipeRemover,
)
from hydroforge.wdn_modelling.modifiers.network_model_modifier import (
    NetworkComponentModifier,
)
from hydroforge.wdn_modelling.modifiers.common import (
    PipeNotFoundException,
    BridgeRemovalException,
    LoggingMixin,
    StructuredLoggingMixin,
)

warnings.warn(
    "hydroforge.modifiers is a deprecated compatibility shim; import from "
    "hydroforge.wdn_modelling.modifiers instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "NetworkGraphComponentModifier",
    "NetworkGraphPipeRemover",
    "NetworkComponentModifier",
    "PipeNotFoundException",
    "BridgeRemovalException",
    "LoggingMixin",
    "StructuredLoggingMixin",
]
