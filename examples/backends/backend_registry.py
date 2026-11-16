"""Discover registered backends without importing every solver package."""

from rich.console import Console
from rich.table import Table

from hydroforge.wdn_modelling.backends import BackendName, get_backend

console = Console()


def main() -> None:
    """Show registered backends and whether each can be resolved."""
    table = Table(title="HydroForge Backend Registry")
    table.add_column("Name", style="cyan")
    table.add_column("Status")
    table.add_column("Adapter", style="dim")

    for name in BackendName:
        try:
            backend = get_backend(name.value)
        except (ImportError, ModuleNotFoundError) as exc:
            table.add_row(name.value, "[yellow]unavailable[/yellow]", str(exc))
        else:
            table.add_row(
                name.value, "[green]available[/green]", type(backend).__name__
            )

    console.print(table)


if __name__ == "__main__":
    main()
