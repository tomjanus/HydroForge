"""Registry and loading utilities for HydroForge simulation backends."""
from __future__ import annotations

import importlib
from functools import lru_cache
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .common.backends import Backend

# Lazy registration to keep the registry importable even when optional backend
# packages are not installed.
_BACKENDS: dict[str, str] = {
    "wntr": "hydroforge.backends.wntr_backend:WNTRBackend",
    "tsnet": "hydroforge.backends.tsnet_backend:TSNetBackend",
    "tsnetplus": "hydroforge.backends.tsnetplus_backend:TSNetPlusBackend",
    "ptsnet": "hydroforge.backends.ptsnet_backend:PTSNetBackend",
}


def _resolve_backend_class(name: str) -> type[Backend[Any, Any, Any, Any]]:
    """Resolve a backend name to its concrete implementation class.
    
    Parameters
    ----------
    name : str
        The name of the backend to resolve.
    """
    try:
        backend_ref = _BACKENDS[name]
    except KeyError:
        available = ", ".join(_BACKENDS)
        raise ValueError(
            f"Unknown backend {name!r}. Available backends: {available}."
        ) from None

    module_name, _, attr_name = backend_ref.partition(":")
    module = importlib.import_module(module_name)
    try:
        return getattr(module, attr_name)
    except AttributeError as exc:
        raise ImportError(
            f"Backend '{name}' is registered but the class '{attr_name}' was "
            f"not found in module '{module_name}'."
        ) from exc


@lru_cache(maxsize=None)
def get_backend(name: str) -> Backend[Any, Any, Any, Any]:
    """Return a cached HydroForge backend instance for ``name``.
    
    Example
    -------
    >>> from hydroforge.backends import get_backend
    >>> backend = get_backend("wntr")
    >>> backend
    <WNTRBackend>
    """
    backend_class = _resolve_backend_class(name)
    return backend_class()
