"""Targeted interior-history capture for TSNetPlus simulations."""

from __future__ import annotations

import contextlib
import inspect
import threading
from dataclasses import dataclass
from typing import Any, Iterator, Literal, Sequence

import numpy as np

InteriorQuantity = Literal["head", "velocity", "flowrate"]

_CAPTURE_LOCK = threading.RLock()

_EXPECTED_INNER_PIPE_PARAMETERS = (
    "linkp",
    "pn",
    "dt",
    "links1",
    "links2",
    "utype",
    "dtype",
    "p",
    "H0",
    "V0",
    "H",
    "V",
    "H10",
    "V10",
    "H20",
    "V20",
    "pump",
    "valve",
    "friction",
    "dVdt",
    "dVdx",
    "dVdt10",
    "dVdx10",
    "dVdt20",
    "dVdx20",
)


@dataclass(frozen=True)
class InteriorCaptureSpec:
    """One configured interior capture location for a pipe."""

    pipe_id: str
    quantity: InteriorQuantity = "head"
    fraction: float | None = None
    index: int | None = None

    def __post_init__(self) -> None:
        if self.fraction is None and self.index is None:
            raise ValueError("an interior capture needs a fraction or mesh index")
        if self.fraction is not None and self.index is not None:
            raise ValueError("use either a fraction or a mesh index, not both")


def validate_interior_spec(num_segments: int, spec: InteriorCaptureSpec) -> None:
    """Validate a capture location against a pipe discretization."""
    if num_segments < 2:
        raise ValueError("interior capture requires at least two pipe segments")
    n_points = num_segments + 1
    if spec.fraction is not None:
        if not 0.0 < float(spec.fraction) < 1.0:
            raise ValueError("interior fraction must lie strictly between 0 and 1")
    if spec.index is not None:
        if not isinstance(spec.index, int) or isinstance(spec.index, bool):
            raise ValueError("interior mesh index must be an integer")
        if spec.index <= 0 or spec.index >= n_points - 1:
            raise ValueError(
                f"interior mesh index must be between 1 and {n_points - 2}"
            )


def interpolate_interior(history: Any, fraction: float) -> np.ndarray:
    """Interpolate an interior quantity from adjacent computational points."""
    array = np.asarray(history, dtype=float)
    if array.ndim != 2:
        raise ValueError("interior history must have shape (time, points)")
    if array.shape[1] < 2:
        raise ValueError("interior history needs at least two computational points")
    if not 0.0 < float(fraction) < 1.0:
        raise ValueError("interior fraction must lie strictly between 0 and 1")
    position = float(fraction) * float(array.shape[1] - 1)
    lower = int(np.floor(position))
    upper = int(np.ceil(position))
    if upper >= array.shape[1]:
        upper = array.shape[1] - 1
    if lower == upper:
        return np.asarray(array[:, lower], dtype=float).copy()
    weight = position - lower
    return np.asarray(
        (1.0 - weight) * array[:, lower] + weight * array[:, upper],
        dtype=float,
    )


def read_interior_index(history: Any, index: int) -> np.ndarray:
    """Read one interior computational point from a history array."""
    array = np.asarray(history, dtype=float)
    if array.ndim != 2:
        raise ValueError("interior history must have shape (time, points)")
    if not isinstance(index, int) or isinstance(index, bool):
        raise ValueError("interior mesh index must be an integer")
    if index <= 0 or index >= array.shape[1] - 1:
        raise ValueError(
            f"interior mesh index must be between 1 and {array.shape[1] - 2}"
        )
    return np.asarray(array[:, index], dtype=float).copy()


@contextlib.contextmanager
def capture_interior_locations(
    model: Any, specs: Sequence[InteriorCaptureSpec]
) -> Iterator[dict[str, Any]]:
    """Capture only requested interior locations during a TSNetPlus run.

    The context manager temporarily instruments TSNetPlus' per-pipe MOC
    update so that one scalar per requested location and timestamp is
    retained.  Full per-pipe mesh histories are never stored.
    """
    try:
        from tsnetplus.kernels.python import single as _single
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("TSNetPlus is not installed") from exc

    specs_by_pipe: dict[str, list[InteriorCaptureSpec]] = {}
    for spec in specs:
        specs_by_pipe.setdefault(spec.pipe_id, []).append(spec)
        pipe = model.get_link(spec.pipe_id)
        validate_interior_spec(int(pipe.number_of_segments), spec)

    buffers: dict[str, Any] = {_spec_key(spec): [] for spec in specs}
    original_inner_pipe = _single.inner_pipe

    def instrumented_inner_pipe(
        linkp,
        pn,
        dt,
        links1,
        links2,
        utype,
        dtype,
        p,
        H0,
        V0,
        H,
        V,
        H10,
        V10,
        H20,
        V20,
        pump,
        valve,
        friction,
        dVdt,
        dVdx,
        dVdt10,
        dVdx10,
        dVdt20,
        dVdx20,
    ):
        result = original_inner_pipe(
            linkp,
            pn,
            dt,
            links1,
            links2,
            utype,
            dtype,
            p,
            H0,
            V0,
            H,
            V,
            H10,
            V10,
            H20,
            V20,
            pump,
            valve,
            friction,
            dVdt,
            dVdx,
            dVdt10,
            dVdx10,
            dVdt20,
            dVdx20,
        )
        pipe_specs = specs_by_pipe.get(getattr(linkp, "name", None))
        if pipe_specs:
            area = float(getattr(linkp, "area", 1.0) or 1.0)
            for spec in pipe_specs:
                if spec.fraction is not None:
                    position = float(spec.fraction) * float(len(H) - 1)
                    lower = int(np.floor(position))
                    upper = int(np.ceil(position))
                    if upper >= len(H):
                        upper = len(H) - 1
                    weight = position - lower
                    if lower == upper:
                        head_value = float(H[lower])
                        velocity_value = float(V[lower])
                    else:
                        head_value = float(
                            (1.0 - weight) * H[lower] + weight * H[upper]
                        )
                        velocity_value = float(
                            (1.0 - weight) * V[lower] + weight * V[upper]
                        )
                else:
                    idx = int(spec.index)
                    head_value = float(H[idx])
                    velocity_value = float(V[idx])
                if spec.quantity == "head":
                    buffers[_spec_key(spec)].append(head_value)
                elif spec.quantity == "velocity":
                    buffers[_spec_key(spec)].append(velocity_value)
                elif spec.quantity == "flowrate":
                    buffers[_spec_key(spec)].append(velocity_value * area)
                else:  # pragma: no cover - validated earlier
                    raise ValueError(f"unsupported interior quantity {spec.quantity!r}")
        return result

    try:
        signature = inspect.signature(original_inner_pipe)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("unable to inspect TSNetPlus inner_pipe") from exc
    if tuple(signature.parameters) != _EXPECTED_INNER_PIPE_PARAMETERS:
        raise RuntimeError(
            "incompatible TSNetPlus inner_pipe signature: expected "
            f"{_EXPECTED_INNER_PIPE_PARAMETERS}, got {tuple(signature.parameters)}"
        )

    _CAPTURE_LOCK.acquire()
    try:
        _single.inner_pipe = instrumented_inner_pipe
        try:
            yield buffers  # lists are populated during the run
        finally:
            _single.inner_pipe = original_inner_pipe
            for key, values in list(buffers.items()):
                buffers[key] = np.asarray(values, dtype=float)
            model._hydroforge_interior_buffers = buffers
    finally:
        _CAPTURE_LOCK.release()


def _spec_key(spec: InteriorCaptureSpec) -> str:
    location = (
        f"frac{spec.fraction}" if spec.fraction is not None else f"idx{spec.index}"
    )
    return f"{spec.pipe_id}:{spec.quantity}:{location}"
