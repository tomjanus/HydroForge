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
from __future__ import annotations
import copy
import glob
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TypeAlias, Literal
import tsnet
from hydroforge.auxiliary.io_wrappers import save_pickle
from .common import DemandModel, Simulator
from .results import TSNetSimulationResults

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

TSNetNetworkModel: TypeAlias = tsnet.network.TransientModel
WaveSpeed: TypeAlias = float | Sequence[float]
FrictionModel: TypeAlias = Literal['steady', 'quasi-steady', 'unsteady']
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TSNetSimulatorConfig:
    """Configuration for the TSNet transient simulator.

    Parameters
    ----------
    duration : float
        Duration of the transient simulation in seconds.
    wave_speed : float or sequence of float
        Wave speed in metres per second. A scalar applies the same wave speed
        to all pipes. A sequence can be used to specify a wave speed for each
        pipe.
    friction_model : {'steady', 'quasi-steady', 'unsteady'}, optional
        Friction model used by TSNet to calculate friction losses during the
        transient simulation. Default is ``'steady'``.
    time_step : float or None, optional
        Initial time step in seconds. If ``None``, TSNet determines the
        maximum allowable time step. TSNet subsequently adjusts the time
        step and wave speeds during its discretization procedure.
    steady_state_engine : DemandModel, optional
        Hydraulic engine used by TSNet to calculate the steady-state initial
        condition. The default is demand-driven (``DemandModel.DD``).
    initial_time : float, optional
        Time at which the steady-state initial condition is calculated.
        Default is 0 seconds.
    results_name : str, optional
        Name used by TSNet when storing the transient results object.
        Default is ``"results"``.
    clean_files : bool, optional
        If ``True``, temporary EPANET files created during the simulation are 
        removed after the simulation completes. Default is ``True``.

    Notes
    -----
    TSNet's ``set_time`` method accepts both the simulation duration and
    time step. The time step may subsequently be modified by TSNet to
    satisfy its spatial and temporal discretization requirements.

    TSNet performs the steady-state initialization using WNTR before
    starting the transient MOC simulation.
    """
    duration: float
    wave_speed: WaveSpeed= 1_200.0
    friction_model: FrictionModel = 'steady'
    time_step: float | None = None
    steady_state_engine: DemandModel = DemandModel.DD
    initial_time: float = 0.0
    results_name: str | None = "tsnet_simulation_results.obj"
    clean_files: bool = True

# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TSNetSimulator(Simulator[TSNetNetworkModel, TSNetSimulationResults]):
    """TSNet transient hydraulic simulator.

    Parameters
    ----------
    config : TSNetSimulatorConfig, optional
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
    >>> simulator = TSNetSimulator(config=config)
    >>> results = simulator.run(model)
    """
    config: TSNetSimulatorConfig = field(
        default_factory=lambda: TSNetSimulatorConfig(
            duration=0.0,
        )
    )
    inplace: bool = True

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

    def run(self, model: TSNetNetworkModel) -> TSNetSimulationResults:
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
        tm.set_wavespeed(self.config.wave_speed)
        # Configure simulation duration and time step.
        tm.set_time(self.config.duration, self.config.time_step)
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


if __name__ == "__main__":
    pass
