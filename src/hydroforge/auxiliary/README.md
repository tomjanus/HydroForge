# Auxiliary Module

Utility functions, I/O wrappers, constants, and helper tools for the HydroForge framework.

---

## Overview

The auxiliary module provides foundational utilities used throughout the HydroForge package:
- **File I/O**: Loading/saving configuration files (YAML, JSON), DataFrames (CSV, Excel)
- **EPANET Parsing**: Reading and writing EPANET input files
- **Dynamic Loading**: Automatic discovery and registration of leak locator classes
- **Logging**: Timestamped logging with color-coded output
- **Utilities**: Package resource access, directory management, execution timing

---

## Module Structure

```
auxiliary/
├── __init__.py              # Package initialization
├── exceptions.py            # Custom exception classes
├── io_wrappers.py           # File I/O wrapper functions
├── epanet_file_parser.py    # EPANET input file parser
├── utils.py                 # General utility functions
└── README.md                # This file
```

---

## Core Components

---

### 1. Custom Exceptions ([custom_exceptions.py](./custom_exceptions.py))

Custom exception classes with enhanced error reporting.

#### UserConfigLoadException

Exception for configuration loading errors with optional original exception tracking.

```python
from hydroforge.auxiliary.custom_exceptions import UserConfigLoadException

try:
    config = load_yaml("config.yaml")
except FileNotFoundError as e:
    raise UserConfigLoadException(
        "Configuration file not found",
        original=e,
        show_original=True
    )
```

**Features**:
- Human-friendly error messages
- Original exception preservation
- Pretty-printed logging with Rich formatting
- Optional exception chaining display

**Methods**:
- `log()`: Pretty-print error message with optional original exception

---

### 2. I/O Wrappers ([io_wrappers.py](./io_wrappers.py))

Convenient wrapper functions for file input/output operations.

#### Configuration Loading

```python
from hydroforge.auxiliary.io_wrappers import load_config, read_yaml_config

# Modern approach (recommended)
config = load_config("config.yaml")

# Legacy approach (deprecated)
config = read_yaml_config("config.yaml")
```

**load_config()**:
- Comprehensive error handling with `UserConfigLoadException`
- Handles: FileNotFoundError, PermissionError, UnicodeDecodeError, YAMLError, OSError
- UTF-8 encoding by default

#### Data Saving

```python
from hydroforge.auxiliary.io_wrappers import save_to_json, save_dataframe
import pathlib
import pandas as pd

# Save dictionary to JSON
data = {"sensors": ["S1", "S2", "S3"], "count": 3}
save_to_json(data, pathlib.Path("output.json"), indent=4)

# Save DataFrame to CSV or Excel
df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})

# Automatically creates directory if missing
save_dataframe(df, pathlib.Path("results/data.csv"), create_path_if_missing=True)
save_dataframe(df, pathlib.Path("results/data.xlsx"), create_path_if_missing=True)
```

**save_dataframe()** features:
- Auto-detects format from extension (`.csv`, `.xlsx`, `.xls`)
- CSV uses semicolon (`;`) separator
- Optional automatic directory creation
- Excel files saved to 'Sheet1'

---

### 5. EPANET File Parser ([epanet_file_parser.py](./epanet_file_parser.py))

Parser for EPANET input files.

#### Reading EPANET Files

```python
from hydroforge.auxiliary.epanet_file_parser import EPANETFileParser
from collections import OrderedDict

# Read EPANET input file
model_data: OrderedDict = EPANETFileParser.read_inp_file("network.inp")

# Access sections
junctions = model_data.get("JUNCTIONS", [])
pipes = model_data.get("CONDUITS", [])
```

**Format**:
- Returns `OrderedDict` preserving section order
- Each section maps to a list of tokenized lines
- Automatically removes comments and blank lines
- Sections identified by `[SECTION_NAME]` headers

#### Writing EPANET Files

```python
from hydroforge.auxiliary.epanet_file_parser import EPANETFileParser

# Modify data
model_data["JUNCTIONS"].append(["J1", "100", "0", "0", "0", "0"])

# Write back to file
EPANETFileParser.write_inp_file("modified_network.inp", model_data)
```

#### Error Handling

```python
from hydroforge.auxiliary.exceptions import EPANETFileParserError

try:
    model = read_inp_file("network.inp")
except EPANETFileParserError as e:
    print(f"Parse error: {e}")
```

**EPANETFileParserError**: Raised when file format is invalid (e.g., missing section headers)

#### Command-Line Usage

```bash
# Parse and rewrite EPANET file
python -m hydroforge.auxiliary.epanet_file_parser input.inp output.inp
```

---

### 6. Utilities ([utils.py](./utils.py))

General-purpose utility functions for common tasks.

#### Directory Management

```python
from hydroforge.auxiliary.utils import ensure_directory_exists
import pathlib

# Ensure parent directories exist before saving
file_path = pathlib.Path("outputs/results/data.csv")
ensure_directory_exists(file_path)

# Now safe to save file
with open(file_path, 'w') as f:
    f.write("data")
```

#### Package Resources

```python
from hydroforge.auxiliary.utils import get_package_root, get_package_file

# Get package root directory (useful for accessing test data, configs)
root = get_package_root()
# Returns: /path/to/HydroForge/

# Access packaged data files
network_file = get_package_file("data", "inputs", "base_networks", "L-Town.inp")
# Returns: /path/to/hydroforge/data/inputs/base_networks/L-Town.inp
```

**get_package_root()**: Finds project root by looking for indicators like `setup.py`, `pyproject.toml`, `.git`

#### Logging

```python
from hydroforge.auxiliary.utils import log

log("INFO", "Processing started")
log("WARN", "High memory usage detected")
log("ERROR", "Connection failed")
```

**Features**:
- Timestamp prefixed (YYYY-MM-DD HH:MM:SS)
- Color-coded output (INFO=blue, WARN=yellow, ERROR=red)
- Rich formatting
- Output to stderr

#### Execution Timing

```python
from hydroforge.auxiliary.utils import timer

@timer
def expensive_computation():
    # Long-running operation
    result = sum(range(1000000))
    return result

# Automatically prints:
# ⏱️  expensive_computation() executed in 0.045123 seconds
result = expensive_computation()

# Also works with methods
class DataProcessor:
    @timer
    def process_data(self):
        # Processing logic
        pass

# Prints:
# ⏱️  DataProcessor.process_data() executed in 0.123456 seconds
```

---

## Common Workflows

### Workflow 1: Loading Configuration with Error Handling

```python
from hydroforge.auxiliary.io_wrappers import load_config
from hydroforge.auxiliary.custom_exceptions import UserConfigLoadException
import sys

try:
    config = load_config("user_config.yaml")
    
    # Access configuration
    network_path = config["network"]["path"]
    sensors = config["sensors"]["locations"]
    
except UserConfigLoadException as e:
    e.log()  # Pretty-print with Rich
    sys.exit(1)
```

### Workflow 2: EPANET File Manipulation

```python
from hydroforge.auxiliary.epanet_file_parser import EPANETFileParser
import pathlib

# Read EPANET input
model = EPANETFileParser.read_inp_file("original.inp")

# Modify junctions
for junction in model["JUNCTIONS"]:
    # junction is a list: [name, elevation, ...]
    if junction[0] == "J1":
        junction[1] = "105.0"  # Update elevation

# Add new pipe
model["PIPES"].append([
    "P1",      # Name
    "J1",      # From node
    "J2",      # To node
    "300",     # Length
    "0.5",     # Roughness
    "0",       # InletOffset
    "0",       # OutletOffset
    "0",       # InitFlow
    "0"        # MaxFlow
])

# Write modified model
EPANETFileParser.write_inp_file("modified.inp", model)
```

### Workflow 3: Timed Operations with Logging

```python
from hydroforge.auxiliary.utils import timer, log
from hydroforge.auxiliary.io_wrappers import save_dataframe
import pandas as pd

@timer
def generate_dataset(network_path: str, num_scenarios: int) -> pd.DataFrame:
    log("INFO", f"Generating {num_scenarios} scenarios")
    
    # Expensive computation
    results = []
    for i in range(num_scenarios):
        # Simulate network
        result = simulate_scenario(network_path, scenario=i)
        results.append(result)
    
    df = pd.DataFrame(results)
    log("INFO", f"Generated {len(df)} scenarios")
    return df

# Execute
df = generate_dataset("network.inp", 1000)
# Prints:
# 2025-12-29 10:30:15: INFO: Generating 1000 scenarios
# 2025-12-29 10:30:45: INFO: Generated 1000 scenarios
# ⏱️  generate_dataset() executed in 30.123456 seconds

# Save results
save_dataframe(df, pathlib.Path("results/scenarios.csv"))
```

### Workflow 4: Accessing Package Data

```python
from hydroforge.auxiliary.utils import get_package_root, get_package_file

# Access test networks included with package
test_network = get_package_file("data", "inputs", "base_networks", "Real_network.inp")

# Access configuration templates
config_template = get_package_file("data", "config", "default_config.yaml")

# Build paths relative to package root
root = get_package_root()
output_dir = root / "outputs" / "experiment_1"
output_dir.mkdir(parents=True, exist_ok=True)
```

---

## Integration with Other Modules

### With `hydroforge.graphs`

```python
from hydroforge.graphs.graph import EPANETNetworkGraph
from hydroforge.auxiliary.epanet_file_parser import read_inp_file

# Parse EPANET file
model = EPANETFileParser.read_inp_file("network.inp")

# Create graph from parsed data
network = EPANETNetworkGraph.from_model(model)
```

### With `hydroforge.uncertainty`

```python
from hydroforge.auxiliary.io_wrappers import load_config
from hydroforge.uncertainty.parameters import Parameter
from hydroforge.uncertainty.distributions import NormalDistribution

# Load parameter definitions from config
config = load_config("uncertainty_config.yaml")

# Create uncertain parameters
params = []
for param_name, param_spec in config["parameters"].items():
    dist = NormalDistribution(
        mean=param_spec["mean"],
        std_dev=param_spec["std_dev"]
    )
    param = Parameter(name=param_name, nominal_value=param_spec["nominal"], distribution=dist)
    params.append(param)
```

---

## Error Handling Best Practices

### Configuration Loading

```python
from hydroforge.auxiliary.io_wrappers import load_config
from hydroforge.auxiliary.exceptions import UserConfigLoadException

try:
    config = load_config("config.yaml")
except UserConfigLoadException as e:
    # Log with pretty formatting
    e.log()
    
    # Or handle programmatically
    if "not found" in e.message:
        print("Using default configuration")
        config = get_default_config()
    else:
        raise
```

### EPAENT Parsing

```python
from hydroforge.auxiliary.epanet_file_parser import EPANETFileParser
from hydroforge.auxiliary.exceptions import EPANETFileParserError

try:
    model = EPANETFileParser.read_inp_file("network.inp")
except EPANETFileParserError as e:
    print(f"Invalid EPANET file format: {e}")
    # Optionally validate or repair
except FileNotFoundError:
    print("Network file not found")
```

---

## Type Aliases

```python
from hydroforge.auxiliary.utils import LogType

# LogType = Literal['INFO', 'WARN', 'WARNING', 'ERROR']
```


## License

This module is part of the HydroForge uncertainty injection toolbox.
