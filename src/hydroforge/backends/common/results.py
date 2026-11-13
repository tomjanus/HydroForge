"""Core interface for HydroForge simulation results.

This module defines the common interface and type aliases used to represent
and access results produced by water-network simulations. The
:class:`SimulationResults` abstraction provides a backend-independent API for
retrieving simulated variables associated with network nodes and links.

Concrete simulation backends, such as WNTR, TSNet, TSNetPlus, and PTSNet,
should provide specialized :class:`SimulationResults` implementations that
map their native result structures to this common interface.

Type Aliases
------------
NodeVariable
    Name of a variable associated with a network node.
LinkVariable
    Name of a variable associated with a network link.
TimeLocation
    Specification of one or more simulation time locations.

Classes
-------
SimulationResults
    Abstract interface for accessing node and link variables from simulation
    results.

Notes
-----
Simulation results may be returned either as NumPy arrays or pandas
DataFrames. The ``as_dataframe`` argument of the retrieval methods allows
callers to explicitly select the desired representation.

Concrete subclasses must define the ``node_variables`` and
``link_variables`` class variables. These specify the variables supported by
the backend and are used to validate variable requests.

The module imports NumPy and pandas only during static type checking. This
allows the results interface to expose precise type annotations without
requiring either package to be imported when this module is loaded.
"""

from __future__ import annotations
from typing import ClassVar, Sequence, TYPE_CHECKING, Literal, overload, TypeAlias, Any
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd

    SimulationOutputs = np.ndarray | pd.DataFrame
else:
    SimulationOutputs = object


NodeVariable: TypeAlias = str
"""Name of a variable associated with a network node."""

LinkVariable: TypeAlias = str
"""Name of a variable associated with a network link."""

TimeLocation: TypeAlias = int | slice | tuple[int, int] | Sequence[int]


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
                f"{cls.__name__} must define class variable " "'node_variables'."
            )
        if "link_variables" not in cls.__dict__:
            raise TypeError(
                f"{cls.__name__} must define class variable " "'link_variables'."
            )

    @overload
    def get_node_variable(
        self,
        variable: NodeVariable,
        nodes: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: Literal[False] = False,
    ) -> np.ndarray: ...

    @overload
    def get_node_variable(
        self,
        variable: NodeVariable,
        nodes: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: Literal[True],
    ) -> pd.DataFrame: ...

    @abstractmethod
    def get_node_variable(
        self,
        variable: NodeVariable,
        nodes: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> SimulationOutputs:
        """Return simulated values for a node variable.

        Parameters
        ----------
        variable
            Name of the node variable to retrieve.
        nodes
            Node identifiers to retrieve.
        times
            Time locations to retrieve.
        as_dataframe
            If ``True``, return the result as a pandas DataFrame;
            otherwise return a NumPy array.

        Returns
        -------
        SimulationOutputs (np.ndarray or pd.DataFrame)
            Requested simulation results.
        """

    @overload
    def get_link_variable(
        self,
        variable: LinkVariable,
        links: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: Literal[False] = False,
    ) -> np.ndarray: ...

    @overload
    def get_link_variable(
        self,
        variable: LinkVariable,
        links: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: Literal[True],
    ) -> pd.DataFrame: ...

    @abstractmethod
    def get_link_variable(
        self,
        variable: LinkVariable,
        links: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> SimulationOutputs:
        """Return simulated values for a link variable.

        Parameters
        ----------
        variable
            Name of the link variable to retrieve.
        links
            Link identifiers to retrieve.
        times
            Time locations to retrieve.
        as_dataframe
            If ``True``, return the result as a pandas DataFrame;
            otherwise return a NumPy array.

        Returns
        -------
        SimulationOutputs (np.ndarray or pd.DataFrame)
            Requested simulation results.
        """
