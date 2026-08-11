"""Core abstractions and utilities for hydraulic network simulation.

This module defines the common interfaces used by hydraulic simulation
backends within HydroForge. It provides abstractions for simulation
strategies and simulation results, allowing different hydraulic solvers
to expose a consistent API for running simulations and retrieving node
and link variables.

The module currently supports simulation backends based on WNTR and
TSNet and provides utilities for constructing TSNet transient models
from EPANET input files.

Classes
-------
DemandModel
    Enumeration of supported hydraulic demand models.
SimulationResults
    Abstract interface for accessing simulation results.
Simulator
    Generic abstract interface for hydraulic simulation strategies.

Functions
---------
load_tsnet_model
    Load a TSNet transient model from an EPANET input file.
load_wntr_model
    Load a WNTR model from an EPANET input file.

Notes
-----
Concrete implementations of :class:`SimulationResults` must define the
``node_variables`` and ``link_variables`` class variables. Concrete
implementations of :class:`Simulator` must implement the ``run`` method.

The abstractions in this module are intentionally solver-agnostic where
possible. This allows simulation backends with substantially different
result representations, such as steady-state WNTR simulations and
transient TSNet simulations, to be exposed through a common interface.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
import pathlib
from typing import TypeAlias, TypeVar, ClassVar, Generic, Any
from collections.abc import Sequence
import pandas as pd
import numpy as np
import wntr
import tsnet


NodeVariable: TypeAlias = str
LinkVariable: TypeAlias = str
TimeLocation: TypeAlias = (
    int
    | slice
    | tuple[int, int]
    | Sequence[int]
)
#Solver: TypeAlias = wntr.sim.WNTRSimulator | wntr.sim.EpanetSimulator


ModelT = TypeVar("ModelT")


class DemandModel(Enum):
    """Supported demand models for hydraulic simulation.

    Values
    ------
    DD
        Demand-driven model.
    PDD
        Pressure-driven model.
    """
    DD = "DD"    # Demand-Driven
    PDD = "PDD"  # Pressure-Driven


class SimulationResults(ABC):
    """Common interface for simulation results from water network simulations.
    
    Attributes
    ----------
    node_variables : ClassVar[tuple[NodeVariable, ...]]
        Tuple of supported node variable names.
    link_variables : ClassVar[tuple[LinkVariable, ...]]
        Tuple of supported link variable names.
        
    Notes
    -----
    Subclasses must define the class variables ``node_variables`` and
    ``link_variables`` to specify the supported variable names for nodes and links,
    respectively. These variables are used to validate requests for simulation
    results.
    """
    node_variables: ClassVar[tuple[NodeVariable, ...]]
    link_variables: ClassVar[tuple[LinkVariable, ...]]

    def __init_subclass__(cls: type[SimulationResults], **kwargs: Any) -> None:
        """ 
        Validate that subclasses define required class variables.
        """
        super().__init_subclass__(**kwargs)
        if "node_variables" not in cls.__dict__:
            raise TypeError(
                f"{cls.__name__} must define class variable "
                "'node_variables'."
            )
        if "link_variables" not in cls.__dict__:
            raise TypeError(
                f"{cls.__name__} must define class variable "
                "'link_variables'."
            )

    @abstractmethod
    def get_node_variable(
        self,
        variable: NodeVariable,
        nodes: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> np.ndarray | pd.DataFrame:
        """Return a node variable."""

    @abstractmethod
    def get_link_variable(
        self,
        variable: LinkVariable,
        links: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> np.ndarray | pd.DataFrame:
        """Return a link variable."""


ResultT = TypeVar("ResultT", bound=SimulationResults)


class Simulator(Generic[ModelT, ResultT], ABC):   
    """Abstract base class for hydraulic simulator strategies.

    The base class defines a uniform interface for running hydraulic simulations
    against a water network model. Concrete implementations must provide the
    ``run`` method which returns the simulation results.
    """
    
    @abstractmethod
    def run(self, model: ModelT) -> ResultT:
        """Run the configured simulation and return the results."""


def load_tsnet_model(model: str | pathlib.Path) -> tsnet.network.TransientModel:
    """Load a TSNet transient model from an INP file.

    Parameters
    ----------
    model
        Path to the EPANET ``.inp`` input file used to construct
        the TSNet transient model.

    Returns
    -------
    tsnet.network.TransientModel
        Initialized TSNet transient model.

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
        raise FileNotFoundError(f"TSNet model file not found: {model}")
    return tsnet.network.TransientModel(str(model))


def load_wntr_model(model: str | pathlib.Path) -> wntr.network.WaterNetworkModel:
    """Load a WNTR model from an INP file.

    Parameters
    ----------
    model
        Path to the EPANET ``.inp`` input file used to construct
        the WNTR model.

    Returns
    -------
    wntr.network.WaterNetworkModel
        Initialized WNTR model.

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
        raise FileNotFoundError(f"WNTR model file not found: {model}")
    return wntr.network.WaterNetworkModel(str(model))


if __name__ == "__main__":
    pass
