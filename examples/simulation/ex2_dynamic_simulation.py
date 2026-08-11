"""Example: dynamic (transient) simulation with TSNet."""

from __future__ import annotations

from pathlib import Path

from rich import print as rprint

from hydroforge.simulation import TSNetSimulator, TSNetSimulatorConfig, load_tsnet_model
from hydroforge.simulation.events import DemandPulseEvent


def _tsnet_network_path() -> Path:
    """Return a TSNet-ready INP file path."""
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        project_root / "data" / "case_studies" / "tsnet" / "Tnet1.inp",
        project_root / "data" / "case_studies" / "Test" / "Real_network.inp",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Could not find a TSNet example INP file.")


def main() -> None:
    """Run a TSNet transient simulation and inspect key outputs."""
    model = load_tsnet_model(_tsnet_network_path())

    duration = 20.0
    time_step = 0.1
    model.set_wavespeed(1200.0)
    model.set_time(duration, time_step)

    junctions = list(model.junction_name_list[:3])
    links = list(model.pipe_name_list[:3])

    # Add a small demand pulse to showcase event-driven transient behavior.
    pulse = DemandPulseEvent(
        node=junctions[0],
        pulse_duration=2.0,
        start_time=2.0,
        duration_time=8.0,
        multiplier=1.2,
    )
    pulse.apply_to(model)

    config = TSNetSimulatorConfig(
        wave_speed=1200.0,
        duration=duration,
        time_step=time_step,
        friction_model="steady",
        results_name=None,
        clean_files=True,
    )
    simulator = TSNetSimulator(config=config, inplace=False)
    results = simulator.run(model)

    head_df = results.get_node_variable(
        "head",
        junctions,
        times=(0, 10),
        as_dataframe=True,
    )
    flow_df = results.get_link_variable(
        "start_node_flowrate",
        links,
        times=[0, 2, 5, 10, 15, 20],
        as_dataframe=True,
    )

    rprint("[bold]HydroForge Dynamic Simulation Example (TSNet)[/bold]")
    rprint(f"Network file: {_tsnet_network_path()}")
    rprint(f"Junctions tracked: {junctions}")
    rprint(f"Links tracked: {links}")
    rprint("\nHead time series (first rows):")
    rprint(head_df.head())
    rprint("\nSelected transient flow snapshots:")
    rprint(flow_df)
    rprint("\n[green]Dynamic simulation completed successfully.[/green]")


if __name__ == "__main__":
    main()
