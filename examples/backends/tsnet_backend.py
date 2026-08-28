"""Select TSNet, configure a transient model, and run MOC simulation."""
from pathlib import Path

from rich.console import Console

from hydroforge.backends import get_backend
from hydroforge.backends.tsnet.config import TSNetConfig


MODEL = Path(__file__).resolve().parents[2] / "tests/base_networks/Net1.inp"
console = Console()


def main() -> None:
    backend = get_backend("tsnet")
    model = backend.load_model(MODEL)
    config = TSNetConfig(duration=2.0, time_step=0.01, wave_speed=1200.0)
    backend.apply_config(config)
    results = backend.create_simulator(config).run(model)
    console.print("[bold green]TSNet backend loaded and configured[/bold green]")
    console.print(f"[cyan]Simulation timestamps:[/cyan] {len(results.model.simulation_timestamps)}")


if __name__ == "__main__":
    try:
        main()
    except (ImportError, ModuleNotFoundError) as exc:
        console.print(f"[yellow]TSNet example skipped: {exc}[/yellow]")
