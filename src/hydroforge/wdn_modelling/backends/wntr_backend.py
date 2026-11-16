"""WNTR backend wrapper for HydroForge."""

from __future__ import annotations

import pathlib
from typing import Literal

from .common.backends import Backend
from .common.events import TransientEvent
from ..auxiliary.logging_utils import get_logger
from .wntr import (
    EPANETSimulatorConfig,
    WNTRConfig,
    WNTRModel,
    WNTRSimulationResults,
    WNTRSimulatorConfig,
)
from .wntr.config import WNTRConfig as WNTRSimulationConfig
from .wntr.loader import load_wntr_model
from .wntr.simulator import EPANETSimulator, WNTRSimulator

WNTRRunConfig = WNTRSimulatorConfig | EPANETSimulatorConfig


class WNTRBackend(Backend[WNTRModel, WNTRSimulationResults, WNTRConfig, WNTRRunConfig]):
    """Concrete backend adapter for the WNTR hydraulic solver."""

    package_name = "wntr"

    def __init__(self, simulator: Literal["wntr", "epanet"] = "wntr") -> None:
        self.model: WNTRModel | None = None
        self.simulator: WNTRSimulator | EPANETSimulator | None = None
        self._simulator_type = simulator

    def load_model(self, file: str | pathlib.Path) -> WNTRModel:
        self.model = load_wntr_model(file)
        return self.model

    def get_config(self) -> WNTRConfig:
        if self.model is None:
            return WNTRSimulationConfig()
        return WNTRConfig.from_options(self.model.options)

    def apply_config(self, config: WNTRConfig) -> None:
        if self.model is None:
            raise ValueError("No model has been loaded for the WNTR backend.")
        config.apply_to(self.model.options)

    def add_event(self, event: TransientEvent[WNTRModel]) -> None:
        get_logger(__name__).info(
            "WNTR does not support transient events; ignoring %s.", type(event).__name__
        )

    def create_simulator(
        self, config: WNTRRunConfig | None = None
    ) -> WNTRSimulator | EPANETSimulator:
        if self._simulator_type == "epanet":
            if config is not None and not isinstance(config, EPANETSimulatorConfig):
                raise TypeError("EPANETSimulator requires EPANETSimulatorConfig.")
            self.simulator = EPANETSimulator(
                config=config or EPANETSimulatorConfig(), inplace=True
            )
            return self.simulator
        if self._simulator_type == "wntr":
            if config is not None and not isinstance(config, WNTRSimulatorConfig):
                raise TypeError("WNTRSimulator requires WNTRSimulatorConfig.")
            self.simulator = WNTRSimulator(
                config=config or WNTRSimulatorConfig(), inplace=True
            )
            return self.simulator
        raise ValueError(
            f"Invalid simulator type: {self._simulator_type}. Must be 'wntr' or 'epanet'."
        )
