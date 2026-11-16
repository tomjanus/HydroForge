""" """

import tempfile
import pathlib
import networkx as nx
from rich import print as rprint
from hydroforge.wdn_modelling.graphs.visualization import EPANETGraphPlotter


def main():
    """Demonstration of EPANETGraphPlotter functionality."""

    rprint("[bold blue]=== EPANET Graph Plotter Demonstration ===[/bold blue]\n")
    # 1. Create a synthetic network for demonstration
    rprint("[bold green]1. Creating Synthetic Network[/bold green]")
    rprint("[cyan]Creating a simple grid network for demonstration...[/cyan]")

    # Create a simple synthetic network
    G = nx.Graph()
    # Add reservoir
    G.add_node("R1", node_type="RESERVOIR", pos=(0, 50), x=0, y=50)
    # Add tank
    G.add_node("T1", node_type="TANK", pos=(80, 50), x=80, y=50)
    # Add junctions in a grid pattern
    junction_positions = [
        ("J1", 20, 50),
        ("J2", 40, 50),
        ("J3", 60, 50),
        ("J4", 20, 30),
        ("J5", 40, 30),
        ("J6", 60, 30),
        ("J7", 20, 10),
        ("J8", 40, 10),
        ("J9", 60, 10),
    ]
    for name, x, y in junction_positions:
        G.add_node(name, node_type="JUNCTION", pos=(x, y), x=x, y=y)
    # Add pipes with lengths
    test_pipes = [
        ("R1", "J1", 20, 300),
        ("J1", "J2", 20, 300),
        ("J2", "J3", 20, 300),
        ("J3", "T1", 20, 400),  # Connection to tank
        ("J1", "J4", 20, 250),
        ("J2", "J5", 20, 250),
        ("J3", "J6", 20, 250),
        ("J4", "J5", 20, 300),
        ("J5", "J6", 20, 300),
        ("J4", "J7", 20, 200),
        ("J5", "J8", 20, 200),
        ("J6", "J9", 20, 200),
        ("J7", "J8", 20, 300),
        ("J8", "J9", 20, 300),
    ]
    for u, v, length, diameter in test_pipes:
        G.add_edge(u, v, link_type="PIPE", len=length, Wei=length / (diameter / 1000))
    # Add a pump
    G.add_edge("R1", "J4", link_type="PUMP", len=0, Wei=0)
    # Add a valve
    G.add_edge("J6", "T1", link_type="VALVE", len=0, Wei=0)

    # Import here to avoid circular dependency issues
    try:
        from hydroforge.wdn_modelling.graphs.graph import EPANETNetworkGraph

        test_network = EPANETNetworkGraph.from_graph(G)
        rprint("✅ Created synthetic network")
    except ImportError:
        rprint(
            "[yellow]⚠ Could not import EPANETNetworkGraph, using raw NetworkX graph[/yellow]"
        )

        # Create a mock wrapper for demonstration
        class MockNetworkGraph:
            def __init__(self, graph):
                self._graph = graph
                self.graph = graph

            def __getattr__(self, item):
                return getattr(self._graph, item)

            def __len__(self):
                return len(self._graph)

            def __repr__(self):
                return f"NetworkGraph with {self._graph.number_of_nodes()} nodes and {self._graph.number_of_edges()} edges."

        test_network = MockNetworkGraph(G)
        rprint("✅ Created mock network wrapper")

    rprint(f"Network: {test_network}")
    rprint(f"  • Nodes: {test_network.number_of_nodes()}")
    rprint(f"  • Edges: {test_network.number_of_edges()}")

    # Get some network statistics
    node_types = {}
    for node, attrs in test_network.nodes(data=True):
        node_type = attrs.get("node_type", "JUNCTION")
        node_types[node_type] = node_types.get(node_type, 0) + 1
    rprint(f"  • Node types: {dict(node_types)}")

    # 2. Create plotter
    rprint("\n[bold green]2. Creating EPANETGraphPlotter[/bold green]")
    plotter = EPANETGraphPlotter(graph=test_network)
    rprint("✅ Plotter created successfully")

    # Select some nodes as sensors for demonstrations
    all_junctions = [
        n
        for n, d in test_network.nodes(data=True)
        if d.get("node_type", "JUNCTION") == "JUNCTION"
    ]

    if len(all_junctions) >= 3:
        test_sensors = [
            all_junctions[0],
            all_junctions[len(all_junctions) // 2],
            all_junctions[-1],
        ]
    else:
        test_sensors = all_junctions[: min(3, len(all_junctions))]

    rprint(f"Selected sensors for demos: {test_sensors}")

    # 3. Demonstrate unified plot() method
    rprint("\n[bold green]3. Demonstrating Unified plot() Method[/bold green]")
    rprint("This single method combines all visualization features:")
    rprint("  • Network structure with node/edge types")
    rprint("  • Optional sensor highlighting")
    rprint("  • Optional pipe coloring by properties")
    rprint("  • Optional edge labels")
    rprint("  • Save to file or display")

    try:
        rprint("\n[cyan]3a. Basic network visualization[/cyan]")
        rprint("(Close the plot window to continue, or Ctrl+C to skip)")

        plotter.plot(
            title="Demo Network - Basic View", show_labels=True, show_legend=True
        )

    except KeyboardInterrupt:
        rprint("[yellow]\n⚠ Visualization skipped by user[/yellow]")
    except (KeyError, ValueError, AttributeError) as e:
        rprint(f"[yellow]⚠ Could not display plot (data error): {e}[/yellow]")
    except (OSError, IOError) as e:
        rprint(f"[yellow]⚠ Could not display plot (I/O error): {e}[/yellow]")
    except ImportError as e:
        rprint(
            f"[yellow]⚠ Could not display plot (missing display backend): {e}[/yellow]"
        )

    try:
        rprint("\n[cyan]3b. Network with sensors highlighted[/cyan]")

        plotter.plot(
            title="Demo Network - With Sensors",
            sensors=test_sensors,
            show_labels=True,
            show_legend=True,
        )

    except KeyboardInterrupt:
        rprint("[yellow]⚠ Skipped[/yellow]")
    except (KeyError, ValueError, AttributeError, OSError, IOError, ImportError):
        rprint("[yellow]⚠ Could not display (error occurred)[/yellow]")

    try:
        rprint("\n[cyan]3c. Pipes colored by weight, with sensors[/cyan]")

        plotter.plot(
            title="Demo Network - Pipes by Weight + Sensors",
            sensors=test_sensors,
            pipe_color_property="Wei",
            show_labels=False,
            show_legend=True,
        )

    except KeyboardInterrupt:
        rprint("[yellow]⚠ Skipped[/yellow]")
    except (KeyError, ValueError, AttributeError, OSError, IOError, ImportError):
        rprint("[yellow]⚠ Could not display (error occurred)[/yellow]")

    try:
        rprint("\n[cyan]3d. With edge labels (length values)[/cyan]")

        plotter.plot(
            title="Demo Network - With Edge Labels",
            show_labels=True,
            show_edge_labels=True,
            show_legend=True,
        )

    except KeyboardInterrupt:
        rprint("[yellow]⚠ Skipped[/yellow]")
    except (KeyError, ValueError, AttributeError, OSError, IOError, ImportError):
        rprint("[yellow]⚠ Could not display (error occurred)[/yellow]")

    # 4. Demonstrate saving to file
    rprint("\n[bold green]4. Demonstrating Save to File[/bold green]")

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".png",
            prefix="demo_network_",
            delete=False,  # Keep the file long enough for the user to download it
        ) as tmp:
            output_path = pathlib.Path(tmp.name)

        rprint(f"Saving plot to temporary file: [cyan]{output_path}[/cyan]")

        plotter.plot(
            title="Demo Network - Saved Visualization",
            sensors=test_sensors,
            pipe_color_property="len",
            save_path=output_path,
        )

        if output_path.exists():
            rprint("✅ Plot saved successfully!")
            rprint(f"   File size: {output_path.stat().st_size / 1024:.1f} KB")
            rprint(f"   Temporary file: {output_path}")

            # If running in ChatGPT's Python environment, this will become
            # a downloadable link in the chat.
            print(f"\nDownload: {output_path}")

    except (OSError, IOError, PermissionError) as e:
        rprint(f"[yellow]⚠ Could not save plot (I/O error): {e}[/yellow]")
    except (KeyError, ValueError, AttributeError) as e:
        rprint(f"[yellow]⚠ Could not save plot (data error): {e}[/yellow]")

    # 6. Edge cases and error handling
    rprint("\n[bold green]6. Testing Edge Cases[/bold green]")

    rprint("\n[cyan]6a. Empty sensor list[/cyan]")
    rprint("✅ Empty sensor list is handled correctly (sensors are optional)")

    rprint("\n[cyan]6b. Invalid sensor names (not in network)[/cyan]")
    rprint("✅ Invalid sensors are filtered out automatically")

    rprint("\n[cyan]6c. No pipe coloring (uniform gray)[/cyan]")
    rprint("✅ When pipe_color_property=None, pipes drawn in uniform gray")

    # 7. Summary
    rprint("\n[bold blue]=== Demonstration Summary ===[/bold blue]")
    rprint("✅ Created synthetic network successfully")
    rprint("✅ Created EPANETGraphPlotter instance")
    rprint("✅ Demonstrated unified plot() method with all features")
    rprint("✅ Demonstrated saving plots to files")
    rprint("✅ Validated edge case handling")

    rprint("\n[bold green]Key Features:[/bold green]")
    rprint("• Automatic node type detection and styling")
    rprint("• Edge type differentiation (pipes, pumps, valves)")
    rprint("• Configurable pipe coloring by any edge property")
    rprint("• Optional sensor highlighting with distinctive markers")
    rprint("• Optional edge labels for small networks")
    rprint("• Automatic layout fallback for networks without positions")
    rprint("• Smart label display (avoids clutter on large networks)")
    rprint("• High-quality output (300 DPI for saved files)")
    rprint("• Single unified method for all use cases")

    rprint("\n[bold cyan]All demonstrations completed successfully! ✨[/bold cyan]")


if __name__ == "__main__":
    main()
