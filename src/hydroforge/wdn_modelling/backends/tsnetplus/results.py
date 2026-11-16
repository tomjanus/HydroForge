""" """

from typing import ClassVar, Sequence
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .model import TSNetPlusModel
from ..common.results import SimulationResults, NodeVariable, LinkVariable, TimeLocation
from ..common.utils import _resolve_times


@dataclass(slots=True)
class TSNetPlusSimulationResults(SimulationResults):
    """Wrapper around TSNet+ transient simulation results.

    Parameters
    ----------
    model : TSNetPlusModel
        TSNet+ transient model containing simulation results.

    Notes
    -----
    TSNet+ stores each result variable as a NumPy time-series array on
    the corresponding node or link. The common simulation time axis is
    ``model.simulation_timestamps``.
    """

    model: TSNetPlusModel

    node_variables: ClassVar[tuple[NodeVariable, ...]] = (
        "head",
        "emitter_discharge",
        "demand_discharge",
    )

    link_variables: ClassVar[tuple[LinkVariable, ...]] = (
        "start_node_head",
        "start_node_velocity",
        "start_node_flowrate",
        "end_node_head",
        "end_node_velocity",
        "end_node_flowrate",
    )

    def __post_init__(self) -> None:
        """Validate that the model contains transient simulation results after
        initialization.
        """
        self._validate_results_exist()

    def _validate_results_exist(self) -> None:
        """Validate that the model contains transient simulation results."""
        if getattr(self.model, "simulation_timestamps", None) is None:
            raise ValueError(
                "The TSNet transient model does not contain simulation results. "
                "Run MOCSimulator before creating TSNetSimulationResults."
            )

    @staticmethod
    def _as_dataframe(
        values: np.ndarray,
        *,
        index: pd.Index,
        columns: Sequence[str],
        dtype: type = float,
    ) -> pd.DataFrame:
        """ """
        return pd.DataFrame(values, index=index, columns=columns, dtype=dtype)

    @staticmethod
    def _as_array(values: np.ndarray) -> np.ndarray:
        return values

    @staticmethod
    def _validate_variable(variable: str, allowed: tuple[str, ...]) -> None:
        """Helper method to validate a variable name against allowed variables.

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

    @property
    def _timestamps(self) -> pd.Index:
        """Return TSNet simulation timestamps as a pandas Index."""
        return pd.Index(
            np.asarray(self.model.simulation_timestamps),
            name="time",
        )

    def _extract_node_results(
        self,
        variable: NodeVariable,
        nodes: Sequence[str],
        times: TimeLocation,
    ) -> tuple[np.ndarray, pd.Index]:
        """Extract node results for a given variable, nodes, and times.

        Parameters
        ----------
        variable : NodeVariable
            Node variable to extract (for example, ``'head'`` or ``'emitter_discharge'``).
        nodes : Sequence[str]
            Node names to extract results from.
        times : TimeLocation
            Time locations to extract data from (default: all times).

        Returns
        -------
        tuple[np.ndarray, pd.Index]
            Tuple containing the extracted values and corresponding timestamps.

        Raises
        ------
        ValueError
            If the requested variable is not valid.
        ValueError
            If the simulation results contain no time steps.
        RuntimeError
            If the number of time steps in the results does not match the number of timestamps.
        """
        self._validate_variable(variable, self.node_variables)
        timestamps = self._timestamps
        if len(timestamps) == 0:
            raise ValueError("Simulation results contain no time steps.")
        values = np.column_stack(
            [
                np.asarray(getattr(self.model.get_node(node_name), variable))
                for node_name in nodes
            ]
        )
        if values.shape[0] != len(timestamps):
            raise RuntimeError(
                f"TSNet results for {variable!r} contain "
                f"{values.shape[0]} time steps, but "
                f"{len(timestamps)} timestamps were found."
            )
        table = pd.DataFrame(values, index=timestamps, columns=nodes)
        selected = table.loc[_resolve_times(timestamps, times), :]
        return selected.to_numpy(), selected.index

    def _extract_link_results(
        self,
        variable: LinkVariable,
        links: Sequence[str],
        times: TimeLocation,
    ) -> tuple[np.ndarray, pd.Index]:
        """Extract link results for a given variable, links, and times.

        Parameters
        ----------
        variable : LinkVariable
            Link variable to extract (for example, ``'start_node_head'`` or ``'end_node_velocity'``).
        links : Sequence[str]
            Link names to extract results from.
        times : TimeLocation
            Time locations to extract data from (default: all times).

        Returns
        -------
        tuple[np.ndarray, pd.Index]
            Tuple containing the extracted values and corresponding timestamps.

        Raises
        ------
        ValueError
            If the requested variable is not valid.
        ValueError
            If the simulation results contain no time steps.
        RuntimeError
            If the number of time steps in the results does not match the number of timestamps.
        """
        self._validate_variable(variable, self.link_variables)
        timestamps = self._timestamps
        if len(timestamps) == 0:
            raise ValueError("Simulation results contain no time steps.")
        values = np.column_stack(
            [
                np.asarray(getattr(self.model.get_link(link_name), variable))
                for link_name in links
            ]
        )
        if values.shape[0] != len(timestamps):
            raise RuntimeError(
                f"TSNet results for {variable!r} contain "
                f"{values.shape[0]} time steps, but "
                f"{len(timestamps)} timestamps were found."
            )
        table = pd.DataFrame(values, index=timestamps, columns=links)
        selected = table.loc[_resolve_times(timestamps, times), :]
        return selected.to_numpy(), selected.index

    def get_node_variable(
        self,
        variable: NodeVariable,
        nodes: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> np.ndarray | pd.DataFrame:
        """Get node variable data for specified node names at given times.
        Parameters
        ----------
        variable : NodeVariable
            Node variable to retrieve (for example, ``'head'`` or ``'emitter_discharge'``).
        nodes : Sequence[str]
            Node names to retrieve data for.
        times : TimeLocation, optional
            Time locations to retrieve data from (default: all times).
        as_dataframe : bool, optional
            If True, return the data as a pandas DataFrame (default: False).

        Returns
        -------
        np.ndarray | pd.DataFrame
            Node variable data as a NumPy array or pandas DataFrame.
            The returned data will have shape (num_times, num_nodes), where
            num_times is the number of time steps selected and num_nodes is the
            number of nodes specified. If ``as_dataframe`` is True, the DataFrame
            will have timestamps as the index and node names as the columns.
        """
        values, timestamps = self._extract_node_results(variable, nodes, times)
        if as_dataframe:
            return pd.DataFrame(values, index=timestamps, columns=nodes)
        return values

    def get_link_variable(
        self,
        variable: LinkVariable,
        links: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> np.ndarray | pd.DataFrame:
        """Get node variable data for specified node names at given times.
        Parameters
        ----------
        variable : LinkVariable
            Link variable to retrieve (for example, ``'start_node_head'`` or ``'end_node_velocity'``).
        links : Sequence[str]
            Node names to retrieve data for.
        times : TimeLocation, optional
            Time locations to retrieve data from (default: all times).
        as_dataframe : bool, optional
            If True, return the data as a pandas DataFrame (default: False).

        Returns
        -------
        np.ndarray | pd.DataFrame
            Node variable data as a NumPy array or pandas DataFrame.
            The returned data will have shape (num_times, num_links), where
            num_times is the number of time steps selected and num_links is the
            number of links specified. If ``as_dataframe`` is True, the DataFrame
            will have timestamps as the index and node names as the columns.
        """
        values, timestamps = self._extract_link_results(variable, links, times)
        if as_dataframe:
            return pd.DataFrame(values, index=timestamps, columns=links)
        return values
