"""Select WNTR, load an EPANET model, configure it, and simulate it."""

from pathlib import Path

from rich.console import Console

from hydroforge.backends import get_backend
from hydroforge.backends.wntr.config import (
    EPANETSimulatorConfig,
    WNTRConfig,
    WNTRTimeConfig,
)
from hydroforge.backends.wntr_backend import WNTRBackend

MODEL = Path(__file__).resolve().parents[2] / "tests/base_networks/Net1.inp"
console = Console()


def main() -> None:
    backend = get_backend("wntr")
    model = backend.load_model(MODEL)
    config = WNTRConfig(time=WNTRTimeConfig(duration=0))
    backend.apply_config(config)
    results = backend.create_simulator().run(model)
    pressure = results.raw.node["pressure"]
    console.print("[bold green]WNTR backend loaded and configured[/bold green]")
    console.print(f"[cyan]Model:[/cyan] {MODEL}")
    console.print(
        f"[cyan]Pressure results:[/cyan] {pressure.shape[0]} time rows x {pressure.shape[1]} nodes"
    )

    epanet_backend = WNTRBackend(simulator="epanet")
    epanet_model = epanet_backend.load_model(MODEL)
    epanet_backend.apply_config(config)
    epanet_results = epanet_backend.create_simulator(
        EPANETSimulatorConfig(file_prefix="hydroforge_epanet_example")
    ).run(epanet_model)
    console.print("[bold green]EPANET runtime options applied separately[/bold green]")
    console.print(
        f"[cyan]EPANET pressure results:[/cyan] "
        f"{epanet_results.raw.node['pressure'].shape[0]} time rows"
    )


if __name__ == "__main__":
    main()
