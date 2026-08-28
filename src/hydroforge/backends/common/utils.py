"""
Utilities for resolving simulation result time locations.

This module provides helper functions for converting user-friendly time
selection specifications into indexers suitable for selecting simulation
results from pandas objects.

Functions
---------
_resolve_times
    Resolve an integer, slice, time range, or sequence of times against a
    simulation results index and return an appropriate indexer.

Notes
-----
Time locations may be specified as a single time, a range represented by a
two-element tuple, a slice, or a sequence of individual times. When an
exactly requested time is not present in the results index, the nearest
available time is selected.

The module only imports pandas when type checking is performed. This avoids
making pandas a runtime dependency of the module when it is not otherwise
required at runtime.
"""

from __future__ import annotations
from typing import Sequence, TYPE_CHECKING
from ..common.results import TimeLocation

if TYPE_CHECKING:
    import pandas as pd


def _resolve_times(index: pd.Index, times: TimeLocation) -> slice | Sequence[int]:
    """Resolve a time location specification.

    Parameters
    ----------
    index : pd.Index
        Index of time steps from simulation results.
    times : TimeLocation
        Time selection. An integer selects a single time, a slice selects
        a range of index labels, a two-element tuple selects an inclusive
        time range, and a sequence selects individual times.

    Returns
    -------
    slice or sequence of int
        Indexer suitable for use with ``DataFrame.loc``.

    Raises
    ------
    ValueError
        If the results are empty or ``times`` has an invalid format.
    """
    if len(index) == 0:
        raise ValueError("Simulation results contain no time steps.")
    # Slice: let pandas handle label-based slicing.
    #
    # Examples:
    #     slice(None)       -> all rows (:)
    #     slice(100, 500)   -> times 100 to 500
    #     slice(100, 500, 2) -> every second index label
    if isinstance(times, slice):
        return times
    # Single time.
    if isinstance(times, int):
        if times == 0:
            return [index[0]]
        if times in index:
            return [times]
        return [min(index, key=lambda x: abs(x - times))]
    # Time range.
    if isinstance(times, tuple) and len(times) == 2:
        start, end = times
        return list(index[(index >= start) & (index <= end)])
    # Multiple individual times.
    if isinstance(times, Sequence) and not isinstance(times, (str, bytes)):
        return [
            time if time in index else min(index, key=lambda x: abs(x - time))
            for time in times
        ]
    raise ValueError(
        "Invalid time location. Expected an integer, slice, "
        "(start, end) tuple, or sequence of times."
    )
