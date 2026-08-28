"""TSNet transient hydraulic simulation strategy.

This module provides a simulator strategy for running transient hydraulic
simulations using TSNet.

The simulator follows the common :class:`Simulator` interface used by the
other HydroForge simulation backends while exposing TSNet-specific
configuration through :class:`TSNetSimulatorConfig`.

TSNet simulations consist of two stages:

1. A steady-state initialization using TSNet's ``Initializer``.
2. A transient simulation using TSNet's Method of Characteristics (MOC)
   solver.

Notes
-----
TSNet's ``TransientModel`` is a subclass of WNTR's ``WaterNetworkModel``,
but contains additional state required for transient simulation. A
``TransientModel`` should therefore be supplied to :class:`TSNetSimulator`,
rather than an ordinary WNTR network model.
"""
import glob
import os
import copy
from dataclasses import dataclass, field
import tsnet
from .config import TSNetSimulatorConfig
from .model import TSNetModel
from .results import TSNetSimulationResults
from ..common.simulator import Simulator
from ...auxiliary.io import save_pickle


@dataclass(slots=True)
class TSNetSimulator(Simulator[TSNetModel, TSNetSimulationResults, TSNetSimulatorConfig]):
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
    >>> from hydroforge.simulation import load_tsnet_model, DemandModel
    >>> 
    >>> model = load_tsnet_model("network.inp")
    >>> config = TSNetSimulatorConfig(
    ...     wave_speed=1200.0,
    ...     duration=20.0,
    ...     time_step=0.1,
    ... )
    >>> simulator = TSNetPlusSimulator(config=config)
    >>> results = simulator.run(model)
    """
    config: TSNetSimulatorConfig = field(
        default_factory=lambda: TSNetSimulatorConfig(
            duration=0.0,
        )
    )
    inplace: bool = True

    def configure(self, config: TSNetSimulatorConfig) -> None:
        self.config = config

    def _cleanup_temp_files(self) -> None:
        """Remove temporary EPANET files created during simulation.

        Notes
        -----
        Attempts to remove files matching the configured ``file_prefix`` and
        ignores errors if files are not present or cannot be removed.
        """
        default_filename = 'temp'
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

    def run(self, model: TSNetModel) -> TSNetSimulationResults:
        """Run the TSNet transient simulation.

        Parameters
        ----------
        model : tsnet.network.TransientModel
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
        tm = tsnet.simulation.Initializer(
            tm,
            self.config.initial_time,
            self.config.steady_state_engine.value,
        )
        if self.config.clean_files:
            self._cleanup_temp_files()
        # Run the transient Method of Characteristics simulation.
        tm = tsnet.simulation.MOCSimulator(
            tm,
            results_obj = 'no',
            friction=self.config.friction_model
        )
        _results = TSNetSimulationResults(tm)
        if self.config.results_name is not None:
            save_pickle(_results, self.config.results_name)
        return _results