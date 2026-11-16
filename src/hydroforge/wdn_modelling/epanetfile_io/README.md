# epanetfile_io Module

---

## Overview

This module provides everything needed to read, modify, and write EPANET
`.inp` files **without relying on external simulation packages such as
WNTR**. It is organized in five files, each with a single responsibility:

- **`file_io.py`** — Low-level parser that reads a raw `.inp` file into an
  `OrderedDict` of tokenized section rows, and writes such a dict back to a
  `.inp` file.
- **`mixins.py`** — Reusable mixins shared by the dataclasses in
  `components.py`: generic list ⇄ dataclass conversion, and automatic
  coercion of assigned values into `Decimal`.
- **`components.py`** — The dataclass definitions themselves (one per
  EPANET section — `Junction`, `Pipe`, `Pump`, `Valve`, etc.).
- **`model_wrapper.py`** — The generic `NetworkCollection[T]` container and
  the `EPANETNetworkModel` aggregate, giving convenient, typed attribute
  access (e.g. `junction.elevation`) instead of raw index-based list access
  (e.g. `junction[1]`).
- **`model_io.py`** — Serialization and file I/O for `EPANETNetworkModel`:
  converting to/from plain dictionaries, JSON files, and `.inp` files.

---

## Module Structure

```
epanetfile_io/
├── __init__.py              # Package initialization / public exports
├── file_io.py               # Low-level EPANET .inp file parser/writer
├── mixins.py                # ListConversionMixin, AutoDecimalMixin
├── components.py            # Dataclass definitions for EPANET INP sections
├── model_wrapper.py         # NetworkCollection[T] and EPANETNetworkModel
├── model_io.py               # Serialization / file I/O for the model
└── README.md                # This file
```

---

## Core Components

### 1. Low-level file I/O ([file_io.py](./file_io.py))

`EPANETFileIO` reads and writes raw EPANET input files.

```python
from hydroforge.wdn_modelling.epanetfile_io.file_io import EPANETFileIO
from collections import OrderedDict

# Read EPANET input file
model_data: OrderedDict = EPANETFileIO.read_inp_file("network.inp")

# Access sections (raw tokenized rows)
junctions = model_data.get("JUNCTIONS", [])
pipes = model_data.get("PIPES", [])

# Write back to file
EPANETFileIO.write_inp_file("output.inp", model_data)
```

**Format**:
- Returns `OrderedDict` preserving section order
- Each section maps to a list of tokenized lines (`list[list[str]]`)
- Automatically removes comments and blank lines
- Sections identified by `[SECTION_NAME]` headers
- Raises `EPANETFileReaderError` (also exported from this module) if a
  section header is expected but not found

This is a thin, low-level layer — values are always raw strings and there
is no notion of individual network components (junctions, pipes, etc.). For
most use cases, prefer the typed model described below.

---

### 2. Conversion mixins ([mixins.py](./mixins.py))

`mixins.py` provides the machinery that lets the dataclasses in
`components.py` convert automatically between raw INP tokens and typed
Python values, without each class having to implement its own conversion
logic.

- **`ListConversionMixin`** — Implements generic `to_list()`/`from_list()`
  methods for any dataclass. `from_list()` builds an instance from a list of
  raw (typically string) tokens, coercing values into `int`/`float`/
  `Decimal` wherever the corresponding dataclass field is annotated as such
  (fields may be omitted from the input list if the trailing fields declare
  defaults). `to_list()` performs the reverse conversion, formatting numeric
  fields back to strings and trimming trailing empty fields.
- **`AutoDecimalMixin`** — Automatically converts any value assigned to a
  `Decimal`-annotated field into a `Decimal` instance, both at construction
  time and on later attribute assignment (e.g. `junction.elevation = 105.0`
  is stored as `Decimal('105.0')`). This keeps numeric fields consistently
  typed even when callers assign plain `int`/`float`/`str` values.

Both mixins resolve field types via `typing.get_type_hints()` rather than
`dataclasses.fields()[i].type` directly, since `components.py` uses
`from __future__ import annotations` (which turns raw field annotations into
unresolved strings).

Most network item dataclasses combine both mixins:
`class Junction(AutoDecimalMixin, ListConversionMixin): ...`.

---

### 3. Dataclass definitions ([components.py](./components.py))

`components.py` defines one `@dataclass(slots=True)` per EPANET section:

| Class | Section | Notes |
|---|---|---|
| `TitleLine` | `[TITLE]` | Stores tokens verbatim |
| `Junction` | `[JUNCTIONS]` | `elevation`, `base_demand`: `Decimal` |
| `Reservoir` | `[RESERVOIRS]` | `head`: `Decimal` |
| `Tank` | `[TANKS]` | All measurement fields: `Decimal` |
| `Pipe` | `[PIPES]` | `length`, `diameter`, `roughness`, `minor_loss`: `Decimal` |
| `Pump` | `[PUMPS]` | `keyword`/`value` kept as `str` (may reference a curve ID) |
| `Valve` | `[VALVES]` | `diameter`, `minor_loss`: `Decimal`; `type`/`setting` kept as `str` |
| `Demand` | `[DEMANDS]` | `base_demand`: `Decimal` |
| `Pattern` | `[PATTERNS]` | Variable-length multiplier list |
| `Curve` | `[CURVES]` | `x_value`, `y_value`: `Decimal` |
| `Control` | `[CONTROLS]` | Variable-length token tuple |
| `Coordinate` | `[COORDINATES]` | `x_coord`, `y_coord`: `Decimal` |
| `TokenizedLine` (+ `Energy`, `Reaction`, `Time`, `Report`, `Option`, `Backdrop`) | `[ENERGY]`, `[REACTIONS]`, `[TIMES]`, `[REPORT]`, `[OPTIONS]`, `[BACKDROP]` | Generic keyword/value lines with a variable token count |

Numeric fields are typed as `Decimal` (not `float`/`str`) to preserve the
precision of values read from and written to EPANET input files. Classes
implementing `to_list()`/`from_list()` do so either via `ListConversionMixin`
(fixed-schema records) or by storing their tokens verbatim as a `tuple`
(variable-length records such as `TitleLine`, `Pattern`, `Control`, and
`TokenizedLine`).

---

### 4. Typed network model ([model_wrapper.py](./model_wrapper.py))

`model_wrapper.py` builds on the dataclasses from `components.py` and
provides two container types:

- **`NetworkCollection[T]`** — A generic, lazily-converting, list-like
  collection of items of type `T`. Items are stored internally as raw
  tokenized rows and converted to dataclass instances on first access;
  converted instances are cached and become the source of truth for later
  serialization, so in-place attribute mutations are correctly persisted.
  Implements the `MutableSequence` protocol (indexing, slicing, `append`,
  `insert`, `del`, iteration) plus helpers: `get_by_field`,
  `get_index_by_field`, `modify_by_field`.
- **`EPANETNetworkModel`** — A `@dataclass(slots=True)` aggregating one
  `NetworkCollection` per EPANET section (`junctions`, `pipes`, `pumps`,
  `valves`, `tanks`, `reservoirs`, `patterns`, `curves`, `controls`,
  `coordinates`, etc.), plus plain `list` fields for sections without a
  dedicated dataclass (`tags`, `status`, `rules`, `emitters`, `quality`,
  `sources`, `mixing`, `vertices`, `labels`). Provides collection-name/
  field-value based helper methods: `get_item_by_index`,
  `get_item_by_field_value`, `get_item_index_by_field_value`,
  `modify_item_by_field_value`. The class-level `COLLECTION_MAPPINGS` and
  `LIST_FIELD_MAPPINGS` tuples of `FieldMapping(section, attr_name,
  item_type)` drive the conversions performed by `model_io.py`.

```python
from hydroforge.wdn_modelling.epanetfile_io.model_io import EPANETNetworkModelIO

# Load a network (see model_io.py below for file I/O)
network = EPANETNetworkModelIO.from_inp_file("network.inp")

# Typed, named attribute access
junction = network.junctions[0]
print(junction.id, junction.elevation, junction.base_demand)

# Modify in place — the change is reflected on save
junction.elevation = 100.0  # coerced to Decimal('100.0') via AutoDecimalMixin

# Look up and modify items by field value
network.junctions.modify_by_field("id", "J1", elevation=105.0)
found = network.junctions.get_by_field("id", "J1")

# Or via EPANETNetworkModel's collection-name based helpers
network.modify_item_by_field_value("junctions", "id", "J1", elevation=105.0)

# Collections behave like lists
for pipe in network.pipes:
    if pipe.diameter < 100:
        pipe.diameter = 150.0
```

---

### 5. Serialization and file I/O ([model_io.py](./model_io.py))

`EPANETNetworkModelIO` converts between `EPANETNetworkModel` and external
representations (dictionaries, JSON files, `.inp` files). This
responsibility is intentionally kept separate from `EPANETNetworkModel`
itself, which focuses only on representing and manipulating data already
in memory.

```python
from hydroforge.wdn_modelling.epanetfile_io.model_io import EPANETNetworkModelIO

# Read an .inp file directly into a typed model
network = EPANETNetworkModelIO.from_inp_file("network.inp")

# ... inspect / modify network ...

# Save back to an .inp file
EPANETNetworkModelIO.to_inp_file(network, "modified_network.inp")

# JSON round-trip is also supported
network = EPANETNetworkModelIO.from_json_file("network.json")
EPANETNetworkModelIO.to_json_file(network, "network.json")

# Dict conversion (e.g. for custom serialization)
data = EPANETNetworkModelIO.to_dict(network)
network2 = EPANETNetworkModelIO.from_dict(data)
```

**Note**: `to_dict()` always appends a trailing `END` section (mirroring
the `[END]` marker every valid EPANET `.inp` file ends with), so that files
written by `to_inp_file()` can be reliably re-parsed by `EPANETFileIO`.

---

## Common Workflow: Read, Modify, Save

```python
from hydroforge.wdn_modelling.epanetfile_io.model_io import EPANETNetworkModelIO
from hydroforge.wdn_modelling.epanetfile_io.components import Pipe

# Read the .inp file straight to a typed, mutable model — no WNTR needed
network = EPANETNetworkModelIO.from_inp_file("original.inp")

# Modify a junction's elevation
junction = network.junctions.get_by_field("id", "J1")
if junction is not None:
    junction.elevation = 105.0

# Add a new pipe
network.pipes.append(
    Pipe(id="P1", start_node="J1", end_node="J2", length=300.0,
         diameter=0.5, roughness=100.0, minor_loss=0.0, status="Open")
)

# Save the modified network back to a valid EPANET .inp file
EPANETNetworkModelIO.to_inp_file(network, "modified.inp")
```

A complete, runnable version of this workflow — covering both JSON and
`.inp` files, plus round-trip validation — is available in
[`examples/epanetfile_io/ex1.py`](../../../examples/epanetfile_io/ex1.py).

---

## License

This module is part of the HydroForge uncertainty injection toolbox.
