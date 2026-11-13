import pathlib
import tsnet


def load_tsnet_model(model: str | pathlib.Path) -> tsnet.network.TransientModel:
    """Load a TSNet transient model from an INP file.

    Parameters
    ----------
    model
        Path to the EPANET ``.inp`` input file used to construct
        the TSNetPlus transient model.

    Returns
    -------
    tsnet.network.TransientModel
        Initialized TSNet transient model.

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
        raise FileNotFoundError(f"TSNet model file not found: {model}")
    return tsnet.network.TransientModel(str(model))
