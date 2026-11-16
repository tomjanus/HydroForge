""" """

from rich import print as rprint
from hydroforge.wdn_modelling.graphs.graph import EPANETNetworkGraph
from hydroforge.wdn_modelling.graphs.visualization import EPANETGraphPlotter
from hydroforge.wdn_modelling.epanetfile_io import EPANETNetworkModelIO
from hydroforge.auxiliary.utils import get_package_root


def main():
    model_path = get_package_root() / "tests/base_networks/L-Town.inp"
    model = EPANETNetworkModelIO.from_inp_file(model_path)
    rprint("🔧 Testing graph creation on L-Town network...")
    rprint("\n📦 `EPANETNetworkGraph.from_model`:")
    G1 = EPANETNetworkGraph.from_model(model)
    rprint(f"   Nodes: {len(G1.nodes())}")
    rprint(f"   Edges: {len(G1.edges())}")
    # Test new method with safety checks
    rprint("\n🔒 `EPANETNetworkGraph.from_model` with extra_safety=True):")
    G2 = EPANETNetworkGraph.from_model(model, extra_safety=True)
    rprint(f"   Nodes: {len(G2.nodes())}")
    rprint(f"   Edges: {len(G2.edges())}")
    # Optionally draw the graph (comment out if running in headless environment)
    EPANETGraphPlotter(G2).plot("L-Town Network", show_labels=False)
    rprint(G2)
    distance_df_G2 = G2.shortest_distances_all_nodes(as_dataframe=True)
    rprint("\n🔒 `shortest_distances_all_nodes` -- formerly `distance_nodes`:")
    rprint(distance_df_G2)
    rprint("\n🔒 Total length of the network:", G2.find_total_length())
    rprint("\n🔒 `Checking bridge-finding functionality:")
    bridges = G2.find_bridges()
    # Get pipe names for those bridges
    bridge_names = set()
    for u, v in bridges:
        edge_data = G2.get_edge_data(u, v)
        if isinstance(edge_data, dict) and "key" in edge_data:
            bridge_names.add(edge_data["key"])
    rprint("Bridge names", bridge_names)


if __name__ == "__main__":
    main()
