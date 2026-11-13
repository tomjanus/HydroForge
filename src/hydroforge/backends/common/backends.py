"""Core interfaces for HydroForge simulation backends.

The :mod:`hydroforge.backends` package defines the core interfaces and
utilities for HydroForge simulation backends. A backend provides access to a
hydraulic modelling package and knows how to construct models and HydroForge
simulators using that package. The package currently supports backends based
on WNTR, TSNet, TSNetPlus, and PTSNet.
The :class:`Backend` interface defines the methods that a backend must implement,
including loading models and creating simulators. The :class:`BackendName`
enumeration provides a list of supported backend names.
"""

from __future__ import annotations
import pathlib
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from .events import TransientEvent
    from .simulator import Simulator


ModelT = TypeVar("ModelT")
ResultT = TypeVar("ResultT")
ModelConfigT = TypeVar("ModelConfigT")
SimulatorConfigT = TypeVar("SimulatorConfigT")


@runtime_checkable
class Backend(Protocol[ModelT, ResultT, ModelConfigT, SimulatorConfigT]):
    """Interface implemented by HydroForge simulation backends.

    A backend provides access to a hydraulic modelling package and knows
    how to construct models and HydroForge simulators using that package.
    """

    package_name: str
    model: ModelT | None
    simulator: Simulator[ModelT, ResultT, SimulatorConfigT] | None

    def load_model(self, file: str | pathlib.Path) -> ModelT:
        """Load a hydraulic model from an EPANET input file."""

    def get_config(self) -> ModelConfigT:
        """Return a configuration representing the loaded model options."""

    def apply_config(self, config: ModelConfigT) -> None:
        """Apply a persistent configuration to the loaded model."""

    def add_event(self, event: TransientEvent[...]) -> None:
        """Apply event to the simulator or to the model"""

    def create_simulator(
        self, config: SimulatorConfigT | None = None
    ) -> Simulator[ModelT, ResultT, SimulatorConfigT]:
        """Create a simulator using its runtime-only configuration."""
