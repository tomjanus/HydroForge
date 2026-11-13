"""File I/O wrappers for loading and saving configuration and data files.

This module provides convenient wrappers for common file I/O operations including:
- Loading YAML configuration files with error handling
- Saving dictionaries to JSON files
- Saving pandas DataFrames to CSV or Excel formats

All functions include proper error handling and validation.
"""

from typing import Any
import pathlib
import pickle
import json
import yaml
import pandas as pd
from .exceptions import UserConfigLoadException
from .utils import ensure_directory_exists

# -----------------------------------`
# File input wrappers
# -----------------------------------


def load_config(file_path: str | pathlib.Path) -> dict:
    """Load user configuration from a YAML file.

    Parameters
    ----------
    file_path : str or pathlib.Path
        Path to the YAML configuration file.

    Returns
    -------
    dict
        Dictionary containing the user configuration.

    Raises
    ------
    UserConfigLoadException
        If there is an error loading or parsing the configuration file.
        Possible causes include: file not found, permission denied,
        encoding errors, YAML parsing errors, or I/O errors.
    """
    file_path = pathlib.Path(file_path)
    try:
        with open(file_path, "r", encoding="utf-8") as file_handle:
            user_config: dict = yaml.safe_load(file_handle)
    except FileNotFoundError as exc:
        raise UserConfigLoadException(
            "Configuration file not found", exc, show_original=True
        ) from exc
    except PermissionError as exc:
        raise UserConfigLoadException(
            "Permission denied while reading configuration file",
            exc,
            show_original=True,
        ) from exc
    except UnicodeDecodeError as exc:
        raise UserConfigLoadException(
            "Encoding error while reading configuration file", exc, show_original=True
        ) from exc
    except yaml.YAMLError as exc:
        raise UserConfigLoadException(
            "YAML parsing error in configuration file", exc, show_original=True
        ) from exc
    except OSError as exc:
        raise UserConfigLoadException(
            "I/O error while reading configuration file", exc, show_original=True
        ) from exc
    return user_config


# -----------------------------------`
# File output wrappers`
# -----------------------------------`


def save_to_json(data: dict, filepath: pathlib.Path, indent: int = 4) -> None:
    """Save a dictionary to a JSON file with proper formatting.

    Parameters
    ----------
    data : dict
        The dictionary to save.
    filepath : pathlib.Path
        Path where the JSON file will be saved.
    indent : int, default=4
        Number of spaces for JSON indentation.

    Examples
    --------
    >>> save_to_json(my_dict, pathlib.Path("output.json"))
    """
    with open(filepath, "w", encoding="utf-8") as f_handle:
        json.dump(data, f_handle, indent=indent)


def save_dataframe(
    df: pd.DataFrame, filename: pathlib.Path, create_path_if_missing: bool = True
) -> None:
    """Save a DataFrame to CSV or Excel depending on file extension.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to save.
    filename : pathlib.Path
        Path where to save the file.
    create_path_if_missing : bool, default=True
        If True, create directory path if it doesn't exist.

    Raises
    ------
    ValueError
        If the file extension is not supported (.csv, .xlsx, .xls).

    Notes
    -----
    - CSV files use semicolon (;) as separator.
    - Excel files are saved with sheet name 'Sheet1'.
    """
    if create_path_if_missing:
        ensure_directory_exists(filename)
    ext = filename.suffix.lower()
    if ext == ".csv":
        df.to_csv(filename, sep=";", index=False)
    elif ext in (".xlsx", ".xls"):
        df.to_excel(filename, index=False, sheet_name="Sheet1")
    else:
        raise ValueError(f"Unsupported file extension: {ext}")


def save_pickle(
    obj: Any,
    path: str | pathlib.Path,
    *,
    create_parent: bool = True,
) -> pathlib.Path:
    """Serialize an object to a pickle file.

    Parameters
    ----------
    obj
        Python object to serialize.
    path
        Destination path for the pickle file.
    create_parent
        If True, create missing parent directories.

    Returns
    -------
    pathlib.Path
        Path to the created pickle file.

    Raises
    ------
    TypeError
        If the object cannot be pickled.
    OSError
        If the destination file cannot be written.
    """
    path = pathlib.Path(path)
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("wb") as file:
            pickle.dump(obj, file, protocol=pickle.HIGHEST_PROTOCOL)
    except pickle.PicklingError as exc:
        raise TypeError(
            f"Object of type {type(obj).__name__!r} cannot be pickled."
        ) from exc
    return path


def read_pickle(path: str | pathlib.Path) -> Any:
    """Deserialize an object from a pickle file.

    Parameters
    ----------
    path
        Path to the pickle file.

    Returns
    -------
    Any
        Deserialized Python object.

    Raises
    ------
    FileNotFoundError
        If the pickle file does not exist.
    OSError
        If the file cannot be opened or read.
    pickle.UnpicklingError
        If the file contains invalid or corrupted pickle data.
    """
    with pathlib.Path(path).open("rb") as file:
        return pickle.load(file)
