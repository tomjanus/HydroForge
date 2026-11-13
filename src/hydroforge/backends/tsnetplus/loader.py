""" """

import pathlib
from .model import TSNetPlusModel


def load_tsnetplus_model(model: str | pathlib.Path) -> TSNetPlusModel:
    """Load a TSNetPlus transient model from an INP file.

    Parameters
    ----------
    model
        Path to the EPANET ``.inp`` input file used to construct
        the TSNetPlus transient model.

    Returns
    -------
    TSNetPlusModel
        Initialized TSNetPlus transient model.

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
        raise FileNotFoundError(f"TSNetPlus model file not found: {model}")
    return TSNetPlusModel(str(model))
