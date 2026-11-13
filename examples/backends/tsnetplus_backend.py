"""Select TSNetPlus, add an event, and run a transient simulation."""

from pathlib import Path

from rich.console import Console

from hydroforge.backends import get_backend
from hydroforge.backends.tsnetplus.config import TSNetPlusConfig
from hydroforge.backends.tsnetplus.events import DemandPulseEvent

MODEL = Path(__file__).resolve().parents[2] / "data/case_studies/tsnet/Tnet1.inp"
console = Console()


def main() -> None:
    """Configure TSNetPlus and schedule a demand-pulse event."""
    backend = get_backend("tsnetplus")
    model = backend.load_model(MODEL)
    config = TSNetPlusConfig(
        duration=20.0,
        time_step=0.1,
        wave_speed=1200.0,
        results_name=None,
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
    console.print("[bold green]TSNetPlus event simulation completed[/bold green]")
    console.print(
        f"[cyan]Simulation timestamps:[/cyan] "
        f"{len(results.model.simulation_timestamps)}"
    )


if __name__ == "__main__":
    try:
        main()
    except (ImportError, ModuleNotFoundError) as exc:
        console.print(f"[yellow]TSNetPlus example skipped: {exc}[/yellow]")
