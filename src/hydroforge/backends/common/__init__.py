"""Abstract interfaces for water-network simulation models and results.

This module defines the common interfaces used by hydraulic simulation
backends. :class:`Simulator` represents a simulation engine operating on
a particular model type, while :class:`SimulationResults` provides a
backend-independent interface for accessing simulated node and link
variables.

Concrete simulator implementations should specialize ``Simulator`` with
their model and result types. Concrete result implementations should
subclass :class:`SimulationResults` and define the node and link variables
they support.

The generic relationship between simulators and results is expressed as::

    Simulator[ModelT, ResultT]
        |
        +-- run(ModelT) -> ResultT
                         |
                         +-- SimulationResults

``ResultT`` is bounded by :class:`SimulationResults`, ensuring that a
simulator always returns an object conforming to the common results
interface.

Backends should implement the :class:`Backend` protocol, which defines
methods for loading models, creating simulators, and managing configuration.
"""
from .backends import Backend
from .constants import DemandModel, BackendName
from .results import SimulationResults
from .simulator import Simulator
from .events import TransientEvent


__all__ = [
    "Backend",
    "DemandModel",
    "BackendName",
    "SimulationResults",
    "Simulator",
    "TransientEvent"
]