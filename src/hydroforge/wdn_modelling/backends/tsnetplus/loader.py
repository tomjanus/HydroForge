""" """

import pathlib
from typing import Any

try:
    from .model import TSNetPlusModel
except Exception:  # pragma: no cover - optional dependency
    TSNetPlusModel = Any  # type: ignore[misc, assignment]


def load_tsnetplus_model(model: str | pathlib.Path) -> TSNetPlusModel:
    """Load a TSNetPlus transient model from an INP file.

    Parameters
    ----------
    model
        Path to the EPANET ``.inp`` input file used to construct
        the TSNetPlus transient model.

    Returns
    -------
    TSNetPlusModel
        Initialized TSNetPlus transient model.

    Raises
    ------
    FileNotFoundError
        If the specified model file does not exist.
    OSError
        If the model file cannot be accessed.
    ValueError
        If the model file contains invalid network data.
    """
    model = pathlib.Path(model)
    if not model.is_file():
        raise FileNotFoundError(f"TSNetPlus model file not found: {model}")
    import sys
    import importlib

    for module_name in ("tsnetplus", "tsnetplus.network", "tsnetplus.network.model"):
        cached = sys.modules.get(module_name)
        if cached is not None and not getattr(cached, "__file__", None):
            del sys.modules[module_name]
    importlib.import_module("tsnetplus")
    network = importlib.import_module("tsnetplus.network")

    return network.TransientModel(str(model))
