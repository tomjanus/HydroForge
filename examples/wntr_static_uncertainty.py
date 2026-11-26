"""WNTR static uncertain-model example.

Run with::

    python examples/wntr_static_uncertainty.py
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import wntr

from hydroforge.sampling import LatinHypercubeSampler
from hydroforge.uncertainty.specification import UncertaintySpecification
from hydroforge.wdn_modelling.uncertainty import (
    WNTRModelMapper,
    WNTRParameterBinding,
    WNTRSensorBinding,
)
from hydroforge.wdn_modelling.persistence import load_realization, save_realization

try:
    REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
except NameError:  # Jupyter notebooks do not define __file__.
    REPOSITORY_ROOT = Path.cwd()
    if not (REPOSITORY_ROOT / "tests/base_networks/Net1.inp").is_file():
        REPOSITORY_ROOT = REPOSITORY_ROOT.parent


def build_specification() -> UncertaintySpecification:
    return UncertaintySpecification.from_dict(
        {
            "schema_version": "2.0",
            "parameters": {
                "pipe_diameter": {
                    "nominal_value": 0.30,
                    "uncertainty": {
                        "type": "Additive",
                        "parameters": {
                            "distribution": {
                                "type": "Normal",
                                "parameters": {"mean": 0.0, "std_dev": 0.02},
                            }
                        },
                    },
                },
                "pipe_status": {
                    "nominal_value": "OPEN",
                    "uncertainty": {
                        "type": "BinaryStateFlip",
                        "parameters": {"flip_prob": 0.25, "states": ["OPEN", "CLOSED"]},
                    },
                },
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


def main(output_path: Path | None = None) -> None:
    if output_path is None:
        if "ipykernel" in sys.modules:
            output_path = Path(tempfile.gettempdir()) / "wntr_static_uncertainty.png"
        else:
            parser = argparse.ArgumentParser()
            parser.add_argument(
                "--output",
                type=Path,
                default=Path(tempfile.gettempdir()) / "wntr_static_uncertainty.png",
            )
            args = parser.parse_args()
            output_path = args.output

    model_path = REPOSITORY_ROOT / "tests/base_networks/Net1.inp"
    model = wntr.network.WaterNetworkModel(str(model_path))
    model.options.time.duration = 0

    specification = build_specification()

    diameter = specification.create_parameter("pipe_diameter")
    status = specification.create_parameter("pipe_status")
    sensor_sigma = specification.create_parameter("sensor_sigma")
    sampler = LatinHypercubeSampler([diameter, status, sensor_sigma], seed=42)
    scenarios = list(sampler.generate(8))

    pipe_id = model.pipe_name_list[0]
    sensor_bindings = [WNTRSensorBinding(pipe_id, "flow_sensor", "flowrate")]
    mapper = WNTRModelMapper(
        parameter_bindings=[
            WNTRParameterBinding(pipe_id, "diameter", "pipe_diameter"),
            WNTRParameterBinding(pipe_id, "initial_status", "pipe_status"),
        ],
        sensor_bindings=sensor_bindings,
        sensor_definitions=specification.sensors,
    )
    uncertain_model = mapper.map(specification, model)

    raw_flows = {}
    measured_flows = {}
    for scenario in scenarios:
        instance = uncertain_model.realize(scenario)
        result = instance.run()
        raw_table = result.raw_results.raw.link["flowrate"]
        measured_table = result.measured_outputs["flowrate"]
        raw_flows[scenario.id] = raw_table[pipe_id].copy()
        measured_flows[scenario.id] = measured_table[pipe_id].copy()

    # Save and reload one realization.
    saved_instance = uncertain_model.realize(scenarios[0])
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "realization"
        save_realization(saved_instance, bundle)
        reloaded = load_realization(bundle)
        rerun = reloaded.run()
        print("Reloaded realization reran:", rerun.raw_results is not None)

    figure_path = Path(output_path)
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    for scenario_id, series in raw_flows.items():
        axes[0].plot(series.index, series.values, label=scenario_id, alpha=0.7)
    axes[0].set_title("Raw pipe flow across realizations")
    axes[0].set_ylabel("Flow")
    axes[0].legend(fontsize=7, ncol=2)
    for scenario_id, series in measured_flows.items():
        axes[1].plot(series.index, series.values, label=scenario_id, alpha=0.7)
    axes[1].set_title("Measured pipe flow across realizations")
    axes[1].set_ylabel("Flow")
    axes[1].set_xlabel("Time")
    fig.tight_layout()
    fig.savefig(figure_path)
    plt.close(fig)
    print(f"Saved figure to {figure_path}")


if __name__ == "__main__":
    main()
