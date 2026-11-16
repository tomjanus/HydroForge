""" """

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields
from typing import Any, ClassVar, TypeVar

import wntr
from rich.table import Table
from rich import box
from rich.console import Console
from rich.text import Text

from ...auxiliary.logging_utils import get_logger
from ..common.constants import DemandModel

ConfigT = TypeVar("ConfigT", bound="WNTRConfigSection")

logger = get_logger(__name__)


@dataclass(slots=True)
class WNTRSimulatorConfig:
    """Runtime configuration for the WNTR Python simulator.

    WNTR's Python simulator currently has no HydroForge-specific runtime
    options. Network options belong in :class:`WNTRConfig` and are applied
    by the backend before a simulation is created.
    """


@dataclass(slots=True)
class EPANETSimulatorConfig:
    """Runtime configuration for the EPANET simulator.

    Parameters
    ----------
    file_prefix : str, default="temp"
        Prefix used for EPANET's temporary input, report, binary, and
        hydraulic files.
    demand_model : DemandModel, default=DemandModel.DD
        Demand model expected by the EPANET engine.
    cleanup_files : bool, default=True
        Whether temporary EPANET files are removed after the simulation.
    """

    file_prefix: str = "temp"
    demand_model: DemandModel = DemandModel.DD
    cleanup_files: bool = True


def _format_value(value: Any) -> str:
    """Format a configuration value for Rich output."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        return value
    return repr(value)


def _value_text(
    value: Any,
    *,
    style: str | None = None,
) -> Text:
    """Create styled Rich text for a value."""
    return Text(_format_value(value), style=style or "")


@dataclass
class WNTRConfigSection:
    """Base class for a partial WNTR options section."""

    def to_dict(
        self,
        *,
        include_none: bool = False,
    ) -> dict[str, Any]:
        """Return configured values as a dictionary."""
        result: dict[str, Any] = {}

        for field in fields(self):
            value = getattr(self, field.name)
            if value is None and not include_none:
                continue
            result[field.name] = deepcopy(value)
        return result

    @classmethod
    def from_options(
        cls: type[ConfigT],
        options: Any,
    ) -> ConfigT:
        """Create a configuration from a WNTR options section."""
        values: dict[str, Any] = {}
        for field in fields(cls):
            if hasattr(options, field.name):
                values[field.name] = deepcopy(getattr(options, field.name))
        return cls(**values)

    def apply_to(
        self,
        options: Any,
    ) -> dict[str, tuple[Any, Any]]:
        """Apply configured values to a WNTR options section.

        Only values that are not ``None`` and differ from the
        current value are assigned.

        Returns
        -------
        dict
            Mapping of changed option names to ``(old, new)`` values.
        """
        changes: dict[str, tuple[Any, Any]] = {}
        for field in fields(self):
            new_value = getattr(self, field.name)
            if new_value is None:
                continue
            old_value = getattr(options, field.name)
            if old_value == new_value:
                continue
            changes[field.name] = (
                deepcopy(old_value),
                deepcopy(new_value),
            )
            setattr(options, field.name, deepcopy(new_value))
        return changes

    def differences(
        self,
        options: Any,
    ) -> dict[str, tuple[Any, Any]]:
        """Return configured values that differ from WNTR options."""
        differences: dict[str, tuple[Any, Any]] = {}
        for field in fields(self):
            expected = getattr(self, field.name)
            if expected is None:
                continue
            actual = getattr(options, field.name)
            if actual != expected:
                differences[field.name] = (
                    deepcopy(expected),
                    deepcopy(actual),
                )
        return differences


@dataclass
class WNTRTimeConfig(WNTRConfigSection):
    """Partial configuration of WNTR time options."""

    duration: float | None = None
    hydraulic_timestep: int | None = None
    quality_timestep: int | None = None
    rule_timestep: int | None = None
    pattern_timestep: int | None = None
    pattern_start: float | None = None
    report_timestep: int | None = None
    report_start: float | None = None
    start_clocktime: float | None = None
    statistic: str | None = None
    pattern_interpolation: bool | None = None


@dataclass
class WNTRHydraulicConfig(WNTRConfigSection):
    """Partial configuration of WNTR hydraulic options."""

    headloss: str | None = None
    hydraulics: str | None = None
    hydraulics_filename: str | None = None
    viscosity: float | None = None
    specific_gravity: float | None = None
    pattern: str | None = None
    demand_multiplier: float | None = None
    demand_model: str | None = None
    minimum_pressure: float | None = None
    required_pressure: float | None = None
    pressure_exponent: float | None = None
    emitter_exponent: float | None = None
    trials: int | None = None
    accuracy: float | None = None
    unbalanced: str | None = None
    unbalanced_value: int | None = None
    checkfreq: int | None = None
    maxcheck: int | None = None
    damplimit: float | None = None
    headerror: float | None = None
    flowchange: float | None = None
    inpfile_units: str | None = None
    inpfile_pressure_units: str | None = None


@dataclass
class WNTRReportConfig(WNTRConfigSection):
    """Partial configuration of WNTR report options."""

    pagesize: int | None = None
    report_filename: str | None = None
    status: str | None = None
    summary: str | None = None
    energy: str | None = None
    nodes: bool | None = None
    links: bool | None = None
    report_params: dict[str, bool] | None = None
    param_opts: dict[str, dict[str, Any]] | None = None


@dataclass
class WNTRQualityConfig(WNTRConfigSection):
    """Partial configuration of WNTR quality options."""

    parameter: str | None = None
    trace_node: str | None = None
    chemical_name: str | None = None
    diffusivity: float | None = None
    tolerance: float | None = None
    inpfile_units: str | None = None


@dataclass
class WNTRReactionConfig(WNTRConfigSection):
    """Partial configuration of WNTR reaction options."""

    bulk_order: float | None = None
    wall_order: float | None = None
    tank_order: float | None = None
    bulk_coeff: float | None = None
    wall_coeff: float | None = None
    limiting_potential: float | None = None
    roughness_correl: float | None = None


@dataclass
class WNTREnergyConfig(WNTRConfigSection):
    """Partial configuration of WNTR energy options."""

    global_price: float | None = None
    global_pattern: str | None = None
    global_efficiency: float | None = None
    demand_charge: float | None = None


@dataclass
class WNTRGraphicsConfig(WNTRConfigSection):
    """Partial configuration of WNTR graphics options."""

    dimensions: list[str] | None = None
    units: str | None = None
    offset: list[str] | None = None
    image_filename: str | None = None
    map_filename: str | None = None


@dataclass
class WNTRUserConfig(WNTRConfigSection):
    """Partial configuration of WNTR user options."""

    values: dict[str, Any] | None = None


@dataclass
class WNTRConfig:
    """Partial configuration of WNTR model options.

    A value of ``None`` means that the option is not configured and
    must not be modified when the configuration is applied.
    """

    time: WNTRTimeConfig | None = None
    hydraulic: WNTRHydraulicConfig | None = None
    report: WNTRReportConfig | None = None
    quality: WNTRQualityConfig | None = None
    reaction: WNTRReactionConfig | None = None
    energy: WNTREnergyConfig | None = None
    graphics: WNTRGraphicsConfig | None = None
    user: WNTRUserConfig | None = None

    _SECTION_TYPES: ClassVar[dict[str, type[WNTRConfigSection]]] = {
        "time": WNTRTimeConfig,
        "hydraulic": WNTRHydraulicConfig,
        "report": WNTRReportConfig,
        "quality": WNTRQualityConfig,
        "reaction": WNTRReactionConfig,
        "energy": WNTREnergyConfig,
        "graphics": WNTRGraphicsConfig,
        "user": WNTRUserConfig,
    }

    @classmethod
    def from_options(
        cls,
        options: wntr.network.options,
    ) -> WNTRConfig:
        """Create a complete configuration from WNTR options."""

        return cls(
            time=WNTRTimeConfig.from_options(options.time),
            hydraulic=WNTRHydraulicConfig.from_options(options.hydraulic),
            report=WNTRReportConfig.from_options(options.report),
            quality=WNTRQualityConfig.from_options(options.quality),
            reaction=WNTRReactionConfig.from_options(options.reaction),
            energy=WNTREnergyConfig.from_options(options.energy),
            graphics=WNTRGraphicsConfig.from_options(options.graphics),
            user=WNTRUserConfig.from_options(options.user),
        )

    def to_options(
        self,
        options: wntr.network.options | None = None,
    ) -> wntr.network.options:
        """Return WNTR options with this configuration applied.

        Parameters
        ----------
        options
            Existing WNTR options to copy and modify. If ``None``,
            a new WNTR ``Options`` object is created.

        Returns
        -------
        wntr.network.options
            An independent WNTR options object.
        """
        if options is None:
            result = wntr.network.options()
        else:
            result = deepcopy(options)

        self.apply_to(result)

        return result

    def apply_to(
        self,
        options: wntr.network.options,
    ) -> dict[str, dict[str, tuple[Any, Any]]]:
        """Apply configured values to WNTR options.

        Only non-``None`` values are considered. An option is assigned
        only when its configured value differs from the current value.

        Returns
        -------
        dict
            Mapping of section names to changed options.
        """
        changes: dict[str, dict[str, tuple[Any, Any]]] = {}

        for field in fields(self):
            if field.name.startswith("_"):
                continue

            config = getattr(self, field.name)

            if config is None:
                continue

            target = getattr(options, field.name)

            section_changes = config.apply_to(target)

            if section_changes:
                changes[field.name] = section_changes

        return changes

    def differences(
        self,
        options: wntr.network.options,
    ) -> dict[str, dict[str, tuple[Any, Any]]]:
        """Return configured values that differ from WNTR options."""

        differences: dict[str, dict[str, tuple[Any, Any]]] = {}

        for field in fields(self):
            if field.name.startswith("_"):
                continue

            config = getattr(self, field.name)

            if config is None:
                continue

            target = getattr(options, field.name)

            section_differences = config.differences(target)

            if section_differences:
                differences[field.name] = section_differences

        return differences

    def is_applied(
        self,
        options: wntr.network.options,
    ) -> bool:
        """Return True if all configured values are applied."""
        return not self.differences(options)

    def verify(
        self,
        options: wntr.network.options,
    ) -> None:
        """Raise an error if the configuration is not applied."""
        differences = self.differences(options)

        if differences:
            raise ValueError(
                "WNTR configuration was not applied correctly: " f"{differences!r}"
            )

    def as_table(
        self,
        *,
        title: str = "WNTR Configuration",
        show_none: bool = False,
    ) -> Table:
        """Create a Rich table showing configured WNTR options."""

        table = Table(
            title=title,
            title_style="bold cyan",
            box=box.ROUNDED,
            border_style="bright_black",
            header_style="bold white",
            row_styles=["", "dim"],
            padding=(0, 1),
            expand=False,
        )

        table.add_column(
            "Section",
            style="bold magenta",
            no_wrap=True,
        )
        table.add_column(
            "Option",
            style="cyan",
            no_wrap=True,
        )
        table.add_column(
            "Value",
            justify="right",
        )

        for section_field in fields(self):
            if section_field.name.startswith("_"):
                continue

            config = getattr(self, section_field.name)

            if config is None:
                continue

            first = True

            for option_field in fields(config):
                value = getattr(config, option_field.name)

                if value is None and not show_none:
                    continue

                section = (
                    Text(section_field.name, style="bold magenta")
                    if first
                    else Text("")
                )

                first = False

                value_style = "dim" if value is None else "green"

                table.add_row(
                    section,
                    Text(option_field.name, style="cyan"),
                    _value_text(value, style=value_style),
                )

        return table

    def print(
        self,
        console: Console | None = None,
        *,
        title: str = "WNTR Configuration",
        show_none: bool = False,
    ) -> None:
        """Display the configuration using Rich."""

        if console is None:
            console = Console()

        console.print(
            self.as_table(
                title=title,
                show_none=show_none,
            )
        )

    def comparison_table(
        self,
        options: wntr.network.options.Options,
        *,
        title: str = "WNTR Configuration Changes",
        show_unchanged: bool = False,
    ) -> Table:
        """Create a Rich table comparing configuration with WNTR options.

        Parameters
        ----------
        options
            WNTR options to compare against.
        title
            Title displayed above the table.
        show_unchanged
            If ``True``, show both changed and unchanged configured options.
            If ``False``, show only options whose configured value differs
            from the current WNTR value.
        """

        table = Table(
            title=title,
            title_style="bold cyan",
            box=box.ROUNDED,
            border_style="bright_black",
            header_style="bold white",
            padding=(0, 1),
            expand=False,
        )

        table.add_column(
            "Section",
            style="bold magenta",
            no_wrap=True,
        )
        table.add_column(
            "Option",
            style="cyan",
            no_wrap=True,
        )
        table.add_column(
            "Configured",
            justify="right",
        )
        table.add_column(
            "Current",
            justify="right",
        )
        table.add_column(
            "Status",
            justify="center",
            no_wrap=True,
        )

        changed = 0
        unchanged = 0

        for section_field in fields(self):
            if section_field.name.startswith("_"):
                continue
            config = getattr(self, section_field.name)
            if config is None:
                continue
            target = getattr(options, section_field.name)
            first = True

            for option_field in fields(config):
                expected = getattr(config, option_field.name)
                # None means that this option is not configured.
                if expected is None:
                    continue
                actual = getattr(target, option_field.name)
                is_changed = expected != actual
                if is_changed:
                    changed += 1
                else:
                    unchanged += 1
                    # When requested, hide options that are already correct.
                    if not show_unchanged:
                        continue

                section = (
                    Text(section_field.name, style="bold magenta")
                    if first
                    else Text("")
                )
                first = False

                if is_changed:
                    configured = _value_text(
                        expected,
                        style="bold green",
                    )
                    current = _value_text(
                        actual,
                        style="bold red",
                    )
                    status = Text(
                        "CHANGED",
                        style="bold yellow",
                    )
                else:
                    configured = _value_text(
                        expected,
                        style="dim green",
                    )
                    current = _value_text(
                        actual,
                        style="dim",
                    )
                    status = Text(
                        "OK",
                        style="dim green",
                    )
                table.add_row(
                    section,
                    Text(option_field.name, style="cyan"),
                    configured,
                    current,
                    status,
                )

        # Add a summary footer.
        table.add_row(
            "",
            Text("Summary", style="bold white"),
            Text(
                f"{changed} changed",
                style="bold yellow" if changed else "dim",
            ),
            Text(
                f"{unchanged} unchanged",
                style="dim",
            ),
            Text(
                "✓" if changed == 0 else "!",
                style=("bold green" if changed == 0 else "bold yellow"),
            ),
        )
        return table

    def print_comparison_table(
        self,
        options: wntr.network.options.Options,
        console: Console | None = None,
        *,
        title: str = "WNTR Configuration Changes",
        show_unchanged=False,
    ) -> None:
        """Display configuration differences using Rich."""

        if console is None:
            console = Console()

        console.print(
            self.comparison_table(options, title=title, show_unchanged=show_unchanged)
        )
