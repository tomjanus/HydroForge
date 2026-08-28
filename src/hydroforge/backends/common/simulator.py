"""Core interface for HydroForge network simulators.

This module defines the abstract :class:`Simulator` interface used by
HydroForge to provide a common API for hydraulic and transient network
simulation backends.

The simulator abstraction separates the network model and simulation
configuration from the backend-specific implementation. Concrete simulators
specialize :class:`Simulator` with the model type accepted by the underlying
simulation package and the corresponding :class:`SimulationResults` type
returned after a simulation.

Type Parameters
---------------
ModelT
    Type of network model accepted by the simulator.
ResultT
    Type of simulation results returned by the simulator. Must be a subclass
    of :class:`SimulationResults`.

Classes
-------
Simulator
    Abstract generic interface implemented by concrete HydroForge simulation
    backends.

Type Aliases
------------
SimulatorConfig
    Placeholder type alias for backend-specific simulator configuration.
    Concrete backends may replace this with a more specific configuration
    type.

Notes
-----
Concrete simulator implementations are expected to provide backend-specific
configuration and simulation logic while exposing a consistent interface to
the rest of HydroForge.

Examples
--------
A concrete WNTR-based simulator can specialize the generic interface as
follows::

    class WNTRSimulator(
        Simulator[wntr.network.WaterNetworkModel, WNTRSimulationResults]
    ):
        ...
"""
from abc import ABC, abstractmethod
from typing import TypeVar, Generic
from .results import SimulationResults


ModelT = TypeVar("ModelT")
ResultT = TypeVar("ResultT", bound=SimulationResults)
ConfigT = TypeVar("ConfigT")

class Simulator(Generic[ModelT, ResultT, ConfigT], ABC):
    """Abstract interface for a water-network simulation backend.

    Parameters
    ----------
    ModelT
        Type of model accepted by the simulator.
    ResultT
        Type of results returned by the simulator.
    ConfigT
        Type of configuration accepted by the simulator.

    Notes
    -----
    Concrete subclasses should specialize this class with the model and
    result types used by their backend, for example::

        class WNTRSimulator(
            Simulator[wntr.network.WaterNetworkModel, WNTRSimulationResults]
        ):
            ...
    """
    
    @abstractmethod
    def configure(self, config: ConfigT) -> None:
        """Configure the simulator with the provided configuration.

        Parameters
        ----------
        config : ConfigT
            Configuration object specific to the backend.
        """
        
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the simulator before running a simulation.
        This method generally applies to dynamic simulators such as TSnet, or PTSNet"""
    
    @abstractmethod
    def run(self, model: ModelT) -> ResultT:
        """Run the simulation and return its results.

        Parameters
        ----------
        model
            Network model to simulate.

        Returns
        -------
        ResultT
            Results produced by the simulation.
        """
