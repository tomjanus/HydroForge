"""EPANET network model wrapper.

This module provides a lightweight, in-memory wrapper for water distribution
network data using dataclasses for easy, named access to network components,
eliminating the need for index-based access into raw ``OrderedDict``/list
structures.

The wrapper :class:`EPANETNetworkModel` provides named access to network
components such as junctions, pipes, pumps and valves, making it easier to
inspect and modify the data without needing to remember section-specific
column indices. Both data retrieval and modification are supported through
intuitive methods, and the model can be converted back to the original
``OrderedDict``/list structure at any time.

This module only defines the in-memory data model (dataclasses, the generic
:class:`NetworkCollection` container and :class:`EPANETNetworkModel` itself).
Serialization to/from dictionaries and file I/O (JSON, EPANET INP) are the
responsibility of :mod:`hydroforge.epanetfile_io.model_io`, which keeps this
module focused solely on representing and manipulating network data already
in memory.

Notes
-----
The intent of this wrapper is to allow reading, modifying, and saving EPANET
INP files without depending on external simulation packages (e.g. WNTR): the
file is parsed into an ``OrderedDict`` of raw tokens, wrapped in typed,
mutable objects for convenient editing, and then serialized back to disk.
"""
from __future__ import annotations
from typing import (
    List, Any, Optional, TypeVar, Type, Protocol,
    NamedTuple, Tuple, ClassVar, Generic, Sequence, overload
)
from dataclasses import dataclass, field
from collections.abc import MutableSequence
from .components import (
    TitleLine, Junction, Reservoir, Tank, Pipe, Pump, Valve,
    Demand, Pattern, Curve, Control, Energy, Reaction, Time,
    Report, Option, Coordinate, Backdrop
)


# Type variable bound to the ``Item`` protocol, used for ``NetworkCollection[T]``.
T = TypeVar('T', bound='Item')


@dataclass(frozen=True, slots=True)
class FieldMapping:
    """Mapping between an INP dictionary key and a model attribute.
    
    Parameters
    ----------
    section : str
        Name of the INP section (e.g. ``'JUNCTIONS'``).
    attr_name : str
        Name of the attribute in :class:`EPANETNetworkModel`.
    item_type : type, optional
        Dataclass type of the network item (``Junction``, ``Pipe``, etc.).
    """
    section: str
    attr_name: str
    item_type: type | None = None


class Item(Protocol):
    """Protocol for items that can be converted to/from list format.

    All network item dataclasses must implement this protocol to support
    serialization and deserialization between list and object formats.
    """

    def to_list(self) -> list:
        """Convert the item to list format for serialization.

        Returns
        -------
        list
            List representation of the item's fields.
        """

    @classmethod
    def from_list(cls: Type[T], item_list: list) -> T:
        """Create an instance from a list of values.

        Parameters
        ----------
        item_list : list
            Values corresponding to the item's fields.

        Returns
        -------
        T
            New instance of the item type.
        """


# === Collection wrapper ===
class NetworkCollection(MutableSequence[T], Generic[T]):
    """Lazy-loading, generic collection of network items.

    The collection stores items internally in their serialized (list-based)
    representation and converts them to dataclass objects only when
    accessed. Converted objects are cached to avoid repeated
    deserialization, and are the single source of truth once created: later
    calls to :meth:`to_list` re-serialize from the (possibly mutated) cached
    objects rather than the original raw rows.

    Implements the ``MutableSequence`` protocol for list-like behavior,
    including indexing, slicing, appending, and deleting items. Supports
    both dataclass instances and raw list/tuple values for insertion.

    Parameters
    ----------
    item_type : type[T]
        Dataclass type implementing ``from_list()`` and ``to_list()``.
    data : Sequence[list[Any]], optional
        Initial serialized data. If omitted, an empty collection is
        created. Empty rows are discarded.
    """

    def __init__(
            self,
            item_type: Type[T],
            data: Sequence[list[Any]] | None = None
        ) -> None:
        """Initialize the collection.

        Parameters
        ----------
        item_type : type[T]
            Type of network item (``Junction``, ``Pipe``, etc.).
        data : Sequence[list[Any]], optional
            Raw serialized network data. Empty rows are discarded.
        """
        self._item_type = item_type
        self._data: list[list[Any]] = [list(row) for row in data if row] if data else []
        self._cache: dict[int, T] = {}

    @overload
    def __getitem__(self, index: slice) -> list[T]:
        ...
        
    def __getitem__(self, index: int | slice) -> T | list[T]:
        """Return one or more items.

        Parameters
        ----------
        index : int or slice
            Item index or slice.

        Returns
        -------
        T or list[T]
            Requested item or list of items.
        """
        if isinstance(index, slice):
            return [
                self._convert_item(ix_)
                for ix_ in range(*index.indices(len(self)))
            ]
        return self._convert_item(index)

    @overload
    def __setitem__(
        self,
        index: slice,
        value: Sequence[T | Sequence[Any]],
    ) -> None:
        ...

    def __setitem__(
        self,
        index: int | slice,
        value: T | Sequence[Any] | Sequence[T | Sequence[Any]],
    ) -> None:
        """Replace one or more items.

        Parameters
        ----------
        index : int or slice
            Position(s) to replace.
        value : T or sequence
            Replacement item(s).
        """
        if isinstance(index, slice):
            values = [
                item.to_list() if hasattr(item, "to_list") else list(item)
                for item in value
            ]
            self._data[index] = values
            self._cache.clear()
            return

        if hasattr(value, "to_list"):
            self._data[index] = value.to_list()
        else:
            self._data[index] = list(value)

        self._cache.pop(index, None)

    @overload
    def __delitem__(self, index: int) -> None:
        ...

    @overload
    def __delitem__(self, index: slice) -> None:
        ...

    def __delitem__(self, index: int | slice) -> None:
        """Delete one or more items.

        Parameters
        ----------
        index : int or slice
            Position(s) to delete.
        """
        del self._data[index]
        self._cache.clear()

    def __len__(self) -> int:
        """Return the number of items.

        Returns
        -------
        int
            Number of items in the collection.
        """
        return len(self._data)

    def insert(self, index: int, value: T | Sequence[Any]) -> None:
        """Insert an item.

        Parameters
        ----------
        index : int
            Insertion index.
        value : T or sequence
            Item to insert.
        """
        if hasattr(value, "to_list"):
            self._data.insert(index, value.to_list())
        else:
            self._data.insert(index, list(value))

        self._cache.clear()

    def _convert_item(self, index: int) -> T:
        """Return the cached item, converting and caching it if necessary.

        Parameters
        ----------
        index : int
            Position of the item within the internal raw data.

        Returns
        -------
        T
            Converted, cached dataclass instance.
        """
        if index not in self._cache:
            self._cache[index] = self._item_type.from_list(self._data[index])
        return self._cache[index]

    def to_list(self) -> list[list[Any]]:
        """Return the fully serialized representation.

        Materializes every item (converting and caching as needed) and
        re-serializes it, ensuring that in-place attribute modifications on
        previously converted items are correctly reflected in the output.

        Returns
        -------
        list[list[Any]]
            Serialized network data.
        """
        return [self._convert_item(index).to_list() for index in range(len(self))]

    def get_by_field(self, field_name: str, value: Any) -> T | None:
        """Return the first item matching a field value.

        Parameters
        ----------
        field_name : str
            Field name to search.
        value : Any
            Desired field value.

        Returns
        -------
        T or None
            Matching item, or ``None`` if not found.
        """
        for item in self:
            if getattr(item, field_name, object()) == value:
                return item
        return None

    def get_index_by_field(self, field_name: str, value: Any) -> int | None:
        """Return the index of the first matching item.

        Parameters
        ----------
        field_name : str
            Field name to search.
        value : Any
            Desired field value.

        Returns
        -------
        int or None
            Index of the matching item, or ``None`` if not found.
        """
        for i, item in enumerate(self):
            if getattr(item, field_name, object()) == value:
                return i
        return None

    def modify_by_field(
        self,
        field_name: str,
        value: Any,
        **kwargs: Any,
    ) -> bool:
        """Modify fields of the first matching item.

        Parameters
        ----------
        field_name : str
            Field name to search.
        value : Any
            Desired field value.
        **kwargs : Any
            Field names and replacement values.

        Returns
        -------
        bool
            ``True`` if an item was modified, otherwise ``False``.

        Raises
        ------
        AttributeError
            If one of the requested fields does not exist.
        """
        index = self.get_index_by_field(field_name, value)
        if index is None:
            return False

        item = self[index]

        for key, new_value in kwargs.items():
            if not hasattr(item, key):
                raise AttributeError(
                    f"{type(item).__name__!r} has no attribute {key!r}"
                )
            setattr(item, key, new_value)

        return True


@dataclass(slots=True)
class EPANETNetworkModel:
    """Lightweight, in-memory representation of an EPANET water network.

    Provides named attribute access to network components (junctions,
    pipes, pumps, valves, etc.) with automatic lazy conversion between the
    raw list-of-tokens format produced by the INP parser and typed, mutable
    dataclass instances. Supports both reading and modification of network
    data.

    Conversion to/from dictionaries and files (JSON, EPANET INP) is handled
    separately by
    :class:`hydroforge.epanetfile_io.model_io.EPANETNetworkModelIO`, keeping
    this class focused on representing and manipulating data already in
    memory.

    Examples
    --------
    >>> from hydroforge.epanetfile_io.model_io import EPANETNetworkModelIO
    >>> network = EPANETNetworkModelIO.from_inp_file('network.inp')
    >>> junction = network.junctions.get_by_field('id', 'J1')
    >>> junction.elevation = 100.0
    >>> EPANETNetworkModelIO.to_inp_file(network, 'modified_network.inp')
    """
    
    # Class-level mappings for consistent conversion between dict and object attributes
    COLLECTION_MAPPINGS: ClassVar[Tuple[FieldMapping, ...]] = (
        FieldMapping('TITLE', 'title', TitleLine),
        FieldMapping('JUNCTIONS', 'junctions', Junction),
        FieldMapping('RESERVOIRS', 'reservoirs', Reservoir),
        FieldMapping('TANKS', 'tanks', Tank),
        FieldMapping('PIPES', 'pipes', Pipe),
        FieldMapping('PUMPS', 'pumps', Pump),
        FieldMapping('VALVES', 'valves', Valve),
        FieldMapping('DEMANDS', 'demands', Demand),
        FieldMapping('PATTERNS', 'patterns', Pattern),
        FieldMapping('CURVES', 'curves', Curve),
        FieldMapping('CONTROLS', 'controls', Control),
        FieldMapping('ENERGY', 'energy', Energy),
        FieldMapping('REACTIONS', 'reactions', Reaction),
        FieldMapping('TIMES', 'times', Time),
        FieldMapping('REPORT', 'report', Report),
        FieldMapping('OPTIONS', 'options', Option),
        FieldMapping('COORDINATES', 'coordinates', Coordinate),
        FieldMapping('BACKDROP', 'backdrop', Backdrop),
    )
    
    LIST_FIELD_MAPPINGS: ClassVar[Tuple[FieldMapping, ...]] = (
        FieldMapping('TAGS', 'tags'),
        FieldMapping('STATUS', 'status'),
        FieldMapping('RULES', 'rules'),
        FieldMapping('EMITTERS', 'emitters'),
        FieldMapping('QUALITY', 'quality'),
        FieldMapping('SOURCES', 'sources'),
        FieldMapping('MIXING', 'mixing'),
        FieldMapping('VERTICES', 'vertices'),
        FieldMapping('LABELS', 'labels')
    )
    
    # Reverse mappings for to_dict conversion
    #REVERSE_COLLECTION_MAPPINGS: ClassVar = invert_mappings(COLLECTION_MAPPINGS)
    #REVERSE_LIST_MAPPINGS: ClassVar = invert_mappings(LIST_FIELD_MAPPINGS)
    
    # Main network components
    title: NetworkCollection[TitleLine] = field(default_factory=lambda: NetworkCollection(TitleLine))
    junctions: NetworkCollection[Junction] = field(default_factory=lambda: NetworkCollection(Junction))
    reservoirs: NetworkCollection[Reservoir] = field(default_factory=lambda: NetworkCollection(Reservoir))
    tanks: NetworkCollection[Tank] = field(default_factory=lambda: NetworkCollection(Tank))
    pipes: NetworkCollection[Pipe] = field(default_factory=lambda: NetworkCollection(Pipe))
    pumps: NetworkCollection[Pump] = field(default_factory=lambda: NetworkCollection(Pump))
    valves: NetworkCollection[Valve] = field(default_factory=lambda: NetworkCollection(Valve))
    # Demand and operational data
    tags: List = field(default_factory=list)
    demands: NetworkCollection[Demand] = field(default_factory=lambda: NetworkCollection(Demand))
    status: List = field(default_factory=list)
    patterns: NetworkCollection[Pattern] = field(default_factory=lambda: NetworkCollection(Pattern))
    curves: NetworkCollection[Curve] = field(default_factory=lambda: NetworkCollection(Curve))
    controls: NetworkCollection[Control] = field(default_factory=lambda: NetworkCollection(Control))
    rules: List = field(default_factory=list)
    energy: NetworkCollection[Energy] = field(default_factory=lambda: NetworkCollection(Energy))
    # Quality and analysis
    emitters: List = field(default_factory=list)
    quality: List = field(default_factory=list)
    sources: List = field(default_factory=list)
    reactions: NetworkCollection[Reaction] = field(default_factory=lambda: NetworkCollection(Reaction))
    mixing: List = field(default_factory=list)
    # Simulation settings
    times: NetworkCollection[Time] = field(default_factory=lambda: NetworkCollection(Time))
    report: NetworkCollection[Report] = field(default_factory=lambda: NetworkCollection(Report))
    options: NetworkCollection[Option] = field(default_factory=lambda: NetworkCollection(Option))
    # Spatial data
    coordinates: NetworkCollection[Coordinate] = field(default_factory=lambda: NetworkCollection(Coordinate))
    vertices: List = field(default_factory=list)
    labels: List = field(default_factory=list)
    backdrop: NetworkCollection[Backdrop] = field(default_factory=lambda: NetworkCollection(Backdrop))

    def get_item_by_index(self, collection_name: str, index: int) -> Optional[Any]:
        """Get an item from a collection by index.

        Parameters
        ----------
        collection_name : str
            Collection attribute name (e.g. ``'junctions'``).
        index : int
            Item index.

        Returns
        -------
        Any or None
            Item at ``index``, or ``None`` if not found.
        """
        collection = getattr(self, collection_name, None)
        if isinstance(collection, NetworkCollection) and 0 <= index < len(collection):
            return collection[index]
        return None
    
    def get_item_by_field_value(
            self,
            collection_name: str,
            field_name: str,
            field_value: int | float | str) -> Optional[Any]:
        """Get an item from a collection by field value.

        Parameters
        ----------
        collection_name : str
            Collection attribute name.
        field_name : str
            Field name to match.
        field_value : int, float, or str
            Value to match.

        Returns
        -------
        Any or None
            First matching item, or ``None`` if not found.
        """
        collection = getattr(self, collection_name, None)
        if isinstance(collection, NetworkCollection):
            return collection.get_by_field(field_name, field_value)
        return None
    
    def get_item_index_by_field_value(
            self,
            collection_name: str,
            field_name: str,
            field_value: int | float | str) -> Optional[int]:
        """Get the index of an item in a collection by field value.

        Parameters
        ----------
        collection_name : str
            Collection attribute name.
        field_name : str
            Field name to match.
        field_value : int, float, or str
            Value to match.

        Returns
        -------
        int or None
            Index of the first matching item, or ``None`` if not found.
        """
        collection = getattr(self, collection_name, None)
        if isinstance(collection, NetworkCollection):
            return collection.get_index_by_field(field_name, field_value)
        return None
    
    def modify_item_by_field_value(
            self,
            collection_name: str,
            field_name: str,
            field_value: int | float | str,
            **kwargs) -> bool:
        """Modify an item in a collection by field value.

        Parameters
        ----------
        collection_name : str
            Collection attribute name.
        field_name : str
            Field name to match.
        field_value : int, float, or str
            Value to match.
        **kwargs
            Fields to update with new values.

        Returns
        -------
        bool
            ``True`` if an item was modified, otherwise ``False``.
        """
        collection = getattr(self, collection_name, None)
        if isinstance(collection, NetworkCollection):
            return collection.modify_by_field(field_name, field_value, **kwargs)
        return False
