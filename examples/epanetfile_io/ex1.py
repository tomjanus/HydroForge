"""Usage examples for :mod:`hydroforge.epanetfile_io`.

Demonstrates the full read -> inspect -> modify -> save workflow supported
by :class:`~hydroforge.epanetfile_io.model_wrapper.EPANETNetworkModel` and
:class:`~hydroforge.epanetfile_io.model_io.EPANETNetworkModelIO`, without
depending on any external simulation package (e.g. WNTR).

Covers both supported file formats -- JSON and EPANET ``.inp`` -- as well as
the round-trip validation of each: reading a file and writing it back out
should reproduce an equivalent :class:`EPANETNetworkModel`.
"""

from rich import print as rprint
from hydroforge.auxiliary.utils import get_package_root
from hydroforge.epanetfile_io.model_wrapper import EPANETNetworkModel
from hydroforge.epanetfile_io.components import Pipe
from hydroforge.epanetfile_io.model_io import EPANETNetworkModelIO


def demo_json_workflow() -> EPANETNetworkModel:
    """Demonstrate reading, inspecting, and modifying a JSON network file.

    Returns
    -------
    EPANETNetworkModel
        The modified network, for reuse by later demos.
    """
    rprint("\n[bold blue]=== Modifying networks in WNTR's 'JSON format ===[/bold blue]")

    json_path = get_package_root() / "data/case_studies/L-Town/network_dict_short.json"
    water_network: EPANETNetworkModel = EPANETNetworkModelIO.from_json_file(json_path)

    rprint("\n🔍 Original junctions:")
    for i, junction in enumerate(water_network.junctions):
        rprint(
            f"  {i}: {junction.id} - elevation: {junction.elevation}, pattern: {junction.demand_pattern}"
        )

    # Example 1: Direct index access and modification
    rprint("\n📝 Example 1: Direct index access and modification")
    if len(water_network.junctions) > 1:
        junction = water_network.junctions[1]
        rprint(
            f"Before: Junction {junction.id} has pattern '{junction.demand_pattern}'"
        )
        junction.demand_pattern = "Commercial"
        rprint(
            f"After:  Junction {junction.id} has pattern '{junction.demand_pattern}'"
        )

    # Example 2: Modification by field value, using EPANETNetworkModel helper methods
    rprint("\n📝 Example 2: Modification by ID using EPANETNetworkModel helper methods")
    success = water_network.modify_item_by_field_value(
        "junctions", "id", "n157", demand_pattern="Industrial", elevation="75.0"
    )
    if success:
        modified_junction = water_network.get_item_by_field_value(
            "junctions", "id", "n157"
        )
        rprint(
            f"Successfully modified junction n157: pattern='{modified_junction.demand_pattern}', "
            f"elevation='{modified_junction.elevation}'"
        )
    else:
        rprint("Junction n157 not found")

    # Example 3: Modification by field value, using the NetworkCollection API directly
    rprint("\n📝 Example 3: Modification by ID using NetworkCollection.modify_by_field")
    water_network.junctions.modify_by_field("id", "n1", demand_pattern="Residential")
    modified = water_network.junctions.get_by_field("id", "n1")
    if modified:
        rprint(f"Junction n1 now has pattern '{modified.demand_pattern}'")

    # Example 4: Show modified junctions
    rprint("\n🔍 Modified junctions:")
    for i, junction in enumerate(water_network.junctions):
        rprint(
            f"  {i}: {junction.id} - elevation: {junction.elevation}, pattern: {junction.demand_pattern}"
        )

    # Example 5: Pipe modification and appending a brand new pipe
    rprint("\n📝 Example 5: Pipe modification and creation")
    if len(water_network.pipes) > 0:
        pipe = water_network.pipes[0]
        rprint(
            f"Before: Pipe {pipe.id} diameter={pipe.diameter}, roughness={pipe.roughness}"
        )
        pipe.diameter = 250
        pipe.roughness = 0.05
        rprint(
            f"After:  Pipe {pipe.id} diameter={pipe.diameter}, roughness={pipe.roughness}"
        )

    new_pipe = Pipe(
        id="p_new",
        start_node="n1",
        end_node="n157",
        length=100,
        diameter=200,
        roughness=0.01,
        minor_loss=0,
        status="Open",
    )
    water_network.pipes.append(new_pipe)
    rprint(
        f"Added new pipe '{new_pipe.id}'; pipe count is now {len(water_network.pipes)}"
    )

    # Example 6: Save to JSON and verify the dictionary round-trips correctly
    rprint("\n📝 Example 6: Save to JSON and verify round-trip")
    output_json_path = "/tmp/hydroforge_example_output.json"
    EPANETNetworkModelIO.to_json_file(water_network, output_json_path)
    reloaded_network = EPANETNetworkModelIO.from_json_file(output_json_path)

    original_dict = EPANETNetworkModelIO.to_dict(water_network)
    reloaded_dict = EPANETNetworkModelIO.to_dict(reloaded_network)
    if original_dict == reloaded_dict:
        rprint("✅ JSON round-trip check passed: model is unchanged after save/reload.")
    else:
        rprint("❌ JSON round-trip check failed: model differs after save/reload.")
        _print_dict_diff(original_dict, reloaded_dict)

    return water_network


def demo_inp_workflow() -> None:
    """Demonstrate reading, modifying, and saving an EPANET ``.inp`` file."""
    rprint(
        "\n[bold blue]=== Modifying networks in native EPANET .inp format ===[/bold blue]"
    )

    inp_path = get_package_root() / "tests/base_networks/Net1.inp"
    water_network = EPANETNetworkModelIO.from_inp_file(inp_path)

    rprint("\n🔍 Original junctions:")
    for junction in water_network.junctions:
        rprint(
            f"  {junction.id}: elevation={junction.elevation}, base_demand={junction.base_demand}"
        )

    # Modify a junction's elevation directly (typed as Decimal, not a string)
    rprint("\n📝 Modifying junction '11'")
    junction = water_network.junctions.get_by_field("id", "11")
    if junction is not None:
        rprint(
            f"Before: elevation={junction.elevation} ({type(junction.elevation).__name__})"
        )
        junction.elevation = 725.0
        rprint(
            f"After:  elevation={junction.elevation} ({type(junction.elevation).__name__})"
        )

    # Modify a pipe's diameter using the field-value helper
    water_network.modify_item_by_field_value("pipes", "id", "10", diameter=12.0)
    modified_pipe = water_network.get_item_by_field_value("pipes", "id", "10")
    rprint(f"Pipe '10' diameter is now {modified_pipe.diameter}")

    # Save the modified network to a new .inp file
    rprint("\n📝 Saving modified network to .inp file")
    output_inp_path = "/tmp/hydroforge_example_output.inp"
    EPANETNetworkModelIO.to_inp_file(water_network, output_inp_path)
    rprint(f"Saved to {output_inp_path}")

    # Verify the saved file is valid EPANET INP by re-reading it
    reloaded_network = EPANETNetworkModelIO.from_inp_file(output_inp_path)
    reloaded_junction = reloaded_network.junctions.get_by_field("id", "11")
    rprint(f"Re-read from disk: junction '11' elevation={reloaded_junction.elevation}")

    # Round-trip check: open an .inp file, save it unmodified, and verify
    # the original and saved files are equivalent (compared as parsed
    # models, since exact text is not guaranteed -- e.g. numeric formatting
    # may be normalized during the round-trip).
    rprint("\n📝 Round-trip check: open .inp file, save unmodified, compare")
    original_network = EPANETNetworkModelIO.from_inp_file(inp_path)
    unmodified_copy_path = "/tmp/hydroforge_example_unmodified.inp"
    EPANETNetworkModelIO.to_inp_file(original_network, unmodified_copy_path)
    resaved_network = EPANETNetworkModelIO.from_inp_file(unmodified_copy_path)

    original_dict = EPANETNetworkModelIO.to_dict(original_network)
    resaved_dict = EPANETNetworkModelIO.to_dict(resaved_network)
    if original_dict == resaved_dict:
        rprint(
            "✅ INP round-trip check passed: original and saved files are equivalent."
        )
    else:
        rprint("❌ INP round-trip check failed: original and saved files differ.")
        _print_dict_diff(original_dict, resaved_dict)


def _print_dict_diff(original: dict, converted: dict) -> None:
    """Print a human-readable summary of differences between two dicts.

    Parameters
    ----------
    original : dict
        Expected/original dictionary.
    converted : dict
        Dictionary to compare against ``original``.
    """
    original_keys = set(original.keys())
    converted_keys = set(converted.keys())
    if original_keys != converted_keys:
        rprint("   Different keys:")
        rprint(f"     Original only: {original_keys - converted_keys}")
        rprint(f"     Converted only: {converted_keys - original_keys}")
    for key in original_keys & converted_keys:
        if original[key] != converted[key]:
            rprint(f"   Different values for key: {key}")
            rprint(f"     Original: {original[key]}")
            rprint(f"     Converted: {converted[key]}")


if __name__ == "__main__":
    demo_json_workflow()
    demo_inp_workflow()
    rprint("\n[bold green]✅ Demonstration complete![/bold green]")
