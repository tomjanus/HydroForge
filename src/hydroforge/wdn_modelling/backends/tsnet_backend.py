"""TSNet backend wrapper for HydroForge."""

from __future__ import annotations

import pathlib

from .common.backends import Backend
from .common.events import TransientEvent
from .tsnet import TSNetConfig, TSNetModel, TSNetSimulationResults, TSNetSimulator
from .tsnet.loader import load_tsnet_model


class TSNetBackend(
    Backend[TSNetModel, TSNetSimulationResults, TSNetConfig, TSNetConfig]
):
    """Concrete backend adapter for the TSNet transient solver."""

    package_name = "tsnet"

    def __init__(self) -> None:
        self.model: TSNetModel | None = None
        self.simulator: TSNetSimulator | None = None
        self._config: TSNetConfig | None = None

    def load_model(self, file: str | pathlib.Path) -> TSNetModel:
        self.model = load_tsnet_model(file)
        return self.model

    def get_config(self) -> TSNetConfig:
        if self._config is None:
            self._config = TSNetConfig(duration=0.0)
        return self._config

    def apply_config(self, config: TSNetConfig) -> None:
        self._config = config
        if self.model is not None:
            config.apply_to(self.model)
        if self.simulator is not None:
            self.simulator.configure(config)

    def add_event(self, event: TransientEvent[TSNetModel]) -> None:
        if self.model is None:
            raise ValueError("Load a TSNet model before adding an event.")
        event.apply_to(self.model)

    def create_simulator(self, config: TSNetConfig | None = None) -> TSNetSimulator:
        self.simulator = TSNetSimulator(
            config=config or self.get_config(), inplace=True
        )
        return self.simulator
