""" """

import pathlib
from rich import print as rprint
from hydroforge.sensors.placement import (
    GreedySensorPlacement,
    SensorPlacer,
    FixedLocationSensorPlacement,
    KCentreSensorPlacement,
    CentralityBasedSensorPlacement,
    CoverageBasedSensorPlacement,
    DominatingSetBasedSensorPlacement,
    RandomSensorPlacement,
)
from hydroforge.graphs.graph import EPANETNetworkGraph
from hydroforge.epanetfile_io import EPANETNetworkModelIO
from hydroforge.auxiliary.utils import get_package_root, timer


def main():
    """ """
    # Example usage and comparison of different sensor placement strategies
    network_path = get_package_root() / pathlib.Path("tests/base_networks/L-Town.inp")
    sensors_path = pathlib.Path("sensors.txt")

    # Load the network once for fair comparison
    network_model: OrderedDict = EPANETNetworkModelIO.from_inp_file(network_path)
    base_network_graph: EPANETNetworkGraph = EPANETNetworkGraph.from_model(
        network_model
    )

    # Test 2: SensorPlacer with strategy pattern (class-based strategies)
    # Use GreedyPlacement strategy (class)
    greedy_strategy = GreedySensorPlacement(
        graph=base_network_graph.copy(), num_sensors=50, sources=["R1", "R2"]
    )

    sensor_placer = SensorPlacer(strategy=greedy_strategy)
    sensor_placer.place_sensors()
    rprint(f"Sensors - object (greedy): {sensor_placer.sensors}")

    # Fix the method - does not show the sensors well
    sensor_placer.plot_sensors(
        graph=base_network_graph, title="Sensor Locations - Greedy Placement"
    )

    # Use FixedLocationPlacement strategy (class)
    fixed_locations = ["n27", "n120", "n212", "n317"]
    sensor_placer = SensorPlacer(
        strategy=FixedLocationSensorPlacement(fixed_locations, graph=base_network_graph)
    )
    sensor_placer.place_sensors()
    print(f"Sensors - object (fixed): {sensor_placer.sensors}")
    sensor_placer.plot_sensors(
        graph=base_network_graph, title="Sensor Locations - Fixed Sensor Placement"
    )

    kcentre_strategy = KCentreSensorPlacement(
        graph=base_network_graph, num_sensors=50, sources=["R1", "R2"]
    )
    sensor_placer = SensorPlacer(strategy=kcentre_strategy)
    sensor_placer.place_sensors()
    rprint(f"Sensors - object (k-centre): {sensor_placer.sensors}")
    sensor_placer.plot_sensors(
        graph=base_network_graph, title="Sensor Locations - K-Centre Placement"
    )

    # Centrality-Based Placement
    centrality_strategy = CentralityBasedSensorPlacement(
        graph=base_network_graph,
        num_sensors=50,
        sources=["R1", "R2"],
        centrality_type="degree",
    )
    sensor_placer = SensorPlacer(strategy=centrality_strategy)
    sensor_placer.place_sensors()
    rprint(f"Sensors - object (centrality): {sensor_placer.sensors}")
    sensor_placer.plot_sensors(
        graph=base_network_graph, title="Sensor Locations - Centrality Placement"
    )

    # Coverage-Based Placement
    coverage_strategy = CoverageBasedSensorPlacement(
        graph=base_network_graph,
        num_sensors=50,
        sources=["R1", "R2"],
        coverage_radius=100,
    )
    sensor_placer = SensorPlacer(strategy=coverage_strategy)
    sensor_placer.place_sensors()
    rprint(f"Sensors - object (coverage): {sensor_placer.sensors}")
    sensor_placer.plot_sensors(
        graph=base_network_graph, title="Sensor Locations - Coverage Placement"
    )

    # Dominating Set-Based Placement
    dominating_strategy = DominatingSetBasedSensorPlacement(
        graph=base_network_graph, num_sensors=50, sources=["R1", "R2"]
    )
    sensor_placer = SensorPlacer(strategy=dominating_strategy)
    sensor_placer.place_sensors()
    rprint(f"Sensors - object (dominating set): {sensor_placer.sensors}")
    sensor_placer.plot_sensors(
        graph=base_network_graph, title="Sensor Locations - Dominating Set Placement"
    )

    # Random Placement
    random_strategy = RandomSensorPlacement(
        graph=base_network_graph, num_sensors=50, sources=["R1", "R2"], seed=42
    )
    sensor_placer = SensorPlacer(strategy=random_strategy)
    sensor_placer.place_sensors()
    rprint(f"Sensors - object (random): {sensor_placer.sensors}")
    sensor_placer.plot_sensors(
        graph=base_network_graph, title="Sensor Locations - Random Placement"
    )


if __name__ == "__main__":
    """ """
    main()
