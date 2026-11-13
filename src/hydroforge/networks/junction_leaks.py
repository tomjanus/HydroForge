"""Junction leak management for water distribution networks.

This module provides a dictionary-like container for managing leakage data at
network junctions. Supports adding, removing, and querying leaks with validation
and convenient I/O operations (JSON, CSV, DataFrame).

Key Features:
    - Dictionary-like interface with MutableMapping protocol
    - Leak size validation (non-negative values)
    - Total leakage calculation
    - Import/export via JSON, CSV, and pandas DataFrames
    - Unit tracking (default: m³/s)

Example:
    >>> leaks = JunctionLeaks()
    >>> leaks.add_leak('J1', 0.05)
    >>> leaks.add_leak('J2', 0.03)
    >>> print(leaks.total_leakage)  # 0.08
    >>> leaks.to_json('leaks.json')
"""

from __future__ import annotations
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import Dict, Iterator, Sequence, Union, Optional
import json
import pandas as pd
from rich import print as rprint


@dataclass
class JunctionLeaks(MutableMapping):
    """Dictionary-like wrapper for junction leaks in a water network model.

    This class allows direct access to leak data and provides a simple interface
    for adding and removing leaks and initializing leak data from lists.

    Example:
        leaks = JunctionLeaks()
        leaks['J1'] = 0.05  # Add leak to junction J1
        leak_size = leaks['J1']  # Get leak size for junction J1
        if 'J1' in leaks:  # Check if junction has leak
            print(f"Junction J1 has leak of {leaks['J1']} m³/s")
    """

    _data: Dict[str, float] = field(default_factory=dict, init=False, repr=False)
    unit: Optional[str] = "m³/s"

    @property
    def total_leakage(self) -> float:
        """Total leakage across all junctions."""
        return sum(self._data.values())

    def __eq__(self, other) -> bool:
        if isinstance(other, JunctionLeaks):
            return self._data == other._data
        if isinstance(other, dict):
            return self._data == other
        return NotImplemented

    def __getitem__(self, junction: str) -> float:
        """Get leak size for a junction."""
        return self._data[junction]

    def __setitem__(self, junction: str, size: float):
        """Set leak size for a junction."""
        if size < 0:
            raise ValueError(f"Leak size must be non-negative (got {size})")
        self._data[junction] = size

    def __delitem__(self, junction: str):
        """Remove leak from a junction."""
        del self._data[junction]

    def __iter__(self) -> Iterator[str]:
        """Iterate over junction names."""
        return iter(self._data)

    def __len__(self) -> int:
        """Get number of junctions with leaks."""
        return len(self._data)

    def __repr__(self) -> str:
        """String representation of the object."""
        return f"JunctionLeaks({self._data})"

    def is_empty(self) -> bool:
        """Check if there are no junctions with leakage."""
        return not self._data

    def add_leak(self, junction: str, size: float):
        """Add a junction with leakage.

        Args:
            junction (str): Name of the junction.
            size (float): Size of the leakage.
        """
        if size < 0:
            raise ValueError("Leak size increment must be non-negative")
        self._data[junction] = self._data.get(junction, 0.0) + size

    def remove_leak(self, junction: str, size: float):
        """Decrease leak size or remove entry if zeroed."""
        if size < 0:
            raise ValueError("Leak size decrement must be non-negative")
        if junction in self._data:
            new_size = max(0.0, self._data[junction] - size)
            if new_size == 0.0:
                del self._data[junction]
            else:
                self._data[junction] = new_size

    @classmethod
    def from_lists(
        cls, junctions: Sequence[str], sizes: Union[Sequence[float], float]
    ) -> JunctionLeaks:
        """Create a JunctionLeaks instance from lists of junctions and sizes.

        Args:
            junctions (Sequence[str]): A sequence of junction names.
            sizes (Sequence[float] | float): A sequence of leakage sizes corresponding to the junctions,
                                        or a single size to apply to all junctions.

        Returns:
            JunctionLeaks: Instance with populated data.
        """
        if isinstance(sizes, (int, float)):
            sizes = [float(sizes)] * len(junctions)
        elif len(sizes) != len(junctions):
            raise ValueError("Length of junctions and sizes must match.")
        instance = cls()
        instance._data = dict(zip(junctions, sizes))
        return instance

    def to_dict(self) -> Dict[str, float]:
        """Return a shallow copy of the internal data."""
        return dict(self._data)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame."""
        return pd.DataFrame(list(self._data.items()), columns=["junction", "leak_size"])

    # -------------------------
    # JSON Serialization
    # -------------------------
    def to_json(self, indent: int = 2) -> str:
        """Serialize junction leaks to JSON string."""
        return json.dumps(self._data, indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> JunctionLeaks:
        """Deserialize a JunctionLeaks object from JSON string."""
        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON format: expected a dictionary.")
        instance = cls()
        # Validate all values are numeric
        instance._data = {str(k): float(v) for k, v in data.items()}
        return instance


if __name__ == "__main__":
    # Example usage of JunctionLeaks
    rprint("\n=== Example: Creating and Manipulating JunctionLeaks ===")

    # Create an empty leak set
    leaks = JunctionLeaks()
    rprint("Initial state:", leaks)
    unit = leaks.unit if leaks.unit else "m³/s"

    # Add individual leaks
    leaks["J1"] = 0.05
    leaks["J2"] = 0.02
    rprint("After adding leaks:", leaks)

    # Increase an existing leak
    leaks.add_leak("J1", 0.03)
    rprint("After increasing leak at J1:", leaks)

    # Remove part of a leak
    leaks.remove_leak("J2", 0.01)
    rprint("After partial removal at J2:", leaks)

    # Check membership and retrieval
    for j in ["J1", "J3"]:
        if j in leaks:
            rprint(f"{j} has leak {leaks[j]:.3f} {unit}")
        else:
            rprint(f"{j} has no recorded leak")

    # Add multiple leaks from lists
    new_leaks = JunctionLeaks.from_lists(["J3", "J4"], [0.04, 0.01])
    rprint("\nNew leaks from lists:", new_leaks)

    # Merge both sets
    for j, s in new_leaks.items():
        leaks.add_leak(j, s)
    rprint("After merging new leaks:", leaks)

    # Display total leakage
    rprint(f"Total leakage: {leaks.total_leakage:.3f} {unit}")

    # Serialize to JSON
    json_str = leaks.to_json()
    rprint("\nSerialized JSON:")
    rprint(json_str)

    # Deserialize from JSON
    restored = JunctionLeaks.from_json(json_str)
    rprint("\nRestored from JSON:", restored)

    # Equality check
    rprint("Objects equal:", leaks == restored)

    # Demonstrate dict-like iteration
    rprint("\nIterating through junctions and leaks:")
    for junction, size in leaks.items():
        rprint(f"  {junction}: {size:.3f} {unit}")

    rprint("\nExample complete.")
