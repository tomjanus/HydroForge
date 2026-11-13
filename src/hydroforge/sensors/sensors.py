"""Sensor modeling and windowed measurement helpers for water distribution networks.

This module defines sensor abstractions and concrete sensor models that
simulate measurement error, noise, bias, drift, saturation, and other
real-world sensor behaviors. It also includes window-averaging utilities
for aggregating sequential measurements.
"""

from typing import overload, TypeVar, Union, TypeAlias, TYPE_CHECKING, cast, Any
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


class Sensor(ABC):
    """Abstract interface for sensors (pressure, flow, etc.).

    All sensors are expected to work on both scalar measurements and
    vectors/arrays of measurements. A sensor's output (measurement) has the
    same type and dimensions as the measured signal.
    """

    @overload
    def measure(self, y: float) -> float: ...
    @overload
    def measure(self, y: np.ndarray) -> np.ndarray: ...

    @overload
    def measure(
        self, y: Union[pd.Series, pd.DataFrame]
    ) -> Union[pd.Series, pd.DataFrame]: ...

    @abstractmethod
    def measure(self, y: T) -> T:
        """Return measurement(s) with sensor-specific error applied.

        Parameters
        ----------
        y : float, numpy.ndarray, pandas.DataFrame, or pandas.Series
            True (noise-free) signal value(s) to measure.

        Returns
        -------
        Same type as `y`
            Measured value(s), with the same type and shape as `y`.
        """
        raise NotImplementedError


@dataclass
class PerfectSensor(Sensor):
    """A sensor that returns the exact input without error."""

    def measure(self, y: T) -> T:
        if isinstance(y, float):
            return float(y)
        if isinstance(y, (np.ndarray, pd.DataFrame, pd.Series)):
            return y
        raise TypeError(f"Unsupported type {type(y)}")


@dataclass
class FixedPrecisionSensor(Sensor):
    """A sensor with fixed measurement precision (quantization).

    Truncates measurements to the nearest multiple of `delta_y`.

    Parameters
    ----------
    delta_y : float
        Sensor precision (the quantization step size), :math:`\\Delta y`.

    Notes
    -----
    Used e.g. in Ramon Perez, Gerard Sanz, Vicenc Puig, Joseba Quevedo,
    Miquel Angel Cuguero Escofet, Fatiha Nejjari, Jordi Meseguer, Gabriela
    Cembrano, Josep M. Mirats Tur, and Ramon Sarrate, "A Model-Based
    Methodology Using Pressure Sensors Applied to a Real Network in
    Barcelona", IEEE Control Systems Magazine, August 2014.
    DOI: 10.1109/MCS.2014.2320336
    """

    delta_y: float  # sensor precision Δy

    def measure(self, y: T) -> T:
        """Return measurement(s) truncated to the sensor precision.

        Parameters
        ----------
        y : float, numpy.ndarray, pandas.DataFrame, or pandas.Series
            True signal value(s) to measure.

        Returns
        -------
        Same type as `y`
            Measured value(s) rounded to the nearest multiple of `delta_y`.
        """
        if isinstance(y, (float, int)):
            return float(round(y / self.delta_y) * self.delta_y)
        if isinstance(y, pd.DataFrame):
            return (y / self.delta_y).round() * self.delta_y
        if isinstance(y, pd.Series):
            return (y / self.delta_y).round() * self.delta_y
        if isinstance(y, np.ndarray):
            return np.round(y / self.delta_y) * self.delta_y
        raise TypeError(f"Unsupported type {type(y)} for measurement.")


@dataclass
class RandomNoiseSensor(Sensor):
    """A sensor that adds Gaussian noise to the measurement.

    The noise is drawn from a normal distribution with mean 0 and standard
    deviation `sigma`.

    Parameters
    ----------
    sigma : float
        Standard deviation of the Gaussian noise.
    seed : int, optional
        Random seed used to initialize the internal random number
        generator, for reproducibility.
    """

    sigma: float  # standard deviation of Gaussian noise
    seed: int | None = None  # optional random seed
    _rng: np.random.Generator | None = None  # internal RNG (lazy init)

    def __post_init__(self):
        """Initialize the internal random number generator."""
        if self.seed is not None:
            self._rng = np.random.default_rng(self.seed)
        else:
            self._rng = np.random.default_rng()

    def measure(self, y: T) -> T:
        rng = self._rng
        assert rng is not None
        if isinstance(y, (float, int)):
            noise = rng.normal(loc=0.0, scale=self.sigma)
            return float(y + noise)
        if isinstance(y, pd.DataFrame):
            noise = rng.normal(loc=0.0, scale=self.sigma, size=y.shape)
            return y + pd.DataFrame(noise, index=y.index, columns=y.columns)
        if isinstance(y, pd.Series):
            noise = rng.normal(loc=0.0, scale=self.sigma, size=y.shape)
            return y + pd.Series(noise, index=y.index)
        if isinstance(y, np.ndarray):
            noise = cast(Any, rng.normal(loc=0.0, scale=self.sigma, size=y.shape))
            return y + noise
        raise TypeError(f"Unsupported type {type(y)}")


@dataclass
class OffsetSensor(Sensor):
    """A sensor that adds a constant offset to the measured value.

    Parameters
    ----------
    offset : float
        Constant bias added to every measurement.
    """

    offset: float  # constant bias

    def measure(self, y: T) -> T:
        if isinstance(y, (float, int)):
            return float(y + self.offset)
        if isinstance(y, (np.ndarray, pd.DataFrame, pd.Series)):
            return y + self.offset
        raise TypeError(f"Unsupported type {type(y)}")


@dataclass
class SensitivityErrorSensor(Sensor):
    """A sensor that introduces a scaling (gain) error to the measurements.

    Applies a scaling factor to the input measurement, simulating a
    miscalibrated sensitivity.

    Parameters
    ----------
    scale : float
        Scaling factor applied to the measurements. A value of 1.05 means
        a +5% error.
    """

    scale: float  # wrong gain applied (e.g., 1.05 means +5%)

    def measure(self, y: T) -> T:
        if isinstance(y, (float, int)):
            return float(y * self.scale)
        if isinstance(y, (np.ndarray, pd.DataFrame, pd.Series)):
            return y * self.scale
        raise TypeError(f"Unsupported type {type(y)}")


@dataclass
class DeadBandSensor(Sensor):
    """A sensor that applies a dead-band to the input signal.

    The dead-band is a region around zero where the output is forced to
    zero. This can be useful for removing small amounts of noise from a
    signal.

    Parameters
    ----------
    threshold : float
        Dead-band threshold around zero. Values within +/- threshold are
        set to zero.
    """

    threshold: float  # dead-band threshold around zero

    def measure(self, y: T) -> T:
        def apply_deadband(val: float) -> float:
            return 0.0 if abs(val) < self.threshold else val

        if isinstance(y, (float, int)):
            return apply_deadband(float(y))
        if isinstance(y, pd.DataFrame):
            return y.where(y.abs() >= self.threshold, 0.0)
        if isinstance(y, pd.Series):
            return y.where(y.abs() >= self.threshold, 0.0)
        if isinstance(y, np.ndarray):
            return np.where(np.abs(y) < self.threshold, 0.0, y)
        raise TypeError(f"Unsupported type {type(y)}")


@dataclass
class SaturationSensor(Sensor):
    """A sensor that clips (saturates) the input value to a given range.

    Parameters
    ----------
    min_val : float
        Minimum value the sensor can output.
    max_val : float
        Maximum value the sensor can output.
    """

    min_val: float
    max_val: float

    def measure(self, y: T) -> T:
        if isinstance(y, (float, int)):
            return float(np.clip(y, self.min_val, self.max_val))
        if isinstance(y, pd.DataFrame):
            return y.clip(lower=self.min_val, upper=self.max_val)
        if isinstance(y, pd.Series):
            return y.clip(lower=self.min_val, upper=self.max_val)
        if isinstance(y, np.ndarray):
            return np.clip(y, self.min_val, self.max_val)
        raise TypeError(f"Unsupported type {type(y)}")


@dataclass
class DriftSensor(Sensor):
    """A sensor that introduces a drift (bias) in the measurements.

    The drift accumulates linearly with the number of `measure()` calls.

    Parameters
    ----------
    offset_rate : float
        Rate at which the offset increases per `measure()` call.
    current_offset : float, default=0.0
        Current accumulated offset.
    """

    offset_rate: float  # bias increasing per call or per time step
    current_offset: float = 0.0  # accumulated offset

    def measure(self, y: T) -> T:
        """Return the measurement with accumulated drift applied.

        Each call increases `current_offset` by `offset_rate` before
        applying it to `y`.

        Parameters
        ----------
        y : float, numpy.ndarray, pandas.DataFrame, or pandas.Series
            True signal value(s) to measure.

        Returns
        -------
        Same type as `y`
            Measured value(s) with the current drift offset added.
        """
        self.current_offset += self.offset_rate
        if isinstance(y, (float, int)):
            return float(y + self.current_offset)
        if isinstance(y, (np.ndarray, pd.DataFrame, pd.Series)):
            return y + self.current_offset
        raise TypeError(f"Unsupported type {type(y)}")


class CompositeSensor(Sensor):
    """A sensor composed of other sensors, applied in sequence.

    Parameters
    ----------
    *sensors : Sensor
        Sensors to chain, applied in the order given (the output of each
        sensor is fed as input to the next).
    """

    def __init__(self, *sensors: Sensor):
        """Store the sensors to be chained together.

        Parameters
        ----------
        *sensors : Sensor
            Sensors to chain, applied in the order given.
        """
        self.sensors = sensors

    def measure(self, y: T) -> T:
        """Apply each chained sensor's `measure()` in sequence.

        Parameters
        ----------
        y : float, numpy.ndarray, pandas.DataFrame, or pandas.Series
            True signal value(s) to measure.

        Returns
        -------
        Same type as `y`
            Measured value(s) after applying all chained sensors.
        """
        val: T = y
        for s in self.sensors:
            val = s.measure(val)
        return val
