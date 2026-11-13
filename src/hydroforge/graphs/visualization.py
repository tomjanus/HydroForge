"""Visualization utilities for EPANET water distribution networks using NetworkX and Matplotlib."""

from ..graphs.graph import EPANETNetworkGraph
from typing import Optional, Any
import pathlib
from dataclasses import dataclass
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import networkx as nx
from rich import print as rprint

matplotlib.use("TkAgg")


@dataclass
class EPANETGraphPlotter:
    """
    A class for visualizing EPANET water distribution networks as graphs using NetworkX and Matplotlib.
    This class takes an 'EPANETNetworkGraph' object from found.graphs.graph, which is a NetworkX graph
    representation of an EPANET water network, and provides methods to plot the network with different node
    and edge styles, display labels, legends, and network statistics. It allows for
    customization of the plot, including showing or hiding labels and legends, and differentiating
    node and edge types by color, size, and shape.
    """

    graph: "EPANETNetworkGraph"

    # Style definitions as class constants
    NODE_TYPE_STYLES = {
        "JUNCTION": {
            "color": "#8fd3f4",
            "size": 150,
            "shape": "o",
            "label": "Junctions",
            "linewidths": 0.6,
            "edgecolors": "#2b2b2b",
            "alpha": 0.9,
        },
        "RESERVOIR": {
            "color": "#1f77b4",
            "size": 250,
            "shape": "s",
            "label": "Reservoirs",
            "linewidths": 0.8,
            "edgecolors": "k",
            "alpha": 1.0,
        },
        "TANK": {
            "color": "#ff7f0e",
            "size": 200,
            "shape": "^",
            "label": "Tanks",
            "linewidths": 0.8,
            "edgecolors": "k",
            "alpha": 1.0,
        },
    }

    EDGE_TYPE_STYLES = {
        "PIPE": {"color": "#888888", "width": 1.5, "alpha": 0.6, "label": "Pipes"},
        "PUMP": {"color": "#d62728", "width": 2.0, "alpha": 0.7, "label": "Pumps"},
        "VALVE": {"color": "#9467bd", "width": 2.0, "alpha": 0.7, "label": "Valves"},
    }

    def _get_node_positions(self) -> dict:
        """Extract node positions from graph, supporting multiple conventions.

        Returns:
            dict: Mapping of node IDs to (x, y) coordinate tuples
        """
        node_data = dict(self.graph.nodes(data=True))
        # Try 'pos' attribute first
        if all(
            isinstance(node_data[n].get("pos", None), (tuple, list))
            for n in self.graph.nodes()
        ):
            return {n: tuple(node_data[n]["pos"]) for n in self.graph.nodes()}
        # Try 'x' and 'y' attributes
        if all(
            ("x" in node_data[n] and "y" in node_data[n]) for n in self.graph.nodes()
        ):
            return {
                n: (node_data[n]["x"], node_data[n]["y"]) for n in self.graph.nodes()
            }
        # Fall back to spring layout
        return nx.spring_layout(self.graph, k=0.5, iterations=100, seed=42)

    def _apply_plot_formatting(
        self, ax, title: str, x_vals: list, y_vals: list
    ) -> None:
        """Apply common formatting to plot axes.

        Args:
            ax: Matplotlib axes object
            title: Plot title
            x_vals: List of x coordinates for margin calculation
            y_vals: List of y coordinates for margin calculation
        """
        ax.set_title(title, fontsize=18, fontweight="bold")
        ax.set_axis_off()
        ax.set_aspect("equal", adjustable="box")

        # Adjust view limits with margin
        if x_vals and y_vals:
            xmargin = (
                (max(x_vals) - min(x_vals)) * 0.06
                if max(x_vals) != min(x_vals)
                else 1.0
            )
            ymargin = (
                (max(y_vals) - min(y_vals)) * 0.06
                if max(y_vals) != min(y_vals)
                else 1.0
            )
            ax.set_xlim(min(x_vals) - xmargin, max(x_vals) + xmargin)
            ax.set_ylim(min(y_vals) - ymargin, max(y_vals) + ymargin)

    def plot(
        self,
        title: Optional[str] = None,
        sensors: Optional[list] = None,
        show_labels: bool = True,
        show_legend: bool = True,
        show_edge_labels: bool = False,
        pipe_color_property: Optional[str] = None,
        save_path: Optional[pathlib.Path] = None,
        **kwargs,
    ) -> None:
        """Visualize the water distribution network graph with comprehensive styling options.

        This unified method combines visualization of the network structure with optional
        sensor highlighting, pipe coloring by properties, and flexible output options.

        Args:
            title (Optional[str]): Plot title. Defaults to 'Water Distribution Network'.
            sensors (Optional[list]): List of sensor node IDs to highlight with star markers.
                If None, no sensors are highlighted.
            show_labels (bool): Whether to show node labels. Auto-disabled for networks > 150 nodes.
            show_legend (bool): Whether to show legend for node/edge types and sensors.
            show_edge_labels (bool): Whether to show edge length labels. Auto-enabled only
                for small networks (<= 60 visible edges) when True.
            pipe_color_property (Optional[str]): Edge attribute for pipe coloring.
                Common options: 'len' (length), 'diameter', 'Wei' (length/diameter weight).
                If None or all values identical, pipes drawn in uniform gray.
            save_path (Optional[pathlib.Path]): Path to save plot image (300 DPI PNG). If None, displays plot.
        """
        pos = self._get_node_positions()
        # Prepare sensors list
        try:
            sensor_nodes = list(sensors or [])
        except (AttributeError, TypeError):
            sensor_nodes = []
        sensors = [n for n in sensor_nodes if n in self.graph.nodes()]
        # Create the plot
        fig, ax = plt.subplots(figsize=kwargs.get("figsize", (14, 9)))
        # Group nodes by type (accounting for sensors)
        nodes_by_type: dict[str, list] = {}
        for _node, _node_attrs in self.graph.nodes(data=True):
            # Skip sensors - they'll be drawn separately as overlays
            if _node in sensors:
                continue
            _node_type = _node_attrs.get("node_type", "JUNCTION")
            nodes_by_type.setdefault(_node_type, []).append(_node)

        # Filter out artificial zero-length edges
        visible_edges_set = {
            (u, v) for u, v, d in self.graph.edges(data=True) if d.get("len", 0) > 0
        }
        # Classify edges by type and collect pipe property values
        pipe_edges = []
        pipe_property_values = []
        non_pipe_edges = []

        for u_node, v_node, edge_attrs in self.graph.edges(data=True):
            if (u_node, v_node) not in visible_edges_set and (
                v_node,
                u_node,
            ) not in visible_edges_set:
                continue
            edge_type = edge_attrs.get("link_type", "PIPE")
            if edge_type == "PIPE":
                pipe_edges.append((u_node, v_node))
                pipe_property_values.append(
                    edge_attrs.get(pipe_color_property) if pipe_color_property else None
                )
            else:
                non_pipe_edges.append((u_node, v_node, edge_type))

        # Determine if we should use color mapping for pipes
        valid_values = [v for v in pipe_property_values if v is not None]
        use_pipe_coloring = (
            pipe_color_property and len(valid_values) > 0 and len(set(valid_values)) > 1
        )

        # Draw pipe edges with optional color mapping
        if use_pipe_coloring:
            # Separate edges with and without property values
            edges_with_values = [
                (pipe_edges[i], v)
                for i, v in enumerate(pipe_property_values)
                if v is not None
            ]
            edges_without_values = [
                pipe_edges[i] for i, v in enumerate(pipe_property_values) if v is None
            ]

            if edges_with_values:
                edges, values = zip(*edges_with_values)
                min_val, max_val = min(values), max(values)
                normalized_values = [
                    (v - min_val) / (max_val - min_val) if max_val > min_val else 0.5
                    for v in values
                ]

                edges_drawn = nx.draw_networkx_edges(
                    self.graph,
                    pos,
                    edgelist=list(edges),
                    edge_color=normalized_values,
                    edge_cmap=plt.get_cmap("viridis"),
                    width=kwargs.get("width", 1.5),
                    alpha=kwargs.get("alpha", 0.7),
                    ax=ax,
                )

                # Add colorbar
                if edges_drawn is not None:
                    cbar = plt.colorbar(
                        edges_drawn,
                        ax=ax,
                        label=f"Pipe {pipe_color_property}",
                        shrink=0.8,
                        pad=0.02,
                    )
                    ticks = [0, 0.25, 0.5, 0.75, 1.0]
                    cbar.set_ticks(ticks)
                    cbar.set_ticklabels(
                        [f"{min_val + t * (max_val - min_val):.2g}" for t in ticks]
                    )

            # Draw pipes without property values
            if edges_without_values:
                nx.draw_networkx_edges(
                    self.graph,
                    pos,
                    edgelist=edges_without_values,
                    edge_color="#888888",
                    alpha=kwargs.get("alpha", 0.7),
                    width=kwargs.get("width", 1.5),
                    ax=ax,
                )
        elif pipe_edges:
            # Draw all pipes in uniform color
            nx.draw_networkx_edges(
                self.graph,
                pos,
                edgelist=pipe_edges,
                edge_color="#888888",
                alpha=kwargs.get("alpha", 0.7),
                width=kwargs.get("width", 1.5),
                ax=ax,
            )

        # Draw edge labels if requested (only for small graphs)
        if show_edge_labels and len(list(visible_edges_set)) <= 60:
            edge_labels = {
                (u, v): int(d.get("len", 0))
                for u, v, d in self.graph.edges(data=True)
                if d.get("len", 0) > 0
            }
            if edge_labels:
                nx.draw_networkx_edge_labels(
                    self.graph, pos, edge_labels, font_size=8, ax=ax
                )

        # Draw non-pipe edges (pumps, valves) batched by type
        edges_by_type: dict[str, list] = {}
        for u_node, v_node, edge_type in non_pipe_edges:
            if edge_type in self.EDGE_TYPE_STYLES:
                edges_by_type.setdefault(edge_type, []).append((u_node, v_node))

        for edge_type, edge_list in edges_by_type.items():
            style: dict[str, Any] = self.EDGE_TYPE_STYLES[edge_type]  # type: ignore[assignment, no-redef]
            nx.draw_networkx_edges(
                self.graph,
                pos,
                edgelist=edge_list,
                edge_color=style["color"],
                width=style["width"],
                alpha=style["alpha"],
                ax=ax,
            )

        # Draw nodes by type
        legend_elements: list[Any] = []
        for _node_type, nodes in nodes_by_type.items():
            if _node_type not in self.NODE_TYPE_STYLES:
                continue

            style: dict[str, Any] = self.NODE_TYPE_STYLES[_node_type]  # type: ignore[assignment, no-redef]
            nodes_with_pos = [node for node in nodes if node in pos]

            if nodes_with_pos:
                nx.draw_networkx_nodes(
                    self.graph,
                    pos,
                    nodelist=nodes_with_pos,
                    node_color=style["color"],
                    node_size=style["size"],
                    node_shape=style["shape"],
                    linewidths=style["linewidths"],
                    edgecolors=style["edgecolors"],
                    alpha=style["alpha"],
                    ax=ax,
                )
                legend_elements.append(
                    Patch(
                        facecolor=style["color"],
                        edgecolor=style["edgecolors"],
                        label=style["label"],
                    )
                )

        # Overlay sensor markers (drawn on top with high zorder)
        if sensors:
            xs = [pos[n][0] for n in sensors if n in pos]
            ys = [pos[n][1] for n in sensors if n in pos]
            if xs and ys:
                ax.scatter(
                    xs,
                    ys,
                    s=250,
                    c="#e45756",
                    marker="*",
                    edgecolors="black",
                    linewidths=0.8,
                    zorder=5,
                )
                legend_elements.append(
                    Line2D(
                        [0],
                        [0],
                        marker="*",
                        color="w",
                        label="Sensors",
                        markerfacecolor="#e45756",
                        markeredgecolor="k",
                        markersize=12,
                    )
                )

        # Add edge types to legend
        for edge_type in ["PUMP", "VALVE"]:
            if edge_type in edges_by_type:
                style: dict[str, Any] = self.EDGE_TYPE_STYLES[edge_type]  # type: ignore[assignment, no-redef]
                legend_elements.append(
                    Line2D(
                        [0],
                        [0],
                        color=style["color"],
                        linewidth=style["width"],
                        label=style["label"],
                    )
                )

        # Draw node labels if requested
        if show_labels and self.graph.number_of_nodes() <= 150:
            nx.draw_networkx_labels(
                self.graph, pos, font_size=9, font_weight="medium", ax=ax
            )

        # Add legend
        if show_legend and legend_elements:
            ax.legend(handles=legend_elements, loc="upper right", fontsize=11)

        # Apply formatting
        plot_title = title or "Water Distribution Network"
        x_vals = [p[0] for p in pos.values()]
        y_vals = [p[1] for p in pos.values()]
        self._apply_plot_formatting(ax, plot_title, x_vals, y_vals)

        plt.tight_layout()

        # Save or display
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            rprint(f"Graph saved to: {save_path}")
            plt.close(fig)
        else:
            plt.show()


if __name__ == "__main__":
    pass
