"""Transient events supported by PTSNet simulations."""

from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from ..common.events import (
    TransientEvent,
    validate_name,
    validate_non_negative,
    validate_opening,
    validate_positive,
)
from .model import PTSNetModel


@dataclass(slots=True)
class ValveClosureEvent(TransientEvent[PTSNetModel]):
    """Close a valve over a linear operation interval.

    Parameters
    ----------
    valve : str
        Valve name.
    duration : float
        Closure duration in seconds.
    start_time : float, default=0.0
        Closure start time in seconds.
    final_opening : float, default=0.0
        Final valve opening fraction.
    """

    valve: str
    duration: float
    start_time: float = 0.0
    final_opening: float = 0.0
    target_type: ClassVar[type[PTSNetModel]] = PTSNetModel

    def __post_init__(self) -> None:
        validate_name(self.valve, "valve")
        validate_positive(self.duration, "duration")
        validate_non_negative(self.start_time, "start_time")
        validate_opening(self.final_opening)

    def _apply_to(self, target: PTSNetModel) -> None:
        target.define_valve_operation(
            self.valve,
            1.0,
            self.final_opening,
            self.start_time,
            self.start_time + self.duration,
        )


@dataclass(slots=True)
class ValveOpeningEvent(TransientEvent[PTSNetModel]):
    """Open a valve over a linear operation interval.

    Parameters
    ----------
    valve : str
        Valve name.
    duration : float
        Opening duration in seconds.
    start_time : float, default=0.0
        Opening start time in seconds.
    final_opening : float, default=1.0
        Final valve opening fraction.
    """

    valve: str
    duration: float
    start_time: float = 0.0
    final_opening: float = 1.0
    target_type: ClassVar[type[PTSNetModel]] = PTSNetModel

    def __post_init__(self) -> None:
        validate_name(self.valve, "valve")
        validate_positive(self.duration, "duration")
        validate_non_negative(self.start_time, "start_time")
        validate_opening(self.final_opening)

    def _apply_to(self, target: PTSNetModel) -> None:
        target.define_valve_operation(
            self.valve,
            0.0,
            self.final_opening,
            self.start_time,
            self.start_time + self.duration,
        )


@dataclass(slots=True)
class PumpShutdownEvent(TransientEvent[PTSNetModel]):
    """Shut down a pump over a linear operation interval.

    Parameters
    ----------
    pump : str
        Pump name.
    duration : float
        Shutdown duration in seconds.
    start_time : float, default=0.0
        Shutdown start time in seconds.
    final_opening : float, default=0.0
        Final pump opening fraction.
    """

    pump: str
    duration: float
    start_time: float = 0.0
    final_opening: float = 0.0
    target_type: ClassVar[type[PTSNetModel]] = PTSNetModel

    def __post_init__(self) -> None:
        validate_name(self.pump, "pump")
        validate_positive(self.duration, "duration")
        validate_non_negative(self.start_time, "start_time")
        validate_opening(self.final_opening)

    def _apply_to(self, target: PTSNetModel) -> None:
        target.define_pump_operation(
            self.pump,
            1.0,
            self.final_opening,
            self.start_time,
            self.start_time + self.duration,
        )


@dataclass(slots=True)
class PumpStartupEvent(TransientEvent[PTSNetModel]):
    """Start a pump over a linear operation interval.

    Parameters
    ----------
    pump : str
        Pump name.
    duration : float
        Startup duration in seconds.
    start_time : float, default=0.0
        Startup start time in seconds.
    final_opening : float, default=1.0
        Final pump opening fraction.
    """

    pump: str
    duration: float
    start_time: float = 0.0
    final_opening: float = 1.0
    target_type: ClassVar[type[PTSNetModel]] = PTSNetModel

    def __post_init__(self) -> None:
        validate_name(self.pump, "pump")
        validate_positive(self.duration, "duration")
        validate_non_negative(self.start_time, "start_time")
        validate_opening(self.final_opening)

    def _apply_to(self, target: PTSNetModel) -> None:
        target.define_pump_operation(
            self.pump,
            0.0,
            self.final_opening,
            self.start_time,
            self.start_time + self.duration,
        )


@dataclass(slots=True)
class BurstEvent(TransientEvent[PTSNetModel]):
    """Develop a burst linearly at a node.

    Parameters
    ----------
    node : str
        Node at which the burst occurs.
    start_time : float
        Burst start time in seconds.
    burst_development_time : float
        Time until the burst reaches its final coefficient in seconds.
    final_burst_coeff : float
        Final burst coefficient.
    """

    node: str
    start_time: float
    burst_development_time: float
    final_burst_coeff: float
    target_type: ClassVar[type[PTSNetModel]] = PTSNetModel

    def __post_init__(self) -> None:
        validate_name(self.node, "node")
        validate_non_negative(self.start_time, "start_time")
        validate_positive(self.burst_development_time, "burst_development_time")
        validate_non_negative(self.final_burst_coeff, "final_burst_coeff")

    def _apply_to(self, target: PTSNetModel) -> None:
        target.add_burst(
            self.node,
            self.final_burst_coeff,
            self.start_time,
            self.start_time + self.burst_development_time,
        )


@dataclass(slots=True)
class DemandPulseEvent(TransientEvent[PTSNetModel]):
    """Apply a rectangular demand multiplier pulse at a node.

    Parameters
    ----------
    node : str
        Junction name.
    pulse_duration : float
        Time to ramp to the pulse multiplier in seconds.
    start_time : float
        Pulse start time in seconds.
    duration_time : float
        Time the pulse remains active in seconds.
    multiplier : float, default=1.0
        Demand multiplier while the pulse is active.
    """

    node: str
    pulse_duration: float
    start_time: float
    duration_time: float
    multiplier: float = 1.0
    target_type: ClassVar[type[PTSNetModel]] = PTSNetModel

    def __post_init__(self) -> None:
        validate_name(self.node, "node")
        validate_positive(self.pulse_duration, "pulse_duration")
        validate_non_negative(self.start_time, "start_time")
        validate_positive(self.duration_time, "duration_time")
        validate_non_negative(self.multiplier, "multiplier")

    def _apply_to(self, target: PTSNetModel) -> None:
        ramp_end = self.start_time + self.pulse_duration
        pulse_end = ramp_end + self.duration_time
        target.define_demand_settings(
            self.node,
            np.array([self.start_time, ramp_end, pulse_end]),
            np.array([1.0, self.multiplier, 1.0]),
        )


__all__ = [
    "BurstEvent",
    "DemandPulseEvent",
    "PumpShutdownEvent",
    "PumpStartupEvent",
    "ValveClosureEvent",
    "ValveOpeningEvent",
]
