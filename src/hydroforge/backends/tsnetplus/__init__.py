"""TSNetPlus backend exports with lazy optional-dependency loading."""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import TSNetPlusConfig
    from .loader import load_tsnetplus_model
    from .model import TSNetPlusModel
    from .results import TSNetPlusSimulationResults
    from .simulator import TSNetSPlusSimulator


_EXPORTS = {
    "TSNetSPlusSimulator": (".simulator", "TSNetSPlusSimulator"),
    "TSNetPlusConfig": (".config", "TSNetPlusConfig"),
    "TSNetPlusModel": (".model", "TSNetPlusModel"),
    "TSNetPlusSimulationResults": (".results", "TSNetPlusSimulationResults"),
    "load_tsnetplus_model": (".loader", "load_tsnetplus_model"),
    "events": (".events", None),
}


def __getattr__(name: str):
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name, __name__)
    value = module if attribute_name is None else getattr(module, attribute_name)
    globals()[name] = value
    return value


__all__ = [
    "TSNetSPlusSimulator",
    "TSNetPlusConfig",
    "TSNetPlusModel",
    "TSNetPlusSimulationResults",
    "load_tsnetplus_model",
    "events",
]