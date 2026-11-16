"""
This module provides classes for modifying EPANET network graphs. It includes abstract base classes for defining network
graph modifiers, concrete implementations for removing pipes, and mixins for adding logging functionality. The module
also includes exception classes for handling specific errors during network modification, such as when a pipe is not
found or when removing a pipe would disconnect the network.
Classes:
    - NetworkGraphComponentModifier: Abstract base class for modifying network components in a EPANETNetworkGraph model.
    - NetworkGraphPipeRemover: Modifies the topology of a network graph by removing pipes.
Usage:
    The module can be used to modify EPANET network graphs by creating instances of the modifier
    classes and applying them to an EPANETNetworkGraph object. Logging mixins can be used to
    track the modifications made to the network.
"""

from typing import List, Any, TypeAlias
from .common import PipeNotFoundException, BridgeRemovalException
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from rich import print as rprint
from hydroforge.wdn_modelling.graphs.graph import EPANETNetworkGraph
from .common import LoggingMixin, StructuredLoggingMixin

ComponentName: TypeAlias = Any


class NetworkGraphComponentModifier(ABC):
    """Abstract base class for modifying network components in a EPANETNetworkGraph model."""

    @abstractmethod
    def apply(self, graph: EPANETNetworkGraph) -> None:
        """Applies the network modification to the WNTR network model.

        Args:
            graph (EPANETNetworkGraph): The network graph model to modify.
        """


@dataclass
class NetworkGraphPipeRemover(
    NetworkGraphComponentModifier, LoggingMixin, StructuredLoggingMixin
):
    """Modifies the topology of a network graph by removing pipes.

    This class allows for modification of the network graph topology by removing pipes
    from the graph while maintaining other graph properties.

    Attributes:
        pipe_names (List[ComponentName]): List of pipe names to remove from the graph.
        text_logging (bool): Flag to enable text logging.
        structured_logging (bool): Flag to enable structured logging.
        preserve_connectivity (bool): If True, avoid removing pipes that would
            disconnect the network.
        raise_on_error (bool): If True, raise exception if error found during
            calculations, e.g. pipe could not be removed for any reason.
    """

    pipe_names: List[ComponentName] = field(default_factory=list)
    text_logging: bool = False
    structured_logging: bool = False
    preserve_connectivity: bool = True
    raise_on_error: bool = False

    def __post_init__(self) -> None:
        LoggingMixin.__init__(self, self.text_logging)
        StructuredLoggingMixin.__init__(self, self.structured_logging)

    @staticmethod
    def _find_bridge_names(graph: EPANETNetworkGraph) -> set:
        """ """
        bridge_names = set()
        bridges = graph.find_bridges()
        # Get pipe names for those bridges
        for u, v in bridges:
            edge_data = graph.get_edge_data(u, v)
            if isinstance(edge_data, dict) and "key" in edge_data:
                bridge_names.add(edge_data["key"])
        return bridge_names

    def apply(self, graph: EPANETNetworkGraph) -> None:
        """Applies pipe removal to the network graph.

        Removes specified pipes from the network graph while optionally preserving
        network connectivity. Logs the operations performed.

        Args:
            graph (EPANETNetworkGraph): The network graph to modify.
        """
        # Process each pipe for removal
        for pipe_name in self.pipe_names:
            # Find the edge corresponding to this pipe
            pipe_edge, from_node, to_node = None, None, None
            bridge_names = set()
            # Bridge finding needs to be done after each pipe removal, because
            # each removed pipe affects network topology. Therefore, the number and
            # names of removed pipes may depend on the order of pipes in 'pipe_names'
            if self.preserve_connectivity:
                bridge_names = self._find_bridge_names(graph)

            for u, v, data in graph.edges(data=True):
                if data.get("key") == pipe_name:
                    pipe_edge = (u, v)
                    from_node, to_node = u, v
                    break

            if pipe_edge is None:
                if self.raise_on_error:
                    raise PipeNotFoundException(
                        f"Trying to remove a non-existing pipe (pipe {pipe_name})."
                    )
                self.log_modification(f"Skipped non-existing pipe {pipe_name}")
                self.add_to_structured_log(
                    component_name=pipe_name,
                    component_type="pipe",
                    attribute="existence",
                    old_value="non-existent",
                    new_value="non-existent",
                    details={"status": "skipped", "reason": "not_found"},
                )
                continue

            if self.preserve_connectivity:
                bridge_names = self._find_bridge_names(graph)

            if self.preserve_connectivity and pipe_name in bridge_names:
                if self.raise_on_error:
                    raise BridgeRemovalException(
                        f"Cannot remove pipe '{pipe_name}'. This removal would disconnect the network."
                    )
                self.log_modification(
                    f"Skipped pipe {pipe_name} (bridge - removal would disconnect network)"
                )
                if self.structured_logging:
                    self.add_to_structured_log(
                        component_name=pipe_name,
                        component_type="pipe",
                        attribute="existence",
                        old_value="connected",
                        new_value="preserved",
                        details={
                            "status": "skipped",
                            "reason": "bridge",
                            "from_node": from_node,
                            "to_node": to_node,
                        },
                    )
            else:
                # Get any extra pipe data for logging
                pipe_data = graph.get_edge_data(*pipe_edge).copy()
                # Remove the edge
                graph.remove_edge(*pipe_edge)
                self.log_modification(
                    f"Removed pipe {pipe_name} (connecting {from_node} to {to_node})"
                )
                self.add_to_structured_log(
                    component_name=pipe_name,
                    component_type="pipe",
                    attribute="existence",
                    old_value="connected",
                    new_value="removed",
                    details={
                        "status": "removed",
                        "from_node": from_node,
                        "to_node": to_node,
                        "pipe_data": pipe_data,
                    },
                )


# TODO: Add topological modifications for graph that are analogous as for the model

if __name__ == "__main__":
    import networkx as nx
    from hydroforge.auxiliary.utils import get_package_root

    # Load a WNTR model
    inp_file = get_package_root().joinpath("tests", "base_networks", "L-Town.inp")

    # Create an EPANETNetworkGraph from the WNTR model
    rprint("[bold]Creating network graph from WNTR model[/bold]")
    network_graph = EPANETNetworkGraph.from_epanet_file(inp_file)

    # Print initial graph information
    # G = network_graph.get_networkx_graph()
    rprint(f"[bold blue]Initial graph: [/bold blue] {network_graph}")
    rprint(f"Number of nodes: {network_graph.number_of_nodes()}")
    rprint(f"Number of edges: {network_graph.number_of_edges()}")

    # Get all pipe names
    pipe_names = []
    for _, _, data in network_graph.edges(data=True):
        if "key" in data and data.get("link_type", "") == "PIPE":
            pipe_names.append(data["key"])

    rprint(f"Pipes in network: {pipe_names}")

    # Create a pipe remover to remove some pipes
    pipes_to_remove = pipe_names[:7]  # Remove first two pipes
    rprint(f"Pipes selected for removal: {pipes_to_remove}")

    pipe_remover = NetworkGraphPipeRemover(
        pipe_names=pipes_to_remove,
        text_logging=True,
        structured_logging=True,
        preserve_connectivity=True,
        raise_on_error=False,
    )

    # Apply the modifier
    rprint("[bold]Applying pipe removal to network graph...[/bold]")
    pipe_remover.apply(network_graph)

    # Print results
    # G = network_graph.get_networkx_graph()
    rprint(f"[bold blue]Modified graph: [/bold blue] {network_graph}")
    rprint(f"Number of nodes: {network_graph.number_of_nodes()}")
    rprint(f"Number of edges: {network_graph.number_of_edges()}")

    # Print logs
    rprint("[bold]Text Log:[/bold]")
    for entry in pipe_remover.text_log:
        rprint(f"  {entry}")

    rprint("[bold]Structured Log:[/bold]")
    for class_name, entries in pipe_remover.structured_log.items():
        rprint(f"[bold green]{class_name}:[/bold green]")
        for entry in entries:
            status = entry.get("status", "unknown")
            component = entry["component_name"]
            old_val = entry["old_value"]
            new_val = entry["new_value"]

            status_color = {
                "removed": "red",
                "skipped": "yellow",
                "preserved": "blue",
            }.get(status, "white")

            rprint(
                f"  - {component}: [{status_color}]{status}[/{status_color}] ({old_val} → {new_val})"
            )

            # Print additional details
            details = {
                k: v
                for k, v in entry.items()
                if k
                not in [
                    "component_name",
                    "component_type",
                    "attribute",
                    "old_value",
                    "new_value",
                    "status",
                ]
            }
            if details:
                for k, v in details.items():
                    if k != "pipe_data":  # Skip full pipe data for cleaner output
                        rprint(f"    {k}: {v}")

    # Verify removals
    remaining_pipes = []
    for _, _, data in network_graph.edges(data=True):
        if "key" in data and data.get("link_type", "") == "PIPE":
            remaining_pipes.append(data["key"])

    rprint(f"Remaining pipes: {remaining_pipes}")
    rprint(f"Number of nodes: {network_graph.number_of_nodes()}")
    rprint(f"Number of edges: {network_graph.number_of_edges()}")

    # Analyze connectivity
    components = list(nx.connected_components(network_graph))
    rprint(f"Number of connected components: {len(components)}")
    if len(components) > 1:
        rprint("[bold red]Warning: Network is disconnected![/bold red]")
        for i, comp in enumerate(components):
            rprint(f"  Component {i + 1}: {len(comp)} nodes")
