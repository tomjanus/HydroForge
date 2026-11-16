"""Select PTSNet, configure a transient model, and run a simulation."""

from pathlib import Path

from rich.console import Console

from hydroforge.wdn_modelling.backends import get_backend
from hydroforge.wdn_modelling.backends.ptsnet.config import PTSNetConfig

MODEL = Path(__file__).resolve().parents[2] / "tests/base_networks/Net1.inp"
console = Console()


def main() -> None:
    backend = get_backend("ptsnet")
    model = backend.load_model(MODEL)
    config = PTSNetConfig(
        duration=2.0,
        time_step=0.01,
        default_wave_speed=1000.0,
        show_progress=True,
    )
    backend.apply_config(config)
    results = backend.create_simulator(config).run(model)
    console.print("[bold green]PTSNet backend loaded and configured[/bold green]")
    console.print(f"[cyan]Simulation:[/cyan] {results.model}")


if __name__ == "__main__":
    try:
        main()
    except (ImportError, ModuleNotFoundError) as exc:
        console.print(f"[yellow]PTSNet example skipped: {exc}[/yellow]")
