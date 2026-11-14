"""Synthetic measurement generation for water distribution networks.

This module provides tools for creating artificial sensor measurements with realistic
model and measurement uncertainties. It enables testing calibration algorithms, validating
leak detection methods, and generating synthetic datasets without requiring real sensor data.

Key Components:
    - ArtificialMeasurementCreator: Generate measurements for a single scenario
    - ArtificialMeasurementMultiCreator: Batch generation for multiple scenarios
    - Integration with Simulator strategies (WNTR, EPANET)
    - Flexible sensor uncertainty models (noise, precision, bias)
    - Network model uncertainty via NetworkModifierPipeline

Typical Workflow:
    1. Create simulator with network model
    2. Define sensor locations and uncertainty models
    3. Optional: Define network model uncertainties (roughness, demands, etc.)
    4. Generate measurements with uncertainties applied
    5. Export to CSV or Excel for analysis

Typical Usage:
    >>> from found.simulation.measurement_creator import ArtificialMeasurementCreator
    >>> from found.simulation.simulator import WNTRSimulator
    >>> from found.sensors.sensors import GaussianNoiseSensor
    >>> import wntr
    >>>
    >>> # Load network and create simulator
    >>> wn = wntr.network.WaterNetworkModel('network.inp')
    >>> simulator = WNTRSimulator(wn, time_duration=86400)
    >>>
    >>> # Create measurement generator with noisy sensors
    >>> creator = ArtificialMeasurementCreator(
    ...     simulator=simulator,
    ...     name='scenario_1',
    ...     simulation_time_hours=24,
    ...     pressure_sensor_names=['J1', 'J5', 'J10'],
    ...     pressure_sensors=GaussianNoiseSensor(std_dev=0.5)
    ... )
    >>>
    >>> # Generate measurements with uncertainties
    >>> measurements = creator.create_artificial_measurements(
    ...     save_to_csv=True,
    ...     output_dir='./measurements'
    ... )
    >>> print(measurements['pressure'])  # Noisy pressure data
    >>> print(measurements['flow'])      # Flow data

Design Pattern:
    Strategy pattern - allows pluggable simulator engines and sensor uncertainty models
    while maintaining consistent measurement generation interface.

Notes:
    - All operations work on simulator model copies to prevent modification
    - Model uncertainties are applied before simulation
    - Measurement uncertainties are applied to simulation results
    - Supports time-series measurements with configurable duration
    - Output format compatible with calibration and analysis tools

License: See LICENSE file in repository root
"""

import warnings
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Union
import pathlib
import copy
import wntr
import pandas as pd
from rich import print as rprint
from found.simulation.simulator import Simulator
from found.sensors.sensors import Sensor, PerfectSensor
from found.networks.network_model_modifier import NetworkModifierPipeline

SECONDS_PER_HOUR = 3_600

warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")


@dataclass
class ArtificialMeasurementCreator:
    """Create synthetic sensor measurements with model and measurement uncertainties.

    This class orchestrates the generation of artificial measurements by:
    1. Applying model uncertainties to network parameters (optional)
    2. Running hydraulic simulation
    3. Applying sensor measurement uncertainties to simulation results
    4. Exporting measurements to CSV files

    The generated measurements simulate real-world scenarios where:
    - Network model doesn't perfectly represent reality (model uncertainty)
    - Sensors have noise, bias, and limited precision (measurement uncertainty)

    This is useful for:
    - Testing calibration algorithms with known ground truth
    - Generating training data for leak detection methods
    - Uncertainty quantification studies
    - Validation of network analysis tools

    Attributes:
        simulator: Water network simulator (WNTRSimulator, EPANETSimulator)
        name: Scenario name used for output file naming
        network_modifiers: Pipeline of model modifications (roughness, demands, etc.)
        simulation_time_hours: Simulation duration in hours (default: 24)
        pressure_sensor_names: Junction names for pressure sensors (default: all junctions)
        flow_sensor_names: Pipe names for flow sensors (default: all pipes)
        pressure_sensors: Sensor uncertainty models for pressure measurements
            - Single Sensor: Applied to all pressure sensors
            - Dict[str, Sensor]: Different sensor per location
            - None: Perfect sensors (no uncertainty)
        flow_sensors: Sensor uncertainty models for flow measurements (same format as pressure_sensors)
        output_measurements: Generated measurements after create_artificial_measurements()
            - Dict with keys 'pressure' and 'flow'
            - Values are DataFrames with time index and sensor columns

    Example:
        >>> from found.simulation.simulator import WNTRSimulator
        >>> from found.sensors.sensors import GaussianNoiseSensor
        >>> from found.network_model_modifier import RoughnessModifier, NetworkModifierPipeline
        >>> import wntr
        >>>
        >>> wn = wntr.network.WaterNetworkModel('network.inp')
        >>> simulator = WNTRSimulator(wn, time_duration=0)
        >>>
        >>> # Define model and sensor uncertainties
        >>> modifiers = NetworkModifierPipeline([
        ...     RoughnessModifier(multiplier_range=(0.8, 1.2))
        ... ])
        >>>
        >>> creator = ArtificialMeasurementCreator(
        ...     simulator=simulator,
        ...     name='test_scenario',
        ...     network_modifiers=modifiers,
        ...     simulation_time_hours=24,
        ...     pressure_sensor_names=['J1', 'J5', 'J10'],
        ...     pressure_sensors=GaussianNoiseSensor(std_dev=0.3)
        ... )
        >>>
        >>> measurements = creator.create_artificial_measurements(save_to_csv=True)
        >>> print(measurements['pressure'].head())

    Notes:
        - Simulator model is copied before applying modifications
        - If sensor names not provided, uses all junctions/pipes
        - Measurement uncertainties applied after simulation completes
        - Time index represents seconds from simulation start
    """

    simulator: Simulator
    name: str
    network_modifiers: Optional[NetworkModifierPipeline] = None
    simulation_time_hours: int = 24
    pressure_sensor_names: Optional[List[str]] = None
    flow_sensor_names: Optional[List[str]] = None
    pressure_sensors: Optional[Dict[str, Sensor] | Sensor] = None
    flow_sensors: Optional[Dict[str, Sensor] | Sensor] = None
    output_measurements: Optional[Dict[str, pd.DataFrame]] = field(
        init=False, default=None
    )

    def __post_init__(self):
        self._validate_inputs()
        model = self.simulator.model
        # If sensors not provided, use all junctions/pipes
        self.pressure_sensor_names = self.pressure_sensor_names or list(
            model.junction_name_list
        )
        self.flow_sensor_names = self.flow_sensor_names or list(model.pipe_name_list)
        # Normalize to dict[str, Sensor]
        self.pressure_sensors = self._initialize_sensors(
            self.pressure_sensors, self.pressure_sensor_names
        )
        self.flow_sensors = self._initialize_sensors(
            self.flow_sensors, self.flow_sensor_names
        )

    @property
    def simulation_time_seconds(self) -> int:
        """Duration of simulation in seconds.

        Returns:
            Simulation duration converted from hours to seconds.

        Note:
            Conversion factor: 3600 seconds per hour
        """
        return self.simulation_time_hours * SECONDS_PER_HOUR

    def _validate_inputs(self) -> None:
        """Validate constructor parameters.

        Raises:
            TypeError: If simulator is not a Simulator instance
            ValueError: If simulation_time_hours is not a positive integer
        """
        if not isinstance(self.simulator, Simulator):
            raise TypeError(
                "simulator must be an instance of Simulator or its subclass."
            )
        if (
            not isinstance(self.simulation_time_hours, int)
            or self.simulation_time_hours <= 0
        ):
            raise ValueError("simulation_time_hours must be a positive integer.")

    @staticmethod
    def _initialize_sensors(
        sensors: Optional[Union[Dict[str, Sensor], Sensor]], names: List[str]
    ) -> Dict[str, Sensor]:
        """Normalize sensor input to dictionary mapping sensor names to Sensor objects.

        Args:
            sensors: Sensor specification in one of three forms:
                - None: Creates PerfectSensor for all locations
                - Sensor: Single sensor instance applied to all locations
                - Dict[str, Sensor]: Different sensor per location
            names: List of sensor location names (junction or pipe names)

        Returns:
            Dictionary mapping each sensor name to its Sensor object

        Raises:
            TypeError: If sensors is not None, Sensor, or dict

        Example:
            >>> sensors = _initialize_sensors(
            ...     GaussianNoiseSensor(std_dev=0.5),
            ...     ['J1', 'J2', 'J3']
            ... )
            >>> # Returns: {'J1': GaussianNoiseSensor(...), 'J2': ..., 'J3': ...}
        """
        if sensors is None:
            return {name: PerfectSensor() for name in names}
        if isinstance(sensors, Sensor):
            return {name: sensors for name in names}
        if isinstance(sensors, dict):
            return sensors
        raise TypeError(
            f"sensors must be a Sensor instance, a dict[str, Sensor], or None. Provided type: {type(sensors)}"
        )

    def _retrieve_model_copy(self) -> wntr.network.WaterNetworkModel:
        """Return a deep copy of the water network model.

        Returns:
            Independent copy of the network model from simulator

        Note:
            Uses deep copy to prevent modifications affecting original model
        """
        return copy.deepcopy(self.simulator.model)

    def _update_simulator_model(
        self, new_model: wntr.network.WaterNetworkModel
    ) -> None:
        """Update the simulator with a modified water network model.

        Args:
            new_model: Modified network model to use for simulation

        Note:
            Calls simulator.update_model() which handles simulator-specific updates
        """
        self.simulator.update_model(new_model)

    def apply_model_uncertainty(self) -> None:
        """Apply model uncertainties to the water network model.

        Creates a copy of the network model, applies all modifiers from the
        NetworkModifierPipeline, and updates the simulator with the modified model.

        Model uncertainties can include:
        - Pipe roughness variations
        - Demand multipliers
        - Diameter adjustments
        - Elevation changes
        - Any custom network modifications

        Note:
            If network_modifiers is None, prints warning and skips modification.
            Works on model copy to preserve original network.
        """
        if self.network_modifiers is not None:
            model_copy = self._retrieve_model_copy()
            self.network_modifiers.apply(model_copy)
            self._update_simulator_model(model_copy)
        else:
            rprint(
                "[yellow]No network modifiers provided. Skipping model uncertainty application.[/yellow]"
            )

    def simulate_network(self) -> None:
        """Run hydraulic simulation for the specified duration.

        Executes the simulator's run_simulation() method with the current
        network model (potentially modified by apply_model_uncertainty).

        Note:
            Simulation duration set by simulation_time_hours attribute.
            Results stored internally in simulator for later extraction.
        """
        self.simulator.run_simulation()

    def apply_measurement_uncertainty(self) -> None:
        """Apply sensor measurement uncertainties to simulation results.

        Extracts pressure and flow data from simulation results, then applies
        sensor uncertainty models to generate realistic measurements with noise,
        bias, precision limitations, etc.

        Process:
        1. Extract pressures at all sensor locations for full time range
        2. Extract flows at all sensor locations for full time range
        3. Apply each sensor's measure() method to add uncertainties
        4. Store results in output_measurements dict

        Note:
            Must be called after simulate_network().
            Results stored in self.output_measurements with keys 'pressure' and 'flow'.
        """
        output_pressures: pd.DataFrame = self.simulator.get_pressures(
            sensors=self.pressure_sensor_names,
            times=(
                0,
                self.simulation_time_seconds,
            ),  # ← This requests only time 0 and 86400
            as_dataframe=True,
        )
        output_flows: pd.DataFrame = self.simulator.get_flows(
            pipes=self.flow_sensor_names,
            times=(
                0,
                self.simulation_time_seconds,
            ),  # ← This requests only time 0 and 86400
            as_dataframe=True,
        )
        pressure_sensors = self.pressure_sensors
        flow_sensors = self.flow_sensors
        assert isinstance(pressure_sensors, dict)
        assert isinstance(flow_sensors, dict)
        pressures_measured = pd.DataFrame(
            {
                col: (
                    pressure_sensors[col].measure(output_pressures[col])
                    if col in pressure_sensors
                    else output_pressures[col]
                )
                for col in output_pressures.columns
            }
        )
        flows_measured = pd.DataFrame(
            {
                col: (
                    flow_sensors[col].measure(output_flows[col])
                    if col in flow_sensors
                    else output_flows[col]
                )
                for col in output_flows.columns
            }
        )
        self.output_measurements = {
            "pressure": pressures_measured,
            "flow": flows_measured,
        }

    def create_artificial_measurements(
        self,
        save_to_csv: bool = False,
        output_dir: Optional[Union[str, pathlib.Path]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Generate complete set of artificial measurements with all uncertainties.

        This is the main workflow method that orchestrates:
        1. apply_model_uncertainty() - Modify network parameters
        2. simulate_network() - Run hydraulic simulation
        3. apply_measurement_uncertainty() - Add sensor noise/bias
        4. save_measurements_to_csv() - Optional file export

        Args:
            save_to_csv: If True, automatically save measurements to CSV files (default: False)
            output_dir: Directory for CSV files. If None, uses current directory (default: None)

        Returns:
            Dictionary with keys:
                - 'pressure': DataFrame with pressure measurements (rows=time, columns=sensors)
                - 'flow': DataFrame with flow measurements (rows=time, columns=sensors)

        Example:
            >>> creator = ArtificialMeasurementCreator(...)
            >>> measurements = creator.create_artificial_measurements(
            ...     save_to_csv=True,
            ...     output_dir='./data/measurements'
            ... )
            >>> print(measurements['pressure'].shape)  # (n_timesteps, n_sensors)
            >>> print(measurements['flow'].mean())     # Average flow across all sensors

        Note:
            Results also stored in self.output_measurements attribute.
            Time index represents seconds from simulation start.
        """
        self.apply_model_uncertainty()
        self.simulate_network()
        self.apply_measurement_uncertainty()
        if save_to_csv:
            self.save_measurements_to_csv(output_dir=output_dir)
        output_measurements = self.output_measurements
        assert output_measurements is not None
        return output_measurements

    def save_measurements_to_csv(
        self,
        output_dir: Optional[Union[str, pathlib.Path]] = None,
        pressure_suffix: str = "_pressures",
        flow_suffix: str = "_flows",
        separator: str = ";",
        include_index: bool = True,
    ) -> Dict[str, pathlib.Path]:
        """Save generated measurements to CSV files.

        Creates two CSV files:
        - {name}{pressure_suffix}.csv - Pressure measurements
        - {name}{flow_suffix}.csv - Flow measurements

        Args:
            output_dir: Output directory path. If None, uses current working directory (default: None)
            pressure_suffix: Suffix for pressure filename (default: '_pressures')
            flow_suffix: Suffix for flow filename (default: '_flows')
            separator: CSV column separator (default: ';')
            include_index: If True, write time index as first column (default: True)

        Returns:
            Dictionary with keys 'pressure' and 'flow' mapping to their file paths

        Raises:
            ValueError: If output_measurements is None (must call create_artificial_measurements first)

        Example:
            >>> creator.create_artificial_measurements()
            >>> paths = creator.save_measurements_to_csv(
            ...     output_dir='./data',
            ...     pressure_suffix='_press',
            ...     separator=','
            ... )
            >>> print(paths['pressure'])  # Path: ./data/scenario_1_press.csv

        Note:
            Creates output_dir if it doesn't exist (with parents).
            Overwrites existing files with same name.
        """
        output_measurements = self.output_measurements
        if output_measurements is None:
            raise ValueError(
                "No measurements to save. Run apply_measurement_uncertainty() first."
            )
        # Set up output directory
        if output_dir is None:
            output_dir = pathlib.Path.cwd()
        else:
            output_dir = pathlib.Path(output_dir)
        # Create directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        # Create file paths
        pressure_file = output_dir / f"{self.name}{pressure_suffix}.csv"
        flow_file = output_dir / f"{self.name}{flow_suffix}.csv"
        # Save to CSV
        output_measurements["pressure"].to_csv(
            pressure_file, sep=separator, index=include_index
        )
        output_measurements["flow"].to_csv(
            flow_file, sep=separator, index=include_index
        )
        rprint(f"[green]✓[/green] Saved pressure measurements to: {pressure_file}")
        rprint(f"[green]✓[/green] Saved flow measurements to: {flow_file}")
        return {"pressure": pressure_file, "flow": flow_file}


@dataclass
class ArtificialMeasurementMultiCreator:
    """Batch generation of synthetic measurements for multiple scenarios.

    This class manages multiple ArtificialMeasurementCreator instances to generate
    measurements for different scenarios efficiently. Useful for:
    - Comparing different uncertainty models
    - Generating training datasets with varied conditions
    - Monte Carlo simulations with multiple realizations
    - Sensitivity analysis across different parameters

    Attributes:
        measurement_creators: List of configured ArtificialMeasurementCreator instances
        measurements: Generated measurements after create_artificial_measurements()
            - Dict[scenario_name, Dict['pressure'|'flow', DataFrame]]
            - Each scenario has pressure and flow measurements

    Example:
        >>> from found.simulation.simulator import WNTRSimulator
        >>> from found.sensors.sensors import GaussianNoiseSensor
        >>> import wntr
        >>>
        >>> wn = wntr.network.WaterNetworkModel('network.inp')
        >>>
        >>> # Create multiple scenarios with different noise levels
        >>> creators = [
        ...     ArtificialMeasurementCreator(
        ...         simulator=WNTRSimulator(wn.copy(), time_duration=0),
        ...         name=f'scenario_{i}',
        ...         pressure_sensors=GaussianNoiseSensor(std_dev=0.1*i)
        ...     )
        ...     for i in range(1, 4)
        ... ]
        >>>
        >>> multi_creator = ArtificialMeasurementMultiCreator(creators)
        >>> all_measurements = multi_creator.create_artificial_measurements()
        >>> multi_creator.save_all_to_excel('all_scenarios.xlsx')

    Note:
        Each creator can have different network models, sensor configurations,
        and uncertainty parameters for maximum flexibility.
    """

    measurement_creators: List[ArtificialMeasurementCreator]
    measurements: Optional[Dict[str, pd.DataFrame]] = field(init=False, default=None)

    def create_artificial_measurements(self) -> Dict[str, pd.DataFrame]:
        """Generate measurements for all scenarios.

        Iterates through all measurement creators and generates measurements
        for each scenario using their respective configurations.

        Returns:
            Dictionary mapping scenario names to their measurements:
            - {scenario_name: {'pressure': DataFrame, 'flow': DataFrame}}

        Note:
            Results also stored in self.measurements attribute.
            Scenarios processed sequentially (not parallelized).
        """
        measurements = {
            creator.name: creator.create_artificial_measurements()
            for creator in self.measurement_creators
        }
        self.measurements = measurements
        return self.measurements

    def save_all_to_csv(
        self, output_dir: Optional[Union[str, pathlib.Path]] = None
    ) -> Dict[str, Dict[str, pathlib.Path]]:
        """Save all scenario measurements to separate CSV files.

        Creates one pressure and one flow CSV file per scenario:
        - {scenario_1}_pressures.csv, {scenario_1}_flows.csv
        - {scenario_2}_pressures.csv, {scenario_2}_flows.csv
        - etc.

        Args:
            output_dir: Directory for all CSV files. If None, uses current directory (default: None)

        Returns:
            Nested dictionary: {scenario_name: {'pressure': Path, 'flow': Path}}

        Raises:
            ValueError: If measurements is None (must call create_artificial_measurements first)

        Example:
            >>> multi_creator.create_artificial_measurements()
            >>> file_paths = multi_creator.save_all_to_csv('./measurements')
            >>> print(file_paths['scenario_1']['pressure'])  # Path to CSV file

        Note:
            Each scenario's files named using its 'name' attribute.
            All files saved to same directory.
        """
        if self.measurements is None:
            raise ValueError(
                "No measurements to save. Run create_artificial_measurements() first."
            )
        saved_files = {}
        for creator in self.measurement_creators:
            saved_files[creator.name] = creator.save_measurements_to_csv(
                output_dir=output_dir
            )
        return saved_files

    def save_all_to_excel(
        self,
        filename: Union[str, pathlib.Path],
        output_dir: Optional[Union[str, pathlib.Path]] = None,
        flatten_index: bool = False,
    ) -> pathlib.Path:
        """Save all scenario measurements to a single Excel file with multiple sheets.

        Creates Excel file with two sheets:
        - 'Pressures': All pressure measurements across scenarios
        - 'Flows': All flow measurements across scenarios

        Column format depends on flatten_index:
        - False (default): Multi-index columns (Scenario, Sensor)
          * Columns: (scenario_1, J1), (scenario_1, J2), (scenario_2, J1), ...
          * Better for direct analysis in Excel
        - True: Single-index columns with Scenario as a data column
          * Columns: Time, Scenario, J1, J2, J3, ...
          * Better for certain data processing workflows

        Args:
            filename: Excel filename (with or without .xlsx extension)
            output_dir: Output directory. If None, uses current directory (default: None)
            flatten_index: If True, convert multi-index to long format (default: False)

        Returns:
            Path to the saved Excel file

        Raises:
            ValueError: If measurements is None (must call create_artificial_measurements first)

        Example:
            >>> multi_creator.create_artificial_measurements()
            >>> path = multi_creator.save_all_to_excel(
            ...     'all_scenarios.xlsx',
            ...     output_dir='./results',
            ...     flatten_index=False
            ... )
            >>> print(f"Saved to: {path}")

        Note:
            Requires openpyxl library for Excel writing.
            Automatically appends .xlsx extension if not present.
            Creates output_dir if it doesn't exist.
        """
        if self.measurements is None:
            raise ValueError(
                "No measurements to save. Run create_artificial_measurements() first."
            )

        # Set up output path
        if output_dir is None:
            output_dir = pathlib.Path.cwd()
        else:
            output_dir = pathlib.Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)
        # Ensure .xlsx extension
        filename = str(filename)
        if not filename.endswith(".xlsx"):
            filename += ".xlsx"
        output_file = output_dir / filename
        # Create multi-indexed DataFrames
        pressure_dfs = []
        flow_dfs = []

        for scenario_name, _measurements in self.measurements.items():
            # Add scenario level to column MultiIndex
            pressure_df = _measurements["pressure"].copy()
            flow_df = _measurements["flow"].copy()
            # Create MultiIndex columns: (scenario_name, sensor_name)
            pressure_df.columns = pd.MultiIndex.from_product(
                [[scenario_name], pressure_df.columns], names=["Scenario", "Sensor"]
            )
            flow_df.columns = pd.MultiIndex.from_product(
                [[scenario_name], flow_df.columns], names=["Scenario", "Sensor"]
            )
            pressure_dfs.append(pressure_df)
            flow_dfs.append(flow_df)

        # Concatenate all scenarios
        all_pressures = pd.concat(pressure_dfs, axis=1)
        all_flows = pd.concat(flow_dfs, axis=1)

        # Flatten multi-index columns if requested
        if flatten_index:
            # Stack converts columns to rows, creating a long-form DataFrame
            all_pressures = all_pressures.stack(level="Scenario", future_stack=True)
            all_flows = all_flows.stack(level="Scenario", future_stack=True)

            # Reset index to convert 'Scenario' from index to column
            all_pressures = all_pressures.reset_index()
            all_flows = all_flows.reset_index()

            # Rename the time index column (level_0) to something more meaningful
            all_pressures = all_pressures.rename(columns={"level_0": "Time"})
            all_flows = all_flows.rename(columns={"level_0": "Time"})

        # Save to Excel with multiple sheets
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            all_pressures.to_excel(
                writer, sheet_name="Pressures", index=not flatten_index
            )
            all_flows.to_excel(writer, sheet_name="Flows", index=not flatten_index)

        format_type = "flattened single-index" if flatten_index else "multi-index"
        rprint(
            f"[green]✓[/green] Saved all measurements to Excel ({format_type}): {output_file}"
        )
        return output_file


if __name__ == "__main__":
    from found.simulation.simulator import WNTRSimulator, SimulationConfig
    from found.sensors.sensors import FixedPrecisionSensor, RandomNoiseSensor
    from found.networks.network_model_modifier import PipeDiameterMultiplierModifier
    from found.auxiliary.utils import get_package_root

    # Set up output directory at project root level (outside src/)
    project_root = get_package_root()
    output_dir = project_root / "outputs" / "measurements"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Example 1: Single measurement creator
    rprint("\n=== Example 1: Single Measurement Creator (with Model Uncertainty) ===")

    # Create a simple network
    wn = wntr.network.WaterNetworkModel()
    wn.add_reservoir("R1", base_head=100.0)
    wn.add_junction("J1", base_demand=0.1, elevation=50.0)
    wn.add_junction("J2", base_demand=0.15, elevation=45.0)
    wn.add_pipe("P1", "R1", "J1", length=1000, diameter=0.3, roughness=100)
    wn.add_pipe("P2", "J1", "J2", length=800, diameter=0.2, roughness=100)

    # Create simulator
    simulator = WNTRSimulator(
        wn=wn,
        time_duration=24 * 3_600,
        simulator_config=SimulationConfig(hydraulic_timestep=3_600),
    )

    # Create network modifiers to test model uncertainty
    pipe_diameter_modifier = PipeDiameterMultiplierModifier(
        multipliers={"P1": 0.9, "P2": 1.1}
    )
    network_modifiers = NetworkModifierPipeline(modifiers=[pipe_diameter_modifier])

    # Create measurement creator with sensors and network modifiers
    creator = ArtificialMeasurementCreator(
        simulator=simulator,
        name="scenario_1",
        network_modifiers=network_modifiers,
        simulation_time_hours=24,
        pressure_sensor_names=["J1", "J2"],
        flow_sensor_names=["P1", "P2"],
        pressure_sensors=FixedPrecisionSensor(delta_y=0.1),
        flow_sensors=RandomNoiseSensor(sigma=0.01, seed=42),
    )

    # Create measurements and save to CSV
    measurements = creator.create_artificial_measurements(
        save_to_csv=True, output_dir=output_dir
    )

    rprint(f"Pressure measurements shape: {measurements['pressure'].shape}")
    rprint(f"Flow measurements shape: {measurements['flow'].shape}")
    rprint(f"Files saved to: {output_dir}")

    # Example 2: Multiple measurement creators
    rprint(
        "\n=== Example 2: Multiple Measurement Creators (with Different Model Uncertainties) ==="
    )

    # Create different scenarios with varying model uncertainties
    creators = []
    for i in range(3):
        sim = WNTRSimulator(
            wn=copy.deepcopy(wn),
            time_duration=24 * 3600,
            simulator_config=SimulationConfig(hydraulic_timestep=3_600),
        )

        # Different model uncertainty for each scenario
        diameter_multiplier = 1.0 - (i * 0.05)  # 1.0, 0.95, 0.90
        pipe_modifier = PipeDiameterMultiplierModifier(
            multipliers={"P1": diameter_multiplier, "P2": diameter_multiplier}
        )
        modifiers = NetworkModifierPipeline(modifiers=[pipe_modifier])

        creator = ArtificialMeasurementCreator(
            simulator=sim,
            name=f"scenario_{i + 1}",
            network_modifiers=modifiers,
            simulation_time_hours=24,
            pressure_sensors=RandomNoiseSensor(sigma=0.05 * (i + 1), seed=i),
        )
        creators.append(creator)

    # Create multi-creator
    multi_creator = ArtificialMeasurementMultiCreator(measurement_creators=creators)

    # Create all measurements and save to CSV
    all_measurements = multi_creator.create_artificial_measurements()

    # Save to Excel with multi-index
    multi_creator.save_all_to_excel(
        filename="all_scenarios", output_dir=output_dir, flatten_index=True
    )

    rprint(f"\nCreated measurements for {len(all_measurements)} scenarios")
    rprint(f"All files saved to: {output_dir}")
