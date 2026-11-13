"""Logging utilities for the hydroforge toolbox."""

from __future__ import annotations
from dataclasses import dataclass
import logging

_PACKAGE_NAME = "hydroforge"

# Root logger for the package
_root_logger = logging.getLogger(_PACKAGE_NAME)
_root_logger.addHandler(logging.NullHandler())


@dataclass(slots=True)
class LoggingConfig:
    level: str = "INFO"
    rich: bool = True
    rich_tracebacks: bool = True
    show_path: bool = False
    format: str = "%(message)s"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger within the package namespace.

    Parameters
    ----------
    name : str, optional
        Usually ``__name__`` from the calling module. If omitted, returns the
        package root logger.

    Returns
    -------
    logging.Logger
        Logger instance.
    """
    if name is None:
        return _root_logger
    # If the module is already inside the package, use it directly.
    if name.startswith(_PACKAGE_NAME):
        return logging.getLogger(name)
    # Otherwise make it a child of the package logger.
    return _root_logger.getChild(name)


def configure_logging(config: LoggingConfig | None = None) -> None:
    """Configure HydroForge logging.

    This is intended for scripts, notebooks and command-line tools. Library
    users are free to configure logging themselves.

    Parameters
    ----------
    config
        Logging configuration. If ``None``, a default
        :class:`LoggingConfig` is used.
    """
    if config is None:
        config = LoggingConfig()
    logger = logging.getLogger(_PACKAGE_NAME)
    # Remove the default NullHandler added during package initialization.
    logger.handlers = [
        h for h in logger.handlers if not isinstance(h, logging.NullHandler)
    ]
    # Prevent duplicate handlers.
    if logger.handlers:
        logger.setLevel(config.level)
        return
    if config.rich:
        try:
            from rich.logging import RichHandler

            handler: logging.Handler = RichHandler(
                rich_tracebacks=config.rich_tracebacks,
                show_path=config.show_path,
                markup=True,
            )
        except ImportError:
            handler = logging.StreamHandler()
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(config.format))
    logger.addHandler(handler)
    logger.setLevel(config.level)
    logger.propagate = False


def set_log_level(level: int | str) -> None:
    """Change the HydroForge log level."""
    logging.getLogger(_PACKAGE_NAME).setLevel(level)
