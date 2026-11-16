"""Public API for HydroForge simulation backends.

.. deprecated:: 1.0.0
    ``hydroforge.backends`` is a backwards-compatibility shim that re-exports
    from :mod:`hydroforge.wdn_modelling.backends`. New code should import
    from :mod:`hydroforge.wdn_modelling.backends` directly.
"""

import warnings

from hydroforge.wdn_modelling.backends import Backend, BackendName, get_backend
from hydroforge.wdn_modelling.backends import registry  # noqa: F401  (re-export)

warnings.warn(
    "hydroforge.backends is a deprecated compatibility shim; import from "
    "hydroforge.wdn_modelling.backends instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "Backend",
    "BackendName",
    "get_backend",
    "registry",
]
