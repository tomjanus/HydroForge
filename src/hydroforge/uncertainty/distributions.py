"""Probability distributions for uncertainty quantification.

This module provides a hierarchy of probability distribution classes used to
represent uncertain model parameters. Continuous, discrete, categorical and
deterministic (Dirac delta) distributions are supported through a common
interface defined by the :class:`Distribution` abstract base class.
The public :class:`Distribution` interface separates three concepts:

* ``nominal_value`` is one representative scalar value.
* ``sample`` and ``sample_from_unit`` return NumPy arrays due to sampling being
  vectorised.
* ``cdf`` always returns a NumPy ``float64`` array whose shape matches the input.

Each distribution exposes

- a nominal (deterministic) value,
- sampling from the distribution,
- inverse transform sampling via ``sample_from_unit()``,
- reduction to an equivalent deterministic Dirac delta distribution, and
- serialization through ``to_dict()``.
- cumulative distribution function (CDF) evaluation.

CDF evaluation distinguishes between theoretical and empirical evaluation.
A theoretical CDF is used by default. For distributions without a closed-form
or otherwise implemented theoretical CDF, callers may explicitly request an
empirical approximation with ``empirical=True``.

The module also provides helper enumerations describing distribution
properties, categorical conversion utilities, and helper functions for
querying distribution characteristics.This module defines the probability-distribution objects used by the uncertainty
quantification framework.

Notes
-----

The ``sample_from_unit()`` interface is designed for sampling algorithms that
operate in the unit interval, such as Latin Hypercube Sampling (LHS),
Sobol sequences, and other quasi-random sampling methods.

The empirical CDF is estimated from samples generated through the same
inverse-transform mechanism used by the distribution. A local NumPy random
generator is used when ``random_state`` is supplied, so empirical results can
be made reproducible without changing NumPy's global random state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum, auto
from typing import Any, ClassVar, Generic, Sequence, TypeAlias, TypeVar, overload

import numpy as np
from numpy.typing import NDArray
from scipy.stats import norm, randint, uniform

from .common import TheoreticalCDFAbsent
from ..auxiliary import get_logger

__all__ = [
    "Distribution",
    "DistributionChecker",
    "DistributionDomain",
    "DistributionFamily",
    "DistributionBoundsType",
    "DistributionProperties",
    "TheoreticalCDFAbsent",
    "NormalDistribution",
    "UniformDistribution",
    "DiracDeltaDistribution",
    "ContinuousDiracDeltaDistribution",
    "DiscreteDiracDeltaDistribution",
    "CategoricalDiracDeltaDistribution",
    "DiscreteNormalDistribution",
    "DiscreteUniformDistribution",
    "DiscreteHistogramDistribution",
    "CategoricalNormalDistribution",
    "CategoricalUniformDistribution",
    "CategoricalHistogramDistribution",
]


# ``ValueT`` describes the scalar value represented by a distribution.
ValueT = TypeVar("ValueT")
DiscreteValueT = TypeVar("DiscreteValueT", int, float)

Numeric: TypeAlias = int | float | np.integer[Any] | np.floating[Any]
CDFInput: TypeAlias = Numeric | Sequence[Numeric] | NDArray[Any] | str | Sequence[str]
CDFResult: TypeAlias = NDArray[np.float64]
UnitInput: TypeAlias = float | Sequence[float] | NDArray[np.float64]


logger = get_logger(__name__)


class DistributionDomain(Enum):
    """Enumeration defining the domain types for probability distributions.

    This enum categorizes distributions based on the type of values they can represent,
    which is essential for proper distribution selection and validation.

    Attributes
    ----------
    CONTINUOUS : auto
        Distribution domain for real-valued (float) random variables.
        Examples: Normal, Exponential, Beta distributions.
    DISCRETE : auto
        Distribution domain for integer-valued (int) random variables.
        Examples: Poisson, Binomial, Geometric distributions.
    CATEGORICAL : auto
        Distribution domain for non-numeric categorical variables.
        Examples: Categorical, Multinomial distributions.
    BINARY : auto
        Distribution domain for binary (two-state) variables.
        Examples: Bernoulli, Binary classification outcomes.
    """

    CONTINUOUS = auto()  # real-valued (float)
    DISCRETE = auto()  # integer-valued (int)
    CATEGORICAL = auto()  # non-numeric categories
    BINARY = auto()
    OTHER = auto()  # undefined, e.g. for DiracDelta generic class.


class DistributionFamily(Enum):
    """Enumeration defining various families of probability distributions.
    Attributes
    ----------
    NORMAL : auto
        Normal (Gaussian) distribution.
    UNIFORM : auto
        Uniform distribution.
    LOGNORMAL : auto
        Log-normal distribution.
    TRIANGULAR : auto
        Triangular distribution.
    BETA : auto
        Beta distribution.
    GAMMA : auto
        Gamma distribution.
    POISSON : auto
        Poisson distribution.
    BINOMIAL : auto
        Binomial distribution.
    GEOETRIC : auto
        Geometric distribution.
    CATEGORICAL : auto
        General categorical distribution.
    BERNOULLI : auto
        Bernoulli (binary) distribution.
    OTHER : auto
        Other or unspecified distribution.
    """

    # Continuous
    NORMAL = auto()
    UNIFORM = auto()
    LOGNORMAL = auto()
    TRIANGULAR = auto()
    BETA = auto()
    GAMMA = auto()
    # Discrete
    POISSON = auto()
    BINOMIAL = auto()
    GEOETRIC = auto()
    # Categorical
    CATEGORICAL = auto()  # General categorical
    BERNOULLI = auto()  # Binary / Boolean
    # Dirac
    DIRAC = auto()
    # Other
    OTHER = auto()


class DistributionBoundsType(Enum):
    """Enumeration defining the bound types for probability distributions.

    BOUNDED : auto
        Distribution with both lower and upper bounds.
    SEMI_BOUNDED : auto
        Distribution with either a lower bound or an upper bound.
    UNBOUNDED : auto
        Distribution with no bounds (extends to infinity in both directions).
    """

    BOUNDED = auto()  # [a, b]
    SEMI_BOUNDED = auto()  # [a, inf) or (-inf, a]
    UNBOUNDED = auto()  # (-inf, inf)


@dataclass(frozen=True)
class DistributionProperties:
    """Metadata describing a probability distribution.

    Parameters
    ----------
    family : DistributionFamily
        Family of the distribution.
    bounds_type : DistributionBoundsType
        Whether the distribution is bounded, semi-bounded, or unbounded.
    domain : DistributionDomain
        Value domain of the distribution.
    """

    family: DistributionFamily
    bounds_type: DistributionBoundsType
    domain: DistributionDomain


@dataclass
class Distribution(Generic[ValueT], ABC):
    """Abstract base class for probability distributions.

    ``ValueT`` describes the scalar type returned by :attr:`nominal_value`.
    Sampling is intentionally typed independently from ``ValueT`` because
    samples are NumPy arrays and their NumPy dtype cannot be expressed safely
    as ``NDArray[ValueT]``.  Concrete distributions therefore provide precise
    sample dtypes where useful, while the generic base interface uses
    ``NDArray[Any]``.

    The public ``cdf`` method always returns a ``float64`` NumPy array,
    including for scalar input.  Thus a scalar input produces a zero-dimensional
    array rather than a Python scalar.

    Subclasses must provide :attr:`properties`, :attr:`nominal_value`,
    :meth:`sample_from_unit`, :meth:`reduce`, and :meth:`_theoretical_cdf`.

    Parameters
    ----------
    properties : ClassVar[DistributionProperties]
        Metadata describing the distribution, including its family, bounds type, and domain.

    Notes
    -----
    Sampling is implemented using inverse transform sampling through
    :meth:`sample_from_unit`. The default implementation of :meth:`sample`
    generates uniform random values in ``[0, 1]`` and delegates the mapping
    to subclasses.
    """

    properties: ClassVar[DistributionProperties]
    _empirical_cache: dict[tuple[int, Any], NDArray[Any]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Validate the required distribution metadata on subclass creation.

        Parameters
        ----------
        **kwargs : Any
            Keyword arguments forwarded to ``ABC.__init_subclass__``.

        Raises
        ------
        TypeError
            If the subclass does not define a valid ``properties`` attribute.
        """
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "properties"):
            raise TypeError(f"{cls.__name__} must define class variable `properties`")
        if not isinstance(cls.properties, DistributionProperties):
            raise TypeError(
                f"{cls.__name__}.properties must be a DistributionProperties instance"
            )

    def sample(self, n_samples: int = 1) -> NDArray[Any]:
        """Draw random samples using inverse-transform sampling.

        Parameters
        ----------
        n_samples : int, default=1
            Number of samples to draw.  The returned array has shape
            ``(n_samples,)``.

        Returns
        -------
        NDArray[Any]
            One-dimensional array containing the sampled values.  The concrete
            distribution determines the NumPy dtype.

        Raises
        ------
        ValueError
            If ``n_samples`` is not positive.
        TypeError
            If ``n_samples`` is not an integer.
        """
        if not isinstance(n_samples, (int, np.integer)):
            raise TypeError("n_samples must be an integer")
        if n_samples <= 0:
            raise ValueError("n_samples must be greater than zero")
        unit_samples = np.random.random(int(n_samples))
        return self.sample_from_unit(unit_samples)

    def cdf(
        self,
        x: CDFInput,
        *,
        empirical: bool = False,
        n_samples: int = 10_000,
        random_state: int | np.random.Generator | None = None,
    ) -> CDFResult:
        """Evaluate the cumulative distribution function (CDF).

        Parameters
        ----------
        x : CDFInput
            Point or points at which the CDF is evaluated.
        empirical : bool, default=False
            If ``False``, evaluate the theoretical CDF.  If ``True``, estimate
            the CDF from inverse-transform samples.
        n_samples : int, default=10_000
            Number of samples used for empirical estimation.
        random_state : int, numpy.random.Generator, or None, default=None
            Seed or random generator used for empirical estimation.

        Returns
        -------
        CDFResult
            ``float64`` NumPy array with the same shape as the input.  Scalar
            input produces a zero-dimensional array.

        Raises
        ------
        TheoreticalCDFAbsent
            If a theoretical CDF is unavailable and ``empirical=False``.
        ValueError
            If ``n_samples`` is not positive.
        """
        if empirical:
            return self._empirical_cdf(
                x,
                n_samples=n_samples,
                random_state=random_state,
            )
        return self._theoretical_cdf(x)

    def _get_cached_empirical_samples(
        self,
        n_samples: int,
        random_state: int | np.random.Generator | None,
    ) -> NDArray[Any]:
        """Return sorted samples used by empirical CDF evaluation.

        Parameters
        ----------
        n_samples : int
            Number of samples to generate.
        random_state : int, numpy.random.Generator, or None
            Seed or generator used to generate the samples.

        Returns
        -------
        NDArray[Any]
            One-dimensional sorted sample array.

        Raises
        ------
        ValueError
            If ``n_samples`` is not positive.
        """
        if n_samples <= 0:
            raise ValueError("n_samples must be greater than zero")
        cache_key = _empirical_cache_key(n_samples, random_state)
        if cache_key not in self._empirical_cache:
            rng = (
                random_state
                if isinstance(random_state, np.random.Generator)
                else np.random.default_rng(random_state)
            )
            unit_samples = rng.random(int(n_samples))
            sampled = self.sample_from_unit(unit_samples)
            self._empirical_cache[cache_key] = np.sort(sampled)
        return self._empirical_cache[cache_key]

    def _empirical_cdf(
        self,
        x: CDFInput,
        *,
        n_samples: int,
        random_state: int | np.random.Generator | None,
    ) -> CDFResult:
        """Estimate the CDF from sorted inverse-transform samples.

        Parameters
        ----------
        x : CDFInput
            Point or points at which the CDF is evaluated.
        n_samples : int
            Number of samples used in the empirical estimate.
        random_state : int, numpy.random.Generator, or None
            Seed or generator used for sample generation.

        Returns
        -------
        CDFResult
            Empirical CDF values as a ``float64`` NumPy array matching the
            shape of ``x``.

        Raises
        ------
        TypeError
            If the sampled values are not numerically ordered.
        """
        sorted_samples = self._get_cached_empirical_samples(
            n_samples,
            random_state,
        )
        x_array = np.asarray(x)
        if sorted_samples.dtype.kind not in "iuf":
            raise TypeError(
                "Empirical numerical CDF requires ordered numeric samples; "
                f"{type(self).__name__} produces {sorted_samples.dtype}."
            )
        flat_x = x_array.reshape(-1)
        indices = np.searchsorted(sorted_samples, flat_x, side="right")
        result = indices / len(sorted_samples)
        return np.asarray(result, dtype=np.float64).reshape(x_array.shape)

    def to_dict(self, recursive: bool = False) -> dict[str, Any]:
        """Convert distribution parameters to a dictionary.

        Only constructor (``init=True``) fields are included, so the result is
        the set of document arguments that would rebuild the distribution.
        Internal-state fields (``init=False``, such as empirical-sample caches
        and category lookup tables) and fields opting out via
        ``field(metadata={"serialize": False})`` are always excluded.

        Parameters
        ----------
        recursive : bool, default=False
            If ``True``, recursively convert nested dataclasses, sequences, and
            dictionaries.  If ``False``, only the top-level dataclass is
            converted.

        Returns
        -------
        dict[str, Any]
            Dictionary representation of the distribution.
        """

        def convert(obj: Any) -> Any:
            if is_dataclass(obj):
                return {
                    item.name: (
                        convert(getattr(obj, item.name))
                        if recursive
                        else getattr(obj, item.name)
                    )
                    for item in fields(obj)
                    if item.init and item.metadata.get("serialize", True)
                }
            if recursive and isinstance(obj, (list, tuple)):
                return type(obj)(convert(item) for item in obj)
            if recursive and isinstance(obj, dict):
                return {key: convert(value) for key, value in obj.items()}
            return obj

        return convert(self)

    @property
    @abstractmethod
    def nominal_value(self) -> ValueT:
        """Return the scalar nominal value represented by the distribution.

        Returns
        -------
        ValueT
            Representative deterministic value.  This is deliberately a scalar,
            unlike the vectorised output of :meth:`sample`.
        """
        raise NotImplementedError(
            "Subclasses must implement the `nominal_value` property."
        )

    @abstractmethod
    def sample_from_unit(self, u: UnitInput) -> NDArray[Any]:
        """Transform values from the unit interval into distribution samples.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in the closed interval ``[0, 1]``.  Input shape is preserved.

        Returns
        -------
        NDArray[Any]
            Samples with the same shape as ``u``.  The concrete distribution
            determines the NumPy dtype.

        Raises
        ------
        ValueError
            If any value lies outside ``[0, 1]``.
        TypeError
            If the input is not numeric.
        """
        raise NotImplementedError(
            "Subclasses must implement the `sample_from_unit` method."
        )

    @abstractmethod
    def reduce(self) -> DiracDeltaDistribution[ValueT]:
        """Reduce the distribution to a deterministic Dirac distribution.

        Returns
        -------
        DiracDeltaDistribution[ValueT]
            Dirac distribution centred on :attr:`nominal_value`.
        """
        raise NotImplementedError("Subclasses must implement the `reduce` method.")

    @abstractmethod
    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Evaluate the exact theoretical CDF.

        Parameters
        ----------
        x : CDFInput
            Point or points at which the CDF is evaluated.

        Returns
        -------
        CDFResult
            ``float64`` NumPy array matching the shape of ``x``.

        Raises
        ------
        TheoreticalCDFAbsent
            If no theoretical CDF is defined for the distribution.
        """


@dataclass
class CategoricalConversionMixin:
    """
    Stores mappings between forward (categorical to numerical index) and reverse
    (numerical index to categorical values) and enables bi-directional
    conversions between category labels and integer indices.

    Used for numerical calculations withcategorical distributions.
    """

    _cat_to_num: dict[str, int] = field(init=False, repr=False)
    _num_to_cat: dict[int, str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Build category-to-index lookup tables after dataclass initialisation."""
        categories = getattr(self, "categories", ())
        object.__setattr__(
            self,
            "_cat_to_num",
            {category: index for index, category in enumerate(categories)},
        )
        object.__setattr__(
            self,
            "_num_to_cat",
            dict(enumerate(categories)),
        )

    @overload
    def cat_to_num(self, cat_values: str) -> NDArray[np.int64]: ...

    @overload
    def cat_to_num(self, cat_values: Sequence[str]) -> NDArray[np.int64]: ...

    def cat_to_num(self, cat_values: str | Sequence[str]) -> NDArray[np.int64]:
        """Convert category labels to integer indices.

        Parameters
        ----------
        cat_values : str or Sequence[str]
            One category label or a sequence of category labels.

        Returns
        -------
        NDArray[np.int64]
            Array of integer category indices.  A scalar category produces a
            zero-dimensional array; a sequence preserves its one-dimensional
            shape.  Unknown categories are represented by ``-1``.
        """
        if isinstance(cat_values, str):
            values = [cat_values]
            scalar = True
        else:
            values = list(cat_values)
            scalar = False

        indices = np.asarray(
            [self._cat_to_num.get(value, -1) for value in values],
            dtype=np.int64,
        )
        return indices[0:1].reshape(()) if scalar else indices

    @overload
    def num_to_cat(self, num_values: int) -> NDArray[np.object_]: ...

    @overload
    def num_to_cat(
        self, num_values: Sequence[int] | NDArray[Any]
    ) -> NDArray[np.object_]: ...

    def num_to_cat(
        self,
        num_values: int | Sequence[int] | NDArray[Any],
    ) -> NDArray[np.object_]:
        """Convert integer category indices to category labels.

        Parameters
        ----------
        num_values : int, Sequence[int], or NDArray
            One category index or multiple category indices.

        Returns
        -------
        NDArray[np.object_]
            Array of category labels with the same shape as ``num_values``.
            Unknown indices are represented by an empty string.
        """
        arr = np.asarray(num_values)
        flat = arr.reshape(-1)
        categories = [self._num_to_cat.get(int(index), "") for index in flat]
        return np.asarray(categories, dtype=object).reshape(arr.shape)

    def _categorical_cdf(
        self,
        x: CDFInput,
        probabilities: NDArray[np.float64],
    ) -> CDFResult:
        """Evaluate a categorical CDF using the declared category order.

        Parameters
        ----------
        x : CDFInput
            Category label or labels at which the CDF is evaluated.
        probabilities : NDArray[np.float64]
            Probability assigned to each category.

        Returns
        -------
        CDFResult
            ``float64`` CDF values matching the shape of ``x``.
        """
        cumulative = np.cumsum(probabilities, dtype=np.float64)
        x_array = np.asarray(x, dtype=object)
        flat_x = x_array.reshape(-1)
        result = np.empty(flat_x.shape, dtype=np.float64)

        for index, value in enumerate(flat_x):
            category_index = self._cat_to_num.get(str(value))
            result[index] = (
                0.0 if category_index is None else cumulative[category_index]
            )

        return result.reshape(x_array.shape)

    def _empirical_categorical_cdf(
        self,
        x: CDFInput,
        *,
        n_samples: int,
        random_state: int | np.random.Generator | None,
        probabilities: NDArray[np.float64],
    ) -> CDFResult:
        """Estimate a categorical CDF by sampling the categorical PMF.

        Parameters
        ----------
        x : CDFInput
            Category label or labels at which the CDF is evaluated.
        n_samples : int
            Number of samples used in the empirical estimate.
        random_state : int, numpy.random.Generator, or None
            Seed or generator used for sample generation.
        probabilities : NDArray[np.float64]
            Probability assigned to each category.

        Returns
        -------
        CDFResult
            Empirical CDF values matching the shape of ``x``.

        Raises
        ------
        ValueError
            If ``n_samples`` is not positive.
        """
        if n_samples <= 0:
            raise ValueError("n_samples must be greater than zero")

        # The CDF result depends on ``x``, so the cache stores the drawn
        # category indices (which depend only on ``n_samples`` and
        # ``random_state``) under the same key scheme as the numeric path.
        # ``_empirical_cache`` is declared on the Distribution base class.
        cache: dict[tuple[int, Any], NDArray[Any]] = getattr(self, "_empirical_cache")
        cache_key = _empirical_cache_key(n_samples, random_state)
        indices = cache.get(cache_key)
        if indices is None:
            rng = (
                random_state
                if isinstance(random_state, np.random.Generator)
                else np.random.default_rng(random_state)
            )
            unit_samples = rng.random(int(n_samples))
            cumulative = np.cumsum(probabilities, dtype=np.float64)
            drawn = np.searchsorted(cumulative, unit_samples, side="right")
            indices = np.clip(drawn, 0, len(self._num_to_cat) - 1)
            cache[cache_key] = indices

        x_array = np.asarray(x, dtype=object)
        flat_x = x_array.reshape(-1)
        result = np.empty(flat_x.shape, dtype=np.float64)

        for index, value in enumerate(flat_x):
            category_index = self._cat_to_num.get(str(value))
            result[index] = (
                0.0
                if category_index is None
                else float(np.mean(indices <= category_index))
            )

        return result.reshape(x_array.shape)


@dataclass
class CategoricalNominalMixin:
    """Provide access to the integer index of the nominal category."""

    @property
    def nominal_index(self) -> int:
        """Return the integer index of :attr:`nominal_value`.

        Returns
        -------
        int
            Index of the nominal category in ``categories``.
        """
        return getattr(self, "_cat_to_num")[getattr(self, "nominal_value")]


@dataclass
class NormalDistribution(Distribution[float]):
    """Normal (Gaussian) distribution over real-valued outcomes.

    Parameters
    ----------
    mean : float
        Mean of the distribution.
    std_dev : float
        Standard deviation. Must be positive.
    """

    mean: float
    std_dev: float
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.NORMAL,
        bounds_type=DistributionBoundsType.UNBOUNDED,
        domain=DistributionDomain.CONTINUOUS,
    )

    def __post_init__(self) -> None:
        """Validate distribution parameters."""
        if self.std_dev <= 0:
            raise ValueError(
                "Standard deviation must be positive for normal distribution"
            )

    @property
    def nominal_value(self) -> float:
        """Return the mean as the nominal value.

        Returns
        -------
        float
            Distribution mean.
        """
        return self.mean

    def reduce(self) -> ContinuousDiracDeltaDistribution:
        """Reduce the distribution to a continuous Dirac distribution.

        Returns
        -------
        ContinuousDiracDeltaDistribution
            Dirac distribution centred on the mean.
        """
        return ContinuousDiracDeltaDistribution(value=self.nominal_value)

    def sample_from_unit(self, u: UnitInput) -> NDArray[np.float64]:
        """Transform unit-interval values through the normal quantile function.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in ``[0, 1]``.

        Returns
        -------
        NDArray[np.float64]
            Normal-distributed values with the same shape as ``u``.
        """
        arr = _validate_unit_input(u)
        return np.asarray(
            norm.ppf(arr, loc=self.mean, scale=self.std_dev),
            dtype=np.float64,
        )

    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Evaluate the exact normal CDF.

        Parameters
        ----------
        x : CDFInput
            Real-valued evaluation point or points.

        Returns
        -------
        CDFResult
            ``float64`` CDF values matching the input shape.
        """
        return np.asarray(
            norm.cdf(x, loc=self.mean, scale=self.std_dev),
            dtype=np.float64,
        )


@dataclass
class UniformDistribution(Distribution[float]):
    """Continuous uniform distribution on a finite interval.

    Parameters
    ----------
    lower : float
        Lower bound, inclusive.
    upper : float
        Upper bound, exclusive in the distribution's standard continuous
        interpretation. Must be greater than ``lower``.
    """

    lower: float
    upper: float
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.UNIFORM,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.CONTINUOUS,
    )

    def __post_init__(self) -> None:
        """Validate and normalise distribution bounds."""
        self.lower = float(self.lower)
        self.upper = float(self.upper)
        if self.lower >= self.upper:
            raise ValueError(
                "Lower bound must be less than upper bound for uniform distribution"
            )

    @property
    def nominal_value(self) -> float:
        """Return the midpoint of the interval.

        Returns
        -------
        float
            Midpoint ``(lower + upper) / 2``.
        """
        return (self.lower + self.upper) / 2.0

    def reduce(self) -> ContinuousDiracDeltaDistribution:
        """Reduce the distribution to a continuous Dirac distribution.

        Returns
        -------
        ContinuousDiracDeltaDistribution
            Dirac distribution centred on the interval midpoint.
        """
        return ContinuousDiracDeltaDistribution(value=self.nominal_value)

    def sample_from_unit(self, u: UnitInput) -> NDArray[np.float64]:
        """Transform unit-interval values through the uniform quantile function.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in ``[0, 1]``.

        Returns
        -------
        NDArray[np.float64]
            Uniform-distributed values with the same shape as ``u``.
        """
        arr = _validate_unit_input(u)
        return np.asarray(
            uniform.ppf(arr, loc=self.lower, scale=self.upper - self.lower),
            dtype=np.float64,
        )

    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Evaluate the exact uniform CDF.

        Parameters
        ----------
        x : CDFInput
            Real-valued evaluation point or points.

        Returns
        -------
        CDFResult
            ``float64`` CDF values matching the input shape.
        """
        return np.asarray(
            uniform.cdf(x, loc=self.lower, scale=self.upper - self.lower),
            dtype=np.float64,
        )


@dataclass
class DiracDeltaDistribution(Distribution[ValueT], Generic[ValueT]):
    """Generic deterministic point-mass distribution.

    Parameters
    ----------
    value : ValueT
        Deterministic value represented by the distribution.
    """

    value: ValueT
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.OTHER,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.OTHER,
    )

    @property
    def nominal_value(self) -> ValueT:
        """Return the deterministic value.

        Returns
        -------
        ValueT
            Stored point-mass value.
        """
        return self.value

    def reduce(self) -> DiracDeltaDistribution[ValueT]:
        """Return this distribution unchanged.

        Returns
        -------
        DiracDeltaDistribution[ValueT]
            This deterministic distribution.
        """
        return self

    def sample_from_unit(self, u: UnitInput) -> NDArray[Any]:
        """Return the deterministic value for every unit-interval input.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in ``[0, 1]``. Only the input shape is used.

        Returns
        -------
        NDArray[Any]
            Array filled with :attr:`value`, with the same shape as ``u``.
            The concrete dtype follows ``value``.
        """
        arr = _validate_unit_input(u)
        return np.full(arr.shape, self.value)

    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Reject generic theoretical CDF evaluation.

        Parameters
        ----------
        x : CDFInput
            Evaluation point or points. The argument is unused because a
            generic Dirac distribution may contain values without an ordering.

        Raises
        ------
        TheoreticalCDFAbsent
            Always, because ordering is not defined for arbitrary ``ValueT``.
        """
        raise TheoreticalCDFAbsent(
            f"A theoretical CDF is not defined generically for {type(self).__name__}."
        )


@dataclass
class ContinuousDiracDeltaDistribution(DiracDeltaDistribution[float]):
    """Deterministic Dirac distribution over real-valued outcomes.

    Parameters
    ----------
    value : float
        Deterministic value.
    """

    value: float
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.DIRAC,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.CONTINUOUS,
    )

    def sample_from_unit(self, u: UnitInput) -> NDArray[np.float64]:
        """Return the deterministic floating-point value for every input.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in ``[0, 1]``.

        Returns
        -------
        NDArray[np.float64]
            Array filled with ``value`` and matching the input shape.
        """
        arr = _validate_unit_input(u)
        return np.full(arr.shape, self.value, dtype=np.float64)

    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Evaluate the exact CDF of a continuous point mass.

        Parameters
        ----------
        x : CDFInput
            Real-valued evaluation point or points.

        Returns
        -------
        CDFResult
            ``1.0`` where ``x >= value`` and ``0.0`` otherwise.
        """
        arr = np.asarray(x, dtype=float)
        return np.asarray(arr >= self.value, dtype=np.float64)


@dataclass
class CategoricalDiracDeltaDistribution(DiracDeltaDistribution[str]):
    """Deterministic Dirac distribution over a categorical outcome.

    Parameters
    ----------
    value : str
        Deterministic category label.
    """

    value: str
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.DIRAC,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.CATEGORICAL,
    )

    def sample_from_unit(self, u: UnitInput) -> NDArray[np.object_]:
        """Return the deterministic category for every input.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in ``[0, 1]``.

        Returns
        -------
        NDArray[np.object_]
            Object array filled with ``value`` and matching the input shape.
        """
        arr = _validate_unit_input(u)
        return np.full(arr.shape, self.value, dtype=object)

    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Reject theoretical categorical CDF evaluation without an order.

        Parameters
        ----------
        x : CDFInput
            Category label or labels.

        Raises
        ------
        TheoreticalCDFAbsent
            Always, because a categorical Dirac distribution requires an
            externally defined category order.
        """
        raise TheoreticalCDFAbsent(
            "Categorical CDF evaluation requires an ordered categorical domain."
        )

    def _empirical_cdf(
        self,
        x: CDFInput,
        *,
        n_samples: int,
        random_state: int | np.random.Generator | None,
    ) -> CDFResult:
        """Reject empirical categorical CDF evaluation without an order.

        Parameters
        ----------
        x : CDFInput
            Category label or labels.
        n_samples : int
            Requested empirical sample size.
        random_state : int, numpy.random.Generator, or None
            RNG seed or generator.

        Raises
        ------
        TheoreticalCDFAbsent
            Always, because the category order is undefined.
        """
        raise TheoreticalCDFAbsent(
            "An empirical CDF for categorical Dirac distribution requires category ordering."
        )


@dataclass
class DiscreteDiracDeltaDistribution(
    DiracDeltaDistribution[DiscreteValueT], Generic[DiscreteValueT]
):
    """Deterministic Dirac distribution over discrete numerical outcomes.

    Parameters
    ----------
    value : int or float
        Deterministic discrete value.
    """

    value: DiscreteValueT
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.DIRAC,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.DISCRETE,
    )

    def sample_from_unit(self, u: UnitInput) -> NDArray[Any]:
        """Return the deterministic value for every input.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in ``[0, 1]``.

        Returns
        -------
        NDArray[Any]
            Array filled with ``value`` and matching the input shape. The
            concrete NumPy dtype follows the type of ``value``.
        """
        arr = _validate_unit_input(u)
        return np.full(arr.shape, self.value)

    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Evaluate the exact CDF of a discrete point mass.

        Parameters
        ----------
        x : CDFInput
            Real-valued evaluation point or points.

        Returns
        -------
        CDFResult
            ``1.0`` where ``x >= value`` and ``0.0`` otherwise.
        """
        arr = np.asarray(x, dtype=float)
        return np.asarray(arr >= self.value, dtype=np.float64)


@dataclass
class DiscreteNormalDistribution(Distribution[int]):
    """Discretised normal distribution for integer-valued outcomes.

    Sampling applies the normal inverse CDF followed by rounding to the nearest
    integer.  The theoretical CDF uses the standard continuity correction.

    Parameters
    ----------
    mean : int
        Integer centre of the normal distribution.
    std_dev : float
        Standard deviation. Must be positive.
    """

    mean: int
    std_dev: float
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.NORMAL,
        bounds_type=DistributionBoundsType.UNBOUNDED,
        domain=DistributionDomain.DISCRETE,
    )

    def __post_init__(self) -> None:
        """Validate and normalise distribution parameters."""
        if isinstance(self.mean, float) and not self.mean.is_integer():
            raise ValueError(f"Mean must be an integer, got {self.mean}")
        self.mean = int(self.mean)
        if self.std_dev <= 0:
            raise ValueError("Standard deviation must be positive")

    @property
    def nominal_value(self) -> int:
        """Return the integer normal mean.

        Returns
        -------
        int
            Distribution mean.
        """
        return self.mean

    def reduce(self) -> DiscreteDiracDeltaDistribution[int]:
        """Reduce the distribution to an integer Dirac distribution.

        Returns
        -------
        DiscreteDiracDeltaDistribution
            Dirac distribution centred on ``mean``.
        """
        return DiscreteDiracDeltaDistribution(value=self.nominal_value)

    def sample_from_unit(self, u: UnitInput) -> NDArray[np.int64]:
        """Transform unit-interval values into integer samples.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in ``[0, 1]``.

        Returns
        -------
        NDArray[np.int64]
            Integer samples with the same shape as ``u``.
        """
        arr = _validate_unit_input(u)
        return np.rint(norm.ppf(arr, loc=self.mean, scale=self.std_dev)).astype(
            np.int64
        )

    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Evaluate the continuity-corrected discrete normal CDF.

        Parameters
        ----------
        x : CDFInput
            Integer or real-valued evaluation point or points.

        Returns
        -------
        CDFResult
            ``float64`` CDF values matching the input shape.
        """
        arr = np.asarray(x, dtype=float)
        result = norm.cdf(
            np.floor(arr) + 0.5,
            loc=self.mean,
            scale=self.std_dev,
        )
        return np.asarray(result, dtype=np.float64)


@dataclass
class DiscreteUniformDistribution(Distribution[int]):
    """Discrete uniform distribution over an inclusive integer interval.

    Parameters
    ----------
    lower : int
        Smallest possible integer.
    upper : int
        Largest possible integer. Must be greater than ``lower``.
    """

    lower: int
    upper: int
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.UNIFORM,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.DISCRETE,
    )

    def __post_init__(self) -> None:
        """Validate and normalise integer bounds."""
        self.lower = int(self.lower)
        self.upper = int(self.upper)
        if self.lower >= self.upper:
            raise ValueError("Lower bound must be less than upper bound")

    @property
    def nominal_value(self) -> int:
        """Return the midpoint integer of the range.

        Returns
        -------
        int
            Integer midpoint ``(lower + upper) // 2``.
        """
        return (self.lower + self.upper) // 2

    def reduce(self) -> DiscreteDiracDeltaDistribution:
        """Reduce the distribution to an integer Dirac distribution.

        Returns
        -------
        DiscreteDiracDeltaDistribution
            Dirac distribution centred on the nominal integer.
        """
        return DiscreteDiracDeltaDistribution(value=self.nominal_value)

    def sample_from_unit(self, u: UnitInput) -> NDArray[np.int64]:
        """Transform unit-interval values into integer uniform samples.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in ``[0, 1]``.

        Returns
        -------
        NDArray[np.int64]
            Integer samples with the same shape as ``u``.
        """
        arr = _validate_unit_input(u)
        return np.asarray(
            randint.ppf(arr, self.lower, self.upper + 1),
            dtype=np.int64,
        )

    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Evaluate the exact discrete uniform CDF.

        Parameters
        ----------
        x : CDFInput
            Integer or real-valued evaluation point or points.

        Returns
        -------
        CDFResult
            ``float64`` CDF values matching the input shape.
        """
        return np.asarray(
            randint.cdf(x, self.lower, self.upper + 1),
            dtype=np.float64,
        )


@dataclass
class DiscreteHistogramDistribution(Distribution[float]):
    """Discrete numerical distribution defined by values and probabilities.

    Parameters
    ----------
    values : tuple of float, default=()
        Distinct numerical outcomes.
    probabilities : tuple of float, default=()
        Non-negative probability weights associated with ``values``.
        Weights are normalised to sum to one.
    rtol : float, default=1e-4
        Relative tolerance for probability normalization.
    """

    values: tuple[float, ...] = field(default_factory=tuple)
    probabilities: tuple[float, ...] = field(default_factory=tuple)
    rtol: ClassVar[float] = 1e-4
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.OTHER,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.DISCRETE,
    )

    def __post_init__(self) -> None:
        """Validate, normalise, and sort histogram outcomes."""
        if not self.values:
            raise ValueError("Values must not be empty")
        if len(self.values) != len(self.probabilities):
            raise ValueError("Values and probabilities must have the same length")
        if any(probability < 0 for probability in self.probabilities):
            raise ValueError("Probabilities must be non-negative")
        probability_sum = float(sum(self.probabilities))
        if probability_sum <= 0:
            raise ValueError("Probabilities must sum to a positive value")
        if not np.isclose(probability_sum, 1.0, rtol=self.rtol):
            logger.warning(
                "Sum of probabilities is not 1.0 before normalization: %f",
                probability_sum,
            )

        probabilities = (
            tuple(probability / probability_sum for probability in self.probabilities)
            if not np.isclose(probability_sum, 1.0, rtol=self.rtol)
            else tuple(float(probability) for probability in self.probabilities)
        )

        order = np.argsort(np.asarray(self.values, dtype=float))
        self.values = tuple(float(self.values[index]) for index in order)
        self.probabilities = tuple(probabilities[index] for index in order)

    @property
    def nominal_value(self) -> float:
        """Return a representative outcome with the largest probability.

        For a uniform histogram, the middle sorted outcome is returned.

        Returns
        -------
        float
            Representative histogram value.
        """
        if np.allclose(self.probabilities, self.probabilities[0]):
            return self.values[len(self.values) // 2]
        return self.values[int(np.argmax(self.probabilities))]

    def reduce(self) -> DiscreteDiracDeltaDistribution[float]:
        """Reduce the histogram to a discrete Dirac distribution.

        Returns
        -------
        DiscreteDiracDeltaDistribution
            Dirac distribution centred on the nominal outcome.
        """
        return DiscreteDiracDeltaDistribution(value=self.nominal_value)

    def sample_from_unit(self, u: UnitInput) -> NDArray[np.float64]:
        """Transform unit-interval values using the histogram quantile function.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in ``[0, 1]``.

        Returns
        -------
        NDArray[np.float64]
            Histogram outcomes with the same shape as ``u``.
        """
        arr = _validate_unit_input(u)
        cumulative = np.cumsum(self.probabilities, dtype=np.float64)
        indices = np.clip(
            np.searchsorted(cumulative, arr, side="right"),
            0,
            len(self.values) - 1,
        )
        return np.asarray(self.values, dtype=np.float64)[indices]

    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Evaluate the exact empirical-histogram CDF.

        Parameters
        ----------
        x : CDFInput
            Numerical evaluation point or points.

        Returns
        -------
        CDFResult
            ``float64`` CDF values matching the input shape.
        """
        values = np.asarray(self.values, dtype=np.float64)
        cumulative = np.cumsum(self.probabilities, dtype=np.float64)
        arr = np.asarray(x, dtype=np.float64)
        indices = np.searchsorted(values, arr, side="right")
        result = np.where(
            indices == 0,
            0.0,
            cumulative[np.minimum(indices, len(cumulative)) - 1],
        )
        return np.asarray(result, dtype=np.float64)


@dataclass
class CategoricalNormalDistribution(
    CategoricalConversionMixin,
    CategoricalNominalMixin,
    Distribution[str],
):
    """
    An ordered categorical distribution whose probability mass follows a
    discretised Gaussian shape around the nominal category..

    Categories are ordered according to their position in ``categories``.
    Gaussian weights are assigned to these integer positions.

    Parameters
    ----------
    categories : tuple of str, default=()
        Ordered category labels.
    mean : int, default=0
        Gaussian centre in category-index space.
    spread : float, default=1.0
        Apread of the Gaussian-shaped probability mass in category-index space.
    nominal_category : str or None, default=None
        Nominal (centre) category around which the distribution is centred.
    """

    categories: tuple[str, ...] = field(default_factory=tuple)
    spread: float = 1.0
    nominal_category: str | None = None
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.NORMAL,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.CATEGORICAL,
    )

    def __post_init__(self) -> None:
        """Validate parameters and initialise category lookup tables."""
        if not self.categories:
            raise ValueError("Categories must not be empty")
        if self.spread <= 0:
            raise ValueError("Spread of the distribution must be positive")
        if (
            self.nominal_category is not None
            and self.nominal_category not in self.categories
        ):
            raise ValueError(
                f"Nominal category '{self.nominal_category}' not in"
                f" available categories: {self.categories}"
            )
        if self.nominal_category is None and len(self.categories) % 2 == 0:
            raise ValueError(
                "Nominal category is required for even number of categories"
            )
        super().__post_init__()

    @property
    def _nominal_index(self) -> int:
        """Return the index of the nominal category."""
        if self.nominal_category is None:
            return len(self.categories) // 2
        return self.categories.index(self.nominal_category)

    @property
    def nominal_value(self) -> str:
        """Return the explicit or central nominal category.

        Returns
        -------
        str
            Nominal category label.
        """
        return self.categories[self._nominal_index]

    def reduce(self) -> CategoricalDiracDeltaDistribution:
        """Reduce the distribution to a categorical Dirac distribution.

        Returns
        -------
        CategoricalDiracDeltaDistribution
            Dirac distribution centred on the nominal category.
        """
        return CategoricalDiracDeltaDistribution(value=self.nominal_value)

    def _probabilities(self) -> NDArray[np.float64]:
        """Calculate normal-shaped category probabilities.

        Returns
        -------
        NDArray[np.float64]
            Probability for each category, normalised to sum to one.
        """
        indices = np.arange(len(self.categories), dtype=np.intp)
        nominal_index = self._nominal_index
        probabilities = np.exp(-0.5 * ((indices - nominal_index) / self.spread) ** 2)
        return np.asarray(
            probabilities / probabilities.sum(),
            dtype=np.float64,
        )

    def sample_from_unit(self, u: UnitInput) -> NDArray[np.object_]:
        """Transform unit-interval values into categorical samples.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in ``[0, 1]``.

        Returns
        -------
        NDArray[np.object_]
            Category labels with the same shape as ``u``.
        """
        arr = _validate_unit_input(u)
        cumulative = np.cumsum(self._probabilities(), dtype=np.float64)
        indices = np.clip(
            np.searchsorted(cumulative, arr, side="right"),
            0,
            len(self.categories) - 1,
        )
        return np.asarray(self.categories, dtype=object)[indices]

    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Evaluate the theoretical categorical CDF.

        Parameters
        ----------
        x : CDFInput
            Category label or labels.

        Returns
        -------
        CDFResult
            Cumulative probabilities matching the input shape.
        """
        return self._categorical_cdf(x, self._probabilities())

    def _empirical_cdf(
        self,
        x: CDFInput,
        *,
        n_samples: int,
        random_state: int | np.random.Generator | None,
    ) -> CDFResult:
        """Estimate the categorical CDF empirically.

        Parameters
        ----------
        x : CDFInput
            Category label or labels.
        n_samples : int
            Number of samples used for the estimate.
        random_state : int, numpy.random.Generator, or None
            Seed or generator used for sample generation.

        Returns
        -------
        CDFResult
            Empirical cumulative probabilities matching the input shape.
        """
        return self._empirical_categorical_cdf(
            x,
            n_samples=n_samples,
            random_state=random_state,
            probabilities=self._probabilities(),
        )


@dataclass
class CategoricalUniformDistribution(
    CategoricalConversionMixin,
    CategoricalNominalMixin,
    Distribution[str],
):
    """Categorical distribution with equal probability for every category.

    Parameters
    ----------
    categories : tuple of str, default=()
        Ordered category labels.
    nominal_category : str or None, default=None
        Optional explicit nominal category.
    """

    categories: tuple[str, ...] = field(default_factory=tuple)
    nominal_category: str | None = None
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.UNIFORM,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.CATEGORICAL,
    )

    def __post_init__(self) -> None:
        """Validate parameters and initialise category lookup tables."""
        if not self.categories:
            raise ValueError("Categories must not be empty")
        if (
            self.nominal_category is not None
            and self.nominal_category not in self.categories
        ):
            raise ValueError(f"Nominal category '{self.nominal_category}' invalid")
        if self.nominal_category is None and len(self.categories) % 2 == 0:
            raise ValueError(
                "Nominal category is required for even number of categories"
            )
        super().__post_init__()

    @property
    def nominal_value(self) -> str:
        """Return the explicit or central nominal category.

        Returns
        -------
        str
            Nominal category label.
        """
        if self.nominal_category is not None:
            return self.nominal_category
        return self.categories[len(self.categories) // 2]

    def reduce(self) -> CategoricalDiracDeltaDistribution:
        """Reduce the distribution to a categorical Dirac distribution.

        Returns
        -------
        CategoricalDiracDeltaDistribution
            Dirac distribution centred on the nominal category.
        """
        return CategoricalDiracDeltaDistribution(value=self.nominal_value)

    def sample_from_unit(self, u: UnitInput) -> NDArray[np.object_]:
        """Transform unit-interval values into uniformly sampled categories.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in ``[0, 1]``.

        Returns
        -------
        NDArray[np.object_]
            Category labels with the same shape as ``u``.
        """
        arr = _validate_unit_input(u)
        n_categories = len(self.categories)
        indices = np.minimum(
            (arr * n_categories).astype(np.intp),
            n_categories - 1,
        )
        return np.asarray(self.categories, dtype=object)[indices]

    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Evaluate the theoretical categorical uniform CDF.

        Parameters
        ----------
        x : CDFInput
            Category label or labels.

        Returns
        -------
        CDFResult
            Cumulative probabilities matching the input shape.
        """
        probabilities = np.full(
            len(self.categories),
            1.0 / len(self.categories),
            dtype=np.float64,
        )
        return self._categorical_cdf(x, probabilities)

    def _empirical_cdf(
        self,
        x: CDFInput,
        *,
        n_samples: int,
        random_state: int | np.random.Generator | None,
    ) -> CDFResult:
        """Estimate the categorical uniform CDF empirically.

        Parameters
        ----------
        x : CDFInput
            Category label or labels.
        n_samples : int
            Number of samples used for the estimate.
        random_state : int, numpy.random.Generator, or None
            Seed or generator used for sample generation.

        Returns
        -------
        CDFResult
            Empirical cumulative probabilities matching the input shape.
        """
        probabilities = np.full(
            len(self.categories),
            1.0 / len(self.categories),
            dtype=np.float64,
        )
        return self._empirical_categorical_cdf(
            x,
            n_samples=n_samples,
            random_state=random_state,
            probabilities=probabilities,
        )


@dataclass
class CategoricalHistogramDistribution(
    CategoricalConversionMixin,
    CategoricalNominalMixin,
    Distribution[str],
):
    """Categorical distribution with explicitly specified PMF weights.

    The probabilities define the probability mass function (PMF) directly.
    They are normalised to sum to one during initialisation.

    The nominal category is inferred as the category with the highest
    probability. If multiple categories share the highest probability,
    the first category in ``categories`` is selected.

    Parameters
    ----------
    categories : tuple of str, default=()
        Ordered category labels. Their order defines the categorical CDF.
        Category labels must be unique.
    probabilities : tuple of float, default=()
        Non-negative probability weights corresponding to ``categories``.
        The weights are normalised to sum to one.
    rtol : float, default=1e-4
        Relative tolerance for checking if the sum of probabilities is close to 1.0.
    """

    categories: tuple[str, ...] = field(default_factory=tuple)
    probabilities: tuple[float, ...] = field(default_factory=tuple)
    rtol: ClassVar[float] = 1e-4
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.OTHER,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.CATEGORICAL,
    )

    def __post_init__(self) -> None:
        """Validate, normalise, and initialise category metadata."""
        self.categories = tuple(self.categories)
        self.probabilities = tuple(self.probabilities)
        if not self.categories:
            raise ValueError("Categories must not be empty")
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("Categories must be unique")
        if len(self.categories) != len(self.probabilities):
            raise ValueError("Categories and probabilities length mismatch")
        if not all(np.isfinite(probability) for probability in self.probabilities):
            raise ValueError("Probabilities must be finite")
        if any(probability < 0 for probability in self.probabilities):
            raise ValueError("Probabilities must be non-negative")
        probability_sum = float(np.sum(self.probabilities, dtype=np.float64))
        if not np.isclose(probability_sum, 1.0):
            logger.warning(
                "Sum of probabilities is not 1.0 before normalization: %f",
                probability_sum,
            )
        if not np.isfinite(probability_sum) or probability_sum <= 0:
            raise ValueError("Probabilities must sum to a positive finite value")
        self.probabilities = tuple(
            probability / probability_sum for probability in self.probabilities
        )
        super().__post_init__()

    @property
    def nominal_value(self) -> str:
        """Return the most probable category.

        If multiple categories share the maximum probability, the first
        category in ``categories`` is returned.

        Returns
        -------
        str
            Most probable category label.
        """
        return self.categories[int(np.argmax(self.probabilities))]

    def reduce(self) -> CategoricalDiracDeltaDistribution:
        """Reduce the distribution to a categorical Dirac distribution.

        Returns
        -------
        CategoricalDiracDeltaDistribution
            Dirac distribution centred on the most probable category.
        """
        return CategoricalDiracDeltaDistribution(value=self.nominal_value)

    def sample_from_unit(self, u: UnitInput) -> NDArray[np.object_]:
        """Transform unit-interval values using the categorical PMF.

        Parameters
        ----------
        u : float, Sequence[float], or NDArray[np.float64]
            Values in ``[0, 1]``.

        Returns
        -------
        NDArray[np.object_]
            Category labels with the same shape as ``u``.
        """
        arr = _validate_unit_input(u)
        cumulative = np.cumsum(self.probabilities, dtype=np.float64)
        indices = np.clip(
            np.searchsorted(cumulative, arr, side="right"),
            0,
            len(self.categories) - 1,
        )
        return np.asarray(self.categories, dtype=object)[indices]

    def _theoretical_cdf(self, x: CDFInput) -> CDFResult:
        """Evaluate the theoretical categorical histogram CDF.

        Parameters
        ----------
        x : CDFInput
            Category label or labels.

        Returns
        -------
        CDFResult
            Cumulative probabilities matching the input shape.
        """
        return self._categorical_cdf(
            x,
            np.asarray(self.probabilities, dtype=np.float64),
        )

    def _empirical_cdf(
        self,
        x: CDFInput,
        *,
        n_samples: int,
        random_state: int | np.random.Generator | None,
    ) -> CDFResult:
        """Estimate the categorical histogram CDF empirically.

        Parameters
        ----------
        x : CDFInput
            Category label or labels.

        n_samples : int
            Number of samples used for the estimate.

        random_state : int, numpy.random.Generator, or None
            Seed or generator used for sample generation.

        Returns
        -------
        CDFResult
            Empirical cumulative probabilities matching the input shape.
        """
        return self._empirical_categorical_cdf(
            x,
            n_samples=n_samples,
            random_state=random_state,
            probabilities=np.asarray(
                self.probabilities,
                dtype=np.float64,
            ),
        )


class DistributionChecker:
    """Utility methods for querying distribution metadata."""

    @staticmethod
    def is_bounded(distribution: Distribution[Any]) -> bool:
        """Check whether a distribution has finite bounds.

        Parameters
        ----------
        distribution : Distribution[Any]
            Distribution to inspect.

        Returns
        -------
        bool
            ``True`` when the distribution is marked as bounded.
        """
        return distribution.properties.bounds_type == DistributionBoundsType.BOUNDED

    @staticmethod
    def is_continuous(distribution: Distribution[Any]) -> bool:
        """Check whether a distribution has a continuous domain.

        Parameters
        ----------
        distribution : Distribution[Any]
            Distribution to inspect.

        Returns
        -------
        bool
            ``True`` when the distribution domain is continuous.
        """
        return distribution.properties.domain == DistributionDomain.CONTINUOUS

    @staticmethod
    def is_discrete(distribution: Distribution[Any]) -> bool:
        """Check whether a distribution has a discrete domain.

        Parameters
        ----------
        distribution : Distribution[Any]
            Distribution to inspect.

        Returns
        -------
        bool
            ``True`` when the distribution domain is discrete.
        """
        return distribution.properties.domain == DistributionDomain.DISCRETE

    @staticmethod
    def is_categorical(distribution: Distribution[Any]) -> bool:
        """Check whether a distribution has a categorical domain.

        Parameters
        ----------
        distribution : Distribution[Any]
            Distribution to inspect.

        Returns
        -------
        bool
            ``True`` when the distribution domain is categorical.
        """
        return distribution.properties.domain == DistributionDomain.CATEGORICAL

    @staticmethod
    def is_binary(distribution: Distribution[Any]) -> bool:
        """Check whether a distribution has a binary domain.

        Parameters
        ----------
        distribution : Distribution[Any]
            Distribution to inspect.

        Returns
        -------
        bool
            ``True`` when the distribution domain is binary.
        """
        return distribution.properties.domain == DistributionDomain.BINARY


def _empirical_cache_key(
    n_samples: int,
    random_state: int | np.random.Generator | None,
) -> tuple[int, int | None]:
    """Build the empirical-sample cache key for a draw configuration.

    Parameters
    ----------
    n_samples : int
        Number of samples in the draw.
    random_state : int, numpy.random.Generator, or None
        Seed or generator used for the draw.  ``Generator`` instances are
        mutable, so their identity is used in the key; this makes repeated CDF
        calls deterministic for a given generator object after the first call.
        Integer seeds and ``None`` are immutable.

    Returns
    -------
    tuple[int, int | None]
        Cache key ``(n_samples, state_key)``.
    """
    state_key: int | None
    if isinstance(random_state, (int, np.integer)) or random_state is None:
        state_key = int(random_state) if random_state is not None else None
    else:
        state_key = id(random_state)
    return (int(n_samples), state_key)


def _validate_unit_input(u: UnitInput) -> NDArray[np.float64]:
    """Convert and validate inverse-transform input values.

    Parameters
    ----------
    u : float, Sequence[float], or NDArray[np.float64]
        Values that must lie in the closed unit interval ``[0, 1]``.

    Returns
    -------
    NDArray[np.float64]
        Floating-point NumPy array with the same shape as the input.

    Raises
    ------
    ValueError
        If any value lies outside ``[0, 1]``.
    TypeError
        If the input cannot be converted to a floating-point array.
    """
    try:
        arr = np.asarray(u, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise TypeError("u must contain numeric values") from exc

    if np.any((arr < 0.0) | (arr > 1.0)):
        raise ValueError("All values in u must be in the range [0, 1]")

    return arr


if __name__ == "__main__":
    pass
