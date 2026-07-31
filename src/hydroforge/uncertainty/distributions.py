"""
Probability distributions for uncertainty quantification.

This module provides a hierarchy of probability distribution classes used to
represent uncertain model parameters. Continuous, discrete, categorical and
deterministic (Dirac delta) distributions are supported through a common
interface defined by the :class:`Distribution` abstract base class.

Each distribution exposes

- a nominal (deterministic) value,
- sampling from the distribution,
- inverse transform sampling via ``sample_from_unit()``,
- reduction to an equivalent deterministic Dirac delta distribution, and
- serialization through ``to_dict()``.

The module also provides helper enumerations describing distribution
properties, categorical conversion utilities, and helper functions for
querying distribution characteristics.

Notes
-----
The ``sample_from_unit()`` interface is designed for sampling algorithms that
operate in the unit interval, such as Latin Hypercube Sampling (LHS),
Sobol sequences, and other quasi-random sampling methods.
"""
from __future__ import annotations
import collections.abc
from typing import ClassVar, Literal, Sequence, TypeVar, Generic, Dict, Tuple, overload
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum, auto
import numpy as np
from scipy.stats import norm, uniform, randint

# Public API
__all__ = [
    "Distribution",
    "NormalDistribution",
    "UniformDistribution",
    "DiracDeltaDistribution",
    "DiscreteNormalDistribution",
    "DiscreteUniformDistribution",
    "DiscreteHistogramDistribution",
    "CategoricalNormalDistribution",
    "CategoricalUniformDistribution",
    "CategoricalHistogramDistribution",
    "is_bounded",
    "is_continuous",
    "is_discrete",
    "is_categorical",
    "is_binary"
]

T = TypeVar("T")

def is_iterable(value) -> bool:
    """
    Check if the value is an iterable.

    Parameters
    ----------
    value : any
        The value to check.

    Returns
    -------
    bool
        True if the value is an iterable and not a scalar, False otherwise.
    """
    # Exclude numpy scalars and Python scalars
    if np.isscalar(value):
        return False
    # Exclude strings and bytes if needed
    if isinstance(value, (str, bytes)):
        return False
    return isinstance(value, collections.abc.Iterable)
    
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
    CONTINUOUS = auto()   # real-valued (float)
    DISCRETE = auto()     # integer-valued (int)
    CATEGORICAL = auto()  # non-numeric categories
    BINARY = auto()
    OTHER = auto()        # undefined, e.g. for DiracDelta generic class.


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
    CATEGORICAL = auto() # General categorical
    BERNOULLI = auto()   # Binary / Boolean
    # Dirac
    DIRAC = auto()
    # Other
    OTHER = auto()


class DistributionBoundsType(Enum):
    """Enumeration defining the bound types for probability distributions.
    Attributes
    ----------
    BOUNDED : auto
        Distribution with both lower and upper bounds.
    SEMI_BOUNDED : auto
        Distribution with either a lower bound or an upper bound.
    UNBOUNDED : auto
        Distribution with no bounds (extends to infinity in both directions).
    """
    BOUNDED = auto()      # [a, b]
    SEMI_BOUNDED = auto() # [a, inf) or (-inf, a]
    UNBOUNDED = auto()    # (-inf, inf)


@dataclass(frozen = True)
class DistributionProperties:
    """
    A dataclass that encapsulates the key properties of a probability distribution.

    This class stores metadata about a distribution including its family type,
    parameter bounds, and domain characteristics.

    Attributes
    ----------
    family : DistributionFamily
        The family or type of the probability distribution (e.g., Normal, Exponential).
    bounds_type : DistributionBoundsType
        The bounds or constraints on the distribution's parameters.
    domain : DistributionDomain
        The domain over which the distribution is defined (e.g., real numbers, positive reals).
    """
    family: DistributionFamily
    bounds_type: DistributionBoundsType
    domain: DistributionDomain


@dataclass
class Distribution(Generic[T], ABC):
    """
    Abstract base class for probability distributions.

    All probability distributions used by the uncertainty framework inherit
    from this class. Subclasses must define the distribution metadata through
    the :attr:`properties` class variable and implement methods for obtaining
    the nominal value, inverse-transform sampling, and reduction to a
    deterministic Dirac delta distribution.

    Attributes
    ----------
    properties : ClassVar[DistributionProperties]
        Metadata describing the distribution family, bounds, and value domain.

    Notes
    -----
    Sampling is implemented using inverse transform sampling through
    :meth:`sample_from_unit`. The default implementation of :meth:`sample`
    generates uniform random values in ``[0, 1]`` and delegates the mapping
    to subclasses.
    """
    properties: ClassVar[DistributionProperties]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if not hasattr(cls, "properties"):
            raise TypeError(
                f"{cls.__name__} must define class variable `properties`"
            )

        if not isinstance(cls.properties, DistributionProperties):
            raise TypeError(
                f"{cls.__name__}.properties must be a DistributionProperties instance"
            )

    @property
    @abstractmethod
    def nominal_value(self) -> T:
        """Return the nominal (representative) value of the distribution."""

    @overload
    def sample(self, n_samples: Literal[1]) -> T: ...

    @overload
    def sample(self, n_samples: int) -> Sequence[T]: ...

    def sample(self, n_samples: int) -> Sequence[T] | T:
        """Random sampling via Uniform(0,1)."""
        if n_samples == 1:
            u = np.random.rand()
            return self.sample_from_unit(u)
        _unit_samples = np.random.rand(n_samples)
        return [self.sample_from_unit(u) for u in _unit_samples]

    @overload
    def sample_from_unit(self, u: float) -> T: ...
    
    @overload
    def sample_from_unit(self, u: Sequence[float]) -> Sequence[T]: ...
        
    @abstractmethod
    def sample_from_unit(self, u: Sequence[float] | float) -> Sequence[T] | T:
        """
        Map values from the unit interval to this distribution.

        This method performs inverse transform sampling by mapping one or more
        values from the interval ``[0, 1]`` to samples drawn from the distribution.
        It is intended for use by sampling techniques such as Latin Hypercube
        Sampling (LHS) and Sobol sampling.

        Parameters
        ----------
        u : float or Sequence[float]
            One or more values in the closed interval ``[0, 1]``.

        Returns
        -------
        T or Sequence[T]
            Sample(s) corresponding to the supplied probability values.
        """
        
    @abstractmethod
    def reduce(self) -> DiracDeltaDistribution:
        """Collapse to Dirac Delta distribution (returns itself).""" 
        
    def to_dict(self, recursive: bool = False) -> dict:
        """
        Convert the distribution to a dictionary.

        Parameters
        ----------
        recursive : bool, default=False
            If True, recursively convert nested dataclasses, containers, and
            dictionaries into serializable objects.

        Returns
        -------
        dict
            Dictionary representation of the distribution.

        Notes
        -----
        Dataclass fields whose metadata contains
        ``{"serialize": False}`` are excluded from the output.
        """
        def convert(obj):
            if is_dataclass(obj):
                return {
                    f.name: convert(getattr(obj, f.name)) if recursive else getattr(obj, f.name)
                    for f in fields(obj)
                    if f.metadata.get("serialize", True)
                }
            if recursive and isinstance (obj, (list, tuple)):
                return type(obj)(convert(item) for item in obj)
            if recursive and isinstance(obj, dict):
                return {key: convert(value) for key, value in obj.items()}
            return obj
        return convert(self)


@dataclass
class CategoricalConversionMixin:
    """
    Mixin for categorical conversion methods.

    Provides mappings between forward (categorical to numerical index) and reverse
    (numerical index to categorical values) mappings and conversion methods.
    Used for numerical calculations in categorical distributions.
    """
    _cat_to_num: Dict[str, int] = field(init=False, repr=False)
    _num_to_cat: Dict[int, str] = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "_cat_to_num", {cat: i for i, cat in enumerate(self.categories)})
        object.__setattr__(self, "_num_to_cat", dict(enumerate(self.categories)))
    
    @staticmethod
    def _is_iterable(value) -> bool:
        """
        Check if the value is an iterable.

        Parameters
        ----------
        value : any
            The value to check.

        Returns
        -------
        bool
            True if the value is an iterable and not a scalar, False otherwise.
        """
        # Exclude numpy scalars and Python scalars
        if np.isscalar(value):
            return False
        # Exclude strings and bytes if needed
        if isinstance(value, (str, bytes)):
            return False
        return isinstance(value, collections.abc.Iterable)

    def cat_to_num(self, cat_values: Sequence[str] | str) -> Sequence[int] | int:
        """Convert categorical values to numerical indices."""
        if not self._is_iterable(cat_values):
            return self._cat_to_num.get(cat_values, None)
        return [self._cat_to_num[cat] for cat in cat_values if cat in self._cat_to_num]

    def num_to_cat(self, num_values: Sequence[int] | int) -> Sequence[str] | str:
        """Convert numerical indices to categorical values."""
        if not self._is_iterable(num_values):
            return self._num_to_cat.get(int(num_values), None)
        return [self._num_to_cat[int(num)] for num in num_values if int(num) in self._num_to_cat]


@dataclass
class CategoricalNominalMixin:
    """Mixin for categorical nominal value retrieval."""
        
    @property
    def nominal_index(self) -> int:
        """Return the numeric index of the nominal category."""
        return self._cat_to_num[self.nominal_value]


@dataclass
class NormalDistribution(Distribution[float]):
    """
    Standard (Gaussian) distribution.

    Attributes
    ----------
    mean : float
        Mean of the normal distribution.
    std_dev : float
        Standard deviation of the normal distribution.
    """
    mean: float
    std_dev: float
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.NORMAL,
        bounds_type=DistributionBoundsType.UNBOUNDED,
        domain=DistributionDomain.CONTINUOUS
    )
    
    def __post_init__(self) -> None:
        """Ensure mean and std_dev are valid for normal distribution."""
        if self.std_dev <= 0:
            raise ValueError("Standard deviation must be positive for normal distribution")
    
    @property
    def nominal_value(self) -> float:
        """Return the mean as the nominal value."""
        return self.mean

    def reduce(self) -> ContinuousDiracDeltaDistribution:
        """Collapse the distribution to a Dirac Delta distribution."""
        return ContinuousDiracDeltaDistribution(value=self.nominal_value)

    @overload
    def sample_from_unit(self, u: float) -> float: ...
    
    @overload
    def sample_from_unit(self, u: Sequence[float]) -> Sequence[float]: ...
    
    def sample_from_unit(self, u: float | Sequence[float]) -> float | Sequence[float]:
        """Return a draw from this distribution given a value in the unit interval.

        Maps a probability value `u` in [0, 1] to a variate from the distribution.

        Parameters
        ----------
        u : float or Sequence[float]
            Value(s) in [0, 1].

        Returns
        -------
        float or Sequence[float]
            Random variate(s) from the distribution.
        """
        if isinstance(u, str):
            raise TypeError("u must be numeric, not str")
        arr = np.asarray(u, dtype=float)
        if np.any((arr < 0.0) | (arr > 1.0)):
            raise ValueError("All values in u must be in the range [0, 1]")
        vals = norm.ppf(arr, loc=self.mean, scale=self.std_dev)
        # Preserve scalar semantics for scalar input
        #return float(vals.item()) if vals.ndim == 0 else vals
        return float(vals) if vals.ndim == 0 else vals.astype(float).tolist()

@dataclass
class UniformDistribution(Distribution[float]):
    """
    Uniform distribution.

    Attributes
    ----------
    lower : int or float
        Lower bound of the uniform distribution.
    upper : int or float
        Upper bound of the uniform distribution.
    """
    lower: int | float
    upper: int | float
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.UNIFORM,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.CONTINUOUS
    )
    
    def __post_init__(self) -> None:
        """Ensure lower is less than upper for uniform distribution."""
        self.lower, self.upper = float(self.lower), float(self.upper)
        if self.lower >= self.upper:
            raise ValueError("Lower bound must be less than upper bound for uniform distribution")
    
    @property
    def nominal_value(self) -> float:
        """Return the midpoint as the nominal value."""
        return (self.lower + self.upper) / 2.0

    def reduce(self) -> ContinuousDiracDeltaDistribution:
        """Collapse the distribution to a Dirac Delta distribution."""
        return ContinuousDiracDeltaDistribution(value=self.nominal_value)

    @overload
    def sample_from_unit(self, u: float) -> float: ...
    
    @overload
    def sample_from_unit(self, u: Sequence[float]) -> Sequence[float]: ...
    
    def sample_from_unit(self, u: float | Sequence[float]) -> float | Sequence[float]:
        """Return a draw from this distribution given a value in the unit interval.

        Maps a probability value `u` in [0, 1] to a variate from the distribution.

        Parameters
        ----------
        u : float or Sequence[float]
            Value(s) in [0, 1].

        Returns
        -------
        float or Sequence[float]
            Random variate(s) from the distribution.
        """
        if isinstance(u, str):
            raise TypeError("u must be numeric, not str")
        arr = np.asarray(u, dtype=float)
        if np.any((arr < 0.0) | (arr > 1.0)):
            raise ValueError("All values in u must be in the range [0, 1]")
        samples = uniform.ppf(
            arr,
            loc=self.lower,
            scale=self.upper - self.lower,
        )
        return float(samples) if samples.ndim == 0 else samples.astype(float).tolist()


@dataclass
class DiracDeltaDistribution(Distribution[T], Generic[T]):
    """Generic Dirac Delta (degenerate) distribution."""

    value: T

    # Default properties; can be overridden in subclasses
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.OTHER,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.OTHER,
    )

    @property
    def nominal_value(self) -> T:
        return self.value
    
    def reduce(self) -> DiracDeltaDistribution:
        """Collapse to Dirac Delta distribution (returns itself)."""
        return self
    
    @overload
    def sample_from_unit(self, u: float) -> T: ...
    
    @overload
    def sample_from_unit(self, u: Sequence[float]) -> Sequence[T]: ...

    def sample_from_unit(self, u: float) -> T | Sequence[T]:
        """Sample from the distribution using a value from the unit interval [0, 1]."""
        if isinstance(u, str):
            raise TypeError("u must be a float or sequence of floats, not str")
        if not is_iterable(u):
            # Handles float, int, np.float64, etc.
            if not (0.0 <= float(u) <= 1.0):
                raise ValueError("Input u must be in the range [0, 1]")
            return self.value
        return [self.value for _ in u]


class ContinuousDiracDeltaDistribution(DiracDeltaDistribution[float]):
    """
    A continuous Dirac delta distribution.

    This distribution represents a point mass at a single location in continuous space.
    The Dirac delta distribution has all probability mass concentrated at a single point,
    making it useful for representing deterministic values in a probabilistic framework.

    The probability density function is zero everywhere except at the location parameter,
    where it is infinite, but integrates to 1 over any interval containing that point.

    Attributes
    ----------
    properties : ClassVar[DistributionProperties]
        Class-level distribution properties indicating this is a bounded
        continuous distribution in the DIRAC family.

    Notes
    -----
    Inherits from DiracDeltaDistribution[float], parameterized for continuous (float) values.
    """
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.DIRAC,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.CONTINUOUS,
    )


class CategoricalDiracDeltaDistribution(DiracDeltaDistribution[str]):
    """
    A Dirac delta distribution for categorical (string) values.

    This distribution represents a deterministic categorical value, where the
    probability mass is concentrated entirely at a single string value. It is
    the categorical equivalent of a point mass distribution.

    Attributes
    ----------
    properties : ClassVar[DistributionProperties]
        Distribution properties indicating this is a bounded,
        categorical distribution in the DIRAC family.

    Examples
    --------
    >>> dist = CategoricalDiracDeltaDistribution(value="cat_A")
    >>> dist.sample()
    'cat_A'
    """
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.DIRAC,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.CATEGORICAL,
    )

class DiscreteDiracDeltaDistribution(DiracDeltaDistribution[int]):
    """
    A Dirac delta distribution for discrete (integer) values.

    This distribution represents a deterministic discrete value, where the
    probability mass is concentrated entirely at a single integer value. It is
    the discrete equivalent of a point mass distribution.

    Attributes
    ----------
    properties : ClassVar[DistributionProperties]
        Distribution properties indicating this is a bounded,
        discrete distribution in the DIRAC family.

    Examples
    --------
    >>> dist = DiscreteDiracDeltaDistribution(value=2)
    >>> dist.sample()
    2
    """
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.DIRAC,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.DISCRETE,
    )


@dataclass
class DiscreteNormalDistribution(Distribution[int]):
    """
    Discrete normal distribution for numerical variables.

    Attributes
    ----------
    mean : int
        Mean of the discrete normal distribution (must be an integer).
    std_dev : float
        Standard deviation of the discrete normal distribution (must be positive).
    """
    mean: int
    std_dev: float
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.NORMAL,
        bounds_type=DistributionBoundsType.UNBOUNDED,
        domain=DistributionDomain.DISCRETE
    )
    
    def __post_init__(self) -> None:
        """Ensure mean is an integer for discrete normal distribution."""
        if isinstance(self.mean, float) and not self.mean.is_integer(): # pylint: disable=no-member 
            raise ValueError(f"Mean must be an integer or a float equivalent to an integer, got {self.mean}")
        object.__setattr__(self, "mean", int(self.mean))
        if self.std_dev <= 0:
            raise ValueError("Standard deviation must be positive for discrete normal distribution")

    @property
    def nominal_value(self) -> int:
        return int(self.mean)

    def reduce(self) -> DiscreteDiracDeltaDistribution:
        """Collapse the distribution to a Dirac Delta distribution."""
        return DiscreteDiracDeltaDistribution(value=self.nominal_value)

    @overload
    def sample_from_unit(self, u: float) -> int: ...
    
    @overload
    def sample_from_unit(self, u: Sequence[float]) -> Sequence[int]: ...

    def sample_from_unit(self, u: float | Sequence[float]) -> int | Sequence[int]:
        """Map u in [0,1] to an integer-valued normal draw."""
        if isinstance(u, str):
            raise TypeError("u must be numeric, not str")
        arr = np.asarray(u, dtype=float)
        if np.any((arr < 0.0) | (arr > 1.0)):
            raise ValueError("All values in u must be in the range [0, 1]")
        vals = norm.ppf(arr, loc=self.mean, scale=self.std_dev)
        out = np.rint(vals).astype(int)
        # return a Python scalar if input was scalar
        return out.item() if out.ndim == 0 else out


@dataclass
class DiscreteUniformDistribution(Distribution[int]):
    """
    Discrete uniform distribution for numerical variables.

    Attributes
    ----------
    lower : int
        Lower bound of the uniform discrete distribution.
    upper : int
        Upper bound of the uniform discrete distribution.
    """
    lower: int
    upper: int
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.UNIFORM,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.DISCRETE
    )
        
    def __post_init__(self) -> None:
        """Ensure bounds are integers for discrete uniform distribution."""
        if not all(isinstance(val, (int, float)) for val in (self.lower, self.upper)):
            raise ValueError("Bounds must be integers or floats equivalent to integers for discrete uniform distribution")
        self.lower, self.upper = int(self.lower), int(self.upper)
        if self.lower >= self.upper:
            raise ValueError("Lower bound must be less than upper bound for discrete uniform distribution")

    @property
    def nominal_value(self) -> int:
        return (int(self.lower) + int(self.upper)) // 2

    def reduce(self) -> DiscreteDiracDeltaDistribution:
        """Collapse the distribution to a Dirac Delta distribution."""
        return DiscreteDiracDeltaDistribution(value=self.nominal_value)

    @overload
    def sample_from_unit(self, u: float) -> int: ...
    
    @overload
    def sample_from_unit(self, u: Sequence[float]) -> Sequence[int]: ...

    def sample_from_unit(self, u: float | Sequence[float]) -> int | Sequence[int]:
        """Map u in [0,1] to a draw from discrete uniform distribution."""
        if isinstance(u, str):
            raise TypeError("u must be numeric, not str")
        arr = np.asarray(u, dtype=float)
        if np.any((arr < 0.0) | (arr > 1.0)):
            raise ValueError("All values in u must be in the range [0, 1]")
        vals = randint.ppf(arr, self.lower, self.upper + 1)
        out = vals.astype(int)
        # Return scalar for scalar input
        return out.item() if out.ndim == 0 else out


@dataclass
class DiscreteHistogramDistribution(Distribution[float]):
    """
    Histogram distribution for numerical variables.

    Attributes
    ----------
    values : Tuple[float, ...]
        Values for the discrete histogram distribution.
    probabilities : Tuple[float, ...]
        Probabilities for each value in the discrete histogram distribution.
    rtol : float
        Relative tolerance to which the sum of probabilities in a histogram is close to 1.0
    """
    values: Tuple[float, ...] = field(default_factory=tuple)
    probabilities: Tuple[float, ...] = field(default_factory=tuple)
    rtol: ClassVar[float] = 1e-4
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.OTHER,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.DISCRETE
    )

    def __post_init__(self) -> None:
        """Ensure values and probabilities are valid for discrete histogram distribution."""
        if not self.values:
            raise ValueError("Values must not be empty for discrete histogram distribution")
        if len(self.values) != len(self.probabilities):
            raise ValueError("Values and probabilities must have the same length")
        if not np.isclose(sum(self.probabilities), 1.0, rtol=self.rtol):
            raise ValueError("Probabilities must sum to 1 for discrete histogram distribution")

    @property
    def nominal_value(self) -> int:
        """Returns the category with the highest probability, or the middle category if all probabilities are equal."""
        # Check if all probabilities are (almost) equal
        if np.allclose(self.probabilities, self.probabilities[0]):
            # Return the middle category
            mid_idx = len(self.values) // 2
            return self.values[mid_idx]
        # Return the category with the highest probability
        max_index = np.argmax(self.probabilities)
        return self.values[max_index]

    def reduce(self) -> DiscreteDiracDeltaDistribution:
        """Collapse the distribution to a Dirac Delta distribution."""
        return DiscreteDiracDeltaDistribution(value=self.nominal_value)

    @overload
    def sample_from_unit(self, u: float) -> float: ...

    @overload
    def sample_from_unit(self, u: Sequence[float]) -> Sequence[float]: ...

    def sample_from_unit(self, u: float | Sequence[float]) -> float | Sequence[float]:
        """Map u in [0,1] to a draw from discrete histogram distribution."""
        if isinstance(u, str):
            raise TypeError("u must be numeric, not str")
        arr = np.asarray(u, dtype=float)
        if np.any((arr < 0.0) | (arr > 1.0)):
            raise ValueError("All values in u must be in the range [0, 1]")
        cdf = np.cumsum(self.probabilities)
        idx = np.searchsorted(cdf, arr, side="right")
        idx = np.clip(idx, 0, len(self.values) - 1)
        out = np.asarray(self.values)[idx]
        # Preserve scalar behavior if input was scalar
        return out.item() if out.ndim == 0 else out


@dataclass
class CategoricalNormalDistribution(
        CategoricalConversionMixin,
        CategoricalNominalMixin,
        Distribution[str]):
    """
    Normal distribution for categorical variables.

    This distribution is defined by a mean and standard deviation, and samples are drawn from a
    normal distribution with respect to the categories.

    Attributes
    ----------
    categories : Tuple[str, ...]
        Categories for the categorical variable.
    mean : float
        Mean of the normal distribution.
    std_dev : float
        Standard deviation of the normal distribution.
    nominal_category : str or None
        If provided, overrides the default nominal category to use this specific category.
    """
    categories: Tuple[str, ...] = field(default_factory=tuple)
    mean: float = 0.0
    std_dev: float = 1.0
    nominal_category: str | None = None
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.NORMAL,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.CATEGORICAL
    )
    
    def __post_init__(self) -> None:
        """Ensure categories are valid for categorical normal distribution."""
        if not self.categories:
            raise ValueError("Categories must not be empty for categorical normal distribution")
        if self.std_dev <= 0:
            raise ValueError("Standard deviation must be positive for categorical normal distribution")
        if self.nominal_category and self.nominal_category not in self.categories:
            raise ValueError(f"Nominal category '{self.nominal_category}' must be one of the categories: {self.categories}")
        # Call the mixin's __post_init__ to initialize _cat_to_num and _num_to_cat
        super().__post_init__()

    @property
    def nominal_value(self) -> str:
        """
        Return the nominal (most representative) category.

        Defaults to the middle category unless explicitly overridden.
        """
        if self.nominal_category is not None:
            return self.nominal_category

        return self.categories[len(self.categories) // 2]

    def reduce(self) -> CategoricalDiracDeltaDistribution:
        """Collapse the distribution to a Dirac Delta distribution."""
        return CategoricalDiracDeltaDistribution(value=self.nominal_value)

    @overload
    def sample_from_unit(self, u: float) -> str: ...

    @overload
    def sample_from_unit(self, u: Sequence[float]) -> Sequence[str]: ...

    def sample_from_unit(self, u: float | Sequence[float]) -> str | Sequence[str]:
        """Map u in [0,1] to a categorical draw via normal-shaped weighting."""
        if isinstance(u, str):
            raise TypeError("u must be numeric, not str")

        # build CDF of normal-shaped category weights
        indices = np.arange(len(self.categories))
        probs = np.exp(-0.5 * ((indices - self.mean) / self.std_dev) ** 2)
        probs /= probs.sum()
        cdf = np.cumsum(probs)
        arr = np.asarray(u, dtype=float)
        if np.any((arr < 0.0) | (arr > 1.0)):
            raise ValueError("All values in u must be in the range [0, 1]")
        idx = np.searchsorted(cdf, arr, side="right")
        idx = np.clip(idx, 0, len(self.categories) - 1)
        out = np.asarray(self.categories, dtype=object)[idx]
        # Preserve scalar behavior when input was scalar
        return out if np.isscalar(out) else out.tolist()


@dataclass
class CategoricalUniformDistribution(CategoricalConversionMixin, CategoricalNominalMixin, Distribution):
    """
    Uniform distribution for categorical variables.

    This distribution is defined by a set of categories and samples are drawn uniformly from these
    categories.

    Attributes
    ----------
    categories : Tuple[str, ...]
        Categories for the categorical variable.
    nominal_category : str or None
        If provided, overrides the default nominal category to use this specific category.
        By default, the middle category is used as the nominal value.
    """
    categories: Tuple[str, ...] = field(default_factory=tuple)
    nominal_category: str | None = None
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.UNIFORM,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.CATEGORICAL
    )
        
    def __post_init__(self) -> None:
        if not self.categories:
            raise ValueError(
                "Categories must not be empty for categorical uniform distribution")
        if self.nominal_category and self.nominal_category not in self.categories:
            raise ValueError(f"Nominal category '{self.nominal_category}' must be one of the categories: {self.categories}")
        # Call the mixin's __post_init__ to initialize _cat_to_num and _num_to_cat
        super().__post_init__()

    @property
    def nominal_value(self) -> str:
        """
        Return the nominal (most representative) category.

        By default, this is the middle category. If `nominal_category`
        is provided, it is used instead.
        """
        if self.nominal_category is not None:
            return self.nominal_category

        return self.categories[len(self.categories) // 2]

    def reduce(self) -> CategoricalDiracDeltaDistribution:
        """Collapse the distribution to a Dirac Delta distribution."""
        return CategoricalDiracDeltaDistribution(value=self.nominal_value)

    @overload
    def sample_from_unit(self, u: float) -> str: ...

    @overload
    def sample_from_unit(self, u: Sequence[float]) -> Sequence[str]: ...

    def sample_from_unit(self, u: float | Sequence[float]) -> str | list[str]:
        """Map u in [0,1] to a draw from uniform categorical distribution."""
        # Handle empty distribution early
        if not self.categories:
            return [] if not np.isscalar(u) and not isinstance(u, str) else ""
        if isinstance(u, str):
            raise TypeError("u must be numeric, not str")
        n = len(self.categories)
        arr = np.asarray(u, dtype=float)
        if np.any((arr < 0.0) | (arr > 1.0)):
            raise ValueError("All values in u must be in the range [0, 1]")
        idx = np.minimum((arr * n).astype(int), n - 1)
        out = np.asarray(self.categories, dtype=object)[idx]
        # Restore scalar semantics for scalar input
        return out if np.isscalar(u) else out.tolist()


@dataclass
class CategoricalHistogramDistribution(
        CategoricalConversionMixin, 
        CategoricalNominalMixin, 
        Distribution[str]):
    """
    Categorical distribution defined by an explicit probability mass function.

    This distribution assigns a probability to each category and performs
    sampling using inverse transform sampling. Probabilities are automatically
    normalized if necessary. The nominal category is the one with the highest
    probability unless explicitly overridden.

    Attributes
    ----------
    categories : Tuple[str, ...]
        Ordered collection of possible categorical values.
    probabilities : Tuple[float, ...]
        Probability assigned to each category. Automatically normalized to sum to 1.
    nominal_category : str or None
        Category to use as the nominal value. If None, uses the highest probability.
    """
    categories: Tuple[str, ...] = field(default_factory=tuple)
    probabilities: Tuple[float, ...] = field(default_factory=tuple)
    nominal_category: str | None = None
    properties: ClassVar[DistributionProperties] = DistributionProperties(
        family=DistributionFamily.OTHER,
        bounds_type=DistributionBoundsType.BOUNDED,
        domain=DistributionDomain.CATEGORICAL
    )
        
    def __post_init__(self) -> None:
        """Validate and normalize the distribution parameters."""
        if not self.categories:
            raise ValueError("Categories must not be empty for categorical histogram distribution")
        if len(self.categories) != len(self.probabilities):
            raise ValueError("Categories and probabilities must have the same length")
        if self.nominal_category and self.nominal_category not in self.categories:
            raise ValueError(f"Nominal category '{self.nominal_category}' must be one of the categories: {self.categories}")
        prob_sum = sum(self.probabilities)
        if prob_sum <= 0:
            raise ValueError("Probabilities must sum to a positive value")
        if not np.isclose(sum(self.probabilities), 1.0):
            self.probabilities = tuple(p / prob_sum for p in self.probabilities)
        self.categories = tuple(self.categories)
        self.probabilities = tuple(self.probabilities)
        # Call the mixin's __post_init__ to initialize _cat_to_num and _num_to_cat
        super().__post_init__()

    @property
    def nominal_value(self) -> str:
        """Return the nominal category (highest probability or explicit override)."""
        if self.nominal_category:
            return self.nominal_category
        index = int(np.argmax(self.probabilities))
        return self.categories[index]

    def reduce(self) -> CategoricalDiracDeltaDistribution:
        """Collapse to a deterministic distribution at the nominal category."""
        return CategoricalDiracDeltaDistribution(value=self.nominal_value)

    @overload
    def sample_from_unit(self, u: float) -> str: ...

    @overload
    def sample_from_unit(self, u: Sequence[float]) -> Sequence[str]: ...
    
    def sample_from_unit(self, u: float | Sequence[float]) -> str | list[str]:
        """
        Map values from the unit interval to categorical outcomes.
    
        Samples are generated using inverse transform sampling. The cumulative
        probability distribution is constructed from the category probabilities,
        and each value in ``u`` selects the corresponding category.
    
        Parameters
        ----------
        u : float or Sequence[float]
            One or more values in the closed interval ``[0, 1]``.
    
        Returns
        -------
        str or list of str
            Sampled category for scalar input, or a list of sampled categories
            for sequence input.
    
        Raises
        ------
        ValueError
            If any value in ``u`` lies outside the interval ``[0, 1]``.
        TypeError
            If a non-numeric scalar value is supplied.
        """
        if not self.categories:
            return [] if is_iterable(u) and not isinstance(u, str) else ""
        cdf = np.cumsum(self.probabilities)
        if not is_iterable(u) or isinstance(u, str):
            uf = float(u)
            if not (0.0 <= uf <= 1.0):
                raise ValueError("Input u must be in the range [0, 1]")
            idx = np.searchsorted(cdf, uf, side="right")
            idx = min(idx, len(self.categories) - 1)
            return self.categories[idx]

        arr = np.asarray(u, dtype=float)
        if np.any((arr < 0.0) | (arr > 1.0)):
            raise ValueError("All values in u must be in the range [0, 1]")
        idxs = np.searchsorted(cdf, arr, side="right")
        idxs = np.clip(idxs, 0, len(self.categories) - 1)
        return [self.categories[i] for i in idxs]


# -----------------------------------------
# Helper functions for distributions
# -----------------------------------------

def is_bounded(distribution: Distribution) -> bool:
    """Check if a distribution is bounded."""
    return distribution.properties.bounds_type == DistributionBoundsType.BOUNDED


def is_continuous(distribution: Distribution) -> bool:
    """Check if a distribution is continuous."""
    return distribution.properties.domain == DistributionDomain.CONTINUOUS


def is_discrete(distribution: Distribution) -> bool:
    """Check if a distribution is discrete."""
    return distribution.properties.domain == DistributionDomain.DISCRETE


def is_categorical(distribution: Distribution) -> bool:
    """Check if a distribution is categorical."""
    return distribution.properties.domain == DistributionDomain.CATEGORICAL


def is_binary(distribution: Distribution) -> bool:
    """Check if a distribution is binary."""
    return distribution.properties.domain == DistributionDomain.BINARY


if __name__ == "__main__":
    pass
