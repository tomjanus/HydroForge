"""TSNetPlus transient hydraulic simulation strategy.

This module provides a simulator strategy for running transient hydraulic
simulations using TSNetPlus.

The simulator follows the common :class:`Simulator` interface used by the
other HydroForge simulation backends while exposing TSNet+-specific
configuration through :class:`TSNetSimulatorConfig`.

TSNet+ simulations consist of two stages:

1. A steady-state initialization using TSNet+'s ``Initializer``.
2. A transient simulation using TSNet+'s Method of Characteristics (MOC)
   solver.
"""

import glob
import os
import copy
from dataclasses import dataclass, field
import tsnetplus
from .config import TSNetPlusConfig
from .model import TSNetPlusModel
from .results import TSNetPlusSimulationResults
from ..common.simulator import Simulator
from ....auxiliary.io import save_pickle


@dataclass(slots=True)
class TSNetSPlusSimulator(
    Simulator[TSNetPlusModel, TSNetPlusSimulationResults, TSNetPlusConfig]
):
    """TSNet transient hydraulic simulator.

    Parameters
    ----------
    config : TSNetSimulationConfig, optional
        Configuration for the transient simulation.
    inplace : bool, optional
        If ``True``, the supplied TSNet model is modified directly.
        If ``False``, a deep copy of the model is simulated and the original
        model is left unchanged. Default is ``True``.

    Notes
    -----
    TSNet modifies the ``TransientModel`` during simulation. In particular,
    wave speed, temporal discretization, initial conditions, and transient
    results are stored on the model. The ``inplace`` option therefore
    determines whether those modifications are applied to the caller's
    model.

    Examples
    --------
    >>> from hydroforge.backends import get_backend
    >>> from hydroforge.backends.tsnetplus.config import TSNetPlusConfig
    >>>
    >>> backend = get_backend("tsnetplus")
    >>> model = backend.load_model("network.inp")
    >>> config = TSNetPlusConfig(
    ...     wave_speed=1200.0,
    ...     duration=20.0,
    ...     time_step=0.1,
    ... )
    >>> simulator = backend.create_simulator(config)
    >>> results = simulator.run(model)
    """

    config: TSNetPlusConfig = field(
        default_factory=lambda: TSNetPlusConfig(
            duration=0.0,
        )
    )
    inplace: bool = True

    def configure(self, config: TSNetPlusConfig) -> None:
        self.config = config

    def _cleanup_temp_files(self) -> None:
        """Remove temporary EPANET files created during simulation.

        Notes
        -----
        Attempts to remove files matching the configured ``file_prefix`` and
        ignores errors if files are not present or cannot be removed.
        """
        default_filename = "temp"
        temp_patterns = [
            f"{default_filename}.inp",
            f"{default_filename}.rpt",
            f"{default_filename}.bin",
            f"{default_filename}.hyd",
            f"{default_filename}.out",
        ]
        for pattern in temp_patterns:
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                except (OSError, FileNotFoundError):
                    # Ignore errors if file doesn't exist or can't be removed
                    pass

    def initialize(self) -> None:
        """Initialize the simulator before running a simulation.
        This method generally applies to dynamic simulators such as TSnet, or PTSNet"""
        pass

    def run(self, model: TSNetPlusModel) -> TSNetPlusSimulationResults:
        """Run the TSNet transient simulation.

        Parameters
        ----------
        model : tsnetplus.network.TransientModel
            TSNet transient network model to simulate.

        Returns
        -------
        TSNetSimulationResults
            Wrapper around the transient results stored in the TSNet model.

        Notes
        -----
        The simulation proceeds in two stages:

        1. TSNet's ``Initializer`` calculates the steady-state initial
           condition using the configured hydraulic engine.
        2. TSNet's ``MOCSimulator`` performs the transient simulation using
           the Method of Characteristics.

        The model is deep-copied when ``inplace=False``.
        """
        tm = model if self.inplace else copy.deepcopy(model)
        # Configure transient wave speed.
        self.config.apply_to(tm)
        # Calculate the steady-state initial condition.
        tm = tsnetplus.simulation.initialize(
            tm,
            self.config.initial_time,
            self.config.steady_state_engine.value,
        )
        if self.config.clean_files:
            self._cleanup_temp_files()
        # Run the transient Method of Characteristics simulation.
        tm = tsnetplus.simulation.MOCSimulator(
            tm, results_obj="no", friction=self.config.friction_model
        )
        _results = TSNetPlusSimulationResults(tm)
        if self.config.results_name is not None:
            save_pickle(_results, self.config.results_name)
        return _results
