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

Locking Behavior:
    When lock is in place, multiple calls to sample() return the same cached value
    within the lock scope. New samples can be generated only if the lock is disabled.
"""
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, Sequence
from enum import Enum, auto
from numbers import Integral
import threading
import numpy as np
from hydroforge.uncertainty.common import T
from hydroforge.uncertainty.uncertainties import Uncertainty, NoUncertainty

# --- per-thread cache for sampling (currently not used) ---
_local = threading.local()
_local.cache = None  # dict | None

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
    metadata : dict[str, Any]
        Optional dictionary for additional information about the parameter.
        Defaults to empty dict.
    """
    name: str
    nominal_value: T
    uncertainty: Uncertainty[T] = field(default_factory=NoUncertainty)
    type: ParameterType = ParameterType.UNDEFINED
    metadata: dict[str, Any] = field(default_factory=dict) # Additional metadata for the parameter
    
    _sampled_value: Optional[T] = field(init=False, default=None, repr=False)
    _locked: bool = field(init=False, default=False, repr=False)
    _lock: threading.Lock = field(init=False, default_factory=threading.Lock, repr=False)
    
    def __post_init__(self):
        """Validate parameter configuration after initialization.

        Raises
        ------
        TypeError
            If uncertainty is not an instance of Uncertainty.
        """
        if not isinstance(self.uncertainty, Uncertainty):
            raise TypeError("uncertainty must be an instance of Uncertainty")

    # --------------------------------------------------
    # Core API
    # --------------------------------------------------
    
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
                return self._sampled_value
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
            return float(val)
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
            Categorical parameters don't support any arithmetic.
            Discrete parameters don't support division.
            Division and multiplication of discrete parameters require integer multipliers.
        """
        # categorical: no arithmetic ever
        if self.type == ParameterType.CATEGORICAL:
            raise TypeError("Arithmetic not allowed for categorical parameters")

        if isinstance(other, Parameter):
            if other.type == ParameterType.CATEGORICAL:
                raise TypeError("Arithmetic not allowed for categorical parameters")

        # discrete-specific rules
        if self.type == ParameterType.DISCRETE:
            if op_name == "div":
                raise TypeError("Division not allowed for discrete parameters")

            if op_name == "mul":
                # allow only integer multipliers
                other_val = (
                    other.sample() if isinstance(other, Parameter) else other
                )
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
            x.sample() if isinstance(x, Parameter) else x
            for x in args
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
        return (f"{self.__class__.__name__}("
                f"{name_str}"
                f"nominal={self.nominal_value}, "
                f"uncertainty={self.uncertainty.__repr__()}, "
                f"type={self.type.name}, "
                f"metadata={self.metadata})")

# ================================================================
#  Demonstration
# ================================================================

if __name__ == "__main__":
    pass
