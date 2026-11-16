"""Graph representation and manipulation for EPANET water distribution networks."""

from typing import Dict, List, Tuple, Any, TypeAlias, Set
from dataclasses import dataclass, field
from collections import OrderedDict, namedtuple
import copy
from numbers import Number
import pathlib
import networkx as nx
import numpy as np
import pandas as pd
from rich import print as rprint
from ..epanetfile_io import EPANETNetworkModelIO, EPANETNetworkModel, EPANETFileIO

# Constants
WEIGHT_COEFFICIENT: int = 1_000
NONPIPE_LINK_LEN: float = 0.5

NodeName: TypeAlias = Any  # Node identifier type (normally, str or int)
SensorName: TypeAlias = str | int

Position = namedtuple("Position", ["x", "y"])


@dataclass(frozen=True)
class PressureZones:
    """Defines the graph of isolated pressure zones and bridges connecting them"""

    zone_graph: nx.Graph  # Graph of disconnected pressure zones
    bridges: List[
        Tuple[NodeName, NodeName]
    ]  # List of bridges (node tuples) connecting different pressure zones

    def compute_zone_pipe_lengths(
        self, sensors: list[str], weight: str = "len"
    ) -> Dict[SensorName, float | None]:
        """Calculate total pipe length per sensor zone.
        Args:
            sensors (list[str]): The list of sensor names.
            weight (str): The edge attribute to use as weight (default 'len').
            as_series (bool): If True, return a pandas Series instead of a dictionary.
        Returns:
            Dict[SensorName, float]: The total pipe lengths per sensor zone.
        """
        zone_graph = self.zone_graph
        zone_sizes: Dict[SensorName, float | None] = {
            sensor: None for sensor in sensors
        }
        # Build a dictionary of node attributes
        closest_sensors_per_node: Dict[SensorName, Any] = nx.get_node_attributes(
            G=zone_graph, name="closest_sensor"
        )
        # Iterate trough all pressure zones and for each, calculate is total length
        for zone in nx.connected_components(zone_graph):
            sensors_in_pressure_zone: Set[SensorName] = {
                closest_sensors_per_node[n] for n in zone
            }
            if len(sensors_in_pressure_zone) == 1:
                sensor: SensorName = next(iter(sensors_in_pressure_zone))
                total_len = sum(
                    zone_graph[u][v].get(weight, 0.0) for u, v in zone_graph.edges(zone)
                )
                zone_sizes[sensor] = total_len
            # else: leave as NaN (ambiguous)
        return zone_sizes


@dataclass(frozen=True)
class SensorInfo:
    """Defines the nearest sensor and pressure zone (for a network node)
    E.g. if a node called "N1" is associated with SensorInfo("S5", 16), it means that
    the closest sensor to "N1" is "S5" and the node is located in pressure zone 16.
    """

    sensor: SensorName  # Sensor Number / Name
    # Pressure zone defined by 'correspondence' of a node to a sensor index (0-based)
    pressure_zone: int


# --------------- helper functions ---------------


def pretty_print_graph_diffs(
    diffs: Dict[str, Any],
    max_examples: int = 10,
    show_node_comparison: bool = False,
    show_edge_comparison: bool = True,
) -> None:
    """Function for displaying graph differences in the Console / Terminal"""
    rprint("Graph comparison summary:")
    for k, v in diffs.get("_summary", {}).items():
        rprint(f" - {k}: {v}")
    if show_node_comparison:
        if diffs["nodes_only_in_g1"]:
            print("\nNodes only in g1 (examples):")
            for n in diffs["nodes_only_in_g1"][:max_examples]:
                rprint("  ", n)
        if diffs["nodes_only_in_g2"]:
            rprint("\nNodes only in g2 (examples):")
            for n in diffs["nodes_only_in_g2"][:max_examples]:
                rprint("  ", n)
        if diffs["node_attr_diffs"]:
            rprint("\nNode attribute mismatches (examples):")
            for i, (node, mismatches) in enumerate(diffs["node_attr_diffs"].items()):
                if i >= max_examples:
                    break
                rprint("  Node:", node)
                for attr, v1, v2 in mismatches:
                    rprint(f"    - {attr}: g1={v1!r}  g2={v2!r}")
    if show_edge_comparison:
        if diffs["edges_only_in_g1"]:
            rprint("\nEdges only in g1 (examples):")
            for e in diffs["edges_only_in_g1"][:max_examples]:
                rprint("  ", e)
        if diffs["edges_only_in_g2"]:
            rprint("\nEdges only in g2 (examples):")
            for e in diffs["edges_only_in_g2"][:max_examples]:
                rprint("  ", e)
        if diffs["edge_attr_diffs"]:
            rprint("\nEdge attribute mismatches (examples):")
            for ix, (edge, mismatches) in enumerate(diffs["edge_attr_diffs"].items()):
                if ix >= max_examples:
                    break
                rprint("  Edge:", edge)
                for attr, v1, v2 in mismatches:
                    rprint(f"    - {attr}: g1={v1!r}  g2={v2!r}")


# --------------- EPANETNetworkGraph ---------------


@dataclass
class EPANETNetworkGraph:
    """Graph representation of an EPANET water distribution network."""

    _graph: nx.Graph = field(default_factory=nx.Graph, init=False, repr=False)

    def __getattr__(self, item):
        # Delegate attribute access to the underlying nx.Graph
        return getattr(self._graph, item)

    def __len__(self) -> int:
        """
        Return the number of nodes in the graph.
        """
        return len(self._graph)

    def __iter__(self):
        """Iterate over the nodes of the underlying graph."""
        return iter(self._graph)

    def __contains__(self, item):
        """Check if a node is in the underlying graph."""
        return item in self._graph

    def __repr__(self) -> str:
        """
        Return a string representation of the graph, including key properties.
        """
        num_nodes = self._graph.number_of_nodes()
        num_edges = self._graph.number_of_edges()
        return f"EPANETNetworkGraph with {num_nodes} nodes and {num_edges} edges."

    @property
    def graph(self) -> nx.Graph:
        """ """
        return self._graph

    def get_networkx_graph(self) -> nx.Graph:
        """Returns the underlying NetworkX graph object."""
        return self._graph

    def find_total_length(self, weight_field: str = "len") -> Number:
        """Returns the sum of all weights in a network graph - by default a total length.
        It implements a special case of nx.Grap.size method where the weight field is not None.
        Otherwise, the method would have returned the total number of edges (an integer).

        Args:
            weight_field (str): The edge attribute to use as weight (default is "len").
        Returns:
            Number: The total length of the network graph.
        """
        return self.size(weight=weight_field)

    @classmethod
    def from_graph(cls, graph: nx.Graph) -> "EPANETNetworkGraph":
        """
        Creates an EPANETNetworkGraph object from an existing networkx graph.

        Warning: This method can be unsafe because a manually created graph may not have the correct attributes
        expected by the EPANETNetworkGraph. Use with caution.

        Args:
            graph (nx.Graph): The networkx graph to use.

        Returns:
            EPANETNetworkGraph: An EPANETNetworkGraph object.
        """
        obj = cls()
        obj._graph = graph
        return obj

    @classmethod
    def from_model(
        cls, model: OrderedDict | EPANETNetworkModel, *args, **kwargs
    ) -> "EPANETNetworkGraph":
        """
        Generates an EPANETNetworkGraph from a model.

        Args:
            model (OrderedDict | EPANETNetworkModel): The model to generate the graph from.
            *args: Additional arguments to pass to the graph constructor.
            **kwargs: Additional keyword arguments to pass to the graph constructor.
        Returns:
            EPANETNetworkGraph: The generated graph.
        """
        model_graph = cls._make_graph(model, *args, **kwargs)
        return cls.from_graph(model_graph)

    @classmethod
    def from_epanet_file(
        cls, filename: pathlib.Path, *args, **kwargs
    ) -> "EPANETNetworkGraph":
        """Create a NetworkGraph from an EPANET .inp file.

        Args:
            filename (pathlib.Path): Path to the .inp file.
            *args: Additional arguments to pass to the NetworkGraph constructor.
            **kwargs: Additional keyword arguments to pass to the NetworkGraph constructor.

        Returns:
            EPANETNetworkGraph: A NetworkGraph object representing the EPANET network.
        """
        model = EPANETFileIO.read_inp_file(filename)
        return cls.from_model(model, *args, **kwargs)

    @staticmethod
    def _make_graph(
        model: OrderedDict | EPANETNetworkModel,
        as_undirected: bool = False,
        extra_safety: bool = False,
    ) -> nx.Graph:
        """
        Creates a NetworkX graph from network model.

        Args:
            model (OrderedDict | EPANETNetworkModel): The model to generate the graph from.
            as_undirected: If True, convert to undirected graph
            extra_safety: If True, perform additional validation checks (slower)
        """
        if isinstance(model, (dict, OrderedDict)):
            model = EPANETNetworkModelIO.from_dict(model)
        G = nx.Graph()
        # Optimization: Create coordinate lookup dictionary for O(1) access
        coord_lookup = {coord.node_id: coord for coord in model.coordinates}
        # Add junction nodes
        for junction in model.junctions:
            name = junction.id
            coord_line = coord_lookup.get(name)
            if coord_line:
                demands = float(junction.base_demand)
                elevations = float(junction.elevation)
                G.add_node(
                    name,
                    pos=(float(coord_line.x_coord), float(coord_line.y_coord)),
                    demand=demands,
                    elevation=elevations,
                    node_type="JUNCTION",
                )
            elif extra_safety:
                # Only warn if extra_safety is enabled
                rprint(f"Warning: No coordinates found for junction {name}")
        # Add reservoir nodes
        for reservoir in model.reservoirs:
            name = reservoir.id
            coord_line = coord_lookup.get(name)
            if coord_line:
                elevations = float(reservoir.head)
                G.add_node(
                    name,
                    pos=(float(coord_line.x_coord), float(coord_line.y_coord)),
                    elevation=elevations,
                    node_type="RESERVOIR",
                )
            elif extra_safety:
                rprint(f"Warning: No coordinates found for reservoir {name}")
        # Add tank nodes
        for tank in model.tanks:
            name = tank.id
            coord_line = coord_lookup.get(name)

            if coord_line:
                elevations = float(tank.elevation)
                G.add_node(
                    name,
                    pos=(float(coord_line.x_coord), float(coord_line.y_coord)),
                    elevation=elevations,
                    node_type="TANK",
                )
            elif extra_safety:
                rprint(f"Warning: No coordinates found for tank {name}")
        # Add pipe edges
        pipe_edges = []
        for pipe in model.pipes:
            name = pipe.id
            start_node = pipe.start_node
            end_node = pipe.end_node
            length = float(pipe.length)
            diameter = float(pipe.diameter)
            weight = (length * WEIGHT_COEFFICIENT) / diameter
            status = pipe.status
            # Collect edge data
            pipe_edges.append(
                (
                    start_node,
                    end_node,
                    {
                        "len": length,
                        "dia": diameter,
                        "Wei": weight,
                        "key": name,
                        "status": status,
                        "link_type": "PIPE",
                    },
                )
            )
        # Add all pipe edges at once
        G.add_edges_from(pipe_edges)
        # Add pump edges
        pump_edges = []
        for pump in model.pumps:
            pump_edges.append(
                (
                    pump.start_node,
                    pump.end_node,
                    {"len": NONPIPE_LINK_LEN, "key": pump.id, "link_type": "PUMP"},
                )
            )
        G.add_edges_from(pump_edges)
        # Add valve edges
        valve_edges = []
        for valve in model.valves:
            diameter = float(valve.diameter)
            weight = (NONPIPE_LINK_LEN * WEIGHT_COEFFICIENT) / diameter
            valve_edges.append(
                (
                    valve.start_node,
                    valve.end_node,
                    {
                        "len": NONPIPE_LINK_LEN,
                        "dia": diameter,
                        "Wei": weight,
                        "key": valve.id,
                        "setting": valve.setting,
                        "link_type": "VALVE",
                    },
                )
            )
        G.add_edges_from(valve_edges)
        if as_undirected:
            # Convert to undirected graph if specified
            G = G.to_undirected()
        return G

    def compare(
        self, other: "EPANETNetworkGraph", float_tol: float = 1e-9
    ) -> Dict[str, Any]:
        """Compare two EPANETNetworkGraph graphs and return a dictionary of differences.

        - For undirected graphs edges are compared as unordered pairs.
        - Numeric attributes are compared with np.isclose using float_tol.
        """

        def _canonical_edge(u, v):
            return tuple(sorted((u, v)))

        def _is_number(x):
            return isinstance(x, (int, float, np.floating, np.integer))

        def _values_equal(a, b):
            # both numbers -> use tolerance
            if _is_number(a) and _is_number(b):
                return np.isclose(a, b, rtol=float_tol, atol=0)
            # both iterables of numbers -> compare elementwise
            try:
                aa = np.asarray(a, dtype=float)
                bb = np.asarray(b, dtype=float)
            except (TypeError, ValueError, OverflowError):
                # Can't convert to numeric arrays — fall back to plain equality
                return a == b
            if aa.shape != bb.shape:
                return False
            return np.allclose(aa, bb, rtol=float_tol, atol=0)

        _diffs: dict[str, Any] = {
            "nodes_only_in_g1": [],
            "nodes_only_in_g2": [],
            "node_attr_diffs": {},  # node -> list of (attr, val1, val2)
            "edges_only_in_g1": [],
            "edges_only_in_g2": [],
            "edge_attr_diffs": {},  # edge_tuple -> list of (attr, val1, val2)
        }

        # Node set differences
        nodes1 = set(self._graph.nodes())
        nodes2 = set(other._graph.nodes())
        _diffs["nodes_only_in_g1"] = sorted(list(nodes1 - nodes2))
        _diffs["nodes_only_in_g2"] = sorted(list(nodes2 - nodes1))

        # Node attribute differences for common nodes
        for n in sorted(nodes1 & nodes2):
            attrs1 = self._graph.nodes[n]
            attrs2 = other._graph.nodes[n]
            keys = set(attrs1.keys()) | set(attrs2.keys())
            node_mismatch = []
            for k in keys:
                v1 = attrs1.get(k, None)
                v2 = attrs2.get(k, None)
                if not _values_equal(v1, v2):
                    node_mismatch.append((k, v1, v2))
            if node_mismatch:
                _diffs["node_attr_diffs"][n] = node_mismatch

        # Edge set differences (use canonical unordered tuples)
        edges1 = {_canonical_edge(u, v) for u, v in self._graph.edges()}
        edges2 = {_canonical_edge(u, v) for u, v in other._graph.edges()}
        _diffs["edges_only_in_g1"] = sorted(list(edges1 - edges2))
        _diffs["edges_only_in_g2"] = sorted(list(edges2 - edges1))

        # Edge attribute differences for common edges
        for e in sorted(edges1 & edges2):
            u, v = e
            # networkx stores data keyed by (u,v) or (v,u) equivalently for nx.Graph objects
            data1 = self._graph.get_edge_data(u, v, default={})
            data2 = other._graph.get_edge_data(u, v, default={})
            keys = set(data1.keys()) | set(data2.keys())
            edge_mismatch = []
            for k in keys:
                v1 = data1.get(k, None)
                v2 = data2.get(k, None)
                if not _values_equal(v1, v2):
                    edge_mismatch.append((k, v1, v2))
            if edge_mismatch:
                _diffs["edge_attr_diffs"][e] = edge_mismatch

        # attach a small summary counts
        _diffs["_summary"] = {
            "nodes_only_in_g1": len(_diffs["nodes_only_in_g1"]),
            "nodes_only_in_g2": len(_diffs["nodes_only_in_g2"]),
            "nodes_attr_mismatches": len(_diffs["node_attr_diffs"]),
            "edges_only_in_g1": len(_diffs["edges_only_in_g1"]),
            "edges_only_in_g2": len(_diffs["edges_only_in_g2"]),
            "edges_attr_mismatches": len(_diffs["edge_attr_diffs"]),
        }
        return _diffs

    def find_bridges(self) -> List[Tuple[NodeName, NodeName]]:
        return list(nx.bridges(self.graph))

    # replaces _graph_editing.distance_nodes but does not save to a csv file
    def shortest_distances_all_nodes(
        self, weight: str = "len", as_dataframe: bool = True
    ) -> dict | pd.DataFrame:
        """Calculate shortest distances between all nodes in the graph.
        Args:
            weight (str): The edge attribute to use as the weight for the shortest path calculation.
            data_type (str): The type of data to return, either 'dict' or 'dataframe'.
        Returns:
            dict or pd.DataFrame: The shortest path lengths between all nodes,
                either as a dictionary or a pandas DataFrame.
        Notes:
            - If the graph is empty, a ValueError is raised.
            - If data_type is 'dict', a dictionary with node pairs as keys and
               their shortest path lengths as values is returned.
            - If data_type is 'dataframe', a pandas DataFrame is returned with nodes as
               rows and their shortest path lengths as columns.
        Example:
            >>> G = EPANETNetworkGraph()
            >>> G.create_graph(model)
            >>> distances = G.shortest_distances_all_nodes(weight='len', data_type='dataframe')
            >>> print(distances)
        Raises:
            ValueError: If the graph is empty or if data_type is not 'dict' or 'dataframe'.

        Example output dataframe
                     n1       n347       n348       n349       n350  ...       n331
                     n328       n770       n774       n329
        n1       0.0000    68.0970   113.5693   164.1124   214.1166  ...  3614.8796
                3628.5462  3633.3429  3660.0800  3684.2814
        n2     475.1108   407.0138   361.5415   310.9984   260.9942  ...  3323.6760
                 3337.3426  3342.1393  3368.8764  3393.0778
        n3     498.8987   430.8017   385.3294        ...  ...  ...  ...  ...  ...  ...
        """
        shortest_path_length = dict(
            nx.all_pairs_dijkstra_path_length(self._graph, weight=weight)
        )
        if not as_dataframe:
            output = shortest_path_length
        else:
            output = pd.DataFrame.from_dict(shortest_path_length, orient="index")
        return output

    def _shortest_path_lengths_from_sensors(
        self, sensors: list, weight: str = "len"
    ) -> Dict[SensorName, Dict[NodeName, float]]:
        """Compute shortest-path lengths from each sensor to all other nodes using graph representation
        of the networks and the list of sensors. We assume that all sensors are present in the network.
        If not, a ValueError will be raised.

        Args:
            sensors (list): List of sensor nodes.
            weight (str): Edge attribute to use as weight (default 'len').

        Returns:
            Dict[SensorName, Dict[NodeName, float]]: A dictionary mapping each sensor to its shortest-path
            lengths to each connectd node.
        """
        missing_sensors: List[str] = [
            sensor for sensor in sensors if sensor not in self._graph.nodes
        ]
        if missing_sensors:
            missing_sensors_str = ", ".join(missing_sensors)
            raise ValueError(
                f"All sensors must be present in the network. These are missing: {missing_sensors_str}"
            )
        shortest_paths_per_sensor: Dict[SensorName, Dict[NodeName, float]] = (
            {}
        )  # mapping sensor : {node : length_to_sensor}
        for sensor in sensors:
            # Compute all shortest paths from this sensor
            lengths: Dict[NodeName, float] = nx.single_source_dijkstra_path_length(
                self._graph, source=sensor, weight=weight
            )  # mapping node : length_to_sensor
            shortest_paths_per_sensor[sensor] = lengths
        return shortest_paths_per_sensor

    def assign_pressure_zones(
        self, sensors: List[SensorName], weight: str = "len"
    ) -> Dict[NodeName, SensorInfo]:
        """Assigns each node to the closest sensor (pressure zone).

        For each node, determines which sensor has the shortest path distance and
        assigns the node to that sensor's "pressure zone". The pressure zone index
        corresponds to the position of the sensor in the provided sensors list.

        Args:
            sensors (List[SensorName]):
                List of sensor identifiers, defining the ordering of pressure zones.
            weight (str): Edge attribute to use as weight for distance calculations (default 'len').

        Returns:
            Dict[NodeName, SensorInfo]: A dictionary mapping each node to its sensor information.
        """
        # Convert the dictionary maping to DataFrame of shortest-path lengths between nodes (junctions) in which
        #        rows = sources, cols = targets.
        shortest_paths_sensors = pd.DataFrame(
            self._shortest_path_lengths_from_sensors(sensors, weight=weight)
        )
        # Find a sensor closeset to every node (represented as row index)
        shortest_sensor: pd.Series = shortest_paths_sensors[sensors].idxmin(axis=1)
        # Precompute a mapping {sensor_name → sensor index}
        sensor_to_idx: Dict[NodeName, int] = {
            sensor: ix for ix, sensor in enumerate(sensors)
        }
        # Replace <sensor_name> with <sensor_index>
        pressure_zone: pd.Series = shortest_sensor.map(sensor_to_idx)
        output_dict: Dict[NodeName, SensorInfo] = {
            node: SensorInfo(sensor=node_sensor, pressure_zone=zone)
            for node, node_sensor, zone in zip(
                shortest_paths_sensors.index, shortest_sensor, pressure_zone
            )
        }
        return output_dict

    def find_pressure_zones(self, inplace: bool = False) -> PressureZones:
        """Find edges that connect different pressure zones (bridges) and return bridges and the graph
        with those edges removed.

        Requires that the 'closest_sensor' attribute is already set for all nodes in the graph.

        Args:
            inplace (bool): If True, modify the graph in place. Otherwise, return a new graph.
        Return:
            PressureZones: A PressureZones object containing the modified graph and the bridges.
        Raises:
            ValueError: If no 'closest_sensor' attributes are found in `netwok_graph'.
        """
        # Work on a copy unless inplace=True
        # graph = self._graph if inplace else copy.deepcopy(self._graph)

        graph = self if inplace else copy.deepcopy(self)

        # Pull 'closest_sensor' attributes once for speed
        shortest_sensors: Dict[NodeName, Any] = nx.get_node_attributes(
            graph, "closest_sensor"
        )
        if not shortest_sensors:
            raise ValueError(
                "No nodes in the network graph contain the 'closest_sensor' attribute."
            )
        if len(shortest_sensors.keys()) < len(graph.nodes):
            raise ValueError(
                "Found nodes that are missing the 'closest_sensor' attribute."
            )
        # Collect bridges
        bridges: List[Tuple[SensorName, SensorName]] = [
            (shortest_sensors[u], shortest_sensors[v])
            for u, v in graph.edges()
            if shortest_sensors[u] != shortest_sensors[v]
        ]
        # Remove those edges in bulk for speed
        edges_to_remove = [
            (u, v)
            for u, v in graph.edges()
            if shortest_sensors[u] != shortest_sensors[v]
        ]
        graph.remove_edges_from(edges_to_remove)
        return PressureZones(zone_graph=graph, bridges=bridges)

    def get_sensor_positions(
        self, sensors: List[SensorName]
    ) -> Dict[SensorName, Position]:
        """Return dict sensor_name (SensorName) -> Position(x,y).
        Args:
            self._graph (nx.Graph): The network graph.
            sensors (List[SensorName]): List of sensor names (SensorName).
        Returns:
            Dict[SensorName, Position]: A mapping of sensor names to their positions.
        Raises:
            ValueError: If any sensor is missing.
        """
        node_locations: Dict[SensorName, Tuple[float, float]] = nx.get_node_attributes(
            self._graph, "pos"
        )
        missing = [s for s in sensors if s not in node_locations]
        if missing:
            raise ValueError(
                f"Missing sensor positions in graph: {', '.join(map(str, missing))}"
            )
        return {s: Position(*node_locations[s]) for s in sensors}

    def set_node_attribute(
        self,
        attributes: Dict[NodeName, Any],
        attribute_name: str,
        inplace: bool = False,
    ) -> nx.Graph:
        """Add a specified attribute to each node in the graph based on the provided attributes dictionary.
        Args:
            attributes (Dict[NodeName, Any]): A mapping of node names to their corresponding attribute values.
            attribute_name (str): The name of the attribute to be added to each node.
            inplace (bool): If True, modify the graph in place. Otherwise, return a new graph.
        Returns:
            nx.Graph: The modified graph with the specified attributes added.
        """
        if inplace:
            graph = self
        else:
            graph = self.copy()
        nx.set_node_attributes(G=self._graph, values=attributes, name=attribute_name)
        return graph

    def set_closest_sensor_attribute(
        self, sensor_info_map: Dict[NodeName, SensorInfo], inplace: bool = False
    ) -> nx.Graph:
        """Add 'closest_sensor' attribute to each node in the graph based on the sensor_info_map.
        Args:
            sensor_info_map (Dict[NodeName, SensorInfo]): A mapping of node names to their sensor information.
            inplace (bool): If True, modify the graph in place. Otherwise, return a new graph.
        Returns:
            nx.Graph: The modified graph with 'closest_sensor' attributes added.
        """
        attributes = {
            node: sensor_info.sensor for node, sensor_info in sensor_info_map.items()
        }
        return self.set_node_attribute(attributes, "closest_sensor", inplace=inplace)


if __name__ == "__main__":
    pass
