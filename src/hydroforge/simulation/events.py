""" 
TransientEvent (ABC)
│
├── ValveClosureEvent
├── ValveOpeningEvent
├── PumpShutdownEvent
├── PumpStartupEvent
├── BurstEvent
└── DemandPulseEvent

for event in self.events:
    event.apply(model)

"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypeAlias
import tsnet


TransientModel: TypeAlias = tsnet.network.TransientModel


class TransientEvent(ABC):
    """Abstract base class for transient simulation events.

    Transient events modify a TSNet ``TransientModel`` before the
    transient simulation is executed.

    Notes
    -----
    Concrete subclasses should implement :meth:`apply` using the
    corresponding TSNet API.
    """
    @abstractmethod
    def apply_to(self, model: TransientModel) -> None:
        """apply_to the event to a transient model.

        Parameters
        ----------
        model : tsnet.network.TransientModel
            Transient model to modify.
        """

# ---------------------------------------------------------------------
# Valve closure and opening events
# ---------------------------------------------------------------------

@dataclass(slots=True)
class ValveClosureEvent(TransientEvent):
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
    curve: list[tuple[float, float]] = None

    def __post_init__(self):
        if self.valve is None or self.valve == "":
            raise ValueError("valve must be a non-empty string.")
        if not (0.0 <= self.final_opening <= 1.0):
            raise ValueError("final_opening must be between 0 and 1.")
        if self.duration <= 0:
            raise ValueError("duration must be positive.")
        if self.start_time < 0:
            raise ValueError("start_time must be non-negative.")
        if self.exponent <= 0:
            raise ValueError("exponent must be positive.")

    def apply_to(self, model: TransientModel) -> None:
        model.valve_closure(
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
class ValveOpeningEvent(TransientEvent):
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
    curve: list[tuple[float, float]] = None

    def apply_to(self, model: TransientModel) -> None:
        model.valve_opening(
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
class PumpShutdownEvent(TransientEvent):
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

    def apply_to(self, model: TransientModel) -> None:
        model.pump_shut_off(
            name = self.pump,
            rule = [
                self.duration,
                self.start_time,
                self.final_opening,
                self.exponent,
            ]
        )


@dataclass(slots=True)
class PumpStartupEvent(TransientEvent):
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

    def apply_to(self, model: TransientModel) -> None:
        model.pump_start_up(
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
class BurstEvent(TransientEvent):
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

    def apply_to(self, model: TransientModel) -> None:
        model.add_burst(
            name=self.node,
            ts = self.start_time,
            tc = self.burst_development_time,
            final_burst_coeff = self.final_burst_coeff
        )

# ---------------------------------------------------------------------
# Demand pulse
# ---------------------------------------------------------------------

@dataclass(slots=True)
class DemandPulseEvent(TransientEvent):
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
    
    def apply_to(self, model: TransientModel) -> None:
        model.add_demand_pulse(
            name=self.node,
            rule=[
                self.pulse_duration,
                self.start_time,
                self.duration_time,
                self.multiplier
            ]
        )