"""Data model definitions for EPANET INP file sections.

This module defines the strongly typed dataclass representations used to model
the sections of an EPANET INP file. Each class corresponds to a specific INP
record type (e.g., junctions, pipes, demands, curves, and options) and provides
a structured interface for accessing and modifying network data.

Most record types inherit from :class:`ListConversionMixin`, which implements
generic serialization to and deserialization from the list-based token format
used by the INP parser. Numeric fields are represented using
:class:`decimal.Decimal` to preserve the precision of values read from and
written to EPANET input files.

Variable-length records, such as title lines, patterns, control statements, and
configuration options, are represented by lightweight container classes that
store the original token sequence without imposing a fixed schema.

Notes
-----
The order of dataclass fields matches the order of tokens in the corresponding
EPANET INP record, allowing generic conversion routines to construct objects
directly from parsed token lists and serialize them back without requiring
record-specific logic.
"""

from __future__ import annotations
from typing import Tuple, Any
from dataclasses import dataclass
from decimal import Decimal
from .mixins import ListConversionMixin, AutoDecimalMixin


@dataclass(slots=True)
class TitleLine:
    """A single line of the ``[TITLE]`` section.

    Attributes
    ----------
    items : tuple of str
        Whitespace-separated tokens making up the title line.
    """

    items: Tuple[str, ...]

    def __str__(self) -> str:
        """Format the title line as a single string.

        Returns
        -------
        str
            Tokens joined with spaces.
        """
        return " ".join(self.items)

    @classmethod
    def from_list(cls, items: list[Any]) -> TitleLine:
        """Create a ``TitleLine`` from a list of tokens.

        Parameters
        ----------
        items : list of Any
            Tokens making up the title line.

        Returns
        -------
        TitleLine
            New instance wrapping the tokens.
        """
        return cls(tuple(items))

    def to_list(self) -> list:
        """Convert to list format for serialization.

        Returns
        -------
        list
            List representation of the title tokens.
        """
        return list(self.items)


@dataclass(slots=True)
class Junction(AutoDecimalMixin, ListConversionMixin):
    """Junction node in the water network.

    Attributes
    ----------
    id : str
        Junction identifier.
    elevation : Decimal
        Elevation above the reference datum.
    base_demand : Decimal
        Base demand value.
    demand_pattern : str
        Associated demand pattern ID. Empty when unset.
    """

    id: str
    elevation: Decimal
    base_demand: Decimal
    demand_pattern: str = ""


@dataclass(slots=True)
class Reservoir(AutoDecimalMixin, ListConversionMixin):
    """Reservoir node with a fixed head.

    Attributes
    ----------
    id : str
        Reservoir identifier.
    head : Decimal
        Hydraulic head (fixed).
    pattern : str
        Optional head pattern ID. Empty when unset.
    """

    id: str
    head: Decimal
    pattern: str = ""


@dataclass(slots=True)
class Tank(AutoDecimalMixin, ListConversionMixin):
    """Storage tank node with a variable water level.

    Attributes
    ----------
    id : str
        Tank identifier.
    elevation : Decimal
        Bottom elevation.
    init_level : Decimal
        Initial water level.
    min_level : Decimal
        Minimum water level.
    max_level : Decimal
        Maximum water level.
    diameter : Decimal
        Tank diameter.
    min_vol : Decimal
        Minimum volume.
    """

    id: str
    elevation: Decimal
    init_level: Decimal
    min_level: Decimal
    max_level: Decimal
    diameter: Decimal
    min_vol: Decimal


@dataclass(slots=True)
class Pipe(AutoDecimalMixin, ListConversionMixin):
    """Pipe link connecting two nodes.

    Attributes
    ----------
    id : str
        Pipe identifier.
    start_node : str
        Starting node ID.
    end_node : str
        Ending node ID.
    length : Decimal
        Pipe length.
    diameter : Decimal
        Pipe diameter.
    roughness : Decimal
        Roughness coefficient.
    minor_loss : Decimal
        Minor loss coefficient.
    status : str
        Pipe status (``OPEN``/``CLOSED``).
    """

    id: str
    start_node: str
    end_node: str
    length: Decimal
    diameter: Decimal
    roughness: Decimal
    minor_loss: Decimal
    status: str


@dataclass(slots=True)
class Pump(AutoDecimalMixin, ListConversionMixin):
    """Pump link that adds energy to the system.

    Attributes
    ----------
    id : str
        Pump identifier.
    start_node : str
        Starting node ID.
    end_node : str
        Ending node ID.
    keyword : str
        Pump parameter keyword (e.g. ``HEAD``, ``POWER``).
    value : str
        Parameter value or curve ID. Kept as ``str`` since it may reference
        either a numeric value or a curve identifier.
    """

    id: str
    start_node: str
    end_node: str
    keyword: str
    value: str


@dataclass(slots=True)
class Valve(AutoDecimalMixin, ListConversionMixin):
    """Valve link for flow/pressure control.

    Attributes
    ----------
    id : str
        Valve identifier.
    start_node : str
        Starting node ID.
    end_node : str
        Ending node ID.
    diameter : Decimal
        Valve diameter.
    type : str
        Valve type (``PRV``, ``PSV``, ``PBV``, ``FCV``, ``TCV``, ``GPV``).
    setting : str
        Valve setting value. Kept as ``str`` since ``GPV`` valves reference a
        curve ID rather than a numeric setting.
    minor_loss : Decimal
        Minor loss coefficient.
    """

    id: str
    start_node: str
    end_node: str
    diameter: Decimal
    type: str
    setting: str
    minor_loss: Decimal = Decimal("0.0")


@dataclass(slots=True)
class Demand(AutoDecimalMixin, ListConversionMixin):
    """Demand specification for a junction.

    Attributes
    ----------
    node_id : str
        Junction ID.
    base_demand : Decimal
        Base demand value.
    demand_pattern : str
        Demand pattern ID.
    category : str
        Demand category. Empty when unset.
    """

    node_id: str
    base_demand: Decimal
    demand_pattern: str
    category: str = ""


@dataclass(slots=True)
class Pattern(ListConversionMixin):
    """Time pattern with a variable number of multipliers.

    Attributes
    ----------
    items : tuple
        Pattern ID followed by multiplier values.
    """

    items: tuple

    @property
    def name(self) -> str:
        """Get the pattern identifier.

        Returns
        -------
        str
            Pattern ID (first item).
        """
        return self.items[0]

    @classmethod
    def from_list(cls, item_list: list) -> Pattern:
        """Create a ``Pattern`` from a list.

        Parameters
        ----------
        items : list
            Pattern ID followed by multiplier values.

        Returns
        -------
        Pattern
            New instance.
        """
        return cls(tuple(item_list))

    def to_list(self) -> list:
        """Convert to list format for serialization.

        Returns
        -------
        list
            List representation of the pattern.
        """
        return list(self.items)


@dataclass(slots=True)
class Curve(AutoDecimalMixin, ListConversionMixin):
    """Data curve with an x-y value pair.

    Attributes
    ----------
    id : str
        Curve identifier.
    x_value : Decimal
        X-coordinate value.
    y_value : Decimal
        Y-coordinate value.
    """

    id: str
    x_value: Decimal
    y_value: Decimal


@dataclass(slots=True)
class Control:
    """Simple control statement.

    Attributes
    ----------
    items : tuple
        Control statement tokens.
    """

    items: tuple

    @classmethod
    def from_list(cls, items: list) -> Control:
        """Create a ``Control`` from a list of tokens.

        Parameters
        ----------
        items : list
            Control statement tokens.

        Returns
        -------
        Control
            New instance.
        """
        return cls(tuple(items))

    def to_list(self) -> list:
        """Convert to list format for serialization.

        Returns
        -------
        list
            List representation of the control statement.
        """
        return list(self.items)


@dataclass(slots=True)
class Coordinate(AutoDecimalMixin, ListConversionMixin):
    """Node spatial coordinates.

    Attributes
    ----------
    node_id : str
        Node identifier.
    x_coord : Decimal
        X-coordinate.
    y_coord : Decimal
        Y-coordinate.
    """

    node_id: str
    x_coord: Decimal
    y_coord: Decimal


@dataclass(slots=True)
class TokenizedLine:
    """Generic whitespace-tokenized data line with a variable token count.

    Several INP sections (``ENERGY``, ``REACTIONS``, ``TIMES``, ``REPORT``,
    ``OPTIONS``, ``BACKDROP``) contain lines whose token count depends on the
    leading keyword(s) (e.g. ``GLOBAL EFFICIENCY 75`` vs. ``DURATION
    24:00``). Rather than forcing these onto a fixed set of fields, such
    lines are stored verbatim as a tuple of tokens.

    Attributes
    ----------
    items : tuple of str
        Whitespace-separated tokens making up the line.
    """

    items: tuple

    @property
    def keyword(self) -> str:
        """First token of the line, typically the option/parameter keyword.

        Returns
        -------
        str
            The leading token.
        """
        return self.items[0]

    @property
    def value(self) -> tuple:
        """Remaining tokens after the keyword.

        Returns
        -------
        tuple of str
            All tokens following the keyword.
        """
        return self.items[1:]

    @classmethod
    def from_list(cls, items: list) -> "TokenizedLine":
        """Create an instance from a list of tokens.

        Parameters
        ----------
        items : list
            Whitespace-separated tokens.

        Returns
        -------
        TokenizedLine
            New instance wrapping the tokens.
        """
        return cls(tuple(items))

    def to_list(self) -> list:
        """Convert to list format for serialization.

        Returns
        -------
        list
            List representation of the tokens.
        """
        return list(self.items)


@dataclass(slots=True)
class Energy(TokenizedLine):
    """Energy analysis option line (e.g. ``GLOBAL EFFICIENCY 75``)."""


@dataclass(slots=True)
class Reaction(TokenizedLine):
    """Water quality reaction parameter line (e.g. ``ORDER BULK 1``)."""


@dataclass(slots=True)
class Time(TokenizedLine):
    """Simulation time parameter line (e.g. ``DURATION 24:00``)."""


@dataclass(slots=True)
class Report(TokenizedLine):
    """Report output option line (e.g. ``STATUS YES``)."""


@dataclass(slots=True)
class Option(TokenizedLine):
    """Hydraulic/quality analysis option line (e.g. ``UNITS GPM``)."""


@dataclass(slots=True)
class Backdrop(TokenizedLine):
    """Network map backdrop setting line (e.g. ``DIMENSIONS 0 0 100 100``)."""
