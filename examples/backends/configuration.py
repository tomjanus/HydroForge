"""Inspect transient backend configs without loading a network or solver."""

from dataclasses import fields
from typing import Any

from rich.console import Console
from rich.table import Table

from hydroforge.wdn_modelling.backends.ptsnet.config import PTSNetConfig
from hydroforge.wdn_modelling.backends.tsnet.config import TSNetConfig
from hydroforge.wdn_modelling.backends.tsnetplus.config import TSNetPlusConfig
from hydroforge.wdn_modelling.backends.wntr.config import (
    EPANETSimulatorConfig,
    WNTRSimulatorConfig,
)

console = Console()


def _config_table(config_type: Any, title: str) -> Table:
    table = Table(title=title)
    table.add_column("Option", style="cyan")
    table.add_column("Default", style="green")
    for config_field in fields(config_type):
        table.add_row(config_field.name, repr(config_field.default))
    return table


def main() -> None:
    """Display model and simulator configuration defaults."""
    console.print(_config_table(TSNetConfig, "TSNetConfig"))
    console.print(_config_table(TSNetPlusConfig, "TSNetPlusConfig"))
    console.print(_config_table(PTSNetConfig, "PTSNetConfig"))
    console.print(_config_table(WNTRSimulatorConfig, "WNTRSimulatorConfig"))
    console.print(_config_table(EPANETSimulatorConfig, "EPANETSimulatorConfig"))
    console.print(
        "[dim]These config imports do not load a network model or run a simulation.[/dim]"
    )


if __name__ == "__main__":
    main()
