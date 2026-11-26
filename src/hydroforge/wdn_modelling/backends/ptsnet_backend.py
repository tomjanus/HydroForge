"""PTSNet backend wrapper for HydroForge."""

from __future__ import annotations

import pathlib
from collections.abc import Mapping

from .common.backends import Backend
from .common.events import TransientEvent
from .ptsnet import PTSNetConfig, PTSNetModel, PTSNetSimulationResults, PTSNetSimulator
from .ptsnet.loader import load_ptsnet_model


class PTSNetBackend(
    Backend[PTSNetModel, PTSNetSimulationResults, PTSNetConfig, PTSNetConfig]
):
    """Concrete backend adapter for the PTSNet transient solver."""

    package_name = "ptsnet"

    def __init__(self) -> None:
        self.model: PTSNetModel | None = None
        self.simulator: PTSNetSimulator | None = None
        self._config: PTSNetConfig | None = None

    def load_model(
        self,
        file: str | pathlib.Path,
        *,
        settings: Mapping[str, object] | None = None,
        workspace_name: str | None = None,
    ) -> PTSNetModel:
        self.model = load_ptsnet_model(
            file,
            settings=settings,
            workspace_name=workspace_name,
        )
        return self.model

    def get_config(self) -> PTSNetConfig:
        if self._config is None:
            self._config = PTSNetConfig()
        return self._config

    def apply_config(self, config: PTSNetConfig) -> None:
        self._config = config
        if self.model is not None:
            config.apply_to(self.model)
        if self.simulator is not None:
            self.simulator.configure(config)

    def add_event(self, event: TransientEvent[PTSNetModel]) -> None:
        if self.model is None:
            raise ValueError("Load a PTSNet model before adding an event.")
        event.apply_to(self.model)

    def create_simulator(self, config: PTSNetConfig | None = None) -> PTSNetSimulator:
        self.simulator = PTSNetSimulator(config or self.get_config())
        return self.simulator
