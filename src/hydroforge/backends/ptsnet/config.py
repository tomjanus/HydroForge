"""
Configuration for PTSNet simulations.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import PTSNetModel


@dataclass(slots=True)
class PTSNetConfig:
    """Configuration forwarded to ``PTSNetSimulation`` settings."""

    time_step: float = 0.01
    duration: float = 20.0
    warnings_on: bool = False
    parallel: bool = False
    gpu: bool = False
    skip_compatibility_check: bool = False
    show_progress: bool = False
    save_results: bool = True
    profiler_on: bool = False
    period: float = 0.0
    default_wave_speed: float = 1000.0
    wave_speed_file_path: str | None = None
    delimiter: str = ","
    wave_speed_method: str = "optimal"

    def _to_settings(self) -> dict[str, object]:
        """Return settings accepted by PTSNet's public constructor."""
        return {
            "time_step": self.time_step,
            "duration": self.duration,
            "warnings_on": self.warnings_on,
            "parallel": self.parallel,
            "gpu": self.gpu,
            "skip_compatibility_check": self.skip_compatibility_check,
            "show_progress": self.show_progress,
            "save_results": self.save_results,
            "profiler_on": self.profiler_on,
            "period": self.period,
            "default_wave_speed": self.default_wave_speed,
            "wave_speed_file_path": self.wave_speed_file_path,
            "delimiter": self.delimiter,
            "wave_speed_method": self.wave_speed_method,
        }

    def apply_to(self, model: PTSNetModel) -> None:
        """Apply settings to an existing PTSNet simulation model."""
        for name, value in self._to_settings().items():
            setattr(model.settings, name, value)
