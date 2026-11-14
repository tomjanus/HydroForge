# Auxiliary Module

Utility functions, file I/O helpers, and error types shared across HydroForge.

---

## Module Structure

```
auxiliary/
├── __init__.py          # Re-exports the public helpers below
├── exceptions.py        # UserConfigLoadException
├── io.py                # load_config, save_to_json, save_dataframe, save_pickle, read_pickle
├── logging_utils.py     # LoggingConfig, get_logger, configure_logging, set_log_level
├── utils.py             # ensure_directory_exists, get_package_file, get_package_root, log, timer
└── README.md
```

All public names are re-exported from `hydroforge.auxiliary`, so either
`from hydroforge.auxiliary import load_config` or
`from hydroforge.auxiliary.io import load_config` works.

---

## Exceptions

### `UserConfigLoadException`

Wraps configuration-file failures (missing file, permissions, encoding,
YAML syntax, generic I/O) in a single user-friendly exception.

```python
from hydroforge.auxiliary import UserConfigLoadException

try:
    config = load_config("config.yaml")
except UserConfigLoadException as exc:
    exc.log()          # rich-formatted message to the console
    raise
```

Constructor: `UserConfigLoadException(message, original=None, *, show_original=False)`.
The `original` exception is included in `str()` and `log()` output when
`show_original=True`.

> `exceptions.py` currently defines only `UserConfigLoadException`. There is no
> `EPANETFileParserError`; EPANET parsing lives in `hydroforge.epanetfile_io`.

---

## File I/O (`io.py`)

### `load_config(file_path) -> dict`

Load a YAML configuration file with UTF-8 encoding. Raises
`UserConfigLoadException` for `FileNotFoundError`, `PermissionError`,
`UnicodeDecodeError`, `yaml.YAMLError`, and `OSError`.

```python
from hydroforge.auxiliary import load_config

config = load_config("config.yaml")
```

Note: `yaml.safe_load` returns `None` for an empty file; the return type
annotation is `dict`, so callers should validate content when empty files are
possible.

### `save_to_json(data, filepath, indent=4) -> None`

Serialize a dictionary to JSON. Parent directories are **not** created
automatically.

```python
import pathlib
from hydroforge.auxiliary import save_to_json

save_to_json({"count": 3}, pathlib.Path("output.json"), indent=2)
```

### `save_dataframe(df, filename, create_path_if_missing=True) -> None`

Save a pandas `DataFrame`, choosing the format from the extension:

| Extension | Behaviour |
|-----------|-----------|
| `.csv` | Semicolon separator, `index=False` |
| `.xlsx`, `.xls` | Sheet name `Sheet1`, `index=False` |

Any other extension raises `ValueError`. When `create_path_if_missing=True`
(the default) missing parent directories are created.

```python
import pathlib
import pandas as pd
from hydroforge.auxiliary import save_dataframe

df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
save_dataframe(df, pathlib.Path("results/data.csv"))
```

### `save_pickle(obj, path, *, create_parent=True) -> pathlib.Path`

Serialize an object with the highest pickle protocol. Returns the destination
path. `pickle.PicklingError` is re-raised as `TypeError`; write failures raise
`OSError`.

```python
from hydroforge.auxiliary import save_pickle

path = save_pickle({"state": 1}, "checkpoints/run1.pkl")
```

### `read_pickle(path) -> Any`

Deserialize a pickle file. Raises `FileNotFoundError`, `OSError`, or
`pickle.UnpicklingError`.

```python
from hydroforge.auxiliary import read_pickle

state = read_pickle("checkpoints/run1.pkl")
```

> Pickle files execute arbitrary code on load. Only read files you trust.

---

## Logging (`logging_utils.py`)

### `LoggingConfig`

Dataclass with fields `level="INFO"`, `rich=True`, `rich_tracebacks=True`,
`show_path=False`, `format="%(message)s"`.

### `get_logger(name=None) -> logging.Logger`

Return the package root logger when `name` is `None`. Names beginning with
`hydroforge` are returned directly; other names become children of the package
logger.

```python
from hydroforge.auxiliary import get_logger

logger = get_logger(__name__)
logger.info("starting")
```

### `configure_logging(config=None) -> None`

Attach a handler to the `hydroforge` logger. Uses `rich.logging.RichHandler`
when available (falling back to `logging.StreamHandler`), and sets
`propagate = False`. Repeated calls are safe: if a handler is already
configured, only the level is updated.

```python
from hydroforge.auxiliary import LoggingConfig, configure_logging

configure_logging(LoggingConfig(level="DEBUG", rich=False))
```

### `set_log_level(level) -> None`

Set the package logger level from a string or numeric level.

```python
from hydroforge.auxiliary import set_log_level

set_log_level("WARNING")
```

---

## Utilities (`utils.py`)

### `ensure_directory_exists(file_path) -> None`

Create the parent directories of `file_path` (`parents=True, exist_ok=True`).

### `get_package_file(*folders) -> pathlib.Path`

Resolve a packaged data path using `importlib.resources`. The result is
resolved to an absolute path.

```python
from hydroforge.auxiliary import get_package_file

network = get_package_file("data", "inputs", "base_networks", "L-Town.inp")
```

### `get_package_root() -> pathlib.Path`

Return the project root (two levels above `src/hydroforge`). Raises
`FileNotFoundError` if none of `setup.py`, `setup.cfg`, `pyproject.toml`,
`requirements.txt`, or `.git` is found. This assumes the standard
`src/hydroforge` layout.

### `log(log_type, msg) -> None`

Print a timestamped, colour-coded message to **stderr** via `rich`.
`log_type` is one of `INFO`, `WARN`, `WARNING`, `ERROR` (`LogType` alias).

```python
from hydroforge.auxiliary import log

log("INFO", "processing started")
```

### `timer(func)`

Decorator that prints the wall-clock execution time using
`time.perf_counter()` and preserves the wrapped function's metadata.

```python
from hydroforge.auxiliary import timer

@timer
def expensive() -> int:
    return sum(range(1_000_000))
```

---

## Related Modules

- EPANET `.inp` parsing and writing: `hydroforge.epanetfile_io`
- Network graph construction: `hydroforge.graphs`
- Sampling and uncertainty: `hydroforge.sampling` (requires `SALib`)

---

## License

Part of the HydroForge uncertainty injection toolbox. See the repository
`LICENSE` file.
