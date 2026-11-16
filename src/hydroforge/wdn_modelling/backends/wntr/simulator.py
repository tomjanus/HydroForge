""" """

from dataclasses import dataclass, field
import copy
import glob
import os
import wntr
from .config import EPANETSimulatorConfig, WNTRSimulatorConfig
from .model import WNTRModel
from .results import WNTRSimulationResults
from ..common.simulator import Simulator
from ....auxiliary.logging_utils import get_logger

logger = get_logger(__name__)


# -------------------------- Concrete Simulators -------------------------
@dataclass(slots=True)
class WNTRSimulator(Simulator[WNTRModel, WNTRSimulationResults, WNTRSimulatorConfig]):
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

    def configure(self, config: WNTRSimulatorConfig) -> None:
        self.config = config

    def initialize(self) -> None:
        """Initialize the simulator before running a simulation.
        This method generally applies to dynamic simulators such as TSnet, or PTSNet"""
        pass

    def run(self, model: WNTRModel) -> WNTRSimulationResults:
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
        - Runs the simulation using WNTR's built-in solver.
        """
        wn = model if self.inplace else copy.deepcopy(model)
        solver = wntr.sim.WNTRSimulator(wn)
        return WNTRSimulationResults(solver.run_sim())


@dataclass(slots=True)
class EPANETSimulator(
    Simulator[WNTRModel, WNTRSimulationResults, EPANETSimulatorConfig]
):
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

    def _create_solver(self, model: WNTRModel) -> wntr.sim.EpanetSimulator:
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

    def configure(self, config: EPANETSimulatorConfig) -> None:
        self.config = config

    def initialize(self) -> None:
        """Initialize the simulator before running a simulation.
        This method generally applies to dynamic simulators such as TSnet, or PTSNet"""
        pass

    def run(self, model: WNTRModel) -> WNTRSimulationResults:
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
        if self.config.demand_model.value == "PDD":
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
