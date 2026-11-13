This module is designed to create uncertainty scenarios for running analyses on networks with added model and measurement uncertainty with uncertainties sampled using more or less structured sampling algorithms, such as LHS or Sobol.

The intended output is a configuration file with network modifications and sensor specifications for each unique scenario, which
can be used to batch simulate versions of the same network with differing (sampled) model parameters and outputs recorded with non-ideal measurement devices modelled as imprecise sensors with defined characteristics such as offset, precision, drift, etc.

## Overview
- **ArtificialMeasurementCreator**: Create synthetic sensor measurements with model and measurement uncertainties

### Key Features
- ✅ **Synthetic Measurements**: Generate realistic sensor data with uncertainties for testing/calibration

### Measurement Creator

#### ArtificialMeasurementCreator

Create synthetic sensor measurements with model and measurement uncertainties for testing, calibration, or scenario analysis.

**Key Features:**
- Apply model uncertainties (pipe roughness, demands, etc.) via NetworkModifierPipeline
- Add sensor measurement uncertainties (noise, bias, precision)
- Simulate pressure and flow measurements
- Export to CSV for analysis

**Example:**
```python
from hydroforge.simulation.measurement_creator import ArtificialMeasurementCreator
from hydroforge.simulation.simulator import WNTRSimulator
from hydroforge.sensors.sensors import GaussianNoiseSensor
import wntr

wn = wntr.network.WaterNetworkModel('network.inp')
simulator = WNTRSimulator(wn, time_duration=86400)

# Create measurement generator with noisy sensors
measurement_creator = ArtificialMeasurementCreator(
    simulator=simulator,
    name='scenario_1',
    simulation_time_hours=24,
    pressure_sensor_names=['J1', 'J5', 'J10'],
    pressure_sensors=GaussianNoiseSensor(std_dev=0.5)  # ±0.5m noise
)

# Generate measurements with uncertainties
measurements = measurement_creator.create_artificial_measurements(
    save_to_csv=True,
    output_dir='./measurements'
)

print(measurements['pressure'])  # DataFrame with noisy pressure data
print(measurements['flow'])      # DataFrame with flow data
```

## Usage Examples

### Example 1: Creating Synthetic Measurements for Calibration

```python
from hydroforge.scenario_generation.measurement_creator import ArtificialMeasurementCreator
from hydroforge.simulation.simulator import WNTRSimulator
from hydroforge.sensors.sensors import GaussianNoiseSensor
from hydroforge.networks.network_model_modifier import NetworkModifierPipeline, RoughnessModifier
import wntr

wn = wntr.network.WaterNetworkModel('network.inp')
simulator = WNTRSimulator(wn, time_duration=0)

# Define model uncertainties (e.g., roughness variation)
modifiers = NetworkModifierPipeline([
    RoughnessModifier(multiplier_range=(0.8, 1.2))  # ±20% roughness
])

# Create realistic sensor measurements with noise
measurement_creator = ArtificialMeasurementCreator(
    simulator=simulator,
    name='calibration_data',
    simulation_time_hours=1,
    pressure_sensor_names=['J1', 'J5', 'J10', 'J15'],
    pressure_sensors=GaussianNoiseSensor(std_dev=0.3),  # ±0.3m noise
    network_modifiers=modifiers
)

# Generate measurements (applies model + sensor uncertainties)
measurements = measurement_creator.create_artificial_measurements(
    save_to_csv=True,
    output_dir='./calibration_data'
)

# Use these synthetic measurements for calibration testing
print(f"Generated {len(measurements['pressure'])} pressure measurements")
print(f"Measurement files saved to: ./calibration_data/")
```
