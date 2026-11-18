"""Exceptions raised by the uncertainty specification layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SpecificationIssue:
    """A single problem found while validating a specification.

    Parameters
    ----------
    path : str
        Dotted path to the offending entry, relative to the document root.
    message : str
        Human-readable description of the problem.
    """

    path: str
    message: str


class SpecificationError(Exception):
    """Base class for all uncertainty specification errors."""


class SpecificationFormatError(SpecificationError):
    """Raised when a specification source is not a well-formed document."""


class SpecificationValidationError(SpecificationError):
    """Raised when a specification document violates the specification rules.

    Parameters
    ----------
    errors : Iterable[SpecificationIssue]
        The individual problems found in the document.

    Attributes
    ----------
    errors : list[SpecificationIssue]
        The individual problems found in the document.
    """

    def __init__(
        self, errors: Iterable[SpecificationIssue], message: str | None = None
    ) -> None:
        self.errors = list(errors)
        if message is None:
            message = "; ".join(
                f"{issue.path}: {issue.message}" for issue in self.errors
            )
        super().__init__(message)

    @property
    def path(self) -> str:
        """The path of the single error, or an empty string when there are several."""
        return self.errors[0].path if len(self.errors) == 1 else ""
