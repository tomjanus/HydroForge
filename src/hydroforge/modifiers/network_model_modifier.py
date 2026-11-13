"""
This module provides classes for modifying a water network model represented
by the WNTR (Water Network Tool for Resilience) library.
It includes functionalities to modify pipe diameters, roughness, node demands, and valve settings.
The module also provides a pipeline to manage and apply a sequence of network component modifiers.
"""

from __future__ import annotations
from typing import (
    TypeAlias,
    List,
    Any,
    Iterable,
    Union,
    Mapping,
    Type,
    ClassVar,
    Optional,
    Dict,
)
from collections.abc import Hashable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import pathlib
import wntr
import numpy as np
import pandas as pd
from rich import print as rprint
from hydroforge.auxiliary.utils import ensure_directory_exists, log
from hydroforge.uncertainty.parameters import Parameter

NumpyFloat = (
    np.float64
)  # Compatible with numpy2.0 - earlier versions accepted np.float_
WNTRNetworkModel: TypeAlias = wntr.network.WaterNetworkModel
ComponentName: TypeAlias = Hashable
NumValue: TypeAlias = Union[int, float, np.int_, NumpyFloat]
CatValue: TypeAlias = Any  # e.g. str, enums, labels


class StructuredLoggingMixin:
    """Provides structured logging functionality for component modifiers."""

    def __init__(self, enable_structured_log: bool = False) -> None:
        self.enable_structured_log = enable_structured_log
        self.structured_log: dict[str, list[dict[str, Any]]] = {}

    def add_to_structured_log(
        self,
        component_name: ComponentName,
        component_type: str,
        attribute: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        """Add an entry to the structured log if structured logging is enabled."""
        if not self.enable_structured_log:
            return
        class_name = self.__class__.__name__
        self.structured_log.setdefault(class_name, [])
        _log_entry = {
            "component_name": component_name,
            "component_type": component_type,
            "attribute": attribute,
            "old_value": old_value,
            "new_value": new_value,
        }
        self.structured_log[class_name].append(_log_entry)


class NetworkComponentModifier(ABC):  # pylint: disable=too-few-public-methods
    """Abstract base class for modifying network components in a WNTR network model.

    This class defines the interface for modifying network components
    within a WNTR (Water Network Tool for Resilience) network model.
    Subclasses should implement the `apply` and `undo` methods to
    define specific modifications and their corresponding reversals.
    """

    @abstractmethod
    def apply(self, wn: WNTRNetworkModel) -> None:
        """Applies the network modification to the WNTR network model.
        Args:
            wn (WNTRNetworkModel): The WNTR network model to modify.
        """


@dataclass
class NetworkPipeRemover(NetworkComponentModifier, StructuredLoggingMixin):
    """Remove pipes from the network topology."""

    pipe_names: Iterable[ComponentName]
    log: list[str] = field(default_factory=list)
    enable_structured_log: bool = False

    def __post_init__(self) -> None:
        StructuredLoggingMixin.__init__(self, self.enable_structured_log)

    def apply(self, wn: wntr.network.WaterNetworkModel) -> None:
        for name in self.pipe_names:
            if name in wn.pipe_name_list:
                wn.remove_link(name)
                self.log.append(f"Removed pipe {name}")
            else:
                self.log.append(f"Skipped non-existing pipe {name}")
            # Add structured log entry if enabled
            self.add_to_structured_log(
                component_name=name,
                component_type="pipe",
                attribute="null",
                old_value="existing",
                new_value="removed",
            )


@dataclass
class PipeDiameterModifier(NetworkComponentModifier, StructuredLoggingMixin):
    """Modifies pipe diameters in a WaterNetworkModel.
    This class allows for modifying pipe diameters based on a variety of criteria,
    including a list of pipe names and an uncertainty model.
    It also provides functionality to undo the modifications.
    Attributes:
        new_values (Mapping[ComponentName, Union[NumValue, Parameter]]):
            A mapping of pipe names to their new diameter values.
        log (list[str]): A list of strings representing the modifications that have
            been made. Defaults to an empty list.
    Methods:
        apply(wn: wntr.network.WaterNetworkModel) -> None:
            Applies the diameter modifications to the given WaterNetworkModel.
    """

    new_values: Mapping[ComponentName, Union[NumValue, Parameter]] = field()
    log: list[str] = field(default_factory=list)
    enable_structured_log: bool = False

    def __post_init__(self) -> None:
        StructuredLoggingMixin.__init__(self, self.enable_structured_log)

    def apply(self, wn: wntr.network.WaterNetworkModel) -> None:
        """Apply the network modification to the WaterNetworkModel.
        This method modifies the diameters of pipes in the network based on the
        specified pipe names and applies
        uncertainty if provided.
        Args:
            wn (wntr.network.WaterNetworkModel): The water network model to modify.
        Returns:
            None
        """
        self.log.clear()
        for name, new_value in self.new_values.items():
            pipe = wn.get_link(name)
            if pipe is None:
                continue
            old_val = pipe.diameter
            if isinstance(new_value, Parameter):
                # Ensure nominal value is set
                if new_value.nominal_value is None:
                    new_value.nominal_value = old_val
                new_val = float(new_value.sample())
            elif new_value is not None:
                new_val = float(new_value)
            else:
                new_val = old_val
            pipe.diameter = new_val
            self.log.append(
                f"Pipe '{pipe.name}' modified diameter: {old_val} -> {new_val}"
            )
            # Add structured log entry if enabled
            self.add_to_structured_log(
                component_name=pipe.name,
                component_type="pipe",
                attribute="diameter",
                old_value=old_val,
                new_value=new_val,
            )


@dataclass
class PipeDiameterMultiplierModifier(NetworkComponentModifier, StructuredLoggingMixin):
    """Multiplies pipe diameters in a WaterNetworkModel by specified factors.

    This class allows for scaling pipe diameters by multiplication factors. The factors
    can be specified per-pipe using a dictionary, or as a single scalar value to apply
    to all pipes in the network.

    Attributes:
        multipliers (Union[float, Mapping[ComponentName, Union[NumValue, Parameter]]]):
            Either a single scalar multiplier to apply to all pipes, or a mapping of
            pipe names to their specific multiplier values. Multipliers can also be
            Parameter objects for stochastic scaling.
        log (list[str]): A list of strings representing the modifications that have
            been made. Defaults to an empty list.
        enable_structured_log (bool): If True, enables structured logging of modifications.

    Methods:
        apply(wn: wntr.network.WaterNetworkModel) -> None:
            Applies the diameter multipliers to the given WaterNetworkModel.

    Example:
        >>> # Scale specific pipes
        >>> modifier1 = PipeDiameterMultiplierModifier(
        ...     multipliers={'P1': 0.95, 'P2': 0.85}
        ... )
        >>> modifier1.apply(wn)
        >>>
        >>> # Scale all pipes by the same factor
        >>> modifier2 = PipeDiameterMultiplierModifier(multipliers=0.5)
        >>> modifier2.apply(wn)
        >>>
        >>> # Use uncertain multipliers
        >>> modifier3 = PipeDiameterMultiplierModifier(
        ...     multipliers={
        ...         'P1': Parameter(name='P1', nominal_value=0.95, uncertainty=UniformUncertainty(-0.05, 0.05))
        ...     }
        ... )
    """

    multipliers: Union[float, Mapping[ComponentName, Union[NumValue, Parameter]]] = (
        field()
    )
    log: list[str] = field(default_factory=list)
    enable_structured_log: bool = False

    def __post_init__(self) -> None:
        StructuredLoggingMixin.__init__(self, self.enable_structured_log)

    def apply(self, wn: wntr.network.WaterNetworkModel) -> None:
        """Apply diameter multipliers to pipes in the WaterNetworkModel.

        This method multiplies the diameters of pipes in the network. If multipliers
        is a scalar, it applies to all pipes. If it's a mapping, it only applies to
        the specified pipes.

        Args:
            wn (wntr.network.WaterNetworkModel): The water network model to modify.

        Returns:
            None
        """
        self.log.clear()

        # Determine if we're applying a scalar or per-pipe multipliers
        multiplier_map: Mapping[ComponentName, Any]
        if isinstance(self.multipliers, (int, float, np.int_, np.float64)):
            # Apply scalar multiplier to all pipes
            pipe_names = wn.pipe_name_list
            multiplier_map = {name: self.multipliers for name in pipe_names}
        else:
            # Use the provided mapping
            multiplier_map = self.multipliers

        for name, multiplier in multiplier_map.items():
            pipe = wn.get_link(name)
            if pipe is None:
                continue

            old_val = pipe.diameter

            # Determine the multiplier value
            if isinstance(multiplier, Parameter):
                # Ensure nominal value is set
                if multiplier.nominal_value is None:
                    multiplier.nominal_value = 1.0  # Default to no scaling
                mult_val = float(multiplier.sample())
            elif multiplier is not None:
                mult_val = float(multiplier)
            else:
                mult_val = 1.0

            new_val = old_val * mult_val
            pipe.diameter = new_val

            self.log.append(
                f"Pipe '{pipe.name}' modified diameter: {old_val:.6f} × {mult_val:.6f} = {new_val:.6f}"
            )

            # Add structured log entry if enabled
            self.add_to_structured_log(
                component_name=pipe.name,
                component_type="pipe",
                attribute="diameter",
                old_value=old_val,
                new_value=new_val,
            )


@dataclass
class PipeRoughnessModifier(NetworkComponentModifier, StructuredLoggingMixin):
    """Modifies the roughness of specified pipes in a water network model.
    This class allows for the modification of pipe roughness values based on
    a list of pipe names, and can incorporate
    uncertainty through an `Uncertainty` object. It also provides functionality
    to revert the changes made.
    Attributes:
        new_values (Mapping[ComponentName, Union[NumValue, Parameter]]):
            A mapping of pipe names to their new roughness values or uncertain parameters.
        log (list[str]): A list of strings that logs the changes made to the
            pipe roughness values. Each entry in the list describes the pipe
            name, the old roughness value, and the new roughness value.
    Methods:
        apply(wn: wntr.network.WaterNetworkModel) -> None:
            Applies the new roughness values to the selected pipes in the given
            water network model.
    """

    new_values: Mapping[ComponentName, Union[NumValue, Parameter]] = field()
    log: list[str] = field(default_factory=list)
    enable_structured_log: bool = False

    def __post_init__(self) -> None:
        StructuredLoggingMixin.__init__(self, self.enable_structured_log)

    def apply(self, wn: wntr.network.WaterNetworkModel) -> None:
        """Applies the roughness modification to the water network model.
        This method modifies the roughness of selected pipes in the water network model.
        It stores the original roughness values, determines the target pipes based on
        a list of pipe names, and applies the new
        roughness values, potentially with added uncertainty.
        Args:
            wn (wntr.network.WaterNetworkModel): The water network model to modify.
        Returns:
            None
        """
        self.log.clear()
        for name, new_value in self.new_values.items():
            pipe = wn.get_link(name)
            if pipe is None:
                continue
            old_val = pipe.roughness
            if isinstance(new_value, Parameter):
                # Ensure nominal value is set
                if new_value.nominal_value is None:
                    new_value.nominal_value = old_val
                new_val = float(new_value.sample())
            elif new_value is not None:
                new_val = float(new_value)
            else:
                new_val = old_val
            pipe.roughness = new_val
            self.log.append(f"Pipe '{pipe.name}': roughness {old_val} -> {new_val}")
            # Add structured log entry if enabled
            self.add_to_structured_log(
                component_name=pipe.name,
                component_type="pipe",
                attribute="roughness",
                old_value=old_val,
                new_value=new_val,
            )


@dataclass
class NodeDemandModifier(NetworkComponentModifier, StructuredLoggingMixin):
    """
    A class to modify the base demand of specific nodes in a water network model.
    This class allows for modifying the base demand of nodes based on a list of node names.
    It also supports applying an uncertainty to the new demand values.
    Attributes:
        new_values (Mapping[ComponentName, Union[NumValue, Parameter]]):
            A mapping of node names to their new demand values or uncertain parameters.
        log (list[str]): A list to store log messages about the modifications made.
    Methods:
        apply(wn: wntr.network.WaterNetworkModel) -> None:
            Applies the demand modifications to the given water network model.
    """

    new_values: Mapping[ComponentName, Union[NumValue, Parameter]] = field()
    log: list[str] = field(default_factory=list)
    enable_structured_log: bool = False

    def __post_init__(self) -> None:
        StructuredLoggingMixin.__init__(self, self.enable_structured_log)

    def apply(self, wn: wntr.network.WaterNetworkModel) -> None:
        """Apply the demand modification to the water network model.
        This method modifies the base demand of the targeted junctions in the water network model.
        The target junctions are determined by a list of node names.
        The new demand values can be a single value, a mapping from node names to values, or a value with
        uncertainty applied.
        Args:
            wn (wntr.network.WaterNetworkModel): The water network model to modify.
        Returns:
            None
        """
        self.log.clear()
        for name, new_value in self.new_values.items():
            node = wn.get_node(name)
            if (
                node is None
                or not hasattr(node, "demand_timeseries_list")
                or not node.demand_timeseries_list
            ):
                continue
            old_val = node.demand_timeseries_list[0].base_value
            if isinstance(new_value, Parameter):
                # Ensure nominal value is set
                if new_value.nominal_value is None:
                    new_value.nominal_value = old_val
                new_val = float(new_value.sample())
            elif new_value is not None:
                new_val = float(new_value)
            else:
                new_val = old_val
            node.demand_timeseries_list[0].base_value = new_val
            self.log.append(f"Node '{node.name}': demand {old_val} -> {new_val}")
            # Add structured log entry if enabled
            self.add_to_structured_log(
                component_name=node.name,
                component_type="node",
                attribute="demand",
                old_value=old_val,
                new_value=new_val,
            )


@dataclass
class NodeDemandDataFrameModifier(NetworkComponentModifier, StructuredLoggingMixin):
    """
    A class to modify the base demand of specific nodes in a water network model using demand data
    specified in pandas dataframe.
    Change (base) nodal demand in the network using values provided in the `demands'
    dataframe. For nodes that do not feature in the dataframe, set the (base) demand equal to
    default_value if skip_nonexistent = False, otherwise leave the (base) demand value unchanged.

    Attributes:
        new_values (pd.DataFrame):
            A mapping of node names to their new demand values or uncertain parameters.
        default_value (float): Default base demand used in case the value is not provided in demands.
        skip_nonexistent (bool): If True, the base demand values for nodes not featured in demands are left unchanged.
            Otherwise, set base demand to default_value.
        log (list[str]): A list to store log messages about the modifications made.
    Methods:
        apply(wn: wntr.network.WaterNetworkModel) -> None:
            Applies the demand modifications to the given water network model.
    """

    new_values: pd.DataFrame = field()
    default_value: float = 0.0
    skip_nonexistent: bool = True
    log: list[str] = field(default_factory=list)
    enable_structured_log: bool = False

    def __post_init__(self) -> None:
        StructuredLoggingMixin.__init__(self, self.enable_structured_log)

    def apply(self, wn: wntr.network.WaterNetworkModel) -> None:
        """Apply the demand modification to the water network model.
        This method modifies the base demand of the targeted junctions in the water network model.

        Args:
            wn (wntr.network.WaterNetworkModel): The water network model to modify.
        Returns:
            None
        """
        self.log.clear()
        for node_name in wn.junction_name_list:
            node = wn.get_node(node_name)
            old_val = node.demand_timeseries_list[0].base_value
            if node_name in self.new_values.index:
                # Extract scalar value from DataFrame
                new_val = float(
                    self.new_values.loc[node_name].iloc[0]
                    if isinstance(self.new_values.loc[node_name], pd.Series)
                    else self.new_values.loc[node_name]
                )
                node.demand_timeseries_list[0].base_value = new_val
                self.log.append(f"Node '{node.name}': demand {old_val} -> {new_val}")
                # Add structured log entry if enabled
                self.add_to_structured_log(
                    component_name=node.name,
                    component_type="node",
                    attribute="demand",
                    old_value=old_val,
                    new_value=new_val,
                )
            else:
                if not self.skip_nonexistent:
                    new_val = self.default_value
                    node.demand_timeseries_list[0].base_value = new_val
                    self.log.append(
                        f"Node '{node.name}': demand {old_val} -> {new_val} (default value)"
                    )
                    # Add structured log entry if enabled
                    self.add_to_structured_log(
                        component_name=node.name,
                        component_type="node",
                        attribute="demand",
                        old_value=old_val,
                        new_value=new_val,
                    )


@dataclass
class NodeLeakageModifier(NetworkComponentModifier, StructuredLoggingMixin):
    """
    A class to add leakage to specific nodes in a water network model.

    This class allows for adding leakage (additional demand) to nodes based on a mapping
    of node names to leakage values. It supports applying an uncertainty to the leakage values.
    The leakage is added to the existing base demand of the node.

    Attributes:
        new_values (Mapping[ComponentName, Union[NumValue, Parameter]]):
            A mapping of node names to their leakage values or uncertain parameters.
        log (list[str]): A list to store log messages about the modifications made.
        enable_structured_log (bool): If True, enables structured logging of modifications.

    Methods:
        apply(wn: wntr.network.WaterNetworkModel) -> None:
            Applies the leakage modifications to the given water network model.

    Example:
        >>> leak_modifier = NodeLeakageModifier(
        ...     added_leaks={
        ...         "n303": 0.5,
        ...         "n391": Parameter(name='n391', nominal_value=0.3, uncertainty=UniformUncertainty(-0.1, 0.1))
        ...     },
        ...     enable_structured_log=True
        ... )
        >>> leak_modifier.apply(wn)
    """

    added_leaks: Mapping[ComponentName, Union[NumValue, Parameter]] = field()
    log: list[str] = field(default_factory=list)
    enable_structured_log: bool = False

    def __post_init__(self) -> None:
        StructuredLoggingMixin.__init__(self, self.enable_structured_log)

    def apply(self, wn: wntr.network.WaterNetworkModel) -> None:
        """Apply the leakage modification to the water network model.

        This method adds leakage (as additional demand) to the targeted junctions
        in the water network model. The leakage is added to the existing base demand.

        Args:
            wn (wntr.network.WaterNetworkModel): The water network model to modify.

        Returns:
            None
        """
        self.log.clear()
        for name, leak_value in self.added_leaks.items():
            node = wn.get_node(name)
            if (
                node is None
                or not hasattr(node, "demand_timeseries_list")
                or not node.demand_timeseries_list
            ):
                continue

            old_demand = node.demand_timeseries_list[0].base_value

            # Determine the leakage value to add
            if isinstance(leak_value, Parameter):
                # Ensure nominal value is set
                if leak_value.nominal_value is None:
                    leak_value.nominal_value = 0.0  # Default nominal leakage
                leak_val = float(leak_value.sample())
            elif leak_value is not None:
                leak_val = float(leak_value)
            else:
                leak_val = 0.0

            # Add leakage to existing demand
            new_demand = old_demand + leak_val
            node.demand_timeseries_list[0].base_value = new_demand

            self.log.append(
                f"Node '{node.name}': added leakage {leak_val:.6f} "
                f"(demand {old_demand:.6f} -> {new_demand:.6f})"
            )

            # Add structured log entry if enabled
            self.add_to_structured_log(
                component_name=node.name,
                component_type="node",
                attribute="leakage",
                old_value=old_demand,
                new_value=new_demand,
            )


@dataclass
class NodeEmitterModifier(NetworkComponentModifier, StructuredLoggingMixin):
    """
    A class to add leakage to specific nodes in a water network model using emitter coefficients.

    This class adds leakage to nodes by setting emitter coefficients, which model pressure-dependent
    leakage. The emitter discharge follows the relationship: Q = C * P^gamma, where C is the emitter
    coefficient, P is the pressure, and gamma is the pressure exponent (typically 0.5).

    The emitter coefficient can be calculated from a leak diameter using:
    C = 0.75 * sqrt(2/rho) * rho * A * sqrt(P_nominal)
    where A is the leak area (pi * (diameter/2)^2) and P_nominal is the nominal pressure.

    Attributes:
        emitter_coefficients (Mapping[ComponentName, Union[NumValue, Parameter]]):
            A mapping of node names to their emitter coefficient values or uncertain parameters.
        nominal_pressure (float): Nominal pressure used for calculating
        emitter coefficient from diameter (default: 100).
        pressure_exponent (float): Pressure exponent for emitter equation (default: 0.5).
        required_pressure (Optional[float]): Required pressure to set at nodes
        with emitters (default: None, uses nominal_pressure).
        minimum_pressure (float): Minimum pressure at nodes with emitters (default: 0.0).
        log (list[str]): A list to store log messages about the modifications made.
        enable_structured_log (bool): If True, enables structured logging of modifications.

    Methods:
        apply(wn: wntr.network.WaterNetworkModel) -> None:
            Applies the emitter modifications to the given water network model.
        calculate_emitter_from_diameter(diameter: float, nominal_pressure: float = 100.0) -> float:
            Static method to calculate emitter coefficient from leak diameter.

    Example:
        >>> # Using emitter coefficients directly
        >>> emitter_modifier = NodeEmitterModifier(
        ...     emitter_coefficients={
        ...         "n303": 0.001,
        ...         "n391": Parameter(name='n391', nominal_value=0.0015,
                       uncertainty=UniformUncertainty(-0.0002, 0.0002))
        ...     },
        ...     nominal_pressure=100.0,
        ...     enable_structured_log=True
        ... )
        >>> emitter_modifier.apply(wn)
        >>>
        >>> # Calculate emitter from leak diameter
        >>> leak_diameter = 0.01  # 10mm leak
        >>> emitter_coeff = NodeEmitterModifier.calculate_emitter_from_diameter(leak_diameter)
        >>> emitter_modifier = NodeEmitterModifier(
        ...     emitter_coefficients={"n303": emitter_coeff}
        ... )
    """

    emitter_coefficients: Mapping[ComponentName, Union[NumValue, Parameter]] = field()
    nominal_pressure: float = 100.0  # meters
    pressure_exponent: float = 0.5
    required_pressure: Optional[float] = None  # If None, uses nominal_pressure
    minimum_pressure: float = 0.0
    log: list[str] = field(default_factory=list)
    enable_structured_log: bool = False

    def __post_init__(self) -> None:
        StructuredLoggingMixin.__init__(self, self.enable_structured_log)
        if self.required_pressure is None:
            self.required_pressure = self.nominal_pressure

    @staticmethod
    def calculate_emitter_from_diameter(
        diameter: float,
        nominal_pressure: float = 100.0,
        rho: float = 1000.0,  # water density kg/m³
    ) -> float:
        """
        Calculate emitter coefficient from leak diameter.

        Based on orifice equation: Q = 0.75 * sqrt(2/rho) * rho * A * sqrt(P)
        Emitter equation: Q = C * P^0.5
        Therefore: C = 0.75 * sqrt(2/rho) * rho * A * sqrt(P_nominal)

        Args:
            diameter (float): Leak diameter in meters.
            nominal_pressure (float): Nominal pressure in meters (default: 100.0).
            rho (float): Water density in kg/m³ (default: 1000.0).

        Returns:
            float: Emitter coefficient.
        """
        import math

        leak_area = math.pi * (diameter / 2) ** 2
        emitter_coeff = (
            0.75 * math.sqrt(2 / rho) * rho * leak_area * math.sqrt(nominal_pressure)
        )
        return emitter_coeff

    def apply(self, wn: wntr.network.WaterNetworkModel) -> None:
        """Apply the emitter modification to the water network model.

        This method adds emitters to the targeted junctions in the water network model.
        Emitters model pressure-dependent leakage using the relationship Q = C * P^gamma.

        Args:
            wn (wntr.network.WaterNetworkModel): The water network model to modify.

        Returns:
            None
        """
        self.log.clear()
        for name, emitter_value in self.emitter_coefficients.items():
            node = wn.get_node(name)
            if node is None:
                self.log.append(f"Node '{name}' not found in network, skipping.")
                continue

            # Store old emitter coefficient (None if not set)
            old_emitter = getattr(node, "emitter_coefficient", None)

            # Determine the emitter coefficient value
            if isinstance(emitter_value, Parameter):
                # Ensure nominal value is set
                if emitter_value.nominal_value is None:
                    emitter_value.nominal_value = 0.0  # Default nominal emitter
                emitter_coeff = float(emitter_value.sample())
            elif emitter_value is not None:
                emitter_coeff = float(emitter_value)
            else:
                emitter_coeff = 0.0

            # Set emitter properties
            node.emitter_coefficient = emitter_coeff

            # Set pressure constraints if node is a junction
            if hasattr(node, "required_pressure"):
                node.required_pressure = self.required_pressure
            if hasattr(node, "minimum_pressure"):
                node.minimum_pressure = self.minimum_pressure

            self.log.append(
                f"Node '{node.name}': added emitter with coefficient {emitter_coeff:.6e} "
                f"(old: {old_emitter if old_emitter is not None else 'None'}, "
                f"req_pressure: {self.required_pressure}m, min_pressure: {self.minimum_pressure}m)"
            )

            # Add structured log entry if enabled
            self.add_to_structured_log(
                component_name=node.name,
                component_type="node",
                attribute="emitter_coefficient",
                old_value=old_emitter if old_emitter is not None else 0.0,
                new_value=emitter_coeff,
            )


# TODO: ADD NEW PROPERTY FOR MODIFICATION IN VALVEMODIFIER - INITIAL_STATUS, E.G.
# print(prv.initial_status)    # "OPEN"


@dataclass
class ValveModifier(NetworkComponentModifier, StructuredLoggingMixin):
    """
    A class for modifying valve settings in a water network model.
    This class allows for the modification of valve settings based on a mapping
    of valve names to their new settings or uncertain parameters.
    It supports different valve types and their corresponding setting attributes.
    Attributes:
        new_values (Mapping[ComponentName, Union[NumValue, str, Parameter]]):
            A mapping of valve names to their new settings.
        log (list[str]): A list of strings representing the modifications made to each
            valve, including the valve name, the attribute modified, and the old and
            new values. This is populated during the `apply` method.
        verbose (bool): If True, enables verbose logging for operations such as
            applying modifications to valves. Defaults to False.
    Methods:
        apply(wn: wntr.network.WaterNetworkModel) -> None:
            Applies the modifications to the specified valves in the given water
            network model.
        _determine_setting_type(valve: wntr.network.Valve):
            Determines the appropriate setting attribute for a given valve based on
            its type.
    """

    new_values: Mapping[ComponentName, Union[NumValue, str, Parameter]] = field()
    log: list[str] = field(default_factory=list)
    verbose: bool = False
    enable_structured_log: bool = False

    def __post_init__(self) -> None:
        StructuredLoggingMixin.__init__(self, self.enable_structured_log)

    def apply(self, wn: wntr.network.WaterNetworkModel) -> None:
        """Applies modifications to the specified valves in the water network.

        The modifications include setting a new value to a specific attribute of the valve,
        potentially using an Parameter. The modifications are logged for later inspection.

        Args:
            wn (wntr.network.WaterNetworkModel): The water network model to modify.
        """
        self.log.clear()
        for name, new_value in self.new_values.items():
            if name not in wn.link_name_list:
                if self.verbose:
                    log(
                        msg=f"Link '{name}' not found in network, skipping.",
                        log_type="WARNING",
                    )
                continue

            valve = wn.get_link(name)
            if not isinstance(valve, wntr.network.Valve):
                if self.verbose:
                    log(
                        msg=f"Link '{name}' is not a valve, skipping.",
                        log_type="WARNING",
                    )
                continue

            setting_attr, _ = self._determine_setting_type(valve)
            old_val = getattr(valve, setting_attr)

            if isinstance(new_value, Parameter):
                # Ensure nominal value is set
                if new_value.nominal_value is None:
                    new_value.nominal_value = old_val
                setting_value = new_value.sample()
            elif new_value is not None:
                setting_value = new_value
            else:
                setting_value = old_val

            setattr(valve, setting_attr, setting_value)
            self.log.append(
                f"Valve '{valve.name}' ({valve.valve_type}): "
                f"{setting_attr} {old_val} → {setting_value}"
            )

            # Add structured log entry if enabled
            self.add_to_structured_log(
                component_name=valve.name,
                component_type="valve",
                attribute=setting_attr,
                old_value=old_val,
                new_value=setting_value,
            )

    @staticmethod
    def _determine_setting_type(valve: wntr.network.Valve):
        """
        Map valve type to the attribute and whether it's continuous or discrete.
        """
        vtype = valve.valve_type.upper()
        if vtype in ["PRV", "PSV", "FCV", "TCV"]:
            return "initial_setting", "continuous"
        if vtype in ["GPV"]:
            return "curve", "discrete"
        if vtype in ["PBV"]:  # Pressure breaker: OPEN/CLOSED
            return "status", "discrete"
        raise ValueError(f"Unsupported valve type: {vtype}")


@dataclass
class NetworkModifierPipeline:
    """
    A pipeline for applying and managing a sequence of network component modifiers to a water network model.
    This class allows for the sequential application of modifications to a water network,
    keeping track of the modifications made and providing functionality to undo the last modification.
    It maintains a history of applied modifiers and a log of actions performed.
    Attributes:
        modifiers (List[NetworkComponentModifier]): A list of network component modifiers to be applied.
        history (List[NetworkComponentModifier]): A list of network component modifiers that have been applied,
            in the order they were applied.
        log (List[str]): A list of strings representing the log of actions performed by the modifiers.
    Methods:
        add_modifier(modifier: NetworkComponentModifier) -> None:
            Adds a network component modifier to the pipeline.
        pop_modifier(self) -> None:
            Removes the last modifier from the modifiers list.
        apply(wn: wntr.network.WaterNetworkModel) -> None:
            Applies all modifiers in the pipeline to the given water network model,
            records the applied modifiers in the history, and aggregates the logs.
        undo_last(wn: wntr.network.WaterNetworkModel) -> None:
            Undoes the last applied modifier on the given water network model and aggregates the logs.
    """

    modifiers: List[NetworkComponentModifier] = field()
    history: List[NetworkComponentModifier] = field(default_factory=list)
    log: List[str] = field(default_factory=list)
    structured_log: Optional[Dict[str, List[Dict[str, Any]]]] = None

    SUPPORTED_MODIFIERS: ClassVar[List[Type[NetworkComponentModifier]]] = [
        PipeDiameterModifier,
        PipeDiameterMultiplierModifier,
        PipeRoughnessModifier,
        NodeDemandModifier,
        NodeDemandDataFrameModifier,
        NodeLeakageModifier,
        NodeEmitterModifier,
        ValveModifier,
        NetworkPipeRemover,
    ]

    @classmethod
    def register(cls, modifier_class: Type[NetworkComponentModifier]) -> None:
        """Registers a new network component modifier class.
        Args:
            modifier_class (Type[NetworkComponentModifier]): The modifier class to register.
        Raises:
            TypeError: If the provided class is not a subclass of NetworkComponentModifier.
        """
        if not issubclass(modifier_class, NetworkComponentModifier):
            raise TypeError(
                "Registered class must be a subclass of NetworkComponentModifier"
            )
        cls.SUPPORTED_MODIFIERS.append(modifier_class)

    def add_modifier(self, modifier: NetworkComponentModifier) -> None:
        """Adds a network component modifier to the list of modifiers.
        Args:
            modifier (NetworkComponentModifier): The modifier to add.
        """
        if type(modifier) not in self.SUPPORTED_MODIFIERS:
            rprint(
                f"[red]Warning:[/red] Modifier {type(modifier).__name__} is not a registered modifier."
            )
        self.modifiers.append(modifier)

    def pop_modifier(self) -> None:
        """Removes the last modifier from the modifier stack.
        This method is used to undo the last applied modification to the network.
        It removes the most recently added modifier from the `modifiers` list.
        """
        self.modifiers.pop()

    def apply(self, wn: wntr.network.WaterNetworkModel) -> None:
        """Applies a series of network modifiers to the WaterNetworkModel.
        The modifiers are applied sequentially, and their effects are accumulated in the WaterNetworkModel.
        The history of applied modifiers and their logs are also recorded.
        Args:
            wn (wntr.network.WaterNetworkModel): The water network model to modify.
        """
        for m in self.modifiers:
            m.apply(wn)
            self.history.append(m)
            self.log.extend(getattr(m, "log", []))  # aggregate individual modifier log
            # If modifier has a structured log and it's non-empty, initialize pipeline log
            _structured_log = getattr(m, "structured_log", None)
            if _structured_log:
                if any(_structured_log.values()):  # check for non-empty lists
                    if self.structured_log is None:
                        self.structured_log = {}
                    # Merge logs per class name
                    for cls_name, entries in _structured_log.items():
                        self.structured_log.setdefault(cls_name, []).extend(entries)


@dataclass
class WNTRNetworkModifier:
    """Class to modify the water network model.
    Attributes:
        network (WNTRNetworkModel): Instance of EPANET model implementation in WNTR."""

    network: WNTRNetworkModel = field(repr=True)
    pipeline: NetworkModifierPipeline = field(
        default_factory=lambda: NetworkModifierPipeline([]), repr=False
    )

    # Helper functions
    def find_small_pipes(self, diameter_threshold: float = 0.1) -> List[Any]:
        """Finds pipes with diameter less than a specified threshold.

        Args:
            diameter_threshold (float): The diameter threshold in inches.

        Returns:
            A list of pipe IDs with diameter less than the threshold.
        """
        return [
            pipe_name
            for pipe_name, pipe in self.network.pipes()
            if pipe.diameter <= diameter_threshold
        ]

    def modify_network(self) -> None:
        """Applies the modifications defined in the pipeline to the network.
        This method iterates through the operations stored in the pipeline and
        applies them sequentially to the network. The pipeline should contain
        instances of classes that inherit from NetworkOperation, each defining
        a specific modification to be made to the network.
        """
        self.pipeline.apply(self.network)

    def save_network(
        self,
        file_name: pathlib.Path,
        overwrite: bool = False,
        create_folders: bool = True,
        verbose: bool = False,
    ) -> None:
        """Saves the water network model to an EPANET input file.

        Args:
            file_name (pathlib.Path): The path to save the network to.
            overwrite (bool): If True, overwrite the file if it exists.
            create_folders (bool): If True, create parent directories if they don't exist.
            verbose (bool): If True, write additional information to Console

        Raises:
            FileExistsError: If the file exists and overwrite is False.
        """
        if not overwrite and file_name.exists():
            if verbose:
                rprint(
                    f"[yellow]Warning:[/yellow] File {file_name} already exists. It will not be "
                    "overwritten because `overwrite` is set to False."
                )
            return  # Exit the function without saving
        if create_folders:
            ensure_directory_exists(file_name)
        wntr.network.write_inpfile(self.network, str(file_name))

    # --------- node modifications --------
    # Change nodal demands
    # Add leakage
    # Remove leakage

    # ------------ pipe modifications ---------------
    # Add / remove pipes
    # Change pipe status(es)
    # Change pipe roughness


if __name__ == "__main__":
    """ """

    save_modified_network: bool = False
    from hydroforge.auxiliary.utils import get_package_root
    from hydroforge.uncertainty.uncertainties import AdditiveUncertainty
    from hydroforge.uncertainty.distributions import UniformDistribution

    example_inp = get_package_root().joinpath(
        "tests", "base_networks", "Real_network.inp"
    )
    model = WNTRNetworkModel(example_inp)
    network_modifier = WNTRNetworkModifier(model)
    if save_modified_network:
        network_modifier.save_network(
            pathlib.Path("outputs", "modified_network.inp"),
            overwrite=True,
            create_folders=True,
            verbose=True,
        )
    small_pipes_1 = network_modifier.find_small_pipes()

    pipe_modifier1 = PipeDiameterModifier(
        new_values={"p1078": 0.4, "p688": 0.45, "p1077_12": 0.5}
    )

    roughness_modifier = PipeRoughnessModifier(new_values={"p1078": 120, "p778_4": 130})

    # Nodal demand change
    demand_modifier = NodeDemandModifier(
        new_values={
            "n303": 1.5,
            "n391": Parameter(
                name="n391",
                nominal_value=2.0,
                uncertainty=AdditiveUncertainty(
                    distribution=UniformDistribution(-0.5, 0.5)
                ),
            ),
        },
        enable_structured_log=True,
    )

    prv_modifier = ValveModifier(new_values={"PRV-1": 66})

    network_modifiers = NetworkModifierPipeline(
        modifiers=[pipe_modifier1, roughness_modifier, demand_modifier, prv_modifier]
    )
    network_modifiers.apply(model)

    # Check the log
    rprint("\n".join(network_modifiers.log))

    rprint("\n[bold blue]Structured Log (Dictionary):[/bold blue]")
    if network_modifiers.structured_log:
        for cls_name, entries in network_modifiers.structured_log.items():
            rprint(f"[bold green]{cls_name}:[/bold green]")
            for entry in entries:
                rprint(f"  - {entry}")
        rprint()
    else:
        rprint("  No structured log entries.\n")

    def compare_pipe_diameters(wn_before, wn_after, modified_pipe_names):
        """Compare pipe diameters before and after modification."""
        rprint("[bold blue]Pipe Diameter Comparison:[/bold blue]")
        rprint(
            "{:<15} {:<15} {:<15} {:<15}".format(
                "Pipe Name", "Before (mm)", "After (mm)", "Difference (mm)"
            )
        )
        rprint("-" * 60)

        for pipe_name in modified_pipe_names:
            if (
                pipe_name in wn_before.pipe_name_list
                and pipe_name in wn_after.pipe_name_list
            ):
                before = wn_before.get_link(pipe_name).diameter * 1_000  # convert to mm
                after = wn_after.get_link(pipe_name).diameter * 1_000  # convert to mm
                diff = after - before
                rprint(
                    "{:<15} {:<15.2f} {:<15.2f} {:<15.2f}{}".format(
                        pipe_name,
                        before,
                        after,
                        diff,
                        " [bold green]✓[/bold green]" if abs(diff) > 0 else "",
                    )
                )

    # Import needed for deep copying the network
    import copy

    # Create a copy of the original network before modifications
    original_model = copy.deepcopy(model)

    # Define which pipes to modify
    pipes_to_modify = ["p1078", "p688", "p1077_12", "p778_4", "p1083_14"]

    # Create and apply a diameter modifier
    diameter_uncertainty_1 = AdditiveUncertainty(
        distribution=UniformDistribution(-0.05, 0.05)
    )
    diameter_uncertainty_2 = AdditiveUncertainty(
        distribution=UniformDistribution(-0.01, 0.01)
    )
    diameter_modifier = PipeDiameterModifier(
        new_values={
            "p1078": Parameter(
                name="p1078", nominal_value=0.4, uncertainty=diameter_uncertainty_1
            ),
            "p688": Parameter(
                name="p688", nominal_value=0.45, uncertainty=diameter_uncertainty_1
            ),
            "p1077_12": Parameter(
                name="p1077_12", nominal_value=0.75, uncertainty=diameter_uncertainty_1
            ),
            "p1083_14": Parameter(
                name="p1083_14", nominal_value=None, uncertainty=diameter_uncertainty_2
            ),
        },
    )

    # Apply the modifier directly to the model
    diameter_modifier.apply(model)

    # Compare the original and modified networks
    compare_pipe_diameters(original_model, model, pipes_to_modify)

    # Show log of modifications
    rprint("\n[bold blue]Modification Log (Text):[/bold blue]")
    for log_entry in diameter_modifier.log:
        rprint(log_entry)

    # Test NodeDemandDataFrameModifier
    rprint("\n[bold blue]Testing NodeDemandDataFrameModifier:[/bold blue]")

    # Create a sample demand dataframe
    demand_data = pd.DataFrame(
        {"node_id": ["n303", "n391", "n400", "n500"], "demand": [2.5, 3.0, 1.8, 2.2]}
    ).set_index("node_id")

    # Create a copy of the network for comparison
    model_before_demand = copy.deepcopy(model)

    # Create the modifier
    demand_df_modifier = NodeDemandDataFrameModifier(
        new_values=demand_data,
        default_value=0.5,
        skip_nonexistent=True,
        enable_structured_log=True,
    )

    # Apply the modifier
    demand_df_modifier.apply(model)

    # Compare demands before and after
    rprint("\n[bold]Node Demand Comparison:[/bold]")
    rprint(
        "{:<15} {:<20} {:<20} {:<20}".format(
            "Node Name", "Before (m³/s)", "After (m³/s)", "Change"
        )
    )
    rprint("-" * 75)

    test_nodes = [
        "n303",
        "n391",
        "n400",
        "n500",
        "n100",
    ]  # including a non-existent node
    for node_name in test_nodes:
        if node_name in model.junction_name_list:
            before = (
                model_before_demand.get_node(node_name)
                .demand_timeseries_list[0]
                .base_value
            )
            after = model.get_node(node_name).demand_timeseries_list[0].base_value
            change = after - before
            rprint(
                "{:<15} {:<20.6f} {:<20.6f} {:<20.6f}{}".format(
                    node_name,
                    before,
                    after,
                    change,
                    " [bold green]✓[/bold green]" if abs(change) > 0 else "",
                )
            )

    # Show modification log
    rprint("\n[bold blue]NodeDemandDataFrameModifier Log:[/bold blue]")
    for log_entry in demand_df_modifier.log[:10]:  # Show first 10 entries
        rprint(log_entry)

    if len(demand_df_modifier.log) > 10:
        rprint(f"... and {len(demand_df_modifier.log) - 10} more entries")

    # Show structured log if enabled
    if demand_df_modifier.structured_log:
        rprint("\n[bold blue]Structured Log (first 5 entries):[/bold blue]")
        for cls_name, entries in demand_df_modifier.structured_log.items():
            rprint(f"[bold green]{cls_name}:[/bold green]")
            for entry in entries[:5]:
                rprint(f"  - {entry}")
            if len(entries) > 5:
                rprint(f"  ... and {len(entries) - 5} more entries")

    # Test NodeLeakageModifier
    rprint("\n[bold blue]Testing NodeLeakageModifier:[/bold blue]")

    # Create a copy of the network for comparison
    model_before_leak = copy.deepcopy(model)

    # Create the leakage modifier
    leakage_modifier = NodeLeakageModifier(
        added_leaks={
            "n303": 0.5,
            "n391": Parameter(
                name="n391",
                nominal_value=0.3,
                uncertainty=AdditiveUncertainty(
                    distribution=UniformDistribution(-0.1, 0.1)
                ),
            ),
        },
        enable_structured_log=True,
    )

    # Apply the modifier
    leakage_modifier.apply(model)

    # Compare demands before and after
    rprint("\n[bold]Node Leakage Comparison:[/bold]")
    rprint(
        "{:<15} {:<20} {:<20} {:<20}".format(
            "Node Name", "Before (m³/s)", "After (m³/s)", "Leakage Added"
        )
    )
    rprint("-" * 75)

    leak_test_nodes = ["n303", "n391"]
    for node_name in leak_test_nodes:
        if node_name in model.junction_name_list:
            before = (
                model_before_leak.get_node(node_name)
                .demand_timeseries_list[0]
                .base_value
            )
            after = model.get_node(node_name).demand_timeseries_list[0].base_value
            leak_added = after - before
            rprint(
                "{:<15} {:<20.6f} {:<20.6f} {:<20.6f}{}".format(
                    node_name,
                    before,
                    after,
                    leak_added,
                    " [bold green]✓[/bold green]" if abs(leak_added) > 0 else "",
                )
            )

    # Show modification log
    rprint("\n[bold blue]NodeLeakageModifier Log:[/bold blue]")
    for log_entry in leakage_modifier.log:
        rprint(log_entry)

    # Test NodeEmitterModifier
    rprint("\n[bold blue]Testing NodeEmitterModifier:[/bold blue]")

    # Create a copy of the network for comparison
    model_before_emitter = copy.deepcopy(model)

    # Calculate emitter coefficient from leak diameter
    leak_diameter_mm = 10.0  # 10mm leak
    leak_diameter_m = leak_diameter_mm / 1000.0
    emitter_from_diameter = NodeEmitterModifier.calculate_emitter_from_diameter(
        diameter=leak_diameter_m, nominal_pressure=100.0
    )

    rprint(
        f"Emitter coefficient for {leak_diameter_mm}mm leak: {emitter_from_diameter:.6e}"
    )

    # Create the emitter modifier
    emitter_modifier = NodeEmitterModifier(
        emitter_coefficients={
            "n303": emitter_from_diameter,
            "n391": Parameter(
                name="n391",
                nominal_value=0.001,
                uncertainty=AdditiveUncertainty(
                    distribution=UniformDistribution(-0.0002, 0.0002)
                ),
            ),
        },
        nominal_pressure=100.0,
        required_pressure=100.0,
        minimum_pressure=0.0,
        enable_structured_log=True,
    )

    # Apply the modifier
    emitter_modifier.apply(model)

    # Compare emitters before and after
    rprint("\n[bold]Node Emitter Comparison:[/bold]")
    rprint("{:<15} {:<25} {:<25}".format("Node Name", "Before", "After (coefficient)"))
    rprint("-" * 65)

    emitter_test_nodes = ["n303", "n391"]
    for node_name in emitter_test_nodes:
        if node_name in model.junction_name_list:
            node_before = model_before_emitter.get_node(node_name)
            node_after = model.get_node(node_name)
            before = getattr(node_before, "emitter_coefficient", None)
            after = node_after.emitter_coefficient
            rprint(
                "{:<15} {:<25} {:<25.6e}{}".format(
                    node_name,
                    str(before) if before is not None else "None",
                    after,
                    " [bold green]✓[/bold green]",
                )
            )

    # Show modification log
    rprint("\n[bold blue]NodeEmitterModifier Log:[/bold blue]")
    for log_entry in emitter_modifier.log:
        rprint(log_entry)

    # Test PipeDiameterMultiplierModifier
    rprint("\n[bold blue]Testing PipeDiameterMultiplierModifier:[/bold blue]")

    # Create a copy of the network for comparison
    model_before_multiplier = copy.deepcopy(model)

    # Test 1: Scale specific pipes
    rprint("\n[bold]Test 1: Scale specific pipes[/bold]")
    multiplier_modifier1 = PipeDiameterMultiplierModifier(
        multipliers={
            "p1078": 0.95,
            "p688": 0.85,
            "p1077_12": Parameter(
                name="p1077_12",
                nominal_value=0.90,
                uncertainty=AdditiveUncertainty(
                    distribution=UniformDistribution(-0.05, 0.05)
                ),
            ),
        },
        enable_structured_log=True,
    )
    multiplier_modifier1.apply(model)

    rprint("\n[bold]Specific Pipe Diameter Comparison:[/bold]")
    rprint(
        "{:<15} {:<20} {:<20} {:<20}".format(
            "Pipe Name", "Before (m)", "After (m)", "Multiplier"
        )
    )
    rprint("-" * 75)

    for pipe_name in ["p1078", "p688", "p1077_12"]:
        if pipe_name in model.pipe_name_list:
            before = model_before_multiplier.get_link(pipe_name).diameter
            after = model.get_link(pipe_name).diameter
            mult = after / before if before > 0 else 0
            rprint(
                "{:<15} {:<20.6f} {:<20.6f} {:<20.6f}{}".format(
                    pipe_name, before, after, mult, " [bold green]✓[/bold green]"
                )
            )

    # Show log
    rprint("\n[bold blue]PipeDiameterMultiplierModifier Log (first 5):[/bold blue]")
    for log_entry in multiplier_modifier1.log[:5]:
        rprint(log_entry)

    # Test 2: Scale all pipes
    rprint("\n[bold]Test 2: Scale all pipes by 0.5[/bold]")
    model_before_scalar = copy.deepcopy(model)

    multiplier_modifier2 = PipeDiameterMultiplierModifier(
        multipliers=0.5, enable_structured_log=True
    )
    multiplier_modifier2.apply(model)

    rprint("\n[bold]All Pipes Diameter Comparison (sample):[/bold]")
    rprint(
        "{:<15} {:<20} {:<20} {:<20}".format(
            "Pipe Name", "Before (m)", "After (m)", "Multiplier"
        )
    )
    rprint("-" * 75)

    sample_pipes = list(model.pipe_name_list)[:3]
    for pipe_name in sample_pipes:
        before = model_before_scalar.get_link(pipe_name).diameter
        after = model.get_link(pipe_name).diameter
        mult = after / before if before > 0 else 0
        rprint(
            "{:<15} {:<20.6f} {:<20.6f} {:<20.6f}{}".format(
                pipe_name, before, after, mult, " [bold green]✓[/bold green]"
            )
        )

    rprint(f"\n[bold]Total pipes modified:[/bold] {len(multiplier_modifier2.log)}")
