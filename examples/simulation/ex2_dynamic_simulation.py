"""Example: dynamic simulation with the TSNetPlus backend."""

from __future__ import annotations

from pathlib import Path

from rich import print as rprint

from hydroforge.backends import get_backend


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


def run_tsnetplus() -> None:
    """Run TSNetPlus through the common backend API."""
    from hydroforge.backends.tsnetplus.config import TSNetPlusConfig

    backend = get_backend("tsnetplus")
    model = backend.load_model(_tsnet_network_path())
    # Initialize steady state simulation
    # t0 = 0 # initialize the simulation at 0 [s]
    # engine = 'DD' # demand driven simulator
    # model = tsnetplus.simulation.initialize(model, t0, engine)
    duration = 20.0
    time_step = 0.1
    config = TSNetPlusConfig(
        wave_speed=1200.0,
        duration=duration,
        time_step=time_step,
        friction_model="steady",
        results_name=None,
        clean_files=True,
    )
    backend.apply_config(config)
    results = backend.create_simulator(config).run(model)
    rprint(
        f"TSNetPlus completed: {len(results.model.simulation_timestamps)} time steps"
    )
    rprint("Plotting results...")
    plot_results(results, backend)


def run_tsnetplus_with_events() -> None:
    """Run TSNetPlus after scheduling a transient demand-pulse event.

    The event is applied to the loaded transient model before the simulator
    is constructed and run.
    """
    from hydroforge.backends.tsnetplus.config import TSNetPlusConfig
    from hydroforge.backends.tsnetplus.events import DemandPulseEvent

    backend = get_backend("tsnetplus")
    model = backend.load_model(_tsnet_network_path())
    config = TSNetPlusConfig(
        wave_speed=1200.0,
        duration=20.0,
        time_step=0.1,
        friction_model="steady",
        results_name=None,
        clean_files=True,
    )
    backend.apply_config(config)
    backend.add_event(
        DemandPulseEvent(
            node="N2",
            pulse_duration=1.0,
            start_time=2.0,
            duration_time=4.0,
            multiplier=1.5,
        )
    )
    results = backend.create_simulator(config).run(model)
    rprint(
        f"TSNetPlus event simulation completed: "
        f"{len(results.model.simulation_timestamps)} time steps"
    )
    plot_results(results, backend)


def plot_results(results, backend):
    # report results
    import matplotlib.pyplot as plt

    node = "N2"
    tm = backend.model
    if tm is None:
        raise RuntimeError("A TSNetPlus model must be loaded before plotting.")
    node = tm.get_node(node)
    head1 = node.head

    fig = plt.figure(figsize=(8, 5), dpi=80, facecolor="w", edgecolor="k")
    plt.plot(tm.simulation_timestamps, head1, "k", label="dpa =1", linewidth=2.5)
    # plt.plot(tm.simulation_timestamps,head2, 'r', label ='dpa =2', linewidth=2.5)
    plt.xlim([tm.simulation_timestamps[0], tm.simulation_timestamps[-1]])
    plt.xlabel("Time [s]")
    plt.ylabel("Pressure Head [m]")
    plt.legend(loc="best")
    plt.show()
    # fig.savefig('demand_pulse_N2.pdf', format='pdf',dpi=500)


def main() -> None:
    """Run TSNetPlus when its optional dependency is installed."""
    try:
        run_tsnetplus()
    except (ImportError, ModuleNotFoundError) as exc:
        rprint(
            f"[yellow]Skipping tsnetplus: optional dependency unavailable ({exc}).[/yellow]"
        )


if __name__ == "__main__":
    main()
