"""
This module provides various sensor placement strategies for water distribution networks,
including greedy, K-center, random, centrality-based, coverage-based, dominating set-based,
and fixed location placements. It also includes a `SensorPlacer` class to manage the
placement process with different sensor placement algorithms and visualize the results.

The module uses the EPANETNetworkGraph class to represent the water network and
networkx for graph algorithms.
"""

from typing import Protocol, TypeAlias, Literal, Optional, List, Union, cast
import re
from dataclasses import dataclass, field
import pathlib
import random
import heapq
import json
import networkx as nx
from rich import print as rprint
from hydroforge.graphs.graph import EPANETNetworkGraph
from hydroforge.graphs.visualization import EPANETGraphPlotter

# Method for connecting newly added sensors to sources for cases with multiple sources
# 'nearest' - connects to the nearest source
# 'all' - connects to all sources
# 'random' - picks one source at random (non-deterministic, but controllable with seed)
GraphUpdateMethod: TypeAlias = Literal["nearest", "all", "random"]
CentralityType: TypeAlias = Literal["betweenness", "closeness", "degree", "eigenvector"]


class SensorPlacementStrategy(Protocol):
    """Protocol defining the interface for sensor placement strategies."""

    def place(self) -> List[Union[str, int]]:
        """Place sensors in the network according to a placement strategy.

        Returns
        -------
        list of {str, int}
            Nodes selected for sensor placement.
        """
        ...


@dataclass
class SourceFinder:
    """
    Identify source nodes in a network graph based on name matching.

    Parameters
    ----------
    graph : networkx.Graph or EPANETNetworkGraph
        Network graph with named nodes.
    source_keyword : str
        Keyword or regex used to identify source nodes (default: "R").
    case_sensitive : bool
        Whether to treat the search as case-sensitive (default: False).
    use_regex : bool
        Whether to interpret `source_keyword` as a regular expression (default: False).
    """

    graph: EPANETNetworkGraph = field(repr=False)
    source_keyword: str = "R"
    case_sensitive: bool = False
    use_regex: bool = False

    def find_sources(self) -> List[Union[str, int]]:
        """Find source (e.g., reservoir) nodes matching the configured keyword.

        Returns
        -------
        list of str or int
            Node names matching `source_keyword`, according to
            `case_sensitive` and `use_regex`.
        """
        nodes = list(self.graph.nodes)
        keyword = self.source_keyword

        if self.use_regex:
            # Use regex search
            flags = 0 if self.case_sensitive else re.IGNORECASE
            matched_nodes = [
                n for n in nodes if re.search(keyword, str(n), flags=flags)
            ]
        else:
            # Use simple substring search
            if not self.case_sensitive:
                keyword = keyword.lower()
                matched_nodes = [n for n in nodes if keyword in str(n).lower()]
            else:
                matched_nodes = [n for n in nodes if keyword in str(n)]
        return matched_nodes


@dataclass
class GreedySensorPlacement:
    """Calculate optimal sensor placement using a greedy algorithm.

    Iteratively places a sensor at the node farthest (by shortest-path
    distance) from all water sources and previously placed sensors, then
    adds a zero-length edge from the nearest source to that node so it is
    effectively treated as a new source in the next iteration. This
    encourages good spatial distribution of sensors across the network.

    Parameters
    ----------
    graph : EPANETNetworkGraph
        The network graph.
    num_sensors : int
        Number of sensors to place.
    sources : list
        List of source nodes for the sensor placement.
    target_nodes : list, optional
        List of target nodes to find the shortest paths to. Defaults to
        all graph nodes (excluding sources) when None.
    weight : str, default="len"
        Edge weight attribute to use for distance calculations.
    update_method : GraphUpdateMethod, default="nearest"
        Method for connecting a newly placed sensor to the source set:
        ``"nearest"`` connects to the nearest source, ``"all"`` connects to
        all sources, and ``"random"`` connects to a randomly chosen source.
    inplace : bool, default=False
        Whether to modify `graph` in place or operate on a copy.

    Notes
    -----
    Example progression for 3 sensors with sources ``{R1, R2}``:

    1. Place a sensor at the node farthest from ``{R1, R2}``, e.g. J5, and
       add a zero-length edge R1 -> J5.
    2. Place a sensor at the node farthest from ``{R1, R2, J5}``, e.g. J12,
       and add a zero-length edge R1 -> J12.
    3. Place a sensor at the node farthest from ``{R1, R2, J5, J12}``.
    """

    graph: EPANETNetworkGraph = field(repr=False)
    num_sensors: int
    sources: List = field(default_factory=list)
    target_nodes: Optional[List] = None
    weight: str = "len"
    update_method: GraphUpdateMethod = "nearest"
    inplace: bool = False

    def place(self) -> list[str]:
        """Place sensors greedily at the nodes farthest from sources.

        Returns
        -------
        list[str]
            Optimal sensor placement locations.

        Raises
        ------
        ValueError
            If no reservoir nodes are found or target nodes are invalid.
        """
        graph = self.graph if self.inplace else self.graph.copy()
        sensor_places = []
        # Cache for faster lookups
        targets = (
            set(self.target_nodes) - set(self.sources)
            if self.target_nodes
            else set(graph.nodes) - set(self.sources)
        )
        # Initial distances
        shortest_paths = dict(
            nx.multi_source_dijkstra_path_length(
                graph, sources=self.sources, weight=self.weight
            )
        )
        for _ in range(self.num_sensors):
            # Only consider target nodes
            candidate_paths = {
                k: shortest_paths[k] for k in targets if k in shortest_paths
            }
            node_max_distance = max(candidate_paths, key=candidate_paths.get)
            sensor_places.append(node_max_distance)
            # Update sources and distances incrementally
            self.sources.append(node_max_distance)
            new_paths = nx.single_source_dijkstra_path_length(
                graph, node_max_distance, weight=self.weight
            )
            for node, dist in new_paths.items():
                if dist < shortest_paths.get(node, float("inf")):
                    shortest_paths[node] = dist
            # Add zero-length edge from nearest source
            if self.update_method == "all":
                for src in self.sources:
                    graph.add_edge(src, node_max_distance, len=0)
            elif self.update_method == "nearest":
                closest_source = min(self.sources, key=lambda src: shortest_paths[src])
                graph.add_edge(closest_source, node_max_distance, len=0)
            elif self.update_method == "random":
                graph.add_edge(random.choice(self.sources), node_max_distance, len=0)
        return sensor_places


@dataclass
class KCentreSensorPlacement:
    """K-Centre sensor placement using a greedy K-Center algorithm.

    Parameters
    ----------
    graph : EPANETNetworkGraph
        The network graph.
    num_sensors : int
        Number of sensors to place.
    sources : list
        List of source nodes.
    target_nodes : list, optional
        List of target nodes for sensor coverage.
    inplace : bool, default=False
        Whether to modify `graph` in place or operate on a copy.
    """

    graph: EPANETNetworkGraph = field(repr=False)
    num_sensors: int
    sources: List
    target_nodes: Optional[List] = None
    inplace: bool = False

    def place(self) -> list[str]:
        """Place sensors using an optimized greedy K-Center algorithm.

        This version maintains nearest distances incrementally to avoid
        recomputation, reducing complexity from O(k*n^2) to O(k*n) after
        precomputing all pairwise shortest paths.

        Returns
        -------
        list[str]
            Sensor placement locations.
        """
        graph = self.graph if self.inplace else self.graph.copy()
        target_nodes = (
            list(set(graph.nodes()) - set(self.sources))
            if not self.target_nodes
            else list(set(self.target_nodes) - set(self.sources))
        )

        if self.num_sensors >= len(target_nodes):
            return target_nodes[: self.num_sensors]

        # Precompute all shortest path distances (dict of dicts)
        all_distances = dict(nx.all_pairs_dijkstra_path_length(graph, weight="len"))

        # Start with an arbitrary node (could also choose a better heuristic)
        first = target_nodes[0]
        sensor_places = [first]

        # Track distance of each node to nearest chosen sensor
        nearest_dist = {
            node: all_distances[first].get(node, float("inf")) for node in target_nodes
        }

        # Iteratively add sensors
        for _ in range(1, self.num_sensors):
            # Pick the node farthest from any chosen sensor
            best_node = max(nearest_dist, key=nearest_dist.get)
            sensor_places.append(best_node)

            # Update nearest distances
            for node in target_nodes:
                d = all_distances[best_node].get(node, float("inf"))
                if d < nearest_dist[node]:
                    nearest_dist[node] = d

        return sensor_places


@dataclass
class RandomSensorPlacement:
    """Random sensor placement using a random sampling approach.

    Parameters
    ----------
    graph : EPANETNetworkGraph
        The network graph.
    num_sensors : int
        Number of sensors to place.
    sources : list
        List of source nodes.
    target_nodes : list, optional
        List of target nodes for sensor coverage.
    seed : int, optional
        Random seed for reproducibility.
    inplace : bool, default=False
        Whether to modify `graph` in place or operate on a copy.
    """

    graph: EPANETNetworkGraph = field(repr=False)
    num_sensors: int
    sources: List
    target_nodes: Optional[List] = None
    seed: Optional[int] = None
    inplace: bool = False

    def place(self) -> list[str]:
        """Place sensors randomly for baseline comparison.

        Validates that target nodes exist in the graph and are connected
        before randomly selecting sensor locations.

        Returns
        -------
        list[str]
            Randomly selected sensor locations.

        Raises
        ------
        ValueError
            If the graph is empty, target nodes are not found in the graph,
            or `num_sensors` is not positive.
        """
        graph = self.graph if self.inplace else self.graph.copy()
        if not graph.nodes():
            raise ValueError("Graph is empty - no nodes available for sensor placement")
        # Validate that all target nodes exist in the graph
        graph_nodes = set(graph.nodes())
        if self.target_nodes is None:
            target_nodes = list(set(graph.nodes()) - set(self.sources))
        else:
            target_nodes = list(set(self.target_nodes) - set(self.sources))
        invalid_nodes = [node for node in target_nodes if node not in graph_nodes]
        if invalid_nodes:
            raise ValueError(f"Target nodes not found in graph: {invalid_nodes}")

        # Check if target nodes are connected (optional but good practice)
        if len(target_nodes) > 1:
            # Create subgraph with only target nodes and check connectivity
            target_subgraph = graph.subgraph(target_nodes)
            if not nx.is_connected(target_subgraph):
                # This is a warning, not an error, as disconnected nodes might be valid
                rprint("Warning: Some target nodes are disconnected in the network")
        # Validate num_sensors
        if self.num_sensors <= 0:
            raise ValueError("Number of sensors must be positive")
        if self.num_sensors > len(target_nodes):
            rprint(
                f"Warning: Requested {self.num_sensors} sensors but only {len(target_nodes)} target nodes available"
            )
        # Set seed for reproducibility
        if self.seed is not None:
            random.seed(self.seed)
        # Randomly select sensor locations
        return random.sample(target_nodes, min(self.num_sensors, len(target_nodes)))


@dataclass
class CentralityBasedSensorPlacement:
    """Place sensors based on centrality measures.

    Places sensors at nodes with the highest centrality scores, which
    often correspond to important or influential positions in the network.

    Parameters
    ----------
    graph : EPANETNetworkGraph
        The network graph.
    num_sensors : int
        Number of sensors to place.
    sources : list
        List of source nodes.
    target_nodes : list, optional
        List of target nodes for sensor coverage.
    weight : str, default="len"
        Edge weight attribute used for distance-based centrality measures.
    centrality_type : CentralityType, default="degree"
        Centrality measure to use: ``"betweenness"``, ``"closeness"``,
        ``"degree"``, or ``"eigenvector"``.
    inplace : bool, default=False
        Whether to modify `graph` in place or operate on a copy.
    """

    graph: EPANETNetworkGraph = field(repr=False)
    num_sensors: int
    sources: List
    target_nodes: Optional[List] = None
    weight: str = (
        "len"  # Perhaps use different weight e.g. measured pressure difference, etc.
    )
    centrality_type: CentralityType = "degree"
    inplace: bool = False

    def place(self) -> list[str]:
        """Place sensors at the target nodes with the highest centrality scores.

        Returns
        -------
        list[str]
            Sensor locations selected by centrality score.

        Raises
        ------
        ValueError
            If `centrality_type` is not a recognized centrality measure.
        """
        graph = self.graph if self.inplace else self.graph.copy()
        # --- Compute centrality ---
        if self.centrality_type == "betweenness":
            centrality = nx.betweenness_centrality(graph, weight=self.weight)
        elif self.centrality_type == "closeness":
            centrality = nx.closeness_centrality(graph, distance=self.weight)
        elif self.centrality_type == "degree":
            centrality = nx.degree_centrality(graph)
        elif self.centrality_type == "eigenvector":
            try:
                centrality = nx.eigenvector_centrality(
                    graph, weight=self.weight, max_iter=500, tol=1e-06
                )
            except nx.PowerIterationFailedConvergence:
                centrality = nx.degree_centrality(graph)  # fallback
        else:
            raise ValueError(f"Unknown centrality type: {self.centrality_type}")
        # --- Determine target nodes (exclude sources) ---
        if self.target_nodes is None:
            target_nodes = set(graph.nodes()) - set(self.sources)
        else:
            target_nodes = set(self.target_nodes) - set(self.sources)
        # --- Extract scores for targets ---
        target_centrality = {node: centrality.get(node, 0.0) for node in target_nodes}
        # --- Select top-k efficiently ---
        top_nodes = heapq.nlargest(
            self.num_sensors, target_centrality.items(), key=lambda x: x[1]
        )
        return [node for node, _ in top_nodes]


@dataclass
class CoverageBasedSensorPlacement:
    """Place sensors to maximize coverage within a specified radius.

    Uses a greedy approach to place sensors that cover the maximum number
    of uncovered nodes within `coverage_radius`.

    Parameters
    ----------
    graph : EPANETNetworkGraph
        The network graph.
    num_sensors : int
        Number of sensors to place.
    sources : list
        List of source nodes.
    target_nodes : list, optional
        List of target nodes for sensor coverage.
    weight : str, default="len"
        Edge weight attribute to use for distance calculations.
    coverage_radius : float, default=100
        Maximum distance (in `weight` units) within which a sensor is
        considered to cover a node.
    """

    graph: EPANETNetworkGraph = field(repr=False)
    num_sensors: int
    sources: List
    target_nodes: Optional[List] = None
    weight: str = "len"
    coverage_radius: float = 100

    def place(self) -> list[str]:
        """Greedily select sensor locations that maximize node coverage.

        Returns
        -------
        list[str]
            Sensor placement locations.
        """
        sensor_locations = []
        covered_nodes = set()

        # Precompute distances from all target nodes using dijkstra for weighted graphs
        distances = {}

        target_nodes = (
            set(self.graph.nodes()) - set(self.sources)
            if not self.target_nodes
            else set(self.target_nodes) - set(self.sources)
        )

        for node in target_nodes:
            distances[node] = nx.single_source_dijkstra_path_length(
                self.graph.graph, node, cutoff=self.coverage_radius, weight=self.weight
            )

        for _ in range(self.num_sensors):
            best_node = None
            max_new_coverage = 0
            for candidate in target_nodes:
                if candidate in sensor_locations:
                    continue
                # Count how many uncovered nodes this candidate would cover
                new_coverage = 0
                for covered_node in distances[candidate]:
                    if covered_node not in covered_nodes:
                        new_coverage += 1

                if new_coverage > max_new_coverage:
                    max_new_coverage = new_coverage
                    best_node = candidate

            if best_node is None:
                break

            sensor_locations.append(best_node)
            # Add all nodes covered by this sensor to the covered set
            covered_nodes.update(distances[best_node].keys())

        return sensor_locations


@dataclass
class DominatingSetBasedSensorPlacement:
    """Place sensors using a greedy dominating set approach.

    Parameters
    ----------
    graph : EPANETNetworkGraph
        The network graph.
    num_sensors : int
        Maximum number of sensors to place.
    sources : list
        List of source nodes.
    target_nodes : list, optional
        List of target nodes to dominate.
    """

    graph: EPANETNetworkGraph = field(repr=False)
    num_sensors: int
    sources: List
    target_nodes: Optional[List] = None

    def place(self) -> list[str]:
        """Place sensors using a greedy dominating set approach.

        Places sensors such that every target node is either a sensor
        location or adjacent to a sensor location. Uses a greedy algorithm
        to approximate the minimum dominating set.

        Returns
        -------
        list[str]
            Sensor placement locations.
        """
        sensor_places = []
        dominated_nodes = set()
        target_nodes = (
            set(self.graph.nodes()) - set(self.sources)
            if not self.target_nodes
            else set(self.target_nodes) - set(self.sources)
        )

        while len(sensor_places) < self.num_sensors and len(dominated_nodes) < len(
            target_nodes
        ):
            best_node = None
            max_domination = 0
            for candidate in target_nodes:
                if candidate in sensor_places:
                    continue
                # Count how many undominated nodes this candidate would dominate
                domination_count = 0
                # The candidate dominates itself
                if candidate not in dominated_nodes:
                    domination_count += 1
                # Check neighbors
                for neighbor in self.graph.neighbors(candidate):
                    if neighbor in target_nodes and neighbor not in dominated_nodes:
                        domination_count += 1
                if domination_count > max_domination:
                    max_domination = domination_count
                    best_node = candidate
            if best_node is None or max_domination == 0:
                break
            sensor_places.append(best_node)
            # Mark dominated nodes
            dominated_nodes.add(best_node)
            for neighbor in self.graph.neighbors(best_node):
                if neighbor in target_nodes:
                    dominated_nodes.add(neighbor)
        return sensor_places


@dataclass
class FixedLocationSensorPlacement:
    """Place sensors at fixed, pre-determined locations.

    Parameters
    ----------
    sensors : list
        Sensor node IDs to place.
    graph : EPANETNetworkGraph, optional
        Network graph used to validate that `sensors` exist in the graph.
        Validation is skipped when None.
    sources : list, optional
        Source nodes used to validate that `sensors` do not overlap with
        sources. Validation is skipped when None.
    """

    sensors: List
    graph: Optional[EPANETNetworkGraph] = field(repr=False, default=None)
    sources: Optional[List] = None

    def place(self) -> list[str]:
        """Return the fixed sensor locations after validation.

        Returns
        -------
        list[str]
            The configured sensor locations (`self.sensors`).

        Raises
        ------
        ValueError
            If any fixed sensor location is also a source node, or if any
            fixed sensor location is not present in `graph`.
        """
        if self.sources and set(self.sensors) & set(self.sources):
            raise ValueError("Fixed sensor locations must not be source nodes.")
        if self.graph and (set(self.sensors) - set(self.graph.nodes())):
            raise ValueError("Some fixed sensor locations are not in the graph.")
        return self.sensors


@dataclass
class SensorPlacer:
    """Coordinates sensor placement using a configurable placement strategy.

    Parameters
    ----------
    strategy : SensorPlacementStrategy
        The sensor placement strategy to use (e.g., `GreedySensorPlacement`,
        `RandomSensorPlacement`).
    """

    strategy: SensorPlacementStrategy
    sensors: list = field(init=False)

    def place_sensors(self) -> None:
        """Place sensors using the configured strategy.

        Calls `strategy.place()` and stores the resulting sensor locations
        in `self.sensors`.
        """
        # `Protocol` methods are sometimes not recognized by pylint's
        # static inference; cast the result to the declared list type to
        # avoid E1111 (assignment-from-no-return).
        self.sensors = cast(List[Union[str, int]], self.strategy.place())

    def load_sensors(self, file: pathlib.Path) -> None:
        """Load previously saved sensor locations from a JSON file.

        Parameters
        ----------
        file : pathlib.Path
            Path to the JSON file containing sensor locations.
        """
        with open(file, "r", encoding="utf-8") as f_in:
            self.sensors = json.load(f_in)

    def save_sensors(self, file: pathlib.Path) -> None:
        """Save the current sensor locations to a JSON file.

        Parameters
        ----------
        file : pathlib.Path
            Path to the JSON file to write.
        """
        with open(file, "w", encoding="utf-8") as f:
            json.dump(self.sensors, f, ensure_ascii=False)

    def plot_sensors(
        self,
        graph: EPANETNetworkGraph,
        title: str = "Water Distribution Network",
        save_path: Optional[str] = None,
    ):
        """Plot the network graph with sensor locations highlighted.

        Uses `hydroforge.graphs.visualization.EPANETGraphPlotter` to render
        the network.

        Parameters
        ----------
        graph : EPANETNetworkGraph
            The network graph to plot.
        title : str, default="Water Distribution Network"
            Title for the plot.
        save_path : str, optional
            If provided, path to save the plot image to; otherwise the plot
            is only displayed.
        """
        plotter = EPANETGraphPlotter(graph)
        plotter.plot(title, sensors=self.sensors, save_path=save_path)


if __name__ == "__main__":
    pass
