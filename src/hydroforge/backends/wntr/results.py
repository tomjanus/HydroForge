""" """
from typing import ClassVar, Sequence, overload, TypeAlias
from dataclasses import dataclass
import pandas as pd
import numpy as np
import wntr
from ..common.results import SimulationResults, TimeLocation, NodeVariable, LinkVariable
from ..common.utils import _resolve_times

RawWNTRSimulationResults: TypeAlias = wntr.sim.SimulationResults

@dataclass(slots=True)
class WNTRSimulationResults(SimulationResults):
    """Wrapper around WNTR simulation results..

    Parameters
    ----------
    raw : RawWNTRSimulationResults
        Simulation results produced by a WNTR/EPANET run (contains node and link
        time series data).
    """
    raw: RawWNTRSimulationResults

    node_variables: ClassVar[tuple[NodeVariable, ...]] = (
        "leak_demand",
        "pressure",
        "head",
        "demand",
        "quality"
    )
    link_variables: ClassVar[tuple[LinkVariable, ...]] = (
        "flowrate",
        "velocity",
        "status",
        "setting"
    )
    
    @staticmethod
    def _validate_variable(variable: str, allowed: tuple[str, ...]) -> None:
        """ Helper method to validate a variable name against allowed variables.
        
        Raises
        ------
        ValueError
            If the variable is not allowed.
        """
        if variable not in allowed:
            raise ValueError(
                f"Invalid variable: {variable!r}. "
                f"Supported variables: {', '.join(allowed)}."
            )
            
    @staticmethod
    def _format_results(
            results: pd.DataFrame,
            *,
            as_dataframe: bool) -> pd.DataFrame | np.ndarray:
        """Format results as a DataFrame or NumPy array."""
        if as_dataframe:
            return results
        return results.to_numpy()

    def _extract_node_results(
        self,
        variable: NodeVariable,
        nodes: Sequence[str],
        times: TimeLocation,
    ) -> pd.DataFrame:
        """ Extract node results for a given variable, nodes, and times.
        
        Parameters
        ----------
        variable : NodeVariable
            Node variable to extract (for example, ``'pressure'`` or ``'head').
        nodes : Sequence[str]
            Node names to extract results from.
        times : TimeLocation
            Time locations to extract data from (default: all times).
            
        Returns
        -------
        pandas.DataFrame
            DataFrame containing the extracted values indexed by time and
            with columns corresponding to the requested nodes.
        
        Raises
        ------
        ValueError
            If the requested variable is not valid.
        """
        self._validate_variable(variable, self.node_variables)
        try:
            table = self.raw.node[variable]
        except KeyError as exc:
            raise ValueError(
                f"Simulation results do not contain "
                f"{variable!r} data."
            ) from exc
        return table.loc[_resolve_times(table.index, times), nodes]

    def _extract_link_results(
        self,
        variable: LinkVariable,
        links: Sequence[str],
        times: TimeLocation,
    ) -> pd.DataFrame:
        """ Extract link results for a given variable, links, and times. 
        
        Parameters
        ----------
        variable : LinkVariable
            Link variable to extract (for example, ``'flowrate'`` or ``'velocity'``).
        links : Sequence[str]
            Link names to extract results from.
        times : TimeLocation
            Time locations to extract data from (default: all times).
            
        Returns
        -------
        pandas.DataFrame
            Data values for the requested links, times, and variable.
        
        Raises
        ------
        ValueError
            If the requested variable is not valid.
        """
        self._validate_variable(variable, self.link_variables)
        try:
            table = self.raw.link[variable]
        except KeyError as exc:
            raise ValueError(
                f"Simulation results do not contain "
                f"{variable!r} data."
            ) from exc
        return table.loc[_resolve_times(table.index, times), links]

    @overload
    def get_node_variable(
        self,
        variable: NodeVariable,
        nodes: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> pd.DataFrame:
        ...
        
    @overload
    def get_node_variable(
        self,
        variable: NodeVariable,
        nodes: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> np.ndarray:
        ...

    def get_node_variable(
        self,
        variable: NodeVariable,
        nodes: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> np.ndarray | pd.DataFrame:
        """Get pressure data for specified sensor names at given times.

        Parameters
        ----------
        variable:   NodeVariable
            Node variable to extract (for example, ``'pressure'`` or ``'head'``).
        nodes : Sequence[str]
            Sensor node names to extract pressure from.
        times : TimeLocation, optional
            Time locations to extract data from (default: 0 for steady-state).
        as_dataframe : bool, optional
            If True, return a ``pandas.DataFrame``; otherwise return a
            ``numpy.ndarray`` (default: False).

        Returns
        -------
        pandas.DataFrame or numpy.ndarray
            Dta values for the requested sensors, times, and variable.
        """
        results = self._extract_node_results(
            variable=variable,
            nodes=nodes,
            times=times
        )
        return self._format_results(results, as_dataframe=as_dataframe)

    @overload
    def get_link_variable(
        self,
        variable: LinkVariable,
        links: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> pd.DataFrame:
        ...
        
    @overload
    def get_link_variable(
        self,
        variable: LinkVariable,
        links: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> np.ndarray:
        ...

    def get_link_variable(
        self,
        variable: LinkVariable,
        links: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> np.ndarray | pd.DataFrame:
        """Get flow data for specified pipe names at given times.

        Parameters
        ----------
        variable:   LinkVariable
            Node variable to extract (for example, ``'velocity'`` or ``'flowrate'``).
        links : Sequence[str]
            Sensor node names to extract data from.
        times : TimeLocation, optional
            Time locations to extract data from (default: 0 for steady-state).
        as_dataframe : bool, optional
            If True, return a ``pandas.DataFrame``; otherwise return a
            ``numpy.ndarray`` (default: False).

        Returns
        -------
        pandas.DataFrame or numpy.ndarray
            Data values for the requested sensors and times and variable.
        """
        results = self._extract_link_results(
            variable=variable,
            links=links,
            times=times
        )
        return self._format_results(results, as_dataframe=as_dataframe)
