"""Tests for the PTSNET dynamic uncertainty example."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _generated_artifacts(root: Path) -> set:
    """Paths PTSNET/EPANET drop inside the repository when run from it."""
    candidates = [root / "workspaces"]
    base = root / "tests" / "base_networks"
    candidates.extend(base.glob("*.rpt"))
    candidates.extend(base.glob("*.bin"))
    return {path for path in candidates if path.exists()}


def _load_model_in_scratch_dir() -> None:
    """Load the PTSNET model from a scratch dir so the repo stays clean."""
    source = _repo_root() / "tests" / "base_networks" / "Net1.inp"
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / source.name
        shutil.copyfile(source, scratch)
        previous_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            from hydroforge.wdn_modelling.backends.ptsnet_backend import PTSNetBackend

            PTSNetBackend().load_model(scratch)
        finally:
            os.chdir(previous_cwd)


def _require_ptsnet():
    try:
        import importlib.util

        if importlib.util.find_spec("ptsnet") is None:
            pytest.skip(
                "install the PTSNET feature branch with interior output support"
            )
        from ptsnet.simulation.sim import PTSNETSimulation
    except Exception as exc:
        pytest.skip(f"PTSNET optional/native dependencies are unavailable: {exc}")
    if not hasattr(PTSNETSimulation, "add_pipe_output"):
        pytest.skip("install the PTSNET feature branch with add_pipe_output support")
    try:
        _load_model_in_scratch_dir()
    except Exception as exc:
        pytest.skip(f"PTSNET cannot initialize in this environment: {exc}")


def test_example_script_and_notebook_have_matching_code():
    root = _repo_root()
    script = (root / "examples" / "ptsnet_dynamic_uncertainty.py").read_text(
        encoding="utf-8"
    )
    notebook = json.loads(
        (root / "examples" / "ptsnet_dynamic_uncertainty.ipynb").read_text(
            encoding="utf-8"
        )
    )
    code_cells = [
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    ]
    assert code_cells[0] == script
    assert len(code_cells) == 2
    assert "display(" in code_cells[1] and "Image(" in code_cells[1]


def test_example_script_runs_when_ptsnet_is_available(tmp_path):
    _require_ptsnet()
    root = _repo_root()
    output_path = tmp_path / "figure.png"
    before = _generated_artifacts(root)
    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples" / "ptsnet_dynamic_uncertainty.py"),
            "--output",
            str(output_path),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr
    assert output_path.is_file()
    assert "Collected 8 non-empty raw/measured flow pairs" in result.stdout
    assert "Reloaded realization reran with measured interior output" in result.stdout
    assert _generated_artifacts(root) == before


def test_example_keeps_a_user_specified_realization_bundle(tmp_path):
    _require_ptsnet()
    root = _repo_root()
    output_path = tmp_path / "figure.png"
    bundle_path = tmp_path / "bundle"
    before = _generated_artifacts(root)
    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples" / "ptsnet_dynamic_uncertainty.py"),
            "--output",
            str(output_path),
            "--realization",
            str(bundle_path),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr
    assert output_path.is_file()
    assert "Collected 8 non-empty raw/measured flow pairs" in result.stdout
    assert "Reloaded realization reran with measured interior output" in result.stdout
    assert (bundle_path / "manifest.json").is_file()
    manifest = json.loads((bundle_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mapping"]["interior_bindings"]
    assert {path.name for path in bundle_path.iterdir()} == {
        "manifest.json",
        "model.inp",
    }
    assert _generated_artifacts(root) == before
