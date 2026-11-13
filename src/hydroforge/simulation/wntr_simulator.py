"""Hydraulic simulation strategies for static simulatoin of water distribution networks.

This module implements a Strategy pattern for running hydraulic simulations on
WNTR/EPANET water network models. It provides a consistent interface for switching
between simulation engines while configuring common options such as hydraulic
timestep, demand model, and result extraction.

The module exposes concrete simulator strategies and helper dataclasses:

- ``WNTRSimulatorConfig``: Simulation configuration parameters for the WNTR simulator.
- ``EPANETSimulatorConfig``: Simulation configuration parameters for the EPANET simulator.
- ``WNTRSimulationResults``: Lightweight wrapper around WNTR simulation results.
- ``Simulator``: Abstract base class defining the simulator interface.
- ``WNTRSimulator`` / ``EPANETSimulator``: Concrete simulators targeting
  WNTR's Python solver and the original EPANET solver respectively.

Examples
--------
>>> from hydroforge.simulation import WNTRSimulator, WNTRSimulatorConfig, DemandModel
>>> import wntr
>>>
>>> wn = wntr.network.WaterNetworkModel('network.inp')
>>> config = WNTRSimulatorConfig(
>>>     sim_time=7200,
>>>     hydraulic_timestep=3600,
>>>     demand_model=DemandModel.DD
>>> )
>>> simulator = WNTRSimulator(wn, simulator_config=config)
>>> results = simulator.run()

Notes
-----
- Simulators operate on deep copies by default (``inplace=False``).
- ``TimeLocation`` accepts an int, a ``(start, end)`` tuple, or a sequence of ints.
- Results are cached after the first run.
"""

from __future__ import annotations
from typing import TypeAlias
from collections.abc import Sequence
from dataclasses import dataclass, field
import os
import glob
import copy
import wntr
from hydroforge.auxiliary.logging_utils import get_logger
from .common import DemandModel, Simulator
from .results import WNTRSimulationResults

logger = get_logger(__name__)


# ----------------------------- Type Aliases -----------------------------
WNTRNetworkModel: TypeAlias = wntr.network.WaterNetworkModel
TimeLocation: TypeAlias = int | tuple[int, int] | Sequence[int]


@dataclass(slots=True)
class WNTRSimulatorConfig:
    """Configuration for simulation parameters of the WNTR simulator in WNTR.

    Parameters
    ----------
    sim_time : int, optional
        Duration of simulation in seconds (0 for steady-state).
    hydraulic_timestep : int, optional
        Time step for hydraulic calculations in seconds (default: 3600).
    demand_model : DemandModel, optional
        Demand model to use (``DemandModel.DD`` or ``DemandModel.PDD``).

    Examples
    --------
    >>> config = WNTRSimulatorConfig(
            sim_time = 7200,
            hydraulic_timestep=1800,
            demand_model=DemandModel.PDD)
    >>> config.apply_to(wn)
    """

    sim_time: int = 0
    hydraulic_timestep: int = 3_600
    demand_model: DemandModel = DemandModel.DD

    def apply_to(self, model: WNTRNetworkModel) -> None:
        """Apply configuration to a WNTR network model.

        Parameters
        ----------
        model : wntr.network.WaterNetworkModel
            Water network model to configure.
        """
        model.options.time.hydraulic_timestep = self.hydraulic_timestep
        model.options.time.duration = self.sim_time
        if hasattr(model.options, "hydraulic"):
            model.options.hydraulic.demand_model = self.demand_model.value


@dataclass(slots=True)
class EPANETSimulatorConfig:
    """Configuration for simulation parameters of the EPANET simulator in WNTR.

    Parameters
    ----------
    sim_time : int, optional
        Duration of simulation in seconds (0 for steady-state).
    hydraulic_timestep : int, optional
        Time step for hydraulic calculations in seconds (default: 3600).
    demand_model : DemandModel, optional
        Demand model to use (``DemandModel.DD`` or ``DemandModel.PDD``).
    file_prefix : str, optional
        Prefix to use for temporary EPANET files.
    cleanup_files : bool, optional
        Whether to remove temporary files after the run (default True).

    Notes
    -----
    - Temporary files created include: ``.inp``, ``.rpt``, ``.bin``, ``.hyd``, and ``.out``.
    - Pressure-driven demand (PDD) support may vary between EPANET builds.

    Examples
    --------
    >>> config = EPANETSimulatorConfig(
            sim_time = 7200,
            hydraulic_timestep=1800,
            demand_model=DemandModel.PDD)
    >>> config.apply_to(wn)
    """

    sim_time: int = 0
    hydraulic_timestep: int = 3_600
    demand_model: DemandModel = DemandModel.DD
    file_prefix: str = "temp"
    cleanup_files: bool = True

    def apply_to(self, model: WNTRNetworkModel) -> None:
        """Apply configuration to a WNTR network model.

        Parameters
        ----------
        model : wntr.network.WaterNetworkModel
            Water network model to configure.
        """
        model.options.time.hydraulic_timestep = self.hydraulic_timestep
        model.options.time.duration = self.sim_time
        if hasattr(model.options, "hydraulic"):
            model.options.hydraulic.demand_model = self.demand_model.value


# -------------------------- Concrete Simulators -------------------------
@dataclass(slots=True)
class WNTRSimulator(Simulator[WNTRNetworkModel, WNTRSimulationResults]):
    """WNTR simulator strategy with configurable options.

    Parameters
    ----------
    config : SimulationConfig, optional
        Configuration for simulation parameters.
    inplace : bool
        If True, the simulator modifies the provided model in place; otherwise
        it works on a deep copy. Default is True.
    """

    config: WNTRSimulatorConfig = field(default_factory=WNTRSimulatorConfig)
    inplace: bool = True

    def run(self, model: WNTRNetworkModel) -> WNTRSimulationResults:
        """Run the configured simulation and return the results.

        Parameters
        ----------
        model : wntr.network.WaterNetworkModel
            Network model to simulate.

        Returns
        -------
        WNTRSimulationResults
            Simulation results containing node and link time series.

        Notes
        -----
        - Uses a deep copy of the model unless ``inplace`` is True.
        - Applies the provided ``config`` to the model before running.
        - Runs the simulation using WNTR's built-in solver.
        """
        wn = model if self.inplace else copy.deepcopy(model)
        self.config.apply_to(wn)
        solver = wntr.sim.WNTRSimulator(wn)
        return WNTRSimulationResults(solver.run_sim())


@dataclass(slots=True)
class EPANETSimulator(Simulator[WNTRNetworkModel, WNTRSimulationResults]):
    """EPANET simulator strategy using the original EPANET C library.

    This simulator executes EPANET by writing temporary INP files and invoking the
    EPANET executable. It can be faster for large networks but requires an external
    EPANET installation.

    Parameters
    ----------
    model : wntr.network.WaterNetworkModel
        Network model to simulate.
    config : SimulationConfig, optional
        Simulation configuration to apply to the model.

    inplace : bool
        If True, the simulator modifies the provided model in place; otherwise
        it works on a deep copy. Default is False.

    Notes
    -----
    Temporary files created include: ``.inp``, ``.rpt``, ``.bin``, ``.hyd``, and
    ``.out``. Pressure-driven demand (PDD) support may vary between EPANET builds.
    """

    config: EPANETSimulatorConfig = field(default_factory=EPANETSimulatorConfig)
    inplace: bool = False

    def _create_solver(self, model: WNTRNetworkModel) -> wntr.sim.EpanetSimulator:
        """Create an EPANET solver instance for the given model.

        Parameters
        ----------
        model : wntr.network.WaterNetworkModel
            Network model to create the solver for.

        Returns
        -------
        wntr.sim.EpanetSimulator
            Configured EPANET simulator instance.
        """
        return wntr.sim.EpanetSimulator(model)

    def _cleanup_temp_files(self) -> None:
        """Remove temporary EPANET files created during simulation.

        Notes
        -----
        Attempts to remove files matching the configured ``file_prefix`` and
        ignores errors if files are not present or cannot be removed.
        """
        temp_patterns = [
            f"{self.config.file_prefix}.inp",
            f"{self.config.file_prefix}.rpt",
            f"{self.config.file_prefix}.bin",
            f"{self.config.file_prefix}.hyd",
            f"{self.config.file_prefix}.out",
        ]
        for pattern in temp_patterns:
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                except (OSError, FileNotFoundError):
                    # Ignore errors if file doesn't exist or can't be removed
                    pass

    def run(self, model: WNTRNetworkModel) -> WNTRSimulationResults:
        """Run the EPANET solver and return simulation results.

        Returns
        -------
        SimulationResults
            Results container with node and link time series data.

        Notes
        -----
        - The simulator uses a deep copy of the model unless ``inplace`` is True.
        - Temporary files are created using ``file_prefix`` and removed if
          ``cleanup_files`` is True.
        - Results are cached on the instance for later access.
        """
        # Always work on a copy to avoid modifying the original network
        wn = model if self.inplace else copy.deepcopy(model)
        self.config.apply_to(wn)
        if self.config.demand_model == DemandModel.PDD:
            logger.warning(
                "Warning: PDD mode may not be fully supported by this EPANET version"
            )
        solver: wntr.sim.EpanetSimulator = wntr.sim.EpanetSimulator(wn)
        # Use the file_prefix attribute
        results = WNTRSimulationResults(
            solver.run_sim(file_prefix=self.config.file_prefix)
        )
        # Clean up temporary files if requested
        if self.config.cleanup_files:
            self._cleanup_temp_files()
        return results


if __name__ == "__main__":
    pass
