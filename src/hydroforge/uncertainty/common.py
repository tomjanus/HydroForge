"""
Type definitions and utility functions for value handling.

This module defines a collection of type aliases used throughout the uncertainty module
to represent scalar values, NumPy arrays, and categorical data in a consistent
manner. It also provides a small utility function for determining whether an
object should be treated as an array-like value.

The aliases distinguish between:

- Numeric scalars and arrays.
- Categorical scalars and arrays.
- Generic values that may be either numeric or categorical.

These aliases improve type checking, readability, and documentation while
remaining compatible with NumPy 2.0.
"""
from typing import TypeAlias, Union, Any, TypeVar
import collections.abc
import numpy as np
import numpy.typing as npt

# ---- Type aliases ----
# For compatibility with numpy2.0
NumpyFloat = np.float64 # instead of earlier np.float_

Scalar: TypeAlias = Union[int, float, np.int_, NumpyFloat]
Array: TypeAlias = Union[npt.NDArray[NumpyFloat], npt.NDArray[np.int_]]
CatScalar: TypeAlias = Any  # str, Enum, label
CatArray: TypeAlias = npt.NDArray[Any]
CatValue: TypeAlias = Union[CatScalar, CatArray]
NumValue: TypeAlias = Union[Scalar, Array]  # numeric values only
Value: TypeAlias = Union[Scalar, Array, CatValue]  # last Any for categorical cases


T = TypeVar("T", bound=Value)
S = TypeVar("S", bound=NumValue)
C = TypeVar("C", bound=CatValue)



def is_array_like(x: Any) -> bool:
    """
    Determine whether an object is array-like.

    An object is considered array-like if it is iterable but is not a
    string or bytes object. This includes Python collections such as
    lists and tuples as well as NumPy arrays.

    Parameters
    ----------
    x : Any
        Object to test.

    Returns
    -------
    bool
        ``True`` if ``x`` is iterable and not an instance of ``str`` or
        ``bytes``; otherwise ``False``.
    """
    return np.iterable(x) and not isinstance(x, (str, bytes))


def is_iterable(value: object) -> bool:
    """
    Check whether a value is an iterable and not a scalar.

    Parameters
    ----------
    value : object
        The value to check.

    Returns
    -------
    bool
        ``True`` when ``value`` is an iterable that is not a scalar, string,
        or bytes object.
    """
    # Exclude numpy scalars and Python scalars
    if np.isscalar(value):
        return False
    # Exclude strings and bytes if needed
    if isinstance(value, (str, bytes)):
        return False
    return isinstance(value, collections.abc.Iterable)


class TheoreticalCDFAbsent(NotImplementedError):
    """Raised when a theoretical CDF is not available for a distribution."""


class CDFNotAvailable(NotImplementedError):
    """Raised when a CDF is not available for a parameter or uncertainty model.
    
    This exception indicates that a CDF cannot be computed for a parameter because:
    - The underlying uncertainty model doesn't support CDF transformation, or
    - The parameter type (e.g., categorical) doesn't have a well-defined CDF
    
    This typically occurs when using stratified or advanced sampling methods that
    require CDF evaluation.
    """


if __name__ == "__main__":
    pass
