""" """

import math
from dataclasses import dataclass
from .model import PTSNetNetworkModel
from .results import PTSNetSimulationResults
from .config import PTSNetConfig
from ..common.simulator import Simulator


@dataclass(slots=True)
class PTSNetSimulator(
    Simulator[PTSNetNetworkModel, PTSNetSimulationResults, PTSNetConfig]
):
    """PTSNet simulator strategy."""

    def __init__(self, config: PTSNetConfig | None = None) -> None:
        self.config = config or PTSNetConfig()

    def configure(self, config: PTSNetConfig) -> None:
        self.config = config

    def initialize(self) -> None:
        """Initialize the simulator before running a simulation.
        This method generally applies to dynamic simulators such as TSnet, or PTSNet"""
        pass

    def run(self, model: PTSNetNetworkModel) -> PTSNetSimulationResults:
        settings = getattr(model, "settings", None)
        settings_are_fixed = settings is not None and (
            getattr(settings, "is_initialized", False)
            or getattr(settings, "defined_wave_speeds", False)
        )
        if not settings_are_fixed:
            self.config.apply_to(model)
        else:
            if settings is None:
                raise RuntimeError("PTSNet model is missing simulation settings")
            requested_settings = self.config._to_settings()
            preconfigured_settings = getattr(model, "_hydroforge_config_settings", None)
            if preconfigured_settings is not None:
                changed = [
                    name
                    for name, value in requested_settings.items()
                    if preconfigured_settings.get(name) != value
                ]
            else:
                actual_settings = settings.to_dict(simplified=True)
                changed = [
                    name
                    for name, value in requested_settings.items()
                    if name in actual_settings
                    and name not in {"parallel", "gpu", "time_step"}
                    and not (
                        name == "default_wave_speed"
                        and getattr(model, "_hydroforge_wave_speed_overridden", False)
                    )
                    and actual_settings[name] != value
                ]
                actual_time_step = actual_settings.get("time_step")
                requested_time_step = requested_settings.get("time_step")
                if actual_time_step is not None and requested_time_step is not None:
                    if isinstance(actual_time_step, (int, float)) and isinstance(
                        requested_time_step, (int, float)
                    ):
                        timestep_matches = math.isclose(
                            actual_time_step,
                            requested_time_step,
                            rel_tol=1e-2,
                        )
                    else:
                        timestep_matches = actual_time_step == requested_time_step
                    if not timestep_matches:
                        changed.append("time_step")
            if changed:
                raise ValueError(
                    "PTSNet configuration must be supplied before model "
                    "initialization; differing settings: " + ", ".join(sorted(changed))
                )
        model.run()
        return PTSNetSimulationResults(model)
