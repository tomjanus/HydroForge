"""PTSNet backend exports with lazy optional-dependency loading."""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import PTSNetConfig
    from .loader import load_ptsnet_model
    from .model import PTSNetModel
    from .results import PTSNetSimulationResults
    from .simulator import PTSNetSimulator


_EXPORTS = {
    "PTSNetSimulator": (".simulator", "PTSNetSimulator"),
    "PTSNetConfig": (".config", "PTSNetConfig"),
    "PTSNetModel": (".model", "PTSNetModel"),
    "PTSNetSimulationResults": (".results", "PTSNetSimulationResults"),
    "load_ptsnet_model": (".loader", "load_ptsnet_model"),
}


def __getattr__(name: str):
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


__all__ = [
    "PTSNetSimulator",
    "PTSNetConfig",
    "PTSNetModel",
    "PTSNetSimulationResults",
    "load_ptsnet_model",
]
