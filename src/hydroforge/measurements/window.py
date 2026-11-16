"""Windowed measurement helpers for generic sensor models.

This module is domain-agnostic: it has no EPANET / WDN dependence and is safe
to import without any WDN dependency.
"""

from typing import TypeVar, Union, TypeAlias, TYPE_CHECKING, cast
from abc import ABC, abstractmethod
from dataclasses import dataclass
import numpy as np
import pandas as pd
from numpy.typing import NDArray

if TYPE_CHECKING:
    # More specific typing for type checkers
    FloatSeries: TypeAlias = "pd.Series[float]"
    FloatDataFrame: TypeAlias = "pd.DataFrame[float]"
else:
    # Runtime aliases without subscripting
    FloatSeries: TypeAlias = pd.Series
    FloatDataFrame: TypeAlias = pd.DataFrame

# Type variable bound to real numbers or numpy arrays
T = TypeVar("T", float, np.ndarray, FloatDataFrame, FloatSeries)
Measurement = Union[float, NDArray[np.floating], FloatDataFrame, FloatSeries]


@dataclass
class BaseWindowAverager(ABC):
    """
    Base class for window-based averaging.

    Subclasses define how averaging windows are positioned by implementing
    :meth:`_window_starts`.
    """

    window_size: int

    def __post_init__(self) -> None:
        if self.window_size <= 0:
            raise ValueError("window_size must be positive.")

    @abstractmethod
    def _window_starts(self, n: int) -> range:
        """
        Return the starting indices of averaging windows.

        Parameters
        ----------
        n : int
            Number of samples.

        Returns
        -------
        range
            Starting indices of each averaging window.
        """

    def average(self, x: T) -> Measurement:
        """
        Average values over windows.

        Supports numpy arrays, pandas Series and pandas DataFrames.

        Parameters
        ----------
        x
            Input data.

        Returns
        -------
        Same type as input where possible.

        Notes
        -----
        DataFrames are averaged across columns.
        """

        # ------------------------------------------------------------------
        # DataFrame
        # ------------------------------------------------------------------
        if isinstance(x, pd.DataFrame):
            if x.shape[1] < self.window_size:
                raise ValueError(
                    f"Need at least {self.window_size} columns, " f"got {x.shape[1]}."
                )
            starts = list(self._window_starts(x.shape[1]))
            result = pd.concat(
                [x.iloc[:, s : s + self.window_size].mean(axis=1) for s in starts],
                axis=1,
            )
            return result.iloc[:, 0] if result.shape[1] == 1 else result

        # ------------------------------------------------------------------
        # Series
        # ------------------------------------------------------------------
        if isinstance(x, pd.Series):
            values = cast(Measurement, self.average(x.values))
            if isinstance(values, float):
                return values
            starts = list(self._window_starts(len(x)))
            return pd.Series(values, index=x.index[starts])

        # ------------------------------------------------------------------
        # NumPy array / sequence
        # ------------------------------------------------------------------
        arr = np.asarray(x, dtype=float)
        if len(arr) < self.window_size:
            raise ValueError(
                f"Need at least {self.window_size} values, got {len(arr)}."
            )
        starts = list(self._window_starts(len(arr)))
        values = np.array(
            [np.mean(arr[s : s + self.window_size]) for s in starts],
            dtype=float,
        )
        if len(values) == 1:
            return float(values[0])
        return values


@dataclass
class WindowAverager(BaseWindowAverager):
    """
    Average over fixed, non-overlapping windows.

    Examples
    --------
    window_size = 4

    [1 2 3 4] [5 6 7 8] [9 10 11 12]
    """

    def _window_starts(self, n: int) -> range:
        return range(
            0,
            n - self.window_size + 1,
            self.window_size,
        )


@dataclass
class MovingWindowAverager(BaseWindowAverager):
    """
    Average over overlapping sliding windows.

    Parameters
    ----------
    window_size : int
        Number of samples in each window.
    overlap : int, default=0
        Number of samples shared between consecutive windows.

    Examples
    --------
    window_size = 5
    overlap = 2

    [1 2 3 4 5]
          [4 5 6 7 8]
                [7 8 9 10 11]
    """

    overlap: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()

        if not 0 <= self.overlap < self.window_size:
            raise ValueError("overlap must satisfy " "0 <= overlap < window_size.")

    @property
    def stride(self) -> int:
        """Distance between consecutive window starts."""
        return self.window_size - self.overlap

    def _window_starts(self, n: int) -> range:
        return range(
            0,
            n - self.window_size + 1,
            self.stride,
        )
