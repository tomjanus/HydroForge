""" """

import numpy as np
import pandas as pd
from rich import print as rprint
from hydroforge.measurements import (
    WindowAverager,
    MovingWindowAverager,
    PerfectSensor,
    FixedPrecisionSensor,
    RandomNoiseSensor,
    OffsetSensor,
    SensitivityErrorSensor,
    DeadBandSensor,
    SaturationSensor,
    DriftSensor,
    CompositeSensor,
)


def main():
    # Example input data
    scalar_value = 1.07
    vector_values = np.array([1.03, 1.07, 0.94, 1.12, 0.01, -0.02, 2.5])

    rprint("=== SENSOR DEMONSTRATION ===")
    rprint(f"Scalar input: {scalar_value}")
    rprint(f"Vector input: {vector_values}\n")

    sensors = {
        "PerfectSensor": PerfectSensor(),
        "FixedPrecisionSensor": FixedPrecisionSensor(delta_y=0.1),
        "RandomNoiseSensor": RandomNoiseSensor(sigma=0.05, seed=42),
        "OffsetSensor": OffsetSensor(offset=0.2),
        "SensitivityErrorSensor": SensitivityErrorSensor(scale=1.05),
        "DeadBandSensor": DeadBandSensor(threshold=0.05),
        "SaturationSensor": SaturationSensor(min_val=0.0, max_val=1.5),
        "DriftSensor": DriftSensor(offset_rate=0.01),
        "CompositeSensor": CompositeSensor(
            FixedPrecisionSensor(delta_y=0.1),
            RandomNoiseSensor(sigma=0.05),
            OffsetSensor(offset=0.1),
        ),
    }

    for name, sensor in sensors.items():
        rprint(f"--- {name} ---")
        scalar_result = sensor.measure(scalar_value)
        vector_result = sensor.measure(vector_values)
        rprint(f" Scalar: {scalar_result}")
        rprint(f" Vector: {vector_result}\n")

    # Demonstration of Averager
    rprint("=== AVERAGER DEMONSTRATION ===")
    rprint("Vector Values: ", vector_values)
    _window_size = 2
    averager = WindowAverager(window_size=_window_size)

    try:
        avg_scalar = averager.average(vector_values[:2])  # length == num_measurements
        rprint(f"Average of 2 values: {avg_scalar}")
    except ValueError as e:
        rprint(e)

    avg_vector = averager.average(vector_values)  # length > num_measurements
    rprint(f"Windowed averages with window size {_window_size}: {avg_vector}")

    # Demonstrration of MovingWindowAverager
    rprint("\n=== MOVING WINDOW AVERAGER DEMONSTRATION ===")
    _window_size = 3
    _overlap = 1
    rprint(f"Window size: {_window_size}, Overlap: {_overlap}")
    moving_averager = MovingWindowAverager(window_size=_window_size, overlap=_overlap)
    moving_avg_vector = moving_averager.average(vector_values)
    rprint(f"Moving window averages: {moving_avg_vector}")

    def test_2d_support():
        """Test sensors with 2D arrays and DataFrames."""

        rprint("\n=== TESTING 2D ARRAY SUPPORT ===\n")

        # Create test data
        # Simulating 3 sensors × 5 time steps
        array_2d = np.array(
            [
                [1.03, 1.07, 0.94, 1.12, 1.05],
                [2.15, 2.22, 2.08, 2.30, 2.18],
                [3.01, 3.05, 2.98, 3.10, 3.03],
            ]
        )

        df_2d = pd.DataFrame(
            array_2d,
            index=["sensor1", "sensor2", "sensor3"],
            columns=["t0", "t1", "t2", "t3", "t4"],
        )

        rprint(f"2D NumPy array shape: {array_2d.shape}")
        rprint(f"Array:\n{array_2d}\n")
        rprint(f"2D DataFrame shape: {df_2d.shape}")
        rprint(f"DataFrame:\n{df_2d}\n")

        # Test each sensor type
        sensors_to_test = {
            "PerfectSensor": PerfectSensor(),
            "FixedPrecisionSensor": FixedPrecisionSensor(delta_y=0.1),
            "RandomNoiseSensor": RandomNoiseSensor(sigma=0.05, seed=42),
            "OffsetSensor": OffsetSensor(offset=0.2),
            "SensitivityErrorSensor": SensitivityErrorSensor(scale=1.05),
            "DeadBandSensor": DeadBandSensor(threshold=0.05),
            "SaturationSensor": SaturationSensor(min_val=0.0, max_val=2.5),
            "DriftSensor": DriftSensor(offset_rate=0.01),
        }

        for name, sensor in sensors_to_test.items():
            rprint(f"--- Testing {name} ---")

            # Test with 2D NumPy array
            try:
                result_array = sensor.measure(array_2d)
                rprint(
                    f"✓ 2D Array: shape={result_array.shape}, type={type(result_array)}"
                )
                rprint(f"  Result:\n{result_array}")
            except Exception as e:
                rprint(f"✗ 2D Array failed: {e}")

            # Test with DataFrame
            try:
                result_df = sensor.measure(df_2d)
                rprint(f"✓ DataFrame: shape={result_df.shape}, type={type(result_df)}")
                rprint(f"  Result:\n{result_df}")
            except Exception as e:
                rprint(f"✗ DataFrame failed: {e}")

            rprint()

    test_2d_support()


if __name__ == "__main__":
    main()
