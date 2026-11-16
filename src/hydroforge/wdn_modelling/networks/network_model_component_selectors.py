"""Classes for selecting network model components in WNTR networks given certain criteria."""

from typing import (
    Protocol,
    Iterable,
    Any,
    TypeAlias,
    List,
    TypeVar,
    Generic,
    Callable,
    Union,
    Mapping,
    Optional,
    Dict,
)
from dataclasses import dataclass, field
import numpy as np
import networkx as nx
import wntr
from rich import print as rprint
from hydroforge.wdn_modelling.graphs.graph import EPANETNetworkGraph

PipeName: TypeAlias = Any
NodeName: TypeAlias = Any
ValveName: TypeAlias = Any
ComponentName: TypeAlias = Any  # Generic component name
WNTRNetworkModel: TypeAlias = wntr.network.WaterNetworkModel
T = TypeVar("T")
CT = TypeVar("CT", covariant=True)  # Component Type


class IComponentSelector(Protocol[CT]):
    """Protocol for selecting network model components given certain criteria."""

    def select(self, wn: WNTRNetworkModel, candidates: Iterable[T] | None) -> List[T]:
        """Filter candidate component names and return selection."""


class LoggingMixin:
    """Mixin class to add logging functionality to selectors as a list of strings.

    Attributes:
        text_logging (bool): Flag to enable or disable logging.
        text_log (List[str]): List to store log messages.

    Notes: logging and log attributes need to be provided by the child class.

    """

    def __init__(self, text_logging: bool = False) -> None:
        self.text_logging = text_logging
        self.text_log: list = []

    def _clear_logs(self) -> None:
        """Clear logs at the beginning of the method."""
        if hasattr(self, "text_log"):
            self.text_log.clear()
        if hasattr(self, "structured_log"):
            self.structured_log: dict = {}

    def log_selection(self, selected: Iterable[str]) -> None:
        """Log selected items if self.logging is enabled."""
        if not self.text_logging:
            return
        cls_name = self.__class__.__name__
        if not selected:
            self.text_log.append(f"[{cls_name}] nothing selected")
        else:
            selected_str = ", ".join(selected)
            self.text_log.append(f"[{cls_name}] selected {selected_str}")


class StructuredLoggingMixin:
    """Mixin class to add structured logging functionality to selectors."""

    def __init__(self, structured_logging: bool = False) -> None:
        self.structured_logging = structured_logging
        self.structured_log: dict = {}

    def add_to_structured_log(
        self, component_name: ComponentName, component_type: str
    ) -> None:
        """Add an entry to the structured log if structured logging is enabled."""
        if not self.structured_logging:
            return
        class_name = self.__class__.__name__
        self.structured_log.setdefault(class_name, [])
        log_entry = {
            "component_name": component_name,
            "component_type": component_type,
        }
        self.structured_log[class_name].append(log_entry)

    def log_selection_structured(
        self,
        selected: Iterable[ComponentName],
        component_type: str,  # Assumes one compoment type per selected group of components
        reason: Optional[Union[Iterable[str], Mapping[ComponentName, str]]] = None,
    ) -> None:
        """Log selected items to structured log if self.structured_logging is enabled."""
        if not self.structured_logging:
            return
        # Log selected components
        selected_list = list(selected)
        if isinstance(reason, Iterable) and not isinstance(reason, str):
            reason_list = list(reason)
            if len(reason_list) != len(selected_list):
                raise ValueError(
                    "Length of reason iterable must match number of selected components."
                )
            reason = {name: r for name, r in zip(selected_list, reason_list)}
        if reason is None:
            reason = "matched_criteria"
        for name in selected_list:
            self.add_to_structured_log(
                component_name=name, component_type=component_type
            )


@dataclass
class PipeNameSelector(IComponentSelector, LoggingMixin, StructuredLoggingMixin):
    """Select pipes based on a predefined list of names."""

    names: Iterable[str]
    text_logging: bool = False
    structured_logging: bool = False

    def __post_init__(self) -> None:
        LoggingMixin.__init__(self, self.text_logging)
        StructuredLoggingMixin.__init__(self, self.structured_logging)

    def select(
        self, wn: WNTRNetworkModel, candidates: Iterable[PipeName] | None = None
    ) -> List[PipeName]:
        """Select pipes based on a predefined list of names."""
        self._clear_logs()
        if not candidates:
            candidates = wn.pipe_name_list
        selected_pipes = [n for n in self.names if n in candidates]
        # Regular text logging
        self.log_selection(selected_pipes)
        # Structured logging
        self.log_selection_structured(selected_pipes, "pipe")
        return selected_pipes


@dataclass
class AttributeSelector(
    IComponentSelector, LoggingMixin, StructuredLoggingMixin, Generic[CT]
):
    """Select model components based on a predicate function applied to component attributes."""

    predicate: Callable[[CT], bool]  # e.g. lambda pipe: pipe.diameter < 0.3
    component_type: str  # 'pipe', 'node', or 'valve'
    text_logging: bool = False
    structured_logging: bool = False

    def __post_init__(self) -> None:
        LoggingMixin.__init__(self, self.text_logging)
        StructuredLoggingMixin.__init__(self, self.structured_logging)

    def select(
        self, wn: WNTRNetworkModel, candidates: Iterable[ComponentName] | None = None
    ) -> List[ComponentName]:
        """Select components based on a predicate function applied to component attributes."""
        self._clear_logs()
        component_list_attr = f"{self.component_type}_name_list"
        if not hasattr(wn, component_list_attr):
            raise ValueError(f"Invalid component_type: {self.component_type}")

        if not candidates:
            candidates = getattr(wn, component_list_attr)

        selected_components = []
        for name in candidates:
            try:
                component = (
                    wn.get_link(name)
                    if self.component_type != "node"
                    else wn.get_node(name)
                )
            except KeyError:
                if self.text_logging:
                    self.text_log.append(f"Skipping unknown component {name}")
                continue
            if self.predicate(component):  # let exceptions bubble up here
                selected_components.append(name)
        # Regular text logging
        self.log_selection(selected_components)
        # Structured logging
        self.log_selection_structured(selected_components, self.component_type)
        return selected_components


@dataclass
class DiameterThresholdSelector(
    IComponentSelector, LoggingMixin, StructuredLoggingMixin
):
    """Select pipes with diameter below a certain threshold."""

    max_diameter: float
    text_logging: bool = False
    structured_logging: bool = False

    def __post_init__(self) -> None:
        LoggingMixin.__init__(self, self.text_logging)
        StructuredLoggingMixin.__init__(self, self.structured_logging)

    def select(
        self, wn: WNTRNetworkModel, candidates: Iterable[PipeName] | None
    ) -> List[PipeName]:
        """Select pipes with diameter below a certain threshold."""
        self._clear_logs()
        if not candidates:
            candidates = wn.pipe_name_list
        selected_pipes = [
            n for n in candidates if wn.get_link(n).diameter <= self.max_diameter
        ]
        # Regular text logging
        self.log_selection(selected_pipes)
        # Structured logging
        self.log_selection_structured(selected_pipes, "pipe")
        return selected_pipes


@dataclass
class RandomFractionSelector(IComponentSelector, LoggingMixin, StructuredLoggingMixin):
    """Select a random fraction of the available pipes."""

    fraction: float
    random_state: int | None = None
    text_logging: bool = False
    structured_logging: bool = False

    def __post_init__(self) -> None:
        LoggingMixin.__init__(self, self.text_logging)
        StructuredLoggingMixin.__init__(self, self.structured_logging)

    def select(
        self, wn: WNTRNetworkModel, candidates: Iterable[PipeName] | None
    ) -> List[PipeName]:
        """Select a random fraction of the available pipes."""
        self._clear_logs()
        rng = np.random.default_rng(self.random_state)
        if not candidates:
            candidates = wn.pipe_name_list
        candidates_list = list(candidates)
        num_selected_pipes = int(len(candidates_list) * self.fraction)
        if num_selected_pipes <= 0:
            selected_pipes = []
        else:
            selected_pipes = list(
                rng.choice(candidates_list, size=num_selected_pipes, replace=False)
            )
        # Regular text logging
        self.log_selection(selected_pipes)
        # Structured logging
        self.log_selection_structured(selected_pipes, "pipe")
        return selected_pipes


@dataclass
class AvoidBridgesSelector(IComponentSelector, LoggingMixin, StructuredLoggingMixin):
    """Avoid selecting pipes that are bridges in the network topology."""

    log: List[str] = field(default_factory=list)
    iterative_search: bool = False
    text_logging: bool = False
    structured_logging: bool = False

    def __post_init__(self) -> None:
        LoggingMixin.__init__(self, self.text_logging)
        StructuredLoggingMixin.__init__(self, self.structured_logging)

    def select(
        self, wn: WNTRNetworkModel, candidates: Iterable[PipeName] | None
    ) -> List[PipeName]:
        """Avoid selecting pipes that are bridges in the network topology.

        When iterative_search=True this does an order-agnostic iterative removal:
        - compute current bridges
        - remove *all* candidate pipes that are currently not bridges (a batch)
        - repeat until no more candidate pipes can be removed
        """
        self._clear_logs()
        if not candidates:
            candidates = list(wn.pipe_name_list)
        else:
            candidates = list(candidates)

        graph = EPANETNetworkGraph.from_graph(wn.to_graph().to_undirected())
        nx_graph = graph.get_networkx_graph()

        selected_pipes: List[PipeName] = []

        # Helper: build a mapping pipe_name_str -> (u, v, edge_key_or_None)
        def build_pipe_to_uv_map():
            mapping = {}
            # If this is a MultiGraph, edges may have explicit keys
            for u, v in nx_graph.edges():
                edge_data = graph.get_edge_data(u, v)
                if not edge_data:
                    continue
                if isinstance(edge_data, dict):
                    # print('dupa')
                    # edge_data could be {pipe_name: attr} or attr directly
                    # try to collect any pipe-like keys:
                    for key in edge_data.keys():
                        mapping[str(key)] = (u, v, key)
                    # also check nested attr dict values for id/name
                    for val in edge_data.values():
                        if isinstance(val, dict):
                            pid = val.get("id") or val.get("name")
                            if pid is not None:
                                mapping[str(pid)] = (u, v, None)
                else:
                    # fallback single attr-dict
                    if isinstance(edge_data, dict):
                        pid = edge_data.get("id") or edge_data.get("name")
                        if pid is not None:
                            mapping[str(pid)] = (u, v, None)
            return mapping

        if self.iterative_search:
            # Order-agnostic iterative removal in batches
            pipe_to_uv = build_pipe_to_uv_map()
            remaining = set(candidates)

            while True:
                # compute current bridges and the pipe names that correspond to those bridge edges
                bridge_edges = set(nx.bridges(nx_graph))
                bridge_names = set()
                for u, v in bridge_edges:
                    d = graph.get_edge_data(u, v)
                    if not d:
                        continue
                    if isinstance(d, dict):
                        # edge-data is likely mapping of keys -> attrs; collect keys and any nested id/name
                        for key, val in d.items():
                            bridge_names.add(str(key))
                            if isinstance(val, dict):
                                pid = val.get("id") or val.get("name")
                                if pid is not None:
                                    bridge_names.add(str(pid))
                    else:
                        # fallback attr-dict
                        if isinstance(d, dict):
                            pid = d.get("id") or d.get("name")
                            if pid is not None:
                                bridge_names.add(str(pid))

                # Choose all remaining candidate pipes that are currently NOT bridges
                non_bridge_candidates = [
                    p
                    for p in list(remaining)
                    if str(p) not in bridge_names and str(p) in pipe_to_uv
                ]

                if not non_bridge_candidates:
                    # remove any remaining candidates that are not present in the graph at all
                    for p in list(remaining):
                        if str(p) not in pipe_to_uv:
                            remaining.discard(p)
                    break

                # Remove all non-bridge candidates in this batch
                for pipe in non_bridge_candidates:
                    entry = pipe_to_uv.get(str(pipe))
                    if not entry:
                        # try a last-effort dynamic search
                        found = False
                        for u, v in nx_graph.edges():
                            d = graph.get_edge_data(u, v)
                            if not d:
                                continue
                            if isinstance(d, dict) and str(pipe) in d:
                                entry = (u, v, str(pipe))
                                found = True
                                break
                            # check nested attr dictionaries
                            if isinstance(d, dict):
                                for edge_key, val in d.items():
                                    if isinstance(val, dict) and (
                                        val.get("id") == pipe or val.get("name") == pipe
                                    ):
                                        entry = (u, v, edge_key)
                                        found = True
                                        break
                                if found:
                                    break
                        if not found:
                            # can't locate pipe in current graph; skip it
                            remaining.discard(pipe)
                            continue

                    u, v, edge_key = entry
                    nx_graph.remove_edge(u, v)
                    selected_pipes.append(pipe)
                    remaining.discard(pipe)
                # rebuild mapping after batch removals (keeps mapping consistent)
                pipe_to_uv = build_pipe_to_uv_map()
        else:
            # One-shot (non-iterative): compute bridges once and remove those pipes from candidates
            bridge_edges = set(nx.bridges(nx_graph))
            bridge_names = set()
            for u, v in bridge_edges:
                d = graph.get_edge_data(u, v)
                if not d:
                    continue
                if isinstance(d, dict):
                    for key, val in d.items():
                        bridge_names.add(str(key))
                        if isinstance(val, dict):
                            pid = val.get("id") or val.get("name")
                            if pid is not None:
                                bridge_names.add(str(pid))
                else:
                    if isinstance(d, dict):
                        pid = d.get("id") or d.get("name")
                        if pid is not None:
                            bridge_names.add(str(pid))
            selected_pipes = [n for n in candidates if str(n) not in bridge_names]

        # Text logging
        self.log_selection(selected_pipes)
        # Structured logging
        self.log_selection_structured(selected_pipes, "pipe")
        return selected_pipes


# ------------------- Node Selectors -------------------


@dataclass
class NodeNameSelector(IComponentSelector, LoggingMixin, StructuredLoggingMixin):
    """Select nodes based on a predefined list of names."""

    names: Iterable[str]
    text_logging: bool = False
    structured_logging: bool = False

    def __post_init__(self) -> None:
        LoggingMixin.__init__(self, self.text_logging)
        StructuredLoggingMixin.__init__(self, self.structured_logging)

    def select(
        self, wn: WNTRNetworkModel, candidates: Iterable[NodeName] | None = None
    ) -> List[NodeName]:
        """Select nodes based on a predefined list of names."""
        self._clear_logs()
        if not candidates:
            candidates = wn.node_name_list
        selected_nodes = [n for n in self.names if n in candidates]
        # Text logging
        self.log_selection(selected_nodes)
        # Structured logging
        self.log_selection_structured(selected_nodes, "node")
        return selected_nodes


@dataclass
class ElevationThresholdSelector(
    IComponentSelector, LoggingMixin, StructuredLoggingMixin
):
    """Select nodes with elevation above a certain threshold."""

    min_elevation: float
    text_logging: bool = False
    structured_logging: bool = False
    log: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        LoggingMixin.__init__(self, self.text_logging)
        StructuredLoggingMixin.__init__(self, self.structured_logging)

    def select(
        self, wn: WNTRNetworkModel, candidates: Iterable[NodeName] | None = None
    ) -> List[NodeName]:
        """Select nodes with elevation above a certain threshold."""
        self._clear_logs()
        if not candidates:
            candidates = wn.node_name_list
        selected_nodes = [
            n for n in candidates if wn.get_node(n).elevation >= self.min_elevation
        ]
        # Text logging
        self.log_selection(selected_nodes)
        # Structured logging
        self.log_selection_structured(selected_nodes, "node")
        return selected_nodes


@dataclass
class MinimumDemandSelector(IComponentSelector, LoggingMixin, StructuredLoggingMixin):
    """Select nodes with base demand above a certain threshold."""

    min_demand: float
    text_logging: bool = False
    structured_logging: bool = False

    def __post_init__(self) -> None:
        LoggingMixin.__init__(self, self.text_logging)
        StructuredLoggingMixin.__init__(self, self.structured_logging)

    def select(
        self, wn: WNTRNetworkModel, candidates: Iterable[NodeName] | None = None
    ) -> List[NodeName]:
        """Select nodes with base demand above a certain threshold."""
        self._clear_logs()
        if not candidates:
            candidates = wn.node_name_list
        selected_nodes = []
        for node_name in candidates:
            node = wn.get_node(node_name)
            if isinstance(node, wntr.network.Junction):
                # Access the base demand of the first demand pattern
                if (
                    node.demand_timeseries_list
                    and node.demand_timeseries_list[0].base_value >= self.min_demand
                ):
                    selected_nodes.append(node_name)
        # Text logging
        self.log_selection(selected_nodes)
        # Structured logging
        self.log_selection_structured(selected_nodes, "node")
        return selected_nodes


# ------------------- Valve Selectors -------------------


@dataclass
class ValveNameSelector(IComponentSelector, LoggingMixin, StructuredLoggingMixin):
    """Select valves based on a predefined list of names."""

    names: Iterable[str]
    text_logging: bool = False
    structured_logging: bool = False

    def __post_init__(self) -> None:
        LoggingMixin.__init__(self, self.text_logging)
        StructuredLoggingMixin.__init__(self, self.structured_logging)

    def select(
        self, wn: WNTRNetworkModel, candidates: Iterable[ValveName] | None = None
    ) -> List[ValveName]:
        """Select valves based on a predefined list of names."""
        self._clear_logs()
        if not candidates:
            candidates = wn.valve_name_list
        selected_valves = [n for n in self.names if n in candidates]
        # Text logging
        self.log_selection(selected_valves)
        # Structured logging
        self.log_selection_structured(selected_valves, "valve")
        return selected_valves


@dataclass
class ValveTypeSelector(IComponentSelector, LoggingMixin, StructuredLoggingMixin):
    """Select valves of a specific type."""

    valve_type: str  # e.g., 'PRV', 'FCV', etc.
    text_logging: bool = False
    structured_logging: bool = False

    def __post_init__(self) -> None:
        LoggingMixin.__init__(self, self.text_logging)
        StructuredLoggingMixin.__init__(self, self.structured_logging)

    def select(
        self, wn: WNTRNetworkModel, candidates: Iterable[ValveName] | None = None
    ) -> List[ValveName]:
        """Select valves of a specific type."""
        self._clear_logs()
        if not candidates:
            candidates = wn.valve_name_list
        selected_valves = [
            n for n in candidates if wn.get_link(n).valve_type == self.valve_type
        ]
        # Text logging
        self.log_selection(selected_valves)
        # Structured logging
        self.log_selection_structured(selected_valves, "valve")
        return selected_valves


@dataclass
class ModelComponentSelector:
    """Selects model components based on various criteria."""

    selectors: List[IComponentSelector]
    text_log: List[str] = field(default_factory=list)
    structured_log: Optional[Dict[str, List[Dict[str, Any]]]] = None

    def add_selector(self, selector: IComponentSelector) -> None:
        """Add a component selector to the model."""
        self.selectors.append(selector)

    def select(self, wn: WNTRNetworkModel, initial_candidates: List[T]) -> List[T]:
        """Apply all selectors in sequence to filter the initial candidates."""
        candidates = initial_candidates
        if not candidates:
            return []
        for selector in self.selectors:
            candidates = selector.select(wn, candidates)
            # Add text logging
            if hasattr(selector, "text_log") and selector.text_log:
                self.text_log.extend(selector.text_log)
            # Add structured logging
            if (
                hasattr(selector, "structured_log")
                and selector.structured_log is not None
            ):
                if any(selector.structured_log.values()):  # check for non-empty lists
                    if self.structured_log is None:
                        self.structured_log = {}
                    # Merge logs per class name
                    for cls_name, entries in selector.structured_log.items():
                        self.structured_log.setdefault(cls_name, []).extend(entries)
            if not candidates:
                break

        return list(candidates)


if __name__ == "__main__":
    from hydroforge.auxiliary.utils import get_package_root

    example_inp = get_package_root().joinpath(
        "tests", "base_networks", "Net1_with_prv.inp"
    )
    model = wntr.network.WaterNetworkModel(example_inp)

    # ------------------- Pipe Selection Demo -------------------
    rprint("----- Pipe Selection Demo -----")
    pipe_name_selector = PipeNameSelector(names=["10", "11", "12"], text_logging=True)
    diameter_threshold_selector = DiameterThresholdSelector(
        max_diameter=12, text_logging=True, structured_logging=True
    )
    random_fraction_selector = RandomFractionSelector(
        fraction=0.5, random_state=42, text_logging=True, structured_logging=True
    )
    pipe_selector = ModelComponentSelector(
        selectors=[
            pipe_name_selector,
            diameter_threshold_selector,
            random_fraction_selector,
        ]
    )
    initial_pipes = ["10", "11", "12", "21", "31", "111"]
    selected_pipes = pipe_selector.select(model, initial_pipes)
    rprint("Selected Pipes:", selected_pipes)
    rprint(
        "Pipe Selection Log:",
        pipe_name_selector.text_log
        + diameter_threshold_selector.text_log
        + random_fraction_selector.text_log,
    )

    rprint("Structured Log:", pipe_selector.structured_log)

    # ------------------- Node Selection Demo -------------------
    rprint("\n----- Node Selection Demo -----")
    node_name_selector = NodeNameSelector(names=["10", "11", "12"], text_logging=True)
    minimum_demand_selector = MinimumDemandSelector(min_demand=10, text_logging=True)
    elevation_threshold_selector = ElevationThresholdSelector(
        min_elevation=180, text_logging=True
    )
    node_selector = ModelComponentSelector(
        selectors=[
            node_name_selector,
            elevation_threshold_selector,
            minimum_demand_selector,
        ]
    )
    initial_nodes = ["10", "11", "12", "13", "21"]
    selected_nodes = node_selector.select(model, initial_nodes)
    rprint("Selected Nodes:", selected_nodes)
    rprint(
        "Node Selection Log:",
        node_name_selector.text_log + elevation_threshold_selector.text_log,
    )

    # ------------------- Valve Selection Demo -------------------
    rprint("\n----- Valve Selection Demo -----")
    valve_name_selector = ValveNameSelector(names=["PRV-1"], text_logging=True)
    valve_type_selector = ValveTypeSelector(valve_type="PRV", text_logging=True)
    valve_selector = ModelComponentSelector(
        selectors=[valve_name_selector, valve_type_selector]
    )
    initial_valves = ["PRV-1"]
    selected_valves = valve_selector.select(model, initial_valves)
    rprint("Selected Valves:", selected_valves)
    rprint(
        "Valve Selection Log:",
        valve_name_selector.text_log + valve_type_selector.text_log,
    )

    # ------------------- Attribute Selector Demo -------------------
    rprint("\n----- Attribute Selector Demo -----")

    dia_threshold: float = 0.010
    rprint(
        f"\nSelecting pipes with diameter larger than {dia_threshold}m using AttributeSelector"
    )
    # Select pipes with diameter greater than 10
    pipe_attribute_selector = AttributeSelector[wntr.network.Pipe](
        predicate=lambda pipe: pipe.diameter > dia_threshold,
        component_type="pipe",
        text_logging=True,
    )
    initial_pipes = ["10", "11", "12", "21", "31", "111"]
    selected_pipes_attribute = pipe_attribute_selector.select(model, initial_pipes)
    rprint("Selected Pipes (Attribute):", selected_pipes_attribute)
    rprint("Attribute Selection Log:", pipe_attribute_selector.text_log)

    elev_threshold: float = 150
    rprint(
        f"\nSelecting junctions with elevation greater than {elev_threshold}m using AttributeSelector"
    )
    # Select nodes with elevation greater than 150
    node_attribute_selector = AttributeSelector[wntr.network.Junction](
        predicate=lambda node: node.elevation > elev_threshold,
        component_type="node",
        text_logging=True,
    )
    initial_nodes = ["10", "11", "12", "13", "21"]
    selected_nodes_attribute = node_attribute_selector.select(model, initial_nodes)
    rprint("Selected Nodes (Attribute):", selected_nodes_attribute)
    rprint("Attribute Selection Log:", node_attribute_selector.text_log)

    # Select valves that are PRVs
    sel_valve_type: str = "PRV"
    rprint(f"\nSelecting valves of type {sel_valve_type} using AttriuteSelector")
    valve_attribute_selector = AttributeSelector[wntr.network.Valve](
        predicate=lambda valve: valve.valve_type == sel_valve_type,
        component_type="valve",
        text_logging=True,
    )
    initial_valves = ["PRV-1"]
    selected_valves_attribute = valve_attribute_selector.select(model, initial_valves)
    rprint("Selected Valves (Attribute):", selected_valves_attribute)
    rprint("Attribute Selection Log:", valve_attribute_selector.text_log)

    # ------------------- Avoid Bridges Selector Demo -------------------
    rprint("\n----- Avoid Bridges Selector Demo -----")
    avoid_bridges_selector = AvoidBridgesSelector(text_logging=True)
    selected_pipes_no_bridges = avoid_bridges_selector.select(model, candidates=None)
    rprint("Selected Pipes (Excluding Bridges):", selected_pipes_no_bridges)
    rprint("Avoid Bridges Selection Log:", avoid_bridges_selector.text_log)

    # ------------------- Avoid Bridges Selector Demo -------------------
    rprint("\n----- Avoid Bridges Selector Demo 2 ----")
    example_inp2 = get_package_root().joinpath("tests", "base_networks", "L-Town.inp")
    model2 = wntr.network.WaterNetworkModel(example_inp2)
    avoid_bridges_selector2 = AvoidBridgesSelector(
        text_logging=True, iterative_search=True
    )
    selected_pipes_no_bridges2 = avoid_bridges_selector2.select(
        model2,
        candidates=[
            "p1",
            "p2",
            "p3",
            "p4",
            "p5",
            "p6",
            "p7",
            "p8",
            "p9",
            "p10",
            "p253",
        ],
    )
    rprint("Selected Pipes (Excluding Bridges):", selected_pipes_no_bridges2)
    rprint("Avoid Bridges Selection Log:", avoid_bridges_selector2.text_log)
