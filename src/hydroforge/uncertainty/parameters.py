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
from numbers import Integral, Real
import threading
import numpy as np
from .uncertainties import Uncertainty, NoUncertainty
from .uncertainties import (
    BinaryStateFlipUncertainty,
    CategoricalRandomReplacementUncertainty,
    CategoricalReplacementUncertainty,
)
from .common import CDFNotAvailable, _empirical_categorical_cdf_from_indices
from ..auxiliary import get_logger

logger = get_logger(__name__)

ScalarValue: TypeAlias = str | int | float | np.integer | np.floating | Enum

T = TypeVar("T", bound=ScalarValue)

CDFInput = float | str | Sequence[float] | Sequence[str] | np.ndarray
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
        """Infer the parameter type based on the nominal value.

        Returns
        -------
        ParameterType
            ``BINARY`` for boolean nominal values or binary-flip uncertainty,
            ``CATEGORICAL`` for string nominal values or categorical
            replacement uncertainty, ``NUMERICAL`` for ``int``/``float``
            values (including NumPy scalar equivalents), ``DISCRETE`` for
            list/array values, and ``UNDEFINED`` otherwise.  ``bool`` is
            checked before the numeric classes because ``bool`` is a subclass
            of ``int`` in Python.
        """
        if isinstance(self.nominal_value, (bool, np.bool_)) or isinstance(
            self.uncertainty, BinaryStateFlipUncertainty
        ):
            return ParameterType.BINARY
        if isinstance(self.nominal_value, (Integral, Real)):
            return ParameterType.NUMERICAL
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
        """Evaluate the CDF of the parameter's realised value.

        Parameters
        ----------
        x : CDFInput
            Value(s) at which to evaluate the CDF.
        empirical : bool, default=False
            Estimate from samples instead of using a theoretical transform.
            Categorical and binary parameters require an explicit order.
        n_samples : int, default=10_000
            Number of samples used for empirical estimation.
        random_state : int, numpy.random.Generator, or None, default=None
            Seed or generator used for empirical estimation.

        Returns
        -------
        CDFResult
            Float64 CDF values matching the shape of ``x``.

        Raises
        ------
        CDFNotAvailable
            If theoretical CDF evaluation is unavailable, or an empirical
            categorical CDF has no explicit order.
        ValueError
            If empirical CDF estimation fails.

        Notes
        -----
        Theoretical CDF is preferred for efficiency. It is available for:
        distribution-based uncertainties (Additive, Multiplicative) and
        `NoUncertainty`. Empirical categorical CDFs follow the uncertainty's
        declared order; labels are never ordered lexically.
        """
        # Theoretical categorical CDFs remain unavailable. Empirical CDFs are
        # supported only when the uncertainty provides an explicit category order.
        if self.is_categorical():
            if not empirical:
                raise CDFNotAvailable(
                    f"CDF is not defined for categorical parameters like '{self.name}'. "
                    "Theoretical CDF evaluation requires a numerical parameter."
                )
            return self._empirical_categorical_cdf(
                x,
                n_samples=n_samples,
                random_state=random_state,
            )
        if empirical and self.is_binary():
            return self._empirical_categorical_cdf(
                x,
                n_samples=n_samples,
                random_state=random_state,
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

    def _empirical_categorical_cdf(
        self,
        x: CDFInput,
        *,
        n_samples: int,
        random_state: int | np.random.Generator | None,
    ) -> CDFResult:
        """Estimate a categorical CDF using the uncertainty's declared order."""
        if n_samples <= 0:
            raise ValueError("n_samples must be greater than zero")

        rng = (
            random_state
            if isinstance(random_state, np.random.Generator)
            else np.random.default_rng(random_state)
        )
        ordered_samples = self._sample_categorical_values_with_order(n_samples, rng)
        if ordered_samples is None:
            raise CDFNotAvailable(
                f"Empirical CDF for categorical parameter {self.name!r} requires "
                "an uncertainty with an explicit category order."
            )
        categories, samples = ordered_samples

        category_indices = {
            category: index for index, category in enumerate(categories)
        }
        try:
            sample_indices = np.asarray(
                [category_indices[sample] for sample in samples],
                dtype=np.int64,
            )
        except KeyError as exc:
            raise CDFNotAvailable(
                f"Uncertainty for parameter {self.name!r} produced category "
                f"{exc.args[0]!r} outside its declared order."
            ) from exc

        return _empirical_categorical_cdf_from_indices(
            x,
            category_indices,
            sample_indices,
        )

    def _sample_categorical_values_with_order(
        self,
        n_samples: int,
        rng: np.random.Generator,
    ) -> tuple[tuple[Any, ...], np.ndarray] | None:
        """Return sampled categories with an order declared by the uncertainty."""
        values = np.full(n_samples, self.nominal_value, dtype=object)
        uncertainty = self.uncertainty

        if isinstance(uncertainty, BinaryStateFlipUncertainty):
            state_order = uncertainty.states
            if self.nominal_value not in state_order:
                return None
            samples = uncertainty.apply(values, u=rng.random(n_samples).tolist())
            return state_order, np.asarray(samples, dtype=object)

        if isinstance(uncertainty, CategoricalRandomReplacementUncertainty):
            distribution_order = getattr(
                uncertainty.distribution,
                "categories",
                None,
            )
            if not distribution_order:
                return None
            samples = uncertainty.apply(values, u=rng.random(n_samples).tolist())
            return tuple(distribution_order), np.asarray(samples, dtype=object)

        if isinstance(uncertainty, CategoricalReplacementUncertainty):
            replacement_order = getattr(
                uncertainty.replacement_distribution,
                "categories",
                None,
            )
            if not replacement_order or self.nominal_value not in replacement_order:
                return None
            flip_probabilities = np.asarray(
                uncertainty.flip_distribution.sample_from_unit(rng.random(n_samples)),
                dtype=np.float64,
            )
            replacements = np.asarray(
                uncertainty.replacement_distribution.sample_from_unit(
                    rng.random(n_samples)
                ),
                dtype=object,
            )
            flips = rng.random(n_samples) < flip_probabilities
            values[flips] = replacements[flips]
            return tuple(replacement_order), values

        return None

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
            Discrete parameters don't support division, and multiplication of
            discrete parameters requires an integer multiplier; these discrete
            rules bind every ``Parameter`` operand, regardless of operand order.
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

        # discrete-specific rules, enforced on whichever operand is discrete so
        # the policy is symmetric with respect to operand order
        if self.type == ParameterType.DISCRETE:
            Parameter._check_discrete_rules(self, other, op_name)
        elif isinstance(other, Parameter) and other.type == ParameterType.DISCRETE:
            Parameter._check_discrete_rules(other, self, op_name)

    @staticmethod
    def _check_discrete_rules(discrete_operand, other_operand, op_name: str) -> None:
        """Apply the discrete-parameter arithmetic rules to a discrete operand.

        ``discrete_operand`` is the ``Parameter`` typed ``DISCRETE``;
        ``other_operand`` is its counterpart (a ``Parameter`` or a plain value).
        Division is never allowed for a discrete parameter, and multiplication
        requires the counterpart value to be an integer.

        Raises
        ------
        TypeError
            If a discrete rule is violated.
        """
        if op_name == "div":
            raise TypeError("Division not allowed for discrete parameters")
        if op_name == "mul":
            other_val = (
                other_operand.sample()
                if isinstance(other_operand, Parameter)
                else other_operand
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
