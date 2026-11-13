"""Demonstrate the WNTR configuration interface."""

from __future__ import annotations

import pathlib

import wntr
from rich import print as rprint

from hydroforge.backends.wntr.config import (
    WNTRConfig,
    WNTRHydraulicConfig,
    WNTRReportConfig,
    WNTRTimeConfig,
)


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Load a WNTR model
    # ------------------------------------------------------------------

    network_file = (
        pathlib.Path(__file__).resolve().parents[2] / "tests/base_networks/Net1.inp"
    )
    model = wntr.network.WaterNetworkModel(network_file)

    rprint("\n[bold cyan]1. Loaded WNTR model[/bold cyan]")
    rprint(f"Network: [green]{network_file}[/green]")

    # ------------------------------------------------------------------
    # 2. Read the actual WNTR options into a configuration
    # ------------------------------------------------------------------

    original_config = WNTRConfig.from_options(model.options)

    rprint("\n[bold cyan]2. Current WNTR configuration[/bold cyan]")
    original_config.print(
        title="Current WNTR Options",
    )

    # ------------------------------------------------------------------
    # 3. Create a partial configuration
    #
    # None means "do not modify this option".
    #
    # Only these four options will be considered when the configuration
    # is applied.
    # ------------------------------------------------------------------

    config = WNTRConfig(
        time=WNTRTimeConfig(
            hydraulic_timestep=900,
            report_timestep=900,
        ),
        hydraulic=WNTRHydraulicConfig(
            demand_model="PDA",
            required_pressure=10.0,
        ),
    )

    rprint("\n[bold cyan]3. Proposed partial configuration[/bold cyan]")

    config.print(
        title="Proposed WNTR Configuration",
    )

    # ------------------------------------------------------------------
    # 4. Show what would change before applying anything
    # ------------------------------------------------------------------

    rprint("\n[bold cyan]4. Proposed changes[/bold cyan]")

    config.print_comparison_table(
        model.options,
        title="WNTR Configuration — Before Applying",
    )

    # The model has not been modified yet.
    assert config.is_applied(model.options) is False

    # ------------------------------------------------------------------
    # 5. Show the exact differences programmatically
    # ------------------------------------------------------------------

    differences = config.differences(model.options)

    rprint("\n[bold cyan]5. Configuration differences[/bold cyan]")

    if differences:
        for section, options in differences.items():
            for name, (expected, actual) in options.items():
                rprint(
                    f"  [magenta]{section}.{name}[/magenta]: "
                    f"[green]{actual!r}[/green] "
                    "→ "
                    f"[yellow]{expected!r}[/yellow]"
                )
    else:
        rprint("  [green]No differences[/green]")

    # ------------------------------------------------------------------
    # 6. Convert the configuration to a NEW WNTR Options object
    #
    # This must not modify model.options.
    # ------------------------------------------------------------------

    options_copy = config.to_options(model.options)

    rprint("\n[bold cyan]6. Converted configuration to WNTR Options[/bold cyan]")

    assert options_copy is not model.options

    # The new options object contains the requested changes.
    assert options_copy.time.hydraulic_timestep == 900
    assert options_copy.time.report_timestep == 900
    assert options_copy.hydraulic.demand_model == "PDA"
    assert options_copy.hydraulic.required_pressure == 10.0

    # But the actual model is still unchanged.
    assert (
        model.options.time.hydraulic_timestep == original_config.time.hydraulic_timestep
    )

    assert (
        model.options.hydraulic.demand_model == original_config.hydraulic.demand_model
    )

    rprint("  [green]✓ model.options was not modified[/green]")

    # ------------------------------------------------------------------
    # 7. Apply the configuration to the model
    # ------------------------------------------------------------------

    rprint("\n[bold cyan]7. Applying configuration[/bold cyan]")

    changes = config.apply_to(model.options)

    number_changes = sum(len(section) for section in changes.values())

    rprint(f"  [green]Updated {number_changes} WNTR options[/green]")

    # Print exactly what was changed.
    for section, section_changes in changes.items():
        for name, (old, new) in section_changes.items():
            rprint(
                f"  [magenta]{section}.{name}[/magenta]: "
                f"{old!r} → [green]{new!r}[/green]"
            )

    # ------------------------------------------------------------------
    # 8. Verify that the configuration was actually applied
    # ------------------------------------------------------------------

    rprint("\n[bold cyan]8. Verifying configuration[/bold cyan]")

    assert config.is_applied(model.options)

    config.verify(model.options)

    rprint("  [green]✓ All configured options match the model[/green]")

    # ------------------------------------------------------------------
    # 9. Display the configuration against the modified model
    # ------------------------------------------------------------------

    rprint("\n[bold cyan]9. Configuration after applying[/bold cyan]")

    config.print_comparison_table(
        model.options,
        title="WNTR Configuration — After Applying",
    )

    # ------------------------------------------------------------------
    # 10. Demonstrate that applying the same configuration again
    #     produces no changes.
    # ------------------------------------------------------------------

    rprint("\n[bold cyan]10. Applying the same configuration again[/bold cyan]")

    changes = config.apply_to(model.options)

    assert changes == {}

    rprint("  [green]✓ No changes were necessary[/green]")

    # ------------------------------------------------------------------
    # 11. Demonstrate from_options() after modification
    # ------------------------------------------------------------------

    rprint("\n[bold cyan]11. Read modified model back into WNTRConfig[/bold cyan]")

    modified_config = WNTRConfig.from_options(model.options)

    assert modified_config.time.hydraulic_timestep == 900
    assert modified_config.time.report_timestep == 900
    assert modified_config.hydraulic.demand_model == "PDA"
    assert modified_config.hydraulic.required_pressure == 10.0

    modified_config.print(
        title="Complete WNTR Configuration After Modification",
    )

    # ------------------------------------------------------------------
    # 12. Restore the original configuration
    # ------------------------------------------------------------------

    rprint("\n[bold cyan]12. Restoring original configuration[/bold cyan]")

    restore_changes = original_config.apply_to(model.options)

    number_restored = sum(len(section) for section in restore_changes.values())

    rprint(f"  [green]Restored {number_restored} WNTR options[/green]")

    # ------------------------------------------------------------------
    # 13. Verify that the model is exactly back to its original state
    # ------------------------------------------------------------------

    rprint("\n[bold cyan]13. Verifying complete restoration[/bold cyan]")

    restored_config = WNTRConfig.from_options(model.options)

    assert restored_config == original_config

    original_config.verify(model.options)

    assert original_config.is_applied(model.options)

    rprint("  [green]✓ Model options exactly match the original configuration[/green]")

    # ------------------------------------------------------------------
    # 14. Show final comparison
    # ------------------------------------------------------------------

    original_config.print_comparison_table(
        model.options,
        title="Final WNTR Configuration — Restored",
    )

    rprint(
        "\n[bold green]✓ Configuration demonstration completed successfully[/bold green]"
    )


if __name__ == "__main__":
    main()
