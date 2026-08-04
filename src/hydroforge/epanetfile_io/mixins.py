"""Utilities for working with dataclass-based EPANET model objects.

This module provides helper functions and mixins for representing EPANET
objects as strongly typed dataclasses while supporting conversion to and from
the list-based token format used by EPANET INP files.

The :class:`ListConversionMixin` provides generic ``to_list()`` and
``from_list()`` methods that automatically convert between raw string tokens
and the numeric types (``int``, ``float``, and ``Decimal``) declared on
dataclass fields.

The :class:`AutoDecimalMixin` maintains type consistency by automatically
converting values assigned to fields annotated as :class:`decimal.Decimal`
into ``Decimal`` instances. This applies both during object construction and
when attributes are modified after creation, allowing numeric values (e.g.
``str``, ``int``, or ``float``) to be assigned directly while ensuring that
``Decimal`` fields always store ``Decimal`` objects.

Notes
-----
The :class:`ListConversionMixin` assumes that dataclass fields appear in the
same order as the corresponding values in the EPANET INP file. Input lists may
be shorter than the number of dataclass fields provided the omitted trailing
fields define default values.

The :class:`AutoDecimalMixin` performs conversion using
``Decimal(str(value))`` to preserve the expected decimal representation of
numeric values and avoid the precision issues associated with binary
floating-point numbers.
"""
from dataclasses import fields
from typing import Type, TypeVar, ClassVar, Any, get_type_hints
from decimal import Decimal

# Type variable bound to the mixin, used for ``ListConversionMixin.from_list``.
_ItemT = TypeVar('_ItemT', bound='ListConversionMixin')

# Numeric types eligible for automatic string <-> number conversion.
_NUMERIC_TYPES = (float, int, Decimal)


def _format_numeric_as_string(value: float | int | Decimal) -> str:
    """Format a numeric value for EPANET INP output.

    Parameters
    ----------
    value : float, int, or Decimal
        Numeric value to format.

    Returns
    -------
    str
        String representation of ``value``. Floats with no fractional part
        (e.g. ``100.0``) are rendered without the trailing ``.0`` to keep
        output close to typical EPANET formatting.
    """
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def trim_trailing_empty_strings(items: list[Any]) -> list[Any]:
    """Remove trailing empty strings from a list in-place.

    Parameters
    ----------
    items : list[Any]
        List to trim.

    Returns
    -------
    list[Any]
        The same list after removing trailing empty strings.
    """
    while items and items[-1] == "":
        items.pop()
    return items


class ListConversionMixin:
    """Mixin providing automatic list conversion for dataclasses.

    Implements the :class:`Item` protocol with generic ``to_list()`` and
    ``from_list()`` methods that work with any dataclass, automatically
    converting between the raw string tokens used in INP/JSON files and the
    numeric (``float``/``int```/``Decimal``) types declared on the dataclass 
    fields.
    """

    def to_list(self) -> list:
        """Convert dataclass fields to list format.

        Returns
        -------
        list
            Field values in declaration order. Numeric fields are formatted
            back to strings via :func:`_format_numeric`.
        """
        out_list = [
            _format_numeric_as_string(value) if isinstance(value, _NUMERIC_TYPES)
            else value
            for value in (getattr(self, f.name) for f in fields(self))
        ]
        return trim_trailing_empty_strings(out_list)

    @classmethod
    def from_list(cls: Type[_ItemT], item_list: list) -> _ItemT:
        """Create an instance from a list of raw values.

        Parameters
        ----------
        item_list : list
            Raw values (typically strings) corresponding to the dataclass
            fields, in declaration order. May be shorter than the number of
            fields if the trailing fields declare defaults.

        Returns
        -------
        _ItemT
            New instance with fields populated from ``item_list``, coercing
            values into ``float``/``int``/``Decimal`` where the corresponding 
            field is annotated as such.
        """
        # ``get_type_hints`` resolves string annotations (e.g. when the
        # defining module uses ``from __future__ import annotations``) back
        # into actual type objects, unlike ``dataclasses.fields()[i].type``
        # which would otherwise yield the unresolved annotation string.
        type_hints = get_type_hints(cls)
        converted = [
            type_hints[f.name](raw)
            if type_hints[f.name] in _NUMERIC_TYPES and not isinstance(raw, type_hints[f.name])
            else raw
            for f, raw in zip(fields(cls), item_list)
        ]
        return cls(*converted)


class AutoDecimalMixin:
    """Automatically cast assigned values to Decimal."""
    __decimal_fields__: ClassVar[frozenset[str] | None] = None

    def __setattr__(self, name: str, value):
        decimal_fields = self.__class__.__decimal_fields__

        if decimal_fields is None:
            hints = get_type_hints(self.__class__)
            decimal_fields = frozenset(
                field_name
                for field_name, typ in hints.items()
                if typ is Decimal
            )
            self.__class__.__decimal_fields__ = decimal_fields

        if (
            name in decimal_fields
            and value is not None
            and not isinstance(value, Decimal)
        ):
            value = Decimal(str(value))

        super().__setattr__(name, value)