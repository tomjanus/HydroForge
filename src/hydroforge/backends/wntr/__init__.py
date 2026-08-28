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
>>> from hydroforge.backends.wntr import WNTRSimulator, WNTRSimulatorConfig, WNTRNetworkModel
>>> from hydroforge.backends.common import DemandModel
>>> import wntr
>>>
>>> wn = WNTRNetworkModel('network.inp')
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
from .model import WNTRModel
from .results import WNTRSimulationResults
from .simulator import WNTRSimulator, EPANETSimulator
from .config import EPANETSimulatorConfig, WNTRConfig, WNTRSimulatorConfig
from .loader import load_wntr_model


__all__ = [
    "WNTRModel",
    "WNTRSimulationResults",
    "WNTRSimulator",
    "EPANETSimulator",
    "WNTRConfig",
    "WNTRSimulatorConfig",
    "EPANETSimulatorConfig",
    "load_wntr_model",
]
