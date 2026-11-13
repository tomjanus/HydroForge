""" """

from dataclasses import dataclass
from typing import ClassVar, Sequence
import numpy as np
import pandas as pd
from ptsnet.simulation.sim import PTSNETSimulation
from ..common.results import (
    SimulationResults,
    NodeVariable,
    LinkVariable,
    TimeLocation,
)


@dataclass(slots=True)
class PTSNetSimulationResults(SimulationResults):
    """Wrapper around PTSNet transient simulation results.

    Parameters
    ----------
    model : ptsnet.simulation.sim.PTSNETSimulation
        PTSNet transient model containing simulation results.
    """

    model: PTSNETSimulation

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

    def get_node_variable(
        self,
        variable: NodeVariable,
        nodes: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> np.ndarray | pd.DataFrame:
        if variable not in self.node_variables:
            raise ValueError(f"Invalid PTSNet node variable: {variable!r}")
        table = self.model["node"]
        values = np.asarray(getattr(table, variable))
        labels = list(table.labels)
        frame = pd.DataFrame(values.T, index=self.model["time"], columns=labels)
        selected = frame.loc[times, nodes]
        return selected if as_dataframe else selected.to_numpy()

    def get_link_variable(
        self,
        variable: LinkVariable,
        links: Sequence[str],
        times: TimeLocation = slice(None),
        *,
        as_dataframe: bool = False,
    ) -> np.ndarray | pd.DataFrame:
        raise NotImplementedError(
            "PTSNet exposes pipe start/end results separately; use "
            "results.model['pipe.start'] or results.model['pipe.end']."
        )
