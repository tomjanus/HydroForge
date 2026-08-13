"""Module for representing and analyzing sensor networks.

Provides `SensorNetworkGraph`, a lightweight wrapper around a NetworkX
graph in which nodes represent sensors and edges represent bridges
(shared connections) between the pressure zones each sensor monitors.
"""
from typing import Dict, List, Tuple, Any, TypeAlias, NamedTuple
from collections import namedtuple
from dataclasses import dataclass, field
import networkx as nx
import numpy as np
from hydroforge.graphs.graph import PressureZones


SensorName: TypeAlias = str | int
Position = namedtuple("Position", ["x", "y"])

class SensorPathCosts(NamedTuple):
    """Named tuple for sensor path costs data."""
    matrix: np.ndarray
    sensors: tuple[SensorName, ...]


@dataclass
class SensorNetworkGraph:
    """Graph representation of a sensor network.

    Wraps a `networkx.Graph` where each node is a sensor and each edge is a
    bridge connecting the pressure zones monitored by two sensors.
    Attribute access not defined on this class is delegated to the
    underlying `networkx.Graph` instance.
    """
    _graph: nx.Graph = field(default_factory=nx.Graph, init=False, repr=False)

    def __getattr__(self, item):
        """Delegate attribute access to the underlying NetworkX graph.

        Parameters
        ----------
        item : str
            Name of the attribute to look up on the underlying graph.

        Returns
        -------
        Any
            The requested attribute of the underlying `networkx.Graph`.
        """
        return getattr(self._graph, item)
    
    def __len__(self) -> int:
        """
        Return the number of nodes (sensors) in the graph.

        Returns
        -------
        int
            Number of sensor nodes in the graph.
        """
        return len(self._graph)
    
    def __iter__(self):
        """Iterate over the sensor nodes of the underlying graph.

        Returns
        -------
        Iterator
            Iterator over the sensor node names.
        """
        return iter(self._graph)

    def __contains__(self, item):
        """Check if a sensor node is in the underlying graph.

        Parameters
        ----------
        item : SensorName
            Sensor node to check for membership.

        Returns
        -------
        bool
            True if `item` is a node in the graph, False otherwise.
        """
        return item in self._graph
    
    def __repr__(self) -> str:
        """
        Return a string representation of the graph, including key properties.

        Returns
        -------
        str
            Summary string with the number of sensors and connections.
        """
        num_nodes = self._graph.number_of_nodes()
        num_edges = self._graph.number_of_edges()
        return (f"SensorNetworkGraph with {num_nodes} sensors and {num_edges} connections.")

    @property
    def graph(self) -> nx.Graph:
        """Return the underlying NetworkX graph object.

        Returns
        -------
        networkx.Graph
            The underlying graph instance.
        """
        return self._graph
    
    def get_networkx_graph(self) -> nx.Graph:
        """Return the underlying NetworkX graph object.

        Returns
        -------
        networkx.Graph
            The underlying graph instance.
        """
        return self._graph
    
    def shortest_path(self, source: SensorName, target: SensorName) -> List[SensorName]:
        """Compute the shortest path between two sensor nodes.

        Parameters
        ----------
        source : SensorName
            The starting sensor node.
        target : SensorName
            The ending sensor node.

        Returns
        -------
        list of SensorName
            List of sensor nodes representing the shortest path from `source` to `target`.
        
        Raises
        ------
        nx.NetworkXNoPath
            If no path exists between `source` and `target`.
        """
        if source not in self._graph:
            raise ValueError(f"Source node '{source}' is not in the sensor graph.")
        if target not in self._graph:
            raise ValueError(f"Target node '{target}' is not in the sensor graph.")
        return nx.shortest_path(self._graph, source=source, target=target)
    
    @classmethod
    def from_sensor_graph(cls, graph: nx.Graph) -> "SensorNetworkGraph":
        """Create a `SensorNetworkGraph` from an existing NetworkX graph
        representing sensors.

        Parameters
        ----------
        graph : networkx.Graph
            The NetworkX graph to wrap.

        Returns
        -------
        SensorNetworkGraph
            A `SensorNetworkGraph` instance wrapping `graph`.

        Warnings
        --------
        This method can be unsafe because a manually created graph may not
        have the attributes (e.g., ``pos``, ``weight``) expected by
        `SensorNetworkGraph`. Use with caution.
        """
        obj = cls()
        obj._graph = graph
        return obj
    
    @classmethod
    def from_network_graph(cls, graph: nx.Graph, sensor_nodes: List[SensorName]) -> "SensorNetworkGraph":
        """Create a `SensorNetworkGraph` from a network graph and a list of
        sensor nodes.

        Parameters
        ----------
        graph : networkx.Graph
            The underlying network graph.
        sensor_nodes : list of SensorName
            List of sensor node names in the network.

        Returns
        -------
        SensorNetworkGraph
            A `SensorNetworkGraph` instance with the specified sensors.
        """
        obj = cls()
        obj._graph = graph.subgraph(sensor_nodes).copy()
        return obj
    
    @classmethod
    def from_sensor_zones(
            cls,
            sensor_locations: Dict[SensorName, Position],
            zone_sizes: Dict[SensorName, float],
            pressure_zones: PressureZones) -> "SensorNetworkGraph":
        """Create a sensor-level graph from sensor zones and pressure zone bridges.

        Builds a graph whose nodes are sensors, positioned according to
        `sensor_locations` and weighted by `zone_sizes`, and whose edges are
        the bridges connecting different pressure zones.

        Parameters
        ----------
        sensor_locations : dict of {SensorName: Position}
            Mapping of sensor name to its (x, y) position.
        zone_sizes : dict of {SensorName: float}
            Mapping of sensor name to the size (e.g., total pipe length) of
            the pressure zone it monitors.
        pressure_zones : PressureZones
            Object exposing a `bridges` attribute: a list of node-name
            tuples connecting sensors across pressure zones.

        Returns
        -------
        SensorNetworkGraph
            A new `SensorNetworkGraph` built from the given sensor zones.
        """
        _sensor_graph = nx.Graph()
        graph_nodes: List[Tuple[SensorName, Dict[SensorName, Any]]] = [
            (sensor, {"pos": (position.x, position.y), "weight": zone_sizes.get(sensor, 0)})
            for sensor, position in sensor_locations.items()
        ]
        _sensor_graph.add_nodes_from(graph_nodes)
        _sensor_graph.add_edges_from(pressure_zones.bridges)
        return cls.from_sensor_graph(_sensor_graph)

    def sensor_path_costs(self) -> SensorPathCosts:
        """Compute the sensor-level shortest-path weight matrix.

        The shortest path is determined using unweighted graph edges. The
        cost of each path is the sum of the weights assigned to its nodes.
        
        Unreachable sensor pairs have a path cost of ``np.inf``.

        Returns
        -------
        SensorPathCosts
            Contains the sensor path-cost matrix and the corresponding
            sensor ordering. ``matrix[i, j]`` gives the path cost from
            ``sensors[i]`` to ``sensors[j]``. ``np.inf`` indicates that
            no path exists between the two sensors.

        Raises
        ------
        ValueError
            If the graph has no node weights or if one or more graph nodes
            are missing a ``weight`` attribute.
        """
        _weights = nx.get_node_attributes(self._graph, 'weight')
        if not _weights:
            raise ValueError(
                "The graph does not have a 'weight' attribute. "
                "Please ensure the graph nodes have a 'weight' attribute assigned."
            )
        missing_weights = set(self._graph.nodes) - _weights.keys()
        if missing_weights:
            raise ValueError(
                "The following graph nodes are missing a 'weight' attribute: "
                f"{sorted(missing_weights)}"
            )
        sensors = tuple(self._graph.nodes)
        sensor_index = {sensor: i for i, sensor in enumerate(sensors)}
        cost_matrix = np.full(
            (len(sensors), len(sensors)),
            np.inf,
            dtype=float,
        )
        for source, paths in nx.all_pairs_shortest_path(self._graph):
            source_index = sensor_index[source]
            for target, path in paths.items():
                target_index = sensor_index[target]
                cost_matrix[source_index, target_index] = sum(
                    _weights[node] for node in path
                )
        return SensorPathCosts(
            matrix=cost_matrix,
            sensors=sensors,
        )

