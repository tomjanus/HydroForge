"""Example: static hydraulic simulations with WNTR and EPANET backends."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

import numpy as np
from rich import print as rprint

from hydroforge.simulation import (
    DemandModel,
    EPANETSimulator,
    EPANETSimulatorConfig,
    WNTRSimulatorConfig,
    WNTRSimulator,
    load_wntr_model,
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


def run_steady_state_comparison() -> None:
    """Compare WNTR and EPANET on a steady-state DD simulation."""
    wn = load_wntr_model(_example_network())
    sensor_nodes = list(wn.junction_name_list[:5])
    pipe_names = list(wn.pipe_name_list[:5])

    wntr_sim = WNTRSimulator(
        config=WNTRSimulatorConfig(sim_time=0, demand_model=DemandModel.DD),
        inplace=False,
    )
    epanet_sim = EPANETSimulator(
        config=EPANETSimulatorConfig(
            sim_time=0,
            demand_model=DemandModel.DD,
            file_prefix="hf_static_demo",
            cleanup_files=True,
        ),
        inplace=False,
    )

    t0 = perf_counter()
    wntr_results = wntr_sim.run(wn)
    t1 = perf_counter()
    epanet_results = epanet_sim.run(wn)
    t2 = perf_counter()

    wntr_pressures = wntr_results.get_node_variable("pressure", sensor_nodes, times=0)
    epanet_pressures = epanet_results.get_node_variable("pressure", sensor_nodes, times=0)
    wntr_flows = wntr_results.get_link_variable("flowrate", pipe_names, times=0)
    epanet_flows = epanet_results.get_link_variable("flowrate", pipe_names, times=0)

    pressure_diff = np.abs(wntr_pressures - epanet_pressures).max()
    flow_diff = np.abs(wntr_flows - epanet_flows).max()

    rprint("\n[bold]Steady-State DD Comparison[/bold]")
    rprint(f"Nodes used: {sensor_nodes}")
    rprint(f"Pipes used: {pipe_names}")
    rprint(f"WNTR runtime:  {t1 - t0:.4f} s")
    rprint(f"EPANET runtime:{t2 - t1:.4f} s")
    rprint(f"Max pressure difference: {pressure_diff:.6f}")
    rprint(f"Max flow difference:     {flow_diff:.6f}")


def run_extended_duration_showcase() -> None:
    """Showcase time extraction patterns and WNTR PDD support."""
    wn = load_wntr_model(_example_network())
    sensor_nodes = list(wn.junction_name_list[:3])
    pipe_names = list(wn.pipe_name_list[:3])

    duration = 12 * 3600
    timestep = 3600
    wntr_results = WNTRSimulator(
        config=WNTRSimulatorConfig(
            sim_time=duration,
            hydraulic_timestep=timestep,
            demand_model=DemandModel.DD,
        ),
        inplace=False,
    ).run(wn)

    pressures_range = wntr_results.get_node_variable(
        "pressure",
        sensor_nodes,
        times=(0, 6 * 3600),
        as_dataframe=True,
    )
    flows_points = wntr_results.get_link_variable(
        "flowrate",
        pipe_names,
        times=[0, 3 * 3600, 6 * 3600, 12 * 3600],
        as_dataframe=True,
    )

    pdd_results = WNTRSimulator(
        config=WNTRSimulatorConfig(
            sim_time=0,
            demand_model=DemandModel.PDD,
        ),
        inplace=False,
    ).run(wn)
    pdd_pressures = pdd_results.get_node_variable(
        "pressure", sensor_nodes, times=0, as_dataframe=True
    )

    rprint("\n[bold]Extended Duration Showcase (WNTR)[/bold]")
    rprint(f"Duration: {duration}s, timestep: {timestep}s")
    rprint("\nPressure extraction for time range (0h to 6h):")
    rprint(pressures_range.head())
    rprint("\nFlow extraction at selected time points:")
    rprint(flows_points)
    rprint("\nPDD mode pressure snapshot at t=0:")
    rprint(pdd_pressures)


def main() -> None:
    """Run both static simulation showcases."""
    rprint("[bold]HydroForge Static Simulation Example[/bold]")
    run_steady_state_comparison()
    run_extended_duration_showcase()
    rprint("\n[green]All static simulation showcases completed successfully.[/green]")


if __name__ == "__main__":
    main()
