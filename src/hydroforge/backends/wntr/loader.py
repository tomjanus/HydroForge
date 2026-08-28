""" """
import pathlib
from .model import WNTRModel

def load_wntr_model(model: str | pathlib.Path) -> WNTRModel:
    """Load a WNTR model from an INP file.

    Parameters
    ----------
    model
        Path to the EPANET ``.inp`` input file used to construct
        the WNTR model.

    Returns
    -------
    WNTRModel
        Initialized WNTR model.

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
        raise FileNotFoundError(f"WNTR model file not found: {model}")
    return WNTRModel(str(model))
