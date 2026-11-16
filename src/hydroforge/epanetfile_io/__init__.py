"""Typed EPANET ``.inp`` parsing, editing, and writing without WNTR.

.. deprecated:: 1.0.0
    ``hydroforge.epanetfile_io`` is a backwards-compatibility shim that
    re-exports from :mod:`hydroforge.wdn_modelling.epanetfile_io`. New code
    should import from :mod:`hydroforge.wdn_modelling.epanetfile_io`
    directly.
"""

import warnings

from hydroforge.wdn_modelling.epanetfile_io import (
    EPANETFileIO,
    EPANETFileReaderError,
    EPANETNetworkModelIO,
    EPANETNetworkModel,
)

warnings.warn(
    "hydroforge.epanetfile_io is a deprecated compatibility shim; import from "
    "hydroforge.wdn_modelling.epanetfile_io instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "EPANETFileIO",
    "EPANETFileReaderError",
    "EPANETNetworkModelIO",
    "EPANETNetworkModel",
]
