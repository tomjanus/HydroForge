"""Example: static hydraulic simulation through the WNTR backend."""

from __future__ import annotations

from pathlib import Path
from rich import print as rprint

from hydroforge.wdn_modelling.backends import get_backend
from hydroforge.wdn_modelling.backends.wntr.config import (
    WNTRConfig,
    WNTRHydraulicConfig,
    WNTRSimulatorConfig,
    WNTRTimeConfig,
)


def _example_network() -> Path:
    """Return a stable example INP file path from the repository."""
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        project_root / "tests" / "base_networks" / "Net1_shortened.inp",
        project_root / "tests" / "base_networks" / "Net1.inp",
        project_root / "data" / "case_studies" / "Test" / "Real_network.inp",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Could not find a usable example INP file.")


def run_steady_state() -> None:
    """Load and run a steady-state model with WNTR."""
    backend = get_backend("wntr")
    model = backend.load_model(_example_network())
    config = WNTRConfig(
        time=WNTRTimeConfig(duration=0),
        hydraulic=WNTRHydraulicConfig(demand_model="DD"),
    )
    # Model configuration (persistent WNTR options) is applied to the loaded
    # model; simulator runtime configuration is passed separately.
    backend.apply_config(config)
    results = backend.create_simulator(WNTRSimulatorConfig()).run(model)
    rprint("\n[bold]WNTR steady-state simulation[/bold]")
    rprint(f"Network file: {_example_network()}")
    rprint(f"Pressure result shape: {results.raw.node['pressure'].shape}")


def run_extended_duration_showcase() -> None:
    """Showcase time extraction patterns and WNTR PDD support."""
    backend = get_backend("wntr")
    wn = backend.load_model(_example_network())
    sensor_nodes = list(wn.junction_name_list[:3])

    duration = 12 * 3600
    timestep = 3600
    config = WNTRConfig(
        time=WNTRTimeConfig(duration=duration, hydraulic_timestep=timestep),
        hydraulic=WNTRHydraulicConfig(demand_model="DD"),
    )
    backend.apply_config(config)
    wntr_results = backend.create_simulator(WNTRSimulatorConfig()).run(wn)

    pressures_range = wntr_results.get_node_variable(
        "pressure",
        sensor_nodes,
        times=(0, 6 * 3600),
        as_dataframe=True,
    )

    rprint("\n[bold]Extended Duration Showcase (WNTR)[/bold]")
    rprint(f"Duration: {duration}s, timestep: {timestep}s")
    rprint("\nPressure extraction for time range (0h to 6h):")
    rprint(pressures_range.head())


def main() -> None:
    """Run both static simulation examples."""
    rprint("[bold]HydroForge Static Simulation Example[/bold]")
    run_steady_state()
    run_extended_duration_showcase()
    rprint("\n[green]All static simulation examples finished.[/green]")


if __name__ == "__main__":
    main()
