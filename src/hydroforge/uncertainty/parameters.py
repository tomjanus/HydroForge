"""Define uncertain parameters for models with sampling and uncertainty quantification.

An uncertain parameter encapsulates a nominal value along with an associated uncertainty,
allowing for sampling and manipulation of values with uncertainty. The parameter is sampled
once per sampling session to ensure consistency across multiple uses. A lock mechanism ensures
thread safety during sampling operations, and cached values can be read when needed.

Notes
-----
Uncertainty Definition:
    - name : Required name of the parameter
    - nominal_value : The base (unperturbed) value of the parameter
    - uncertainty : An instance of Uncertainty defining how to perturb the nominal_value
    - metadata : Optional dictionary for additional information

Locking Behaviour:
    When lock is in place, multiple calls to sample() return the same cached value
    within the lock scope. New samples can be generated only if the lock is disabled.
"""

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, Sequence, TypeAlias, TypeVar, cast
from enum import Enum, auto
from numbers import Integral
import threading
import numpy as np
from .uncertainties import Uncertainty, NoUncertainty
from .uncertainties import (
    BinaryStateFlipUncertainty,
    CategoricalRandomReplacementUncertainty,
    CategoricalReplacementUncertainty,
)
from .common import CDFNotAvailable
from ..auxiliary import get_logger

logger = get_logger(__name__)

ScalarValue: TypeAlias = str | int | float | np.integer | np.floating | Enum

T = TypeVar("T", bound=ScalarValue)

# --- per-thread cache for sampling (currently not used) ---
_local = threading.local()
_local.cache = None  # dict | None

CDFInput = float | Sequence[float] | np.ndarray
CDFResult = float | np.ndarray


class ParameterType(Enum):
    """Enumeration of parameter types for validation and arithmetic rules.

    Defines the type of parameter for validation and arithmetic operations, and for handling
    different uncertainty sampling methods (e.g., Sobol Sampling, Latin Hypercube) implemented
    in different Python packages (e.g., SALib, Chaospy).

    Attributes
    ----------
    NUMERICAL
        Continuous numerical parameter type.
    DISCRETE
        Integer-valued discrete parameter type.
    CATEGORICAL
        Non-numeric categorical parameter type.
    BINARY
        Binary (two-state) parameter type.
    UNDEFINED
        Parameter type not yet determined.
    """

    NUMERICAL = auto()
    DISCRETE = auto()
    CATEGORICAL = auto()
    BINARY = auto()
    UNDEFINED = auto()


# ================================================================
#  Uncertain Parameters
# ================================================================


class IUncertainParameter(ABC, Generic[T]):
    """Abstract base class for uncertain parameters.

    Defines the interface that all uncertain parameter implementations must follow,
    providing methods for accessing nominal values and generating samples with uncertainty.
    """

    @abstractmethod
    def nominal(self) -> T:
        """Return the nominal (unperturbed) value.

        Returns
        -------
        T
            The base parameter value without uncertainty applied.
        """

    @abstractmethod
    def sample(self) -> T:
        """Return a realised parameter value with uncertainty applied.

        Returns
        -------
        T
            A sample of the parameter with uncertainty applied.
        """

    @abstractmethod
    def sample_from_unit(self, u: float | Sequence[float]) -> T:
        """Return a realised parameter value with uncertainty applied.

        Returns
        -------
        T
            A sample of the parameter with uncertainty applied.
        """

    @abstractmethod
    def cdf(self, x: CDFInput) -> CDFResult:
        """Evaluate the CDF of the realised parameter value."""


@dataclass
class Parameter(IUncertainParameter[T], Generic[T]):
    """Uncertain parameter with sampling and locking support.

    Works for scalars, arrays, or categorical values depending on nominal_value.
    Provides thread-safe sampling with optional caching via locking mechanism.

    Attributes
    ----------
    name : str
        Name of the parameter.
    nominal_value : T
        The base (unperturbed) value of the parameter.
    uncertainty : Uncertainty[T]
        An Uncertainty instance defining how to perturb the nominal value.
        Defaults to NoUncertainty (no perturbation).
    type : ParameterType
        Classification of the parameter (numerical, discrete, categorical, binary, undefined).
        Defaults to UNDEFINED.
    infer_type_from_data : bool
        Whether to infer the parameter type from the nominal value and uncertainty if the type is undefined.
        Defaults to True.
    metadata : dict[str, Any]
        Optional dictionary for additional information about the parameter.
        Defaults to empty dict.
    """

    name: str
    nominal_value: T
    uncertainty: Uncertainty[T] = field(default_factory=NoUncertainty)
    type: ParameterType = ParameterType.UNDEFINED
    infer_type_from_data: bool = field(default=True)
    metadata: dict[str, Any] = field(
        default_factory=dict
    )  # Additional metadata for the parameter

    _sampled_value: Optional[Any] = field(init=False, default=None, repr=False)
    _locked: bool = field(init=False, default=False, repr=False)
    _lock: threading.Lock = field(
        init=False, default_factory=threading.Lock, repr=False
    )

    def __post_init__(self):
        """Validate parameter configuration after initialization.

        Raises
        ------
        TypeError
            If uncertainty is not an instance of Uncertainty.
        """
        if not isinstance(self.uncertainty, Uncertainty):
            raise TypeError("uncertainty must be an instance of Uncertainty")
        if self.type == ParameterType.UNDEFINED and self.infer_type_from_data:
            inferred_type = self._infer_parameter_type()
            logger.info(
                "Parameter type is undefined. Inferring type from nominal value and uncertainty. "
                f"Inferred type: {inferred_type}"
            )
            self.type = inferred_type

    def _infer_parameter_type(self) -> ParameterType:
        """Infer the parameter type based on the nominal value."""
        if isinstance(self.nominal_value, (int, float)):
            return ParameterType.NUMERICAL
        if isinstance(self.nominal_value, bool) or isinstance(
            self.uncertainty, BinaryStateFlipUncertainty
        ):
            return ParameterType.BINARY
        if isinstance(self.nominal_value, str) or isinstance(
            self.uncertainty,
            (
                CategoricalRandomReplacementUncertainty,
                CategoricalReplacementUncertainty,
            ),
        ):
            return ParameterType.CATEGORICAL
        if isinstance(self.nominal_value, (list, np.ndarray)):
            return ParameterType.DISCRETE
        return ParameterType.UNDEFINED

    # --------------------------------------------------
    # Core API
    # --------------------------------------------------

    def cdf(
        self,
        x: CDFInput,
        *,
        empirical: bool = False,
        n_samples: int = 10_000,
        random_state: int | np.random.Generator | None = None,
    ) -> CDFResult:
        """Evaluate the CDF of the realised parameter value.

        Computes F_Y(x) where Y = uncertainty.apply(nominal_value, u).

        The CDF depends on both the nominal value and the uncertainty model.
        For example, with additive uncertainty Y = x + ε, the CDF is F_Y(y) = F_ε(y - x).

        Parameters
        ----------
        x : float or array-like
            Value(s) at which to evaluate the CDF.
        empirical : bool, default=False
            If False, use theoretical CDF transformation if available.
            If True, estimate CDF empirically from samples.
        n_samples : int, default=10_000
            Number of samples for empirical CDF estimation.
        random_state : int, numpy.random.Generator, or None, default=None
            Random seed or generator for empirical estimation.

        Returns
        -------
        CDFResult
            CDF values F_Y(x) as a float64 array matching the shape of x.

        Raises
        ------
        CDFNotAvailable
            If the parameter type (e.g., categorical) or uncertainty model does not
            support CDF evaluation and empirical=False.
        ValueError
            If empirical CDF estimation fails.

        Examples
        --------
        >>> from hydroforge.uncertainty import (
        ...     Parameter, ParameterType, AdditiveUncertainty, NormalDistribution
        ... )
        >>> p = Parameter(
        ...     name="diameter",
        ...     nominal_value=100.0,
        ...     uncertainty=AdditiveUncertainty(NormalDistribution(0, 5)),
        ...     type=ParameterType.NUMERICAL
        ... )
        >>> # CDF at value 105.0
        >>> cdf_at_105 = p.cdf(105.0)
        >>> print(f"P(Diameter <= 105) = {cdf_at_105:.4f}")
        P(Diameter <= 105) = 0.8413

        >>> # Multiple values
        >>> cdf_values = p.cdf([90.0, 100.0, 110.0])
        >>> print(cdf_values)
        [0.0228 0.5    0.9772]

        Notes
        -----
        Theoretical CDF is preferred for efficiency. It is available for:
        - Distribution-based uncertainties (Additive, Multiplicative)
        - NoUncertainty (deterministic)

        For other uncertainty types or when empirical=True, samples are generated
        and an empirical CDF is computed.
        """
        # Check if parameter is categorical
        if self.is_categorical():
            raise CDFNotAvailable(
                f"CDF is not defined for categorical parameters like '{self.name}'. "
                f"Stratified sampling and advanced sampling methods requiring CDF evaluation "
                f"are not supported for categorical parameters."
            )

        # Try theoretical CDF first (unless empirical is explicitly requested)
        if not empirical:
            try:
                return self.uncertainty.transform_cdf(x, self.nominal_value)
            except CDFNotAvailable:
                # Fall through to empirical if theoretical not available
                if empirical is False:
                    # User didn't explicitly request empirical, so raise the error
                    raise
                # Otherwise, continue to empirical computation

        # Compute empirical CDF if theoretical failed or was requested
        return self._empirical_cdf(x, n_samples=n_samples, random_state=random_state)

    def _empirical_cdf(
        self,
        x: CDFInput,
        *,
        n_samples: int,
        random_state: int | np.random.Generator | None,
    ) -> CDFResult:
        """Estimate CDF empirically by sampling the parameter.

        Parameters
        ----------
        x : float or array-like
            Points at which to evaluate the CDF.
        n_samples : int
            Number of parameter samples to generate for empirical CDF.
        random_state : int, Generator, or None
            Random seed or generator.

        Returns
        -------
        CDFResult
            Empirical CDF values.
        """
        if n_samples <= 0:
            raise ValueError("n_samples must be greater than zero")

        # Generate samples
        rng = (
            random_state
            if isinstance(random_state, np.random.Generator)
            else np.random.default_rng(random_state)
        )

        # Create unit-interval samples
        unit_samples = rng.random(int(n_samples))
        samples = np.array([self.sample_from_unit(u) for u in unit_samples])

        # Sort samples for ECDF computation
        sorted_samples = np.sort(samples)

        # Evaluate ECDF at requested points
        x_array = np.asarray(x, dtype=float)
        flat_x = x_array.reshape(-1)
        indices = np.searchsorted(sorted_samples, flat_x, side="right")
        result = indices / len(sorted_samples)

        return np.asarray(result, dtype=np.float64).reshape(x_array.shape)

    def nominal(self) -> T:
        """Return the nominal (unperturbed) value.

        Returns
        -------
        T
            The base parameter value without uncertainty applied.
        """
        return self.nominal_value

    def reset(self) -> None:
        """Reset the sampled value and unlock for new sampling.

        Clears the cached sampled value and releases the lock, allowing
        subsequent calls to sample() to generate new values.
        """
        with self._lock:
            self._sampled_value = None
            self._locked = False

    def sample(self) -> T:
        """Return a realised parameter value with uncertainty applied.

        If already sampled and locked, returns the cached sampled value.
        Sampling is thread-safe.

        Returns
        -------
        T
            A sample of the parameter with uncertainty applied.

        Notes
        -----
        If the lock is active, returns the cached value from the first sample.
        Call reset() to unlock and generate a new sample.
        """
        with self._lock:
            if self._locked:
                return cast(T, self._sampled_value)
            val = self.uncertainty.apply(self.nominal_value)
            self._sampled_value = val
            self._locked = True
            return val

    def sample_from_unit(self, u: float | Sequence[float]) -> T:
        """Sample parameter using unit interval value(s).

        Allows external samplers (LHS, Sobol, etc.) to control sampling by providing
        unit interval values that are transformed through the parameter's uncertainty
        distribution.

        Parameters
        ----------
        u : float or Sequence[float]
            One or more values in the closed interval [0, 1] to use for sampling.

        Returns
        -------
        T
            Sampled parameter value with uncertainty applied.

        Notes
        -----
        This method bypasses the locking mechanism and always generates a new sample.
        Use sample() for locked sampling behavior.
        """
        return self.uncertainty.apply(self.nominal_value, u=u)

    # --------------------------------------------------
    # Helper wrappers for parameter type checks
    # --------------------------------------------------

    def is_categorical(self) -> bool:
        """Check if the parameter is categorical.

        Returns
        -------
        bool
            True if parameter type is CATEGORICAL, False otherwise.
        """
        return self.type == ParameterType.CATEGORICAL

    def is_discrete(self) -> bool:
        """Check if the parameter is discrete.

        Returns
        -------
        bool
            True if parameter type is DISCRETE, False otherwise.
        """
        return self.type == ParameterType.DISCRETE

    def is_binary(self) -> bool:
        """Check if the parameter is binary.

        Returns
        -------
        bool
            True if parameter type is BINARY, False otherwise.
        """
        return self.type == ParameterType.BINARY

    def is_numerical(self) -> bool:
        """Check if the parameter is numerical.

        Returns
        -------
        bool
            True if parameter type is NUMERICAL, False otherwise.
        """
        return self.type == ParameterType.NUMERICAL

    def is_undefined(self) -> bool:
        """Check if the parameter type is undefined.

        Returns
        -------
        bool
            True if parameter type is UNDEFINED, False otherwise.
        """
        return self.type == ParameterType.UNDEFINED

    # --------------------------------------------------
    # Conversions
    # --------------------------------------------------

    def __float__(self) -> float:
        """Convert parameter to float by sampling.

        Returns
        -------
        float
            The parameter value converted to float.

        Raises
        ------
        TypeError
            If the sampled value cannot be converted to float.
        """
        try:
            val = self.sample()
            return float(cast(Any, val))
        except (TypeError, ValueError):
            raise TypeError("Cannot convert uncertain parameter to float") from None

    def __array__(self, dtype=None) -> np.ndarray:
        """Convert parameter to numpy array by sampling.

        Parameters
        ----------
        dtype : data-type, optional
            Data type to use for the array. If not specified, dtype is inferred.

        Returns
        -------
        np.ndarray
            The parameter value as a numpy array (wraps scalar or array input).
        """
        val = self.sample()
        arr = np.array(val, dtype=dtype)
        return arr

    # --------------------------------------------------
    # Arithmetic rules
    # --------------------------------------------------

    def _check_arithmetic_allowed(self, other, op_name: str) -> None:
        """Check if arithmetic operation is allowed based on parameter type.

        Parameters
        ----------
        other : Parameter or other type
            The other operand in the arithmetic operation.
        op_name : str
            Name of the operation ('add', 'sub', 'mul', 'div').

        Raises
        ------
        TypeError
            If the operation is not allowed for the parameter type.
            Categorical and binary parameters don't support any arithmetic
            (binary is treated as categorical for arithmetic purposes).
            Discrete parameters don't support division.
            Division and multiplication of discrete parameters require integer multipliers.
        """
        # categorical and binary: no arithmetic ever
        # (binary states are labels; numeric arithmetic on them is meaningless
        # and silently produces garbage such as repeated strings)
        if self.type == ParameterType.CATEGORICAL:
            raise TypeError("Arithmetic not allowed for categorical parameters")
        if self.type == ParameterType.BINARY:
            raise TypeError(
                "Arithmetic not allowed for binary parameters "
                "(binary parameters are treated as categorical)"
            )

        if isinstance(other, Parameter):
            if other.type == ParameterType.CATEGORICAL:
                raise TypeError("Arithmetic not allowed for categorical parameters")
            if other.type == ParameterType.BINARY:
                raise TypeError(
                    "Arithmetic not allowed for binary parameters "
                    "(binary parameters are treated as categorical)"
                )

        # discrete-specific rules
        if self.type == ParameterType.DISCRETE:
            if op_name == "div":
                raise TypeError("Division not allowed for discrete parameters")

            if op_name == "mul":
                # allow only integer multipliers
                other_val = other.sample() if isinstance(other, Parameter) else other
                if not isinstance(other_val, Integral):
                    raise TypeError(
                        "Multiplication of discrete parameters requires integer multiplier"
                    )

    @staticmethod
    def _coerce_other(other: Any) -> Any:
        """Coerce other operand to its sampled value if it's a Parameter.

        Parameters
        ----------
        other : Parameter or other type
            The operand to coerce.

        Returns
        -------
        Any
            The sampled value if other is a Parameter, otherwise other unchanged.
        """
        return other.sample() if isinstance(other, Parameter) else other

    def __binary_op(self, other, op_name: str, op):
        """General binary operation handler.

        Parameters
        ----------
        other : Parameter or other type
            The other operand.
        op_name : str
            Name of the operation for validation.
        op : callable
            The binary operation function.

        Returns
        -------
        Any
            Result of the binary operation.
        """
        self._check_arithmetic_allowed(other, op_name)
        return op(self.sample(), self._coerce_other(other))

    def __add__(self, other):
        """Add parameter to another value."""
        return self.__binary_op(other, "add", lambda a, b: a + b)

    def __radd__(self, other):
        """Add value to parameter (reverse addition)."""
        return self.__binary_op(other, "add", lambda a, b: b + a)

    def __sub__(self, other):
        """Subtract value from parameter."""
        return self.__binary_op(other, "sub", lambda a, b: a - b)

    def __rsub__(self, other):
        """Subtract parameter from value (reverse subtraction)."""
        return self.__binary_op(other, "sub", lambda a, b: b - a)

    def __mul__(self, other):
        """Multiply parameter by value."""
        return self.__binary_op(other, "mul", lambda a, b: a * b)

    def __rmul__(self, other):
        """Multiply value by parameter (reverse multiplication)."""
        return self.__binary_op(other, "mul", lambda a, b: b * a)

    def __truediv__(self, other):
        """Divide parameter by value."""
        return self.__binary_op(other, "div", lambda a, b: a / b)

    def __rtruediv__(self, other):
        """Divide value by parameter (reverse division)."""
        return self.__binary_op(other, "div", lambda a, b: b / a)

    # --------------------------------------------------
    # NumPy protocol
    # --------------------------------------------------

    def __array_function__(self, func, types, args, kwargs):
        """Enable NumPy functions to operate on Parameter instances by sampling their values.

        Parameters
        ----------
        func : callable
            The NumPy function to apply.
        types : tuple of type
            Types of all arguments to the function.
        args : tuple
            Positional arguments to the function.
        kwargs : dict
            Keyword arguments to the function.

        Returns
        -------
        Any
            Result of applying func to sampled parameter values.

        Raises
        ------
        TypeError
            If parameter is categorical, as NumPy operations are not allowed.
            If types include types other than ndarray or Parameter.
        """
        if self.type == ParameterType.CATEGORICAL:
            raise TypeError("NumPy operations not allowed for categorical parameters")

        if not all(issubclass(t, (np.ndarray, Parameter)) for t in types):
            return NotImplemented

        sampled_args = tuple(
            x.sample() if isinstance(x, Parameter) else x for x in args
        )
        return func(*sampled_args, **kwargs)

    # --------------------------------------------------
    # Representation
    # --------------------------------------------------

    def __repr__(self) -> str:
        """Return a detailed string representation of the parameter.

        Returns
        -------
        str
            String representation including name, nominal value, uncertainty, type, and metadata.
        """
        name_str = f"name='{self.name}', "
        return (
            f"{self.__class__.__name__}("
            f"{name_str}"
            f"nominal={self.nominal_value}, "
            f"uncertainty={self.uncertainty.__repr__()}, "
            f"type={self.type.name}, "
            f"metadata={self.metadata})"
        )


# ================================================================
#  Demonstration
# ================================================================

if __name__ == "__main__":
    pass
