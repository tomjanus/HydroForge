"""TSNetPlus transient events.

The event implementations inherit TSNet's validation and solver calls while
substituting the TSNetPlus transient-model target type.
"""

from typing import ClassVar

from ..tsnet import events as _tsnet_events
from .model import TSNetPlusModel


class ValveClosureEvent(_tsnet_events.ValveClosureEvent):
    """TSNetPlus valve closure event."""

    target_type: ClassVar[type[TSNetPlusModel]] = TSNetPlusModel


class ValveOpeningEvent(_tsnet_events.ValveOpeningEvent):
    """TSNetPlus valve opening event."""

    target_type: ClassVar[type[TSNetPlusModel]] = TSNetPlusModel


class PumpShutdownEvent(_tsnet_events.PumpShutdownEvent):
    """TSNetPlus pump shutdown event."""

    target_type: ClassVar[type[TSNetPlusModel]] = TSNetPlusModel


class PumpStartupEvent(_tsnet_events.PumpStartupEvent):
    """TSNetPlus pump startup event."""

    target_type: ClassVar[type[TSNetPlusModel]] = TSNetPlusModel


class BurstEvent(_tsnet_events.BurstEvent):
    """TSNetPlus burst event."""

    target_type: ClassVar[type[TSNetPlusModel]] = TSNetPlusModel


class DemandPulseEvent(_tsnet_events.DemandPulseEvent):
    """TSNetPlus demand pulse event."""

    target_type: ClassVar[type[TSNetPlusModel]] = TSNetPlusModel


__all__ = [
    "BurstEvent",
    "DemandPulseEvent",
    "PumpShutdownEvent",
    "PumpStartupEvent",
    "ValveClosureEvent",
    "ValveOpeningEvent",
]
