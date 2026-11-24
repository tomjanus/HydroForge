"""Synthetic tests for TSNetPlus targeted interior capture."""

import numpy as np
import pytest

from hydroforge.wdn_modelling.backends.tsnetplus.interior import (
    InteriorCaptureSpec,
    interpolate_interior,
    read_interior_index,
    validate_interior_spec,
)


def test_fractional_interpolation_uses_adjacent_computational_values():
    history = np.array([[0.0, 10.0, 20.0], [1.0, 11.0, 21.0]])

    result = interpolate_interior(history, 0.25)

    np.testing.assert_allclose(result, [5.0, 6.0])


def test_mesh_index_reads_exact_interior_point():
    history = np.array([[0.0, 10.0, 20.0, 30.0]])

    result = read_interior_index(history, 2)

    np.testing.assert_allclose(result, [20.0])


def test_interior_index_rejects_endpoints():
    history = np.array([[0.0, 10.0, 20.0]])

    with pytest.raises(ValueError):
        read_interior_index(history, 0)
    with pytest.raises(ValueError):
        read_interior_index(history, 2)


def test_fraction_rejects_boundaries():
    history = np.array([[0.0, 10.0, 20.0]])

    with pytest.raises(ValueError):
        interpolate_interior(history, 0.0)
    with pytest.raises(ValueError):
        interpolate_interior(history, 1.0)


def test_validate_interior_spec_rejects_invalid_locations():
    with pytest.raises(ValueError):
        validate_interior_spec(2, InteriorCaptureSpec("P1", fraction=0.0))
    with pytest.raises(ValueError):
        validate_interior_spec(2, InteriorCaptureSpec("P1", index=0))
    with pytest.raises(ValueError):
        validate_interior_spec(2, InteriorCaptureSpec("P1", index=2))
    with pytest.raises(ValueError):
        validate_interior_spec(1, InteriorCaptureSpec("P1", fraction=0.5))


def _fake_single_module(monkeypatch, inner_pipe):
    import sys
    import types

    for name in (
        "tsnetplus",
        "tsnetplus.kernels",
        "tsnetplus.kernels.python",
        "tsnetplus.kernels.python.single",
    ):
        sys.modules[name] = types.ModuleType(name)
    sys.modules["tsnetplus.kernels.python.single"].inner_pipe = inner_pipe
    return sys.modules["tsnetplus.kernels.python.single"]


def _expected_inner_pipe(
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
    H[:] = [0.0, 10.0, 20.0]
    V[:] = [0.0, 1.0, 2.0]
    return H, V


def test_capture_interior_locations_captures_selected_scalar(monkeypatch):
    from hydroforge.wdn_modelling.backends.tsnetplus.interior import (
        InteriorCaptureSpec,
        capture_interior_locations,
    )

    fake_single = _fake_single_module(monkeypatch, _expected_inner_pipe)

    class FakePipe:
        name = "P1"
        number_of_segments = 2
        area = 2.0

    class FakeModel:
        def get_link(self, pipe_id):
            return FakePipe()

    model = FakeModel()
    spec = InteriorCaptureSpec("P1", quantity="flowrate", fraction=0.5)

    with capture_interior_locations(model, [spec]) as buffers:
        fake_single.inner_pipe(
            FakePipe(),
            1,
            0.1,
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [0, 0, 0],
            [0, 0, 0],
            [],
            [],
            [],
            [],
            None,
            None,
            "steady",
            [],
            [],
            [],
            [],
            [],
            [],
        )
        assert buffers[list(buffers)[0]] == [2.0]

    assert list(model._hydroforge_interior_buffers.values())[0].tolist() == [2.0]


def test_capture_restores_inner_pipe_on_success_and_exception(monkeypatch):
    from hydroforge.wdn_modelling.backends.tsnetplus.interior import (
        InteriorCaptureSpec,
        capture_interior_locations,
    )

    original = _expected_inner_pipe
    fake_single = _fake_single_module(monkeypatch, original)

    class FakePipe:
        name = "P1"
        number_of_segments = 2
        area = 1.0

    class FakeModel:
        def get_link(self, pipe_id):
            return FakePipe()

    model = FakeModel()
    spec = InteriorCaptureSpec("P1", fraction=0.5)

    with capture_interior_locations(model, [spec]):
        pass
    assert fake_single.inner_pipe is original

    try:
        with capture_interior_locations(model, [spec]):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert fake_single.inner_pipe is original


def test_nested_capture_restores_previous_wrapper(monkeypatch):
    from hydroforge.wdn_modelling.backends.tsnetplus.interior import (
        InteriorCaptureSpec,
        capture_interior_locations,
    )

    original = _expected_inner_pipe
    fake_single = _fake_single_module(monkeypatch, original)

    class FakePipe:
        name = "P1"
        number_of_segments = 2
        area = 1.0

    class FakeModel:
        def get_link(self, pipe_id):
            return FakePipe()

    model = FakeModel()
    spec = InteriorCaptureSpec("P1", fraction=0.5)

    with capture_interior_locations(model, [spec]):
        outer_wrapper = fake_single.inner_pipe
        with capture_interior_locations(model, [spec]):
            assert fake_single.inner_pipe is not outer_wrapper
        assert fake_single.inner_pipe is outer_wrapper
    assert fake_single.inner_pipe is original


def test_capture_rejects_signature_mismatch(monkeypatch):
    from hydroforge.wdn_modelling.backends.tsnetplus.interior import (
        InteriorCaptureSpec,
        capture_interior_locations,
    )

    def bad_signature(linkp):
        return None

    fake_single = _fake_single_module(monkeypatch, bad_signature)

    class FakePipe:
        name = "P1"
        number_of_segments = 2
        area = 1.0

    class FakeModel:
        def get_link(self, pipe_id):
            return FakePipe()

    model = FakeModel()
    spec = InteriorCaptureSpec("P1", fraction=0.5)

    with pytest.raises(RuntimeError, match="incompatible"):
        with capture_interior_locations(model, [spec]):
            pass
    assert fake_single.inner_pipe is bad_signature
