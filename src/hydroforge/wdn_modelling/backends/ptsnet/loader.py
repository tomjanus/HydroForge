""" """

from __future__ import annotations

import pathlib
from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ptsnet.simulation.sim import PTSNETSimulation


def load_ptsnet_model(
    model: str | pathlib.Path,
    settings: Mapping[str, object] | None = None,
    workspace_name: str | None = None,
) -> PTSNETSimulation:
    """Load an INP model, with optional constructor settings and workspace name."""
    model = pathlib.Path(model)
    if not model.is_file():
        raise FileNotFoundError(f"PTSNet model file not found: {model}")
    from ptsnet.simulation.sim import PTSNETSimulation

    kwargs = {}
    if settings is not None:
        if not isinstance(settings, Mapping):
            raise TypeError("PTSNet settings must be a mapping")
        kwargs["settings"] = dict(settings)
    loaded = PTSNETSimulation(
        workspace_name=workspace_name or model.stem,
        inpfile=str(model),
        **kwargs,
    )
    if settings is not None:
        loaded._hydroforge_config_settings = dict(settings)
    return loaded
