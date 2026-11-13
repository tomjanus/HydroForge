"""Utility functions for the HydroForge project.

This module provides utility functions including:
- File I/O: Ensuring directory existence
- Resource Management: Accessing package files and the package root directory
- Logging: Logging messages with timestamps and color-coded log levels
- Timing: Decorator for timing function execution

All functions are designed to work cross-platform (Windows, Linux, macOS).
"""

from typing import TypeAlias, Literal, Callable, Any
import importlib.resources as resources
import functools
import hydroforge
import time
import sys
import pathlib
from datetime import datetime
from rich import print as rprint

LogType: TypeAlias = Literal["INFO", "WARN", "WARNING", "ERROR"]

APPLICATION_NAME: str = "hydroforge"


def ensure_directory_exists(file_path: pathlib.Path) -> None:
    """Ensure that the directory path to a file exists, creating it if necessary.

    Parameters
    ----------
    file_path : pathlib.Path
        Path to the file for which the directory should be ensured.

    Notes
    -----
    This function creates all parent directories in the path if they don't exist.
    It uses parents=True and exist_ok=True to avoid errors if directories already exist.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)


def get_package_file(*folders: str) -> pathlib.Path:
    """Import package data using importlib functionality.

    Parameters
    ----------
    *folders : str
        Variable number of strings representing path components to the packaged data file.

    Returns
    -------
    pathlib.Path
        An OS-independent path to the data file.

    Examples
    --------
    >>> get_package_file('data', 'config.yaml')
    PosixPath('/path/to/hydroforge/data/config.yaml')
    """
    # importlib.resources has files(), so use that:
    pkg = resources.files(APPLICATION_NAME)
    pkg = pkg.joinpath("/".join(folders))
    return pkg.resolve()


def get_package_root() -> pathlib.Path:
    """Find the root folder of the package using importlib.resources (Python 3.9+).

    Returns
    -------
    pathlib.Path
        The root directory of the HydroForge package.

    Raises
    ------
    FileNotFoundError
        If the package root directory cannot be located.

    Notes
    -----
    The function looks for common project indicators (setup.py, pyproject.toml, etc.)
    to verify the correct root directory is found.
    """
    # Get the path to the 'hydroforge' package
    try:
        pkg = resources.files("hydroforge")
        hydroforge_package_dir = pkg.resolve()

        # The package directory is in src/hydroforge, so go up two levels to get to project root
        package_root = hydroforge_package_dir.parent.parent

        # Verify this is the correct root by checking for common project files
        project_indicators = [
            "setup.py",
            "setup.cfg",
            "pyproject.toml",
            "requirements.txt",
            ".git",
        ]
        if any((package_root / indicator).exists() for indicator in project_indicators):
            return package_root

        raise FileNotFoundError(
            f"Could not find the '{APPLICATION_NAME.upper()}' package root directory. "
            "Ensure you are running this script from within the package."
        )
    except (AttributeError, ImportError) as exception:
        # Fallback for older importlib.resources API
        if hasattr(resources, "path"):
            with resources.path(hydroforge, "__init__.py") as init_path:
                hydroforge_package_dir = init_path.parent
                return hydroforge_package_dir.parent.parent
        raise FileNotFoundError(
            "Could not find the hydroforge package root directory. "
            "Ensure you are running this script from within the package."
        ) from exception


def log(log_type: LogType, msg: str) -> None:
    """Log messages with a timestamp and color-coded type.

    Parameters
    ----------
    log_type : {'INFO', 'WARN', 'WARNING', 'ERROR'}
        Type of log message. Determines the color of the output.
    msg : str
        Message to log.

    Notes
    -----
    Messages are printed to stderr with timestamps and color formatting:
    - INFO: blue
    - WARNING/WARN: yellow
    - ERROR: red

    Examples
    --------
    >>> log('INFO', 'Processing started')
    2026-07-31 22:30:00: INFO: Processing started
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Define colors for different log types
    color_map = {
        "INFO": "blue",
        "ERROR": "red",
        "WARNING": "yellow",
        "WARN": "yellow",  # Alternative for WARNING
    }
    # Get color for the log type, default to white if not found
    color = color_map.get(log_type.upper(), "white")
    # Format the log message with colored log type
    rprint(f"{now}: [{color}]{log_type}[/{color}]: {msg}", file=sys.stderr)


def timer(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that times the execution of any function or method.

    Parameters
    ----------
    func : Callable
        The function to be timed.

    Returns
    -------
    Callable
        Wrapped function that prints execution time when called.

    Examples
    --------
    >>> @timer
    ... def my_method():
    ...     # some code
    ...     pass
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Get function name and class name if it's a method
        func_name = func.__name__
        if args and hasattr(args[0], "__class__"):
            class_name = args[0].__class__.__name__
            rprint(
                f"⏱️  {class_name}.{func_name}() executed in {execution_time:.6f} seconds"
            )
        else:
            rprint(f"⏱️  {func_name}() executed in {execution_time:.6f} seconds")

        return result

    return wrapper


if __name__ == "__main__":
    pass
