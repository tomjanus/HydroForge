"""PTSNET dynamic uncertain-model example.

Run with::

    python examples/ptsnet_dynamic_uncertainty.py

PTSNET stores its workspace tree under the process working directory and
EPANET writes a ``.rpt`` report next to the ``.inp`` file it reads, so the
simulation runs inside a temporary directory holding a copy of the network
input and the repository is left untouched.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import numpy as np

try:
    from hydroforge.wdn_modelling.backends.ptsnet_backend import PTSNetBackend
except Exception as exc:  # pragma: no cover - optional dependency
    raise SystemExit(f"PTSNET is unavailable: {exc}")

from hydroforge.sampling import SobolSampler
from hydroforge.uncertainty.specification import UncertaintySpecification
from hydroforge.wdn_modelling.uncertainty.ptsnet_mapping import (
    PTSNetInteriorSensorBinding,
    PTSNetModelMapper,
    PTSNetSurgeProtectionBinding,
    PTSNetWaveSpeedBinding,
)
from hydroforge.wdn_modelling.persistence import load_realization, save_realization

try:
    REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
except NameError:  # Jupyter notebooks do not define __file__.
    REPOSITORY_ROOT = Path.cwd()
    if not (REPOSITORY_ROOT / "tests/base_networks/Net1.inp").is_file():
        REPOSITORY_ROOT = REPOSITORY_ROOT.parent
MODEL_PATH = REPOSITORY_ROOT / "tests/base_networks/Net1.inp"


def build_specification() -> UncertaintySpecification:
    return UncertaintySpecification.from_dict(
        {
            "schema_version": "2.0",
            "parameters": {
                "wave_speed": {
                    "nominal_value": 1000.0,
                    "uncertainty": {
                        "type": "Additive",
                        "parameters": {
                            "distribution": {
                                "type": "Normal",
                                "parameters": {"mean": 0.0, "std_dev": 50.0},
                            }
                        },
                    },
                },
                "surge_area": {"nominal_value": 1.5},
                "sensor_sigma": {"nominal_value": 0.05},
            },
            "sensors": {
                "flow_sensor": {
                    "type": "Composite",
                    "parameters": {
                        "sensors": [
                            {
                                "type": "RandomNoise",
                                "parameters": {"sigma": {"$parameter": "sensor_sigma"}},
                            }
                        ]
                    },
                }
            },
        }
    )


def _save_and_reload_realization(instance, bundle: Path) -> None:
    save_realization(instance, bundle)
    reloaded = load_realization(bundle)
    rerun = reloaded.run()
    raw_series, measured_series = _flow_series(rerun, "flow_sensor")
    if raw_series.empty or measured_series.empty:
        raise RuntimeError("reloaded PTSNET realization produced empty flow outputs")
    if not raw_series.index.equals(measured_series.index):
        raise RuntimeError("reloaded raw and measured flow use different time axes")
    print("Reloaded realization reran with measured interior output.")


def _flow_series(result, output_name: str):
    """Extract paired raw and measured interior flow from a HydroForge result."""
    import pandas as pd

    raw_results = result.raw_results
    raw_model = getattr(raw_results, "model", raw_results)
    interior_results = getattr(raw_model, "interior_results", None)
    if interior_results is None and isinstance(raw_results, dict):
        interior_results = raw_results.get("interior_results")
    timestamps = getattr(raw_model, "time_stamps", None)
    if timestamps is None and isinstance(raw_results, dict):
        timestamps = raw_results.get("time_stamps")
    if not isinstance(interior_results, dict) or output_name not in interior_results:
        raise RuntimeError(f"PTSNET has no raw interior output {output_name!r}")
    if timestamps is None:
        raise RuntimeError("PTSNET results do not expose their time_stamps axis")

    values = interior_results[output_name].get("flowrate")
    if values is None:
        raise RuntimeError(f"PTSNET interior output {output_name!r} has no flowrate")
    raw_series = pd.Series(
        np.asarray(values, dtype=float),
        index=pd.Index(timestamps, name="time"),
        name=output_name,
    )
    measured_table = result.measured_outputs.get("flowrate")
    if measured_table is None or output_name not in measured_table:
        raise RuntimeError(f"HydroForge has no measured flow output {output_name!r}")
    measured_series = measured_table[output_name].copy()
    if raw_series.empty or measured_series.empty:
        raise RuntimeError("PTSNET raw and measured flow outputs must be non-empty")
    if not raw_series.index.equals(measured_series.index):
        raise RuntimeError("PTSNET raw and measured flow use different time axes")
    return raw_series, measured_series


def _compare_realizations(model_path: Path, realization_path: Path | None):
    """Run the sampled scenarios and collect raw/measured interior flows.

    ``model_path`` must already live in the scratch directory the caller
    switched to, so every workspace and report PTSNET writes stays there.
    """
    backend = PTSNetBackend()
    model = backend.load_model(model_path)

    specification = build_specification()
    wave_speed = specification.create_parameter("wave_speed")
    surge_area = specification.create_parameter("surge_area")
    sensor_sigma = specification.create_parameter("sensor_sigma")
    sampler = SobolSampler([wave_speed, surge_area, sensor_sigma], seed=7)
    scenarios = list(sampler.generate(8))

    pipe_id = list(model.ss["pipe"].labels)[0]
    node_id = None
    for candidate in model.ss["node"].labels:
        node_id_value = model.ss["node"].lloc(candidate)
        if model.ss["node"].degree[candidate] != 2:
            continue
        if node_id_value in getattr(model.ss.get("pump", {}), "start_node", []):
            continue
        if node_id_value in getattr(model.ss.get("pump", {}), "end_node", []):
            continue
        if node_id_value in getattr(model.ss.get("valve", {}), "start_node", []):
            continue
        if node_id_value in getattr(model.ss.get("valve", {}), "end_node", []):
            continue
        node_id = candidate
        break
    if node_id is None:
        node_id = list(model.ss["node"].labels)[0]

    mapper = PTSNetModelMapper(
        wave_speed_bindings=[PTSNetWaveSpeedBinding(parameter_key="wave_speed")],
        surge_protection_bindings=[
            PTSNetSurgeProtectionBinding(
                node_id,
                "open",
                tank_area=1.0,
                area_key="surge_area",
            )
        ],
        interior_sensor_bindings=[
            PTSNetInteriorSensorBinding(
                pipe_id, "flow_sensor", "flowrate", name="flow_sensor", fraction=0.5
            )
        ],
        sensor_definitions=specification.sensors,
        simulator_config=None,
    )

    uncertain_model = mapper.map(specification, model)

    raw_flows = {}
    measured_flows = {}
    for scenario in scenarios:
        result = uncertain_model.realize(scenario).run()
        raw_series, measured_series = _flow_series(result, "flow_sensor")
        raw_flows[scenario.id] = raw_series
        measured_flows[scenario.id] = measured_series

    if len(raw_flows) != len(scenarios) or len(measured_flows) != len(scenarios):
        raise RuntimeError("not every PTSNET realization produced both flow series")

    saved_instance = uncertain_model.realize(scenarios[0])
    if realization_path is None:
        with tempfile.TemporaryDirectory(prefix="ptsnet_bundle_") as tmp:
            _save_and_reload_realization(saved_instance, Path(tmp) / "realization")
    else:
        _save_and_reload_realization(saved_instance, realization_path)

    print(
        f"Collected {len(scenarios)} non-empty raw/measured flow pairs "
        "on matching timestamps."
    )
    return raw_flows, measured_flows


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PTSNET dynamic uncertainty example")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(tempfile.gettempdir()) / "ptsnet_dynamic_uncertainty.png",
        help="where to write the comparison figure (default: system temp dir)",
    )
    parser.add_argument(
        "--realization",
        type=Path,
        default=None,
        help=(
            "optional directory for the saved realization bundle; "
            "it is kept after the run instead of being cleaned up"
        ),
    )
    return parser.parse_args()


def main(output_path: Path | None = None, realization_path: Path | None = None) -> None:
    if output_path is None:
        if "ipykernel" in sys.modules:
            output_path = Path(tempfile.gettempdir()) / "ptsnet_dynamic_uncertainty.png"
        else:
            args = _parse_args()
            output_path = args.output
            realization_path = args.realization

    # Resolve caller-supplied paths before entering the scratch directory.
    figure_path = Path(output_path).expanduser().resolve()
    bundle_path = (
        None
        if realization_path is None
        else Path(realization_path).expanduser().resolve()
    )
    source_model = MODEL_PATH.resolve()

    with tempfile.TemporaryDirectory(prefix="ptsnet_dynamic_") as tmp:
        workdir = Path(tmp)
        model_path = workdir / source_model.name
        shutil.copyfile(source_model, model_path)
        previous_cwd = os.getcwd()
        os.chdir(workdir)
        try:
            raw_flows, measured_flows = _compare_realizations(model_path, bundle_path)
        finally:
            os.chdir(previous_cwd)

    figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    for scenario_id, series in raw_flows.items():
        axes[0].plot(series.index, series.values, label=scenario_id, alpha=0.7)
    axes[0].set_title("Raw PTSNET pipe flow across realizations")
    axes[0].set_ylabel("Flow")
    axes[0].legend(fontsize=7, ncol=2)
    for scenario_id, series in measured_flows.items():
        axes[1].plot(series.index, series.values, label=scenario_id, alpha=0.7)
    axes[1].set_title("Measured PTSNET pipe flow across realizations")
    axes[1].set_ylabel("Flow")
    axes[1].set_xlabel("Time")
    fig.tight_layout()
    fig.savefig(figure_path)
    plt.close(fig)
    print(f"Saved figure to {figure_path}")


if __name__ == "__main__":
    main()
