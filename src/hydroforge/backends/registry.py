"""Registry and loading utilities for HydroForge simulation backends."""

from __future__ import annotations

import importlib
import shlex
import subprocess
import sys
from functools import lru_cache
from typing import Any, TYPE_CHECKING

from importlib.util import find_spec

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

_OPTIONAL_DEPENDENCIES: dict[str, tuple[str, str]] = {
    "tsnet": ("tsnet", "git+https://github.com/glorialulu/TSNet.git"),
    "tsnetplus": (
        "tsnetplus",
        "git+https://github.com/tomjanus/TSNetPlus.git",
    ),
    "ptsnet": ("ptsnet", "ptsnet"),
}


def _ensure_optional_dependency(name: str) -> None:
    """Prompt to install a missing package for an optional backend."""
    dependency = _OPTIONAL_DEPENDENCIES.get(name)
    if dependency is None:
        return

    package_name, install_requirement = dependency
    if find_spec(package_name) is not None:
        return

    install_command = shlex.join(
        [sys.executable, "-m", "pip", "install", install_requirement]
    )
    prompt = (
        f"The {name} backend requires the '{package_name}' package, which is "
        "not installed. It must be installed before execution. "
        "Install it now? [y/N]: "
    )
    try:
        response = input(prompt)
    except EOFError:
        response = ""

    if response.strip().lower() not in {"y", "yes"}:
        raise ImportError(
            f"Cannot use the {name} backend because '{package_name}' is not "
            f"installed. Install it before execution with `{install_command}` "
            f"or `pip install -e '.[{name}]'`."
        )

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", install_requirement],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ImportError(
            f"Installation of '{package_name}' failed. Install it before "
            f"using the {name} backend with `{install_command}`."
        ) from exc
    importlib.invalidate_caches()


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

    _ensure_optional_dependency(name)

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
