"""Auxiliary utilities for the HydroForge package.

This package provides auxiliary functionality for HydroForge including:
- File I/O operations (loading/saving configuration and data files)
- Custom exception classes for error handling
- Utility functions (logging, timing, directory management, package resource access)

Modules
-------
exceptions
    Custom exception classes for configuration and parsing errors.
io
    High-level wrappers for file I/O operations.
utils
    General utility functions for logging, timing, and resource management.
logging_utils
    Utility functions for logging.

Examples
--------
>>> from hydroforge.auxiliary import load_config
>>> config = load_config('config.yaml')
"""
from .exceptions import UserConfigLoadException
from .io import load_config, save_to_json, save_dataframe, save_pickle, read_pickle
from .logging_utils import LoggingConfig, get_logger, configure_logging, set_log_level
from .utils import ensure_directory_exists, get_package_file, get_package_root, log, timer


__all__ = [
    "UserConfigLoadException",
    "load_config",
    "save_to_json",
    "save_dataframe",
    "save_pickle",
    "read_pickle",
    "LoggingConfig",
    "get_logger",
    "configure_logging",
    "set_log_level",
    "ensure_directory_exists",
    "get_package_file",
    "get_package_root",
    "log",
    "timer",
]