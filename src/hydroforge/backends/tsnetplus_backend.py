"""TSNetPlus backend wrapper for HydroForge."""
from __future__ import annotations

import pathlib

from .common.backends import Backend
from .common.events import TransientEvent
from .tsnetplus import (
    TSNetPlusConfig,
    TSNetPlusModel,
    TSNetPlusSimulationResults,
    TSNetSPlusSimulator
)
from .tsnetplus.loader import load_tsnetplus_model


class TSNetPlusBackend(
    Backend[
        TSNetPlusModel,
        TSNetPlusSimulationResults,
        TSNetPlusConfig,
        TSNetPlusConfig,
    ]
):
    """Concrete backend adapter for the TSNetPlus transient solver."""
    package_name = "tsnetplus"

    def __init__(self) -> None:
        self.model: TSNetPlusModel | None = None
        self.simulator: TSNetSPlusSimulator | None = None
        self._config: TSNetPlusConfig | None = None

    def load_model(self, file: str | pathlib.Path) -> TSNetPlusModel:
        self.model = load_tsnetplus_model(file)
        return self.model

    def get_config(self) -> TSNetPlusConfig:
        if self._config is None:
            self._config = TSNetPlusConfig(duration=0.0)
        return self._config

    def apply_config(self, config: TSNetPlusConfig) -> None:
        self._config = config
        if self.model is not None:
            config.apply_to(self.model)
        if self.simulator is not None:
            self.simulator.configure(config)

    def add_event(self, event: TransientEvent[TSNetPlusModel]) -> None:
        if self.model is None:
            raise ValueError("Load a TSNetPlus model before adding an event.")
        event.apply_to(self.model)

    def create_simulator(
        self, config: TSNetPlusConfig | None = None
    ) -> TSNetSPlusSimulator:
        self.simulator = TSNetSPlusSimulator(
            config=config or self.get_config(), inplace=True
        )
        return self.simulator
