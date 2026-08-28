from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, Sequence, TypeVar

TargetT = TypeVar("TargetT")


def validate_name(value: str, parameter: str) -> None:
    """Validate an EPANET element identifier."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{parameter} must be a non-empty string.")


def validate_non_negative(value: float, parameter: str) -> None:
    """Validate a non-negative numeric time or coefficient."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{parameter} must be a non-negative number.")


def validate_positive(value: float, parameter: str) -> None:
    """Validate a positive numeric time or exponent."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{parameter} must be a positive number.")


def validate_opening(value: float, parameter: str = "final_opening") -> None:
    """Validate an opening fraction."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
        raise ValueError(f"{parameter} must be between 0 and 1.")


def validate_curve(curve: Sequence[tuple[float, float]] | None) -> None:
    """Validate a TSNet valve-operation curve."""
    if curve is None:
        return
    if not isinstance(curve, Sequence) or isinstance(curve, (str, bytes)):
        raise ValueError("curve must be a sequence of two-number tuples.")
    for point in curve:
        if not isinstance(point, tuple) or len(point) != 2:
            raise ValueError("curve must contain two-number tuples.")
        validate_non_negative(point[0], "curve opening")
        validate_non_negative(point[1], "curve coefficient")


class TransientEvent(ABC, Generic[TargetT]):
    """Abstract base class for a transient simulation event.

    A transient event represents a modification to a transient-model
    or simulator object before or during a transient simulation.

    Parameters
    ----------
    target_type
        Type of object to which the event can be applied - typically a subclass 
        of the transient model (as in TSNet) or simulator object (as in PTSNet).
    """
    
    target_type: type[TargetT]
    
    def apply_to(self, target: TargetT) -> None:
        """Apply the event to its target.

        Parameters
        ----------
        target : TargetT
            The target object to which the event should be applied.

        Raises
        ------
        TypeError
            If ``target`` is not compatible with the event.
        """
        if not isinstance(target, self.target_type):
            raise TypeError(
                f"{type(self).__name__} can only be applied to "
                f"{self.target_type.__name__}, "
                f"not {type(target).__name__}."
            )
        self._apply_to(target)

    @abstractmethod
    def _apply_to(self, target: TargetT) -> None:
        """Apply the event to a validated target."""