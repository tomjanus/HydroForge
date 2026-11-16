""" """

import pathlib
from ptsnet.simulation.sim import PTSNETSimulation


def load_ptsnet_model(
    model: str | pathlib.Path,
) -> PTSNETSimulation:
    """Load a PTSNet transient model from an INP file.

    Parameters
    ----------
    model
        Path to the EPANET ``.inp`` input file used to construct
        the PTSNet transient model.

    Returns
    -------
    ptsnet.simulation.sim.PTSNETSimulation
        Initialized PTSNet transient model.

    Raises
    ------
    FileNotFoundError
        If the specified model file does not exist.
    OSError
        If the model file cannot be accessed.
    ValueError
        If the model file contains invalid network data.
    """
    model = pathlib.Path(model)
    if not model.is_file():
        raise FileNotFoundError(f"PTSNet model file not found: {model}")
    return PTSNETSimulation(
        workspace_name=model.stem,
        inpfile=str(model),
    )
