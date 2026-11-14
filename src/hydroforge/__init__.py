"""HydroForge: Water network uncertainty analysis and leakage localization toolkit.

This package provides tools for:
- Water distribution network modeling and simulation
- Uncertainty analysis and propagation
- Leak detection and localization
- Sensor placement optimization
- Hydraulic analysis tools
"""

__version__ = "1.0.0"
__author__ = "IUT-IBK and Tomasz Janus"

from .auxiliary.logging_utils import configure_logging, LoggingConfig

configure_logging(
    config=LoggingConfig(level="INFO", rich=True, rich_tracebacks=True, show_path=False)
)
