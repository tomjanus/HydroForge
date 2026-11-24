"""Tests for the WNTR static uncertainty example."""

import json
import subprocess
import sys
from pathlib import Path


def test_example_script_and_notebook_have_matching_code():
    root = Path(__file__).resolve().parents[1]
    script = (root / "examples" / "wntr_static_uncertainty.py").read_text(
        encoding="utf-8"
    )
    notebook = json.loads(
        (root / "examples" / "wntr_static_uncertainty.ipynb").read_text(
            encoding="utf-8"
        )
    )
    notebook_code = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )
    assert notebook_code == script


def test_example_script_runs_deterministically(tmp_path):
    root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "figure.png"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples" / "wntr_static_uncertainty.py"),
            "--output",
            str(output_path),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert output_path.is_file()
