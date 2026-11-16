"""Command-line interface for the HydroForge uncertainty analysis toolkit."""

import sys
import argparse
from pathlib import Path


def main():
    """Main entry point for the hydroforge CLI."""
    parser = argparse.ArgumentParser(
        prog="hydroforge",
        description="HydroForge: An uncertainty injection and scenario generation "
        "framework for water distribution network simulations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
 hydroforge --version
 hydroforge run-analysis config.yaml
 hydroforge localize network.inp measurements.csv
For more information, visit: https://github.com/tomjanus/HydroForge
        """,
    )

    parser.add_argument("--version", action="version", version="HydroForge 0.1.0")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Example subcommand: run-analysis
    analysis_parser = subparsers.add_parser(
        "run-analysis", help="Run uncertainty analysis"
    )
    analysis_parser.add_argument(
        "config", type=Path, help="Path to configuration file (YAML)"
    )
    analysis_parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Output directory (default: ./output)",
    )

    # Example subcommand: localize
    localize_parser = subparsers.add_parser("localize", help="Run leak localization")
    localize_parser.add_argument("network", type=Path, help="Path to network INP file")
    localize_parser.add_argument(
        "measurements", type=Path, help="Path to measurement data (CSV)"
    )
    localize_parser.add_argument(
        "--method",
        choices=["differential", "interpolation", "genetic"],
        default="differential",
        help="Localization method (default: differential)",
    )
    localize_parser.add_argument(
        "--output",
        type=Path,
        default=Path("localization_results"),
        help="Output directory (default: ./localization_results)",
    )

    # Example subcommand: sensor-placement
    sensor_parser = subparsers.add_parser(
        "sensor-placement", help="Optimize sensor placement"
    )
    sensor_parser.add_argument("network", type=Path, help="Path to network INP file")
    sensor_parser.add_argument(
        "--num-sensors",
        type=int,
        default=5,
        help="Number of sensors to place (default: 5)",
    )
    sensor_parser.add_argument(
        "--output",
        type=Path,
        default=Path("sensor_placement.csv"),
        help="Output file for sensor locations (default: ./sensor_placement.csv)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Handle commands
    if args.command == "run-analysis":
        return run_analysis(args)
    elif args.command == "localize":
        return run_localization(args)
    elif args.command == "sensor-placement":
        return run_sensor_placement(args)

    return 0


def run_analysis(args):
    """Run uncertainty analysis."""
    print(f"Running analysis with config: {args.config}")
    print(f"Output directory: {args.output}")

    # TODO: Implement actual analysis logic
    # Example:
    # config = load_config(args.config)
    # results = run_uncertainty_analysis(config)
    # save_results(results, args.output)

    print("⚠️  Analysis command not yet implemented")
    print("This is a placeholder. Implement the actual logic in cli.py")
    return 1


def run_localization(args):
    """Run leak localization."""
    print(f"Running localization on network: {args.network}")
    print(f"Using measurements from: {args.measurements}")
    print(f"Method: {args.method}")
    print(f"Output directory: {args.output}")

    # TODO: Implement actual localization logic
    # Example:
    # results = localisation_method.run(args.network, args.measurements)
    # save_results(results, args.output)

    print("⚠️  Localization command not yet implemented")
    print("This is a placeholder. Implement the actual logic in cli.py")
    return 1


def run_sensor_placement(args):
    """Run sensor placement optimization."""
    print(f"Optimizing sensor placement for network: {args.network}")
    print(f"Number of sensors: {args.num_sensors}")
    print(f"Output file: {args.output}")

    # TODO: Implement actual sensor placement logic
    # Example:
    # sensor_locations = optimize_sensor_placement(
    #     args.network, num_sensors=args.num_sensors
    # )
    # save_sensor_locations(sensor_locations, args.output)

    print("⚠️  Sensor placement command not yet implemented")
    print("This is a placeholder. Implement the actual logic in cli.py")
    return 1


if __name__ == "__main__":
    sys.exit(main())
