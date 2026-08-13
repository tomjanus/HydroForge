""" """
from collections import namedtuple
from rich import print as rprint
from rich.table import Table
from rich.console import Console
import networkx as nx
from hydroforge.sensors import SensorNetworkGraph

if __name__ == "__main__":
    """ """
    Position = namedtuple("Position", ["x", "y"])
    
    console = Console()
    
    rprint("[bold blue]=== Sensor Network Graph Demonstration ===[/bold blue]")
    
    # 1. Create sensor locations
    rprint("\n[bold green]1. Creating Sensor Network[/bold green]")
    
    sensor_locations = {
        "S1": Position(x=0.0, y=0.0),
        "S2": Position(x=10.0, y=0.0),
        "S3": Position(x=20.0, y=0.0),
        "S4": Position(x=0.0, y=10.0),
        "S5": Position(x=10.0, y=10.0),
        "S6": Position(x=20.0, y=10.0),
    }
    
    rprint(f"Created {len(sensor_locations)} sensors:")
    for sensor, pos in sensor_locations.items():
        rprint(f"  • {sensor}: ({pos.x:.1f}, {pos.y:.1f})")
    
    # 2. Define zone sizes (pipe lengths monitored by each sensor)
    rprint("\n[bold green]2. Defining Sensor Zone Sizes[/bold green]")
    
    zone_sizes = {
        "S1": 150.0,  # meters of pipe
        "S2": 200.0,
        "S3": 180.0,
        "S4": 220.0,
        "S5": 190.0,
        "S6": 160.0,
    }
    
    rprint("Zone sizes (pipe length monitored by each sensor):")
    for sensor, size in zone_sizes.items():
        rprint(f"  • {sensor}: {size:.1f} m")
    
    # 3. Define pressure zone bridges (connections between zones)
    rprint("\n[bold green]3. Defining Pressure Zone Bridges[/bold green]")
    
    # Create a mock PressureZones object
    class MockPressureZones:
        def __init__(self, bridges):
            self.bridges = bridges
    
    bridges_test = [
        ("S1", "S2"),
        ("S2", "S3"),
        ("S1", "S4"),
        ("S2", "S5"),
        ("S3", "S6"),
        ("S4", "S5"),
        ("S5", "S6"),
    ]
    
    pressure_zones = MockPressureZones(bridges_test)
    
    rprint("Bridges between pressure zones:")
    for bridge in bridges_test:
        rprint(f"  • {bridge[0]} ↔ {bridge[1]}")
    
    # 4. Create SensorNetworkGraph from zones
    rprint("\n[bold green]4. Building Sensor Network Graph[/bold green]")
    
    sensor_graph = SensorNetworkGraph.from_sensor_zones(
        sensor_locations=sensor_locations,
        zone_sizes=zone_sizes,
        pressure_zones=pressure_zones
    )
    
    rprint(f"{sensor_graph}")
    rprint(f"  • Number of sensors: {len(sensor_graph)}")
    rprint(f"  • Number of connections: {sensor_graph.number_of_edges()}")
    
    # 5. Demonstrate graph operations
    rprint("\n[bold green]5. Graph Operations[/bold green]")
    
    # Check if sensor exists
    rprint(f"  • 'S1' in graph: {('S1' in sensor_graph)}")
    rprint(f"  • 'S99' in graph: {('S99' in sensor_graph)}")
    
    # Iterate over sensors
    rprint("  • Iterating over sensors:")
    for sensor in sensor_graph:
        neighbors = list(sensor_graph.neighbors(sensor))
        rprint(f"    - {sensor}: neighbors = {neighbors}")
    
    # 6. Compute sensor-level matrix
    rprint("\n[bold green]6. Computing Sensor-Level Path Matrix[/bold green]")
    rprint("(Sum of node weights along shortest paths)\n")
    
    try:
        sensor_costs = sensor_graph.sensor_path_costs()
        sensor_matrix = sensor_costs.matrix
        sensors = sensor_costs.sensors
        
        # Display as a Rich table
        table = Table(title="Sensor-Level Path Weights (meters)")
        
        # Add columns
        table.add_column("From/To", style="cyan", justify="right")
        for sensor in sensor_costs.sensors:
            table.add_column(sensor, justify="right", style="green")
        
        # Add rows
        row_values = []
        for source_ix, source in enumerate(sensors):
            row_values.append(f"{source}")
            for target_ix, target in enumerate(sensors):
                value = sensor_matrix[source_ix, target_ix]
                if source == target:
                    row_values.append(f"[bold]{value:.1f}[/bold]")
                else:
                    row_values.append(f"{value:.1f}")
            table.add_row(*row_values)
            row_values = []
        
        console.print(table)
        
        # Explain the results
        rprint("\n[bold cyan]Interpretation:[/bold cyan]")
        rprint("• Diagonal values: zone size of each sensor")
        rprint("• Off-diagonal values: sum of zone sizes along shortest path")
        rprint("• Example: S1→S3 = S1_size + S2_size + S3_size (path through S2)")
        
    except ValueError as e:
        rprint(f"[red]Error: {e}[/red]")
    
    # 7. Demonstrate from_graph method
    rprint("\n[bold green]7. Creating from Existing NetworkX Graph[/bold green]")
    
    # Create a simple graph manually
    manual_graph = nx.Graph()
    manual_graph.add_nodes_from([
        ("A", {"pos": (0, 0), "weight": 100}),
        ("B", {"pos": (5, 0), "weight": 150}),
        ("C", {"pos": (10, 0), "weight": 120}),
    ])
    manual_graph.add_edges_from([("A", "B"), ("B", "C")])
    
    manual_sensor_graph = SensorNetworkGraph.from_sensor_graph(manual_graph)
    rprint(f"{manual_sensor_graph}")
    
    # 8. Access underlying NetworkX graph
    rprint("\n[bold green]8. Accessing NetworkX Graph Properties - SensorNetworkGraph behaves like nx.Graph [/bold green]")
    
    rprint(f"  • Graph type: {type(sensor_graph)}")
    rprint(f"  • Is connected: {nx.is_connected(sensor_graph)}")
    rprint(f"  • Average degree: {sum(dict(sensor_graph.degree()).values()) / len(sensor_graph):.2f}")
    
    # Get node attributes
    weights = nx.get_node_attributes(sensor_graph, 'weight')
    positions = nx.get_node_attributes(sensor_graph, 'pos')
    
    rprint("\n  • Node attributes:")
    for node in list(sensor_graph.nodes())[:3]:  # Show first 3
        rprint(f"    - {node}: weight={weights.get(node, 0):.1f}, pos={positions.get(node, 'N/A')}")
    
    # 9. Demonstrate attribute delegation
    rprint("\n[bold green]9. Attribute Delegation to NetworkX[/bold green]")
    rprint("(SensorNetworkGraph delegates calls to underlying nx.Graph)")
    
    rprint(f"  • sensor_graph.degree('S1'): {sensor_graph.degree('S1')}")
    rprint(f"  • sensor_graph.neighbors('S2'): {list(sensor_graph.neighbors('S2'))}")
    rprint(f"  • sensor_graph.has_edge('S1', 'S2'): {sensor_graph.has_edge('S1', 'S2')}")
    rprint(f"  • sensor_graph.has_edge('S1', 'S6'): {sensor_graph.has_edge('S1', 'S6')}")
    
    # 10. Shortest paths
    rprint("\n[bold green]10. Computing Shortest Paths[/bold green]")
    
    path_S1_S6 = sensor_graph.shortest_path("S1", "S6")
    rprint(f"  • Shortest path S1 → S6: {' → '.join(path_S1_S6)}")
    
    path_S3_S4 = sensor_graph.shortest_path("S3", "S4")
    rprint(f"  • Shortest path S3 → S4: {' → '.join(path_S3_S4)}")
    
    rprint("\n[bold cyan]✓ All sensor network demonstrations completed successfully![/bold cyan]")
