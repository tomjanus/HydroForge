"""TSNet backend exports with lazy optional-dependency loading."""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import TSNetConfig
    from .loader import load_tsnet_model
    from .model import TSNetModel
    from .results import TSNetSimulationResults
    from .simulator import TSNetSimulator


_EXPORTS = {
    "TSNetSimulator": (".simulator", "TSNetSimulator"),
    "TSNetConfig": (".config", "TSNetConfig"),
    "TSNetModel": (".model", "TSNetModel"),
    "TSNetSimulationResults": (".results", "TSNetSimulationResults"),
    "load_tsnet_model": (".loader", "load_tsnet_model"),
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
    "TSNetSimulator",
    "TSNetConfig",
    "TSNetModel",
    "TSNetSimulationResults",
    "load_tsnet_model",
]
