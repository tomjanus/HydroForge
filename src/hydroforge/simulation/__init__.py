"""Public API for HydroForge simulation backends."""

from .common import DemandModel, load_tsnet_model, load_wntr_model
from .wntr_simulator import (
	EPANETSimulator,
	EPANETSimulatorConfig,
	WNTRSimulatorConfig,
	WNTRSimulator,
)
from .tsnet_simulator import TSNetSimulator, TSNetSimulatorConfig


# Backward-compatible alias for earlier docs/examples.
WNTRSimulationConfig = WNTRSimulatorConfig


__all__ = [
	"DemandModel",
	"load_wntr_model",
	"load_tsnet_model",
	"WNTRSimulatorConfig",
	"WNTRSimulationConfig",
	"EPANETSimulatorConfig",
	"WNTRSimulator",
	"EPANETSimulator",
	"TSNetSimulatorConfig",
	"TSNetSimulator",
]
    