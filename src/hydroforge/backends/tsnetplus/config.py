""" """
from typing import TypeAlias, Sequence, Literal
from dataclasses import dataclass
from ..common.constants import DemandModel


WaveSpeed: TypeAlias = float | Sequence[float]
FrictionModel: TypeAlias = Literal['steady', 'quasi-steady', 'unsteady']


@dataclass(slots=True)
class TSNetPlusConfig:
    """Configuration for the TSNet+ (also written as TSNetPlus) transient simulator.

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
        Initial time step in seconds. If ``None``, TSNet+ determines the
        maximum allowable time step. TSNet+ subsequently adjusts the time
        step and wave speeds during its discretization procedure.
    steady_state_engine : DemandModel, optional
        Hydraulic engine used by TSNet+ to calculate the steady-state initial
        condition. The default is demand-driven (``DemandModel.DD``).
    initial_time : float, optional
        Time at which the steady-state initial condition is calculated.
        Default is 0 seconds.
    results_name : str, optional
        Name used by TSNet+ when storing the transient results object.
        Default is ``"results"``.
    clean_files : bool, optional
        If ``True``, temporary EPANET files created during the simulation are 
        removed after the simulation completes. Default is ``True``.

    Notes
    -----
    TSNet+'s ``set_time`` method accepts both the simulation duration and
    time step. The time step may subsequently be modified by TSNet+ to
    satisfy its spatial and temporal discretization requirements.

    TSNet+ performs the steady-state initialization using WNTR before
    starting the transient MOC simulation.
    
    Currently, TSNet+'s config is an exact copy of TSNet's config, although
    in the future they might become different if both versions of the software
    diverge further.
    """
    duration: float
    wave_speed: WaveSpeed= 1_200.0
    friction_model: FrictionModel = 'steady'
    time_step: float | None = None
    steady_state_engine: DemandModel = DemandModel.DD
    initial_time: float = 0.0
    results_name: str | None = "tsnetplus_simulation_results.obj"
    clean_files: bool = True
    kernel: Literal["python", "numba"] = "python"

    def apply_to(self, model: object) -> None:
        """Apply model-level settings using the TSNetPlus model API."""
        model.set_wavespeed(self.wave_speed)
        model.set_time(self.duration, self.time_step)
