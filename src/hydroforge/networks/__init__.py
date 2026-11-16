"""Model / graph selectors and ``JunctionLeaks`` for WDN models.

.. deprecated:: 1.0.0
    ``hydroforge.networks`` is a backwards-compatibility shim that re-exports
    from :mod:`hydroforge.wdn_modelling.networks`. New code should import from
    :mod:`hydroforge.wdn_modelling.networks` directly.
"""

import warnings

from hydroforge.wdn_modelling.networks.junction_leaks import JunctionLeaks
from hydroforge.wdn_modelling.networks.network_model_component_selectors import (
    PipeNameSelector,
    AttributeSelector,
    DiameterThresholdSelector,
    RandomFractionSelector,
    AvoidBridgesSelector,
    NodeNameSelector,
    ElevationThresholdSelector,
    MinimumDemandSelector,
    ValveNameSelector,
    ValveTypeSelector,
    ModelComponentSelector,
    IComponentSelector,
    LoggingMixin,
    StructuredLoggingMixin,
)

warnings.warn(
    "hydroforge.networks is a deprecated compatibility shim; import from "
    "hydroforge.wdn_modelling.networks instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "JunctionLeaks",
    "PipeNameSelector",
    "AttributeSelector",
    "DiameterThresholdSelector",
    "RandomFractionSelector",
    "AvoidBridgesSelector",
    "NodeNameSelector",
    "ElevationThresholdSelector",
    "MinimumDemandSelector",
    "ValveNameSelector",
    "ValveTypeSelector",
    "ModelComponentSelector",
    "IComponentSelector",
    "LoggingMixin",
    "StructuredLoggingMixin",
]
