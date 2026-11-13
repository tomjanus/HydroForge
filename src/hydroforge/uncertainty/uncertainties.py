"""
Uncertainty models for deterministic model parameters.

This module defines uncertainty models that perturb deterministic quantities
according to probability distributions or predefined rules. The models support
continuous, categorical and binary parameters and can be applied to either scalar
values or one-dimensional sequences (vectors of values).

The uncertainty classes are intended for representing epistemic or aleatory
uncertainty in water distribution network (WDN) models, for example:

- Pipe diameters
- Pipe roughness coefficients
- Nodal demands
- Valve states (OPEN/CLOSED)
- Pipe states (OPEN/CLOSED)
- Sensor counts or sensor locations
- Other hydraulic network parameters, e.g. wave celerities in unsteady flow models

Classes
-------
Uncertainty
    Abstract base class for all uncertainty models.
NoUncertainty
    Identity uncertainty model that returns the original value.
AdditiveUncertainty
    Applies additive noise sampled from a probability distribution.
MultiplicativeUncertainty
    Applies multiplicative noise sampled from a probability distribution.
BiasUncertainty
    Applies a deterministic additive bias.
CategoricalRandomReplacementUncertainty
    Replaces categorical values with independently sampled categories.
CategoricalReplacementUncertainty
    Conditionally replaces categorical values according to a replacement
    probability.
BinaryStateFlipUncertainty
    Flips between two categorical states with a fixed probability.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Generic, Sequence
from abc import ABC, abstractmethod
import threading
import numpy as np
from numpy.typing import NDArray
from .common import T, S, is_array_like, CatValue, CatScalar, CDFNotAvailable
from .distributions import Distribution

# --- per-thread cache for sampling ---
_local = threading.local()


class SampleCache:
    """
    Context manager for caching uncertainty samples.

    The cache ensures that each uncertain parameter is sampled only once
    within an evaluation context, so repeated references to the same
    parameter use the same sampled realization.

    Supports nested contexts, for example::

        with SampleCache():
            ...
            with SampleCache():
                ...
    """

    def __enter__(self):
        self._previous_cache = getattr(_local, "cache", None)
        _local.cache = {}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._previous_cache is None:
            if hasattr(_local, "cache"):
                del _local.cache
        else:
            _local.cache = self._previous_cache


# TODO: Write a custom check for whether a variable is array-like (or sequence)

# ================================================================
#  Base class for Uncertainty
# ================================================================


class Uncertainty(ABC, Generic[T]):
    """
    Abstract base class for uncertainty models.

    All uncertainty models implement :meth:`apply`, which perturbs one or
    more deterministic values.
    """

    @abstractmethod
    def apply(self, value: T, u: float | Sequence[float] | None = None) -> np.array:
        """
        Apply uncertainty to one or more values.

        Parameters
        ----------
        value
            Deterministic value or sequence of values.
        u
            Unit-interval sample(s). If omitted, random samples are generated.

        Returns
        -------
        numpy.ndarray
            Perturbed value(s).
        """

    def transform_cdf(self, x, nominal_value):
        """Transform a value through the uncertainty model to compute CDF.

        This method computes F_Y(x) where Y = uncertainty.apply(nominal_value, u).
        It enables stratified and advanced sampling methods that require CDF evaluation.

        Parameters
        ----------
        x : float or array-like
            Value(s) at which to evaluate the CDF.
        nominal_value : float
            The base (unperturbed) value used in the uncertainty model.

        Returns
        -------
        numpy.ndarray
            CDF values F_Y(x) as a float64 array matching the shape of x.

        Raises
        ------
        CDFNotAvailable
            If the CDF transformation is not available for this uncertainty type.

        Notes
        -----
        The default implementation raises CDFNotAvailable. Subclasses should override
        this method if they support CDF transformation. The transformation depends on
        the specific uncertainty model:

        - Additive (Y = x + ε): F_Y(y) = F_ε(y - x)
        - Multiplicative (Y = x(1 + ε)): F_Y(y) = F_ε(y/x - 1)
        """
        raise CDFNotAvailable(
            f"{self.__class__.__name__} does not support CDF transformation. "
            f"Stratified and advanced sampling methods requiring CDF evaluation are not available."
        )


# ================================================================
#  Dummy uncertainty class following Uncertainty interface
#  but leaving the quantity unchanged
# ================================================================


@dataclass
class NoUncertainty(Uncertainty[T]):
    """Return the input value unchanged."""

    def apply(self, value: T, u: float | Sequence[float] | None = None) -> np.array:
        value = np.atleast_1d(value)
        return value.item() if value.size == 1 else value

    def transform_cdf(self, x, nominal_value):
        """CDF of deterministic value: step function at nominal_value.

        For no uncertainty, F(x) = 1 if x >= nominal_value, else 0.
        """
        x_arr = np.asarray(x, dtype=float)
        result = np.where(x_arr >= nominal_value, 1.0, 0.0)
        return np.asarray(result, dtype=np.float64).reshape(x_arr.shape)


@dataclass
class _BaseDistributionUncertainty(Uncertainty[T], ABC):
    """
    Base class for distribution-driven uncertainty models.

    This class implements sampling, validation, and shape handling.
    """

    distribution: Distribution[T]

    @abstractmethod
    def _combine(
        self, x: NDArray[np.generic], eps: NDArray[np.generic]
    ) -> NDArray[np.generic]:
        """
        Combine deterministic values with sampled perturbations.

        Parameters
        ----------
        x
            Deterministic values.
        eps
            Samples drawn from the uncertainty distribution.

        Returns
        -------
        numpy.ndarray
            Perturbed values.
        """

    @abstractmethod
    def transform_cdf_value(self, y, nominal_value):
        """Transform a value to the uncertainty distribution's domain.

        For additive: return y - nominal_value
        For multiplicative: return y / nominal_value - 1

        Parameters
        ----------
        y : float or array-like
            The value to transform.
        nominal_value : float
            The base (unperturbed) value.

        Returns
        -------
        float or array
            The transformed value in the distribution's domain.
        """

    def transform_cdf(self, x, nominal_value):
        """Transform CDF of uncertainty distribution to parameter CDF.

        For Y = combine(nominal_value, ε) where ε ~ distribution,
        compute F_Y(y) by transforming y to the distribution domain
        and evaluating the distribution's CDF.

        Parameters
        ----------
        x : float or array-like
            Value(s) at which to evaluate the CDF.
        nominal_value : float
            The base (unperturbed) value.

        Returns
        -------
        numpy.ndarray
            CDF values as a float64 array.
        """
        try:
            x_arr = np.asarray(x, dtype=float)
            # Transform x to distribution's domain
            z = self.transform_cdf_value(x_arr, nominal_value)
            # Evaluate distribution's CDF at transformed value
            cdf_result = self.distribution.cdf(z)
            return np.asarray(cdf_result, dtype=np.float64)
        except Exception as e:
            raise CDFNotAvailable(
                f"Could not compute CDF for {self.__class__.__name__}: {str(e)}"
            ) from e

    def apply(self, value: T, u: float | Sequence[float] | None = None) -> np.array:
        """
        Apply uncertainty to one or more values.

        If ``u`` is provided, it is interpreted as samples from the unit interval
        and transformed through the underlying probability distribution.
        Otherwise, random unit samples are generated.

        Parameters
        ----------
        value
            Scalar or one-dimensional sequence.
        u
            Unit-interval sample(s).

        Returns
        -------
        numpy.ndarray
            Perturbed values.

        Raises
        ------
        ValueError
            If the input value is not scalar or one-dimensional.
        ValueError
            If the shape of ``u`` is incompatible with ``value``.
        """
        is_scalar = not is_array_like(value)
        x = np.atleast_1d(value)
        if x.ndim > 1:
            raise ValueError(
                f"{self.__class__.__name__} only supports scalars or 1D sequences. "
                f"Got input with shape {x.shape}"
            )
        if u is None:
            # Generate random samples if u is not provided
            u = np.random.rand(x.size)
        u_arr = np.atleast_1d(u)
        if u_arr.shape != x.shape and u_arr.size != 1:
            raise ValueError(
                f"Shape of u {u_arr.shape} must match value {x.shape} or be a scalar."
            )
        eps = self.distribution.sample_from_unit(u)
        # Ensure eps is always a numpy array for consistent operations
        eps = np.atleast_1d(eps) if not np.isscalar(eps) else eps
        result = self._combine(x, eps)
        return result.item() if is_scalar else result


# ================================================================
#  Continuous Uncertainties (numeric)
# ================================================================


@dataclass
class AdditiveUncertainty(_BaseDistributionUncertainty[S]):
    """
    Additive uncertainty model.

    The perturbed value is computed as

    .. math::

        x' = x + \varepsilon

    CDF transformation:
        F_Y(y) = F_ε(y - x) where x is the nominal value
    """

    def _combine(self, x, eps):
        return x + eps

    def transform_cdf_value(self, y, nominal_value):
        """Transform: z = y - nominal_value."""
        return y - nominal_value


@dataclass
class MultiplicativeUncertainty(_BaseDistributionUncertainty[S]):
    """
    Multiplicative uncertainty model.

    The perturbed value is computed as

    .. math::

        x' = x (1 + \varepsilon)

    CDF transformation:
        F_Y(y) = F_ε(y/x - 1) where x is the nominal value
    """

    def _combine(self, x, eps):
        return x * (1 + eps)

    def transform_cdf_value(self, y, nominal_value):
        """Transform: z = y/nominal_value - 1."""
        # Guard against division by zero
        if nominal_value == 0:
            raise ValueError(
                "Cannot compute CDF for multiplicative uncertainty with nominal_value=0. "
                "The parameter's nominal value must be non-zero for CDF evaluation."
            )
        return y / nominal_value - 1


@dataclass
class BiasUncertainty(Uncertainty[S]):
    """
    Deterministic additive bias model.

    Parameters
    ----------
    bias
        Fixed bias added to every value.

    Notes
    -----
    BiasUncertainty applies a constant (deterministic) transformation and thus
    has a step-function CDF. However, CDF transformation is not available for
    stratified sampling because the result is deterministic (no randomness).
    Use empirical CDF if stratified sampling is needed.
    """

    bias: S = 0.0

    def apply(self, value: S, u: float | Sequence[float] | None = None) -> np.ndarray:
        value_arr = np.asarray(value, dtype=float)
        bias_arr = np.asarray(self.bias, dtype=float)
        result = value_arr + bias_arr
        return result

    def transform_cdf(self, x, nominal_value):
        """BiasUncertainty has deterministic CDF (step function).

        Raises
        ------
        CDFNotAvailable
            BiasUncertainty produces deterministic results with no variability,
            so CDF transformation for stratified sampling is not applicable.
        """
        raise CDFNotAvailable(
            "BiasUncertainty applies deterministic bias and does not produce "
            "a probabilistic CDF suitable for stratified sampling. "
            "Consider using a distribution-based uncertainty model instead."
        )


# ================================================================
#  Categorical Uncertainties
# ================================================================


@dataclass
class CategoricalRandomReplacementUncertainty(Uncertainty[CatValue]):
    """
    Replace categorical values with independently sampled categories.

    Each output value is drawn independently from the specified categorical
    distribution, regardless of the original category.
    """

    distribution: Distribution[CatScalar]

    def apply(
        self, value: CatValue, u: float | Sequence[float] | None = None
    ) -> np.ndarray:
        """
        Apply categorical replacement.

        - If input is scalar, returns a single sampled category.
        - If input is array-like, returns an array of the same shape
          with independent category draws.

        Parameters
        ----------
        value
            Scalar category or one-dimensional sequence of categories.
        u
            Unit-interval sample(s). If omitted, random samples are generated.

        Returns
        -------
        numpy.ndarray
            Sampled categorical value(s).
        """
        is_scalar = not is_array_like(value)
        x = np.atleast_1d(value)
        if u is None:
            u = np.random.rand(x.size)
        draws = self.distribution.sample_from_unit(u)
        result = np.asarray(draws).reshape(x.shape)
        return result.item() if is_scalar else result


@dataclass
class CategoricalReplacementUncertainty(Uncertainty[CatValue]):
    """
    Conditionally replace categorical values.

    Each category is replaced with a newly sampled category according to a
    replacement probability drawn from ``flip_distribution``.

    Parameters
    ----------
    flip_distribution
        Distribution producing replacement probabilities.
    replacement_distribution
        Distribution producing replacement categories.
    """

    flip_distribution: Distribution[float]
    replacement_distribution: Distribution[CatScalar]

    def apply(
        self, value: CatValue, u: float | Sequence[float] | None = None
    ) -> np.ndarray:
        values = np.asarray(value, dtype=object)
        is_scalar = values.ndim == 0

        # Determine number of samples and generate u if not provided
        n_samples = 1 if is_scalar else values.size
        if u is None:
            u_flip = np.random.rand(n_samples)
            u_replace = np.random.rand(n_samples)
        else:
            # If u is provided, we need to split it for the two distributions
            u_arr = np.atleast_1d(u)
            if u_arr.ndim > 1 or (
                u_arr.size != n_samples and u_arr.size != n_samples * 2
            ):
                raise ValueError(
                    f"For {self.__class__.__name__}, u must be a 1D array of size {n_samples} or {n_samples*2}"
                )
            if u_arr.size == n_samples:  # Use same u for both
                u_flip, u_replace = u_arr, u_arr
            else:  # Split u
                u_flip, u_replace = u_arr[:n_samples], u_arr[n_samples:]

        # Draw flip probabilities
        flip_probs = self.flip_distribution.sample_from_unit(u_flip)
        flip_probs = np.asarray(flip_probs, dtype=float)

        # Bernoulli trial
        flips = np.random.rand(*flip_probs.shape) < flip_probs

        # Draw replacement categories
        replacements = self.replacement_distribution.sample_from_unit(u_replace)
        replacements = np.asarray(replacements, dtype=object)

        # Apply replacements conditionally
        result = values.reshape(-1).copy()
        result[flips] = replacements[flips]
        result = result.reshape(values.shape)
        return result.item() if is_scalar else result


@dataclass
class BinaryStateFlipUncertainty(Uncertainty[CatValue]):
    """
    Binary state uncertainty model.

    Values are flipped between two predefined states with a fixed probability.

    Parameters
    ----------
    flip_prob
        Probability of flipping each state.
    states
        Pair of valid categorical states.
    rng
        Random number generator.
    """

    flip_prob: float = 0.1
    states: tuple[str, str] = ("OPEN", "CLOSED")
    rng: np.random.Generator = field(default_factory=np.random.default_rng)

    def __post_init__(self) -> None:
        if not (0.0 <= self.flip_prob <= 1.0):
            raise ValueError("flip_prob must be in [0, 1]")
        if len(self.states) != 2 or self.states[0] == self.states[1]:
            raise ValueError("states must be a tuple of two distinct values")

    def apply(
        self, value: CatValue, u: float | Sequence[float] | None = None
    ) -> np.ndarray:
        """
        Apply binary state flipping.

        Parameters
        ----------
        value
            Scalar state or one-dimensional sequence of states.
        u
            Optional unit-interval sample(s). If provided, these determine which
            states are flipped.

        Returns
        -------
        numpy.ndarray
            Perturbed state or states.
        """
        values = np.asarray(value, dtype=object)
        is_scalar = values.ndim == 0
        a, b = self.states

        # Use provided u for flips if available, otherwise generate randomly
        if u is not None:
            flips = np.asarray(u) < self.flip_prob
        else:
            flips = (
                self.rng.random(values.shape if not is_scalar else ()) < self.flip_prob
            )

        if is_scalar:  # scalar case
            v = values.item()
            if flips:
                return b if v == a else a
            return v

        flipped = values.copy()
        flipped[values == a] = b
        flipped[values == b] = a
        return np.where(flips, flipped, values)


if __name__ == "__main__":
    pass
