""" 
Transient events for the TSNet backend.

TransientEvent (ABC)
│
├── ValveClosureEvent
├── ValveOpeningEvent
├── PumpShutdownEvent
├── PumpStartupEvent
├── BurstEvent
└── DemandPulseEvent


Example
-------
for event in self.events:
    event.apply_to(target)
"""
from dataclasses import dataclass
from typing import ClassVar, Sequence
from .model import TSNetModel
from ..common.events import (
    TransientEvent,
    validate_curve,
    validate_name,
    validate_non_negative,
    validate_opening,
    validate_positive,
)


# ---------------------------------------------------------------------
# Valve closure and opening events
# ---------------------------------------------------------------------

@dataclass(slots=True)
class ValveClosureEvent(TransientEvent[TSNetModel]):
    """Valve closure transient event.

    Parameters
    ----------
    valve : str
        Valve name.
    duration : float
        Opening duration (s).
    start_time : float, default=0.0
        Time when valve closure begins.
    final_opening : float, default=1.0
        Final valve opening ratio (0-1).
    exponent : float, default=1.0
        Valve closing constant (unitless).
    curve : list | None, default=None
        List of tuples representing the valve closure curve, where each tuple
        contains the open percentage and the corresponding 1/kl value.
    """
    valve: str
    duration: float
    start_time: float = 0.0
    final_opening: float = 0.0
    exponent: float = 1.0
    curve: Sequence[tuple[float, float]] | None = None
    target_type: ClassVar[type[TSNetModel]] = TSNetModel

    def __post_init__(self) -> None:
        self._validate_inputs()
        
    def _validate_inputs(self) -> None:
        validate_name(self.valve, "valve")
        validate_positive(self.duration, "duration")
        validate_non_negative(self.start_time, "start_time")
        validate_opening(self.final_opening)
        validate_positive(self.exponent, "exponent")
        validate_curve(self.curve)

    def _apply_to(self, target: TSNetModel) -> None:
        target.valve_closure(
            name=self.valve,
            rule=[
                self.duration,
                self.start_time,
                self.final_opening,
                self.exponent,
            ],
            curve=self.curve
        )


@dataclass(slots=True)
class ValveOpeningEvent(TransientEvent[TSNetModel]):
    """Valve opening transient event.

    Parameters
    ----------
    valve : str
        Valve name.
    duration : float
        Opening duration (s).
    start_time : float, default=0.0
        Time when valve opening begins.
    final_opening : float, default=1.0
        Final valve opening ratio (0-1).
    exponent : float, default=1.0
        Valve closing constant (unitless).
    curve : list | None, default=None
        List of tuples representing the valve closure curve, where each tuple
        contains the open percentage and the corresponding 1/kl value.
    """
    valve: str
    duration: float
    start_time: float = 0.0
    final_opening: float = 1.0
    exponent: float = 1.0
    curve: Sequence[tuple[float, float]] | None = None
    target_type: ClassVar[type[TSNetModel]] = TSNetModel

    def __post_init__(self) -> None:
        validate_name(self.valve, "valve")
        validate_positive(self.duration, "duration")
        validate_non_negative(self.start_time, "start_time")
        validate_opening(self.final_opening)
        validate_positive(self.exponent, "exponent")
        validate_curve(self.curve)

    def _apply_to(self, target: TSNetModel) -> None:
        target.valve_opening(
            name=self.valve,
            rule=[
                self.duration,
                self.start_time,
                self.final_opening,
                self.exponent,
            ],
            curve=self.curve
        )

# ---------------------------------------------------------------------
# Pump shutdown and startup events
# ---------------------------------------------------------------------

@dataclass(slots=True)
class PumpShutdownEvent(TransientEvent[TSNetModel]):
    """Pump shutdown event.

    Parameters
    ----------
    pump : str
        Pump name.
    duration : float
        Duration of time it takes to shut down the pump (s).
    start_time : float, default=0.0
        Shutdown start time.
    final_opening : float, default=0.0
        Final opening fraction (0-1).
    exponent : float, default=1.0
        Shutdown constant (unitless).
    """
    pump: str
    duration: float
    start_time: float = 0.0
    final_opening: float = 0.0
    exponent: float = 1.0
    target_type: ClassVar[type[TSNetModel]] = TSNetModel

    def __post_init__(self) -> None:
        validate_name(self.pump, "pump")
        validate_positive(self.duration, "duration")
        validate_non_negative(self.start_time, "start_time")
        validate_opening(self.final_opening)
        validate_positive(self.exponent, "exponent")

    def _apply_to(self, target: TSNetModel) -> None:
        target.pump_shut_off(
            name = self.pump,
            rule = [
                self.duration,
                self.start_time,
                self.final_opening,
                self.exponent,
            ]
        )


@dataclass(slots=True)
class PumpStartupEvent(TransientEvent[TSNetModel]):
    """Pump startup event.

    Parameters
    ----------
    pump : str
        Pump name.
    duration : float
        Startup duration (s).
    start_time : float, default=0.0
        Startup time.
    final_opening : float, default=1.0
        Final opening fraction (0-1).
    exponent : float, default=1.0
        Startup constant (unitless).
    """
    pump: str
    duration: float
    start_time: float = 0.0
    final_opening: float = 1.0
    exponent: float = 1.0
    target_type: ClassVar[type[TSNetModel]] = TSNetModel

    def __post_init__(self) -> None:
        validate_name(self.pump, "pump")
        validate_positive(self.duration, "duration")
        validate_non_negative(self.start_time, "start_time")
        validate_opening(self.final_opening)
        validate_positive(self.exponent, "exponent")

    def _apply_to(self, target: TSNetModel) -> None:
        target.pump_start_up(
            name=self.pump,
            rule = [
                self.duration,
                self.start_time,
                self.final_opening,
                self.exponent,
            ]
        )

# ---------------------------------------------------------------------
# Burst event
# ---------------------------------------------------------------------

@dataclass(slots=True)
class BurstEvent(TransientEvent[TSNetModel]):
    """Burst event.

    Parameters
    ----------
    node : str
        Burst node.
    start_time : float
        Burst start time (s).
    burst_development_time : float
        Time for burst to fully develop (s).
    final_burst_coeff : float
        Final emitter coefficient at the burst node (m^3/s/Pa^0.5).
    """
    node: str
    start_time: float
    burst_development_time: float
    final_burst_coeff: float
    target_type: ClassVar[type[TSNetModel]] = TSNetModel

    def __post_init__(self) -> None:
        validate_name(self.node, "node")
        validate_non_negative(self.start_time, "start_time")
        validate_positive(self.burst_development_time, "burst_development_time")
        validate_non_negative(self.final_burst_coeff, "final_burst_coeff")

    def _apply_to(self, target: TSNetModel) -> None:
        target.add_burst(
            name=self.node,
            ts = self.start_time,
            tc = self.burst_development_time,
            final_burst_coeff = self.final_burst_coeff
        )

# ---------------------------------------------------------------------
# Demand pulse
# ---------------------------------------------------------------------

@dataclass(slots=True)
class DemandPulseEvent(TransientEvent[TSNetModel]):
    """Demand pulse event.

    Parameters
    ----------
    node : str
        Junction name.
    pulse_duration : float
        Pulse duration (s).
    start_time : float
        Pulse start time (s).
    duration_time : float
        Pulse duration time (s).
    multiplier : float, default=1.0
        Multiplier for the base demand at the junction.
    """
    node: str
    pulse_duration: float
    start_time: float
    duration_time: float
    multiplier: float = 1.0
    target_type: ClassVar[type[TSNetModel]] = TSNetModel

    def __post_init__(self) -> None:
        validate_name(self.node, "node")
        validate_positive(self.pulse_duration, "pulse_duration")
        validate_non_negative(self.start_time, "start_time")
        validate_positive(self.duration_time, "duration_time")
        validate_non_negative(self.multiplier, "multiplier")
    
    def _apply_to(self, target: TSNetModel) -> None:
        target.add_demand_pulse(
            name=self.node,
            rule=[
                self.pulse_duration,
                self.start_time,
                self.duration_time,
                self.multiplier
            ]
        )
