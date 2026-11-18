"""Load and save uncertainty specifications from dictionaries, JSON, and YAML."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .exceptions import SpecificationFormatError
from .models import UncertaintySpecification

_SUPPORTED_SUFFIXES = frozenset({".json", ".yaml", ".yml"})


def _format_for_path(path: Path) -> str:
    """Return ``"json"`` or ``"yaml"`` for a supported specification path.

    Raises
    ------
    SpecificationFormatError
        If the file extension is not supported.
    """
    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise SpecificationFormatError(
            f"unsupported specification file extension {path.suffix!r}; "
            "expected .json, .yaml, or .yml"
        )
    return "json" if suffix == ".json" else "yaml"


def load_specification(
    source: str | Path | dict[str, Any],
) -> UncertaintySpecification:
    """Load an uncertainty specification from a dictionary, JSON, or YAML source.

    Parameters
    ----------
    source : str, pathlib.Path, or dict
        A path to a `.json`, `.yaml`, or `.yml` file, or an already-parsed
        mapping.

    Returns
    -------
    UncertaintySpecification
        The parsed and validated specification.

    Raises
    ------
    SpecificationFormatError
        If the source is not a supported kind, cannot be read, or is not a
        well-formed document.
    SpecificationValidationError
        If the document violates the specification rules.
    """
    if isinstance(source, dict):
        return UncertaintySpecification.from_dict(source)

    if isinstance(source, (str, Path)):
        path = Path(source)
        file_format = _format_for_path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SpecificationFormatError(
                f"could not read specification file {path}: {exc}"
            ) from exc

        try:
            if file_format == "json":
                document = json.loads(text)
            else:
                document = yaml.safe_load(text)
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            raise SpecificationFormatError(
                f"invalid {file_format.upper()} in {path}: {exc}"
            ) from exc

        if not isinstance(document, dict):
            raise SpecificationFormatError(
                f"specification file {path} must contain a mapping at the top level"
            )
        return UncertaintySpecification.from_dict(document)

    raise SpecificationFormatError(
        f"unsupported specification source type {type(source).__name__}; "
        "expected dict, str, or Path"
    )


def save_specification(spec: UncertaintySpecification, path: str | Path) -> None:
    """Save an uncertainty specification to a `.json`, `.yaml`, or `.yml` file.

    Parameters
    ----------
    spec : UncertaintySpecification
        The specification to serialise.
    path : str or pathlib.Path
        Destination path. The suffix selects the format.

    Raises
    ------
    SpecificationFormatError
        If the suffix is not supported or the file cannot be written.
    """
    path = Path(path)
    file_format = _format_for_path(path)

    data = spec.to_dict()
    if file_format == "json":
        text = json.dumps(data, indent=2) + "\n"
    else:
        text = yaml.safe_dump(data, sort_keys=False)

    try:
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise SpecificationFormatError(
            f"could not write specification file {path}: {exc}"
        ) from exc
