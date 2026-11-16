# Networks Module

Selection helpers for WNTR network components and a container for junction
leakage data.

---

## Module Contents

```
networks/
├── __init__.py                          # Empty; import from the submodules below
├── junction_leaks.py                    # JunctionLeaks
├── network_model_component_selectors.py # Selector classes for WNTR models
└── README.md
```

Import paths:

```python
from hydroforge.wdn_modelling.networks.junction_leaks import JunctionLeaks
from hydroforge.wdn_modelling.networks.network_model_component_selectors import (
    PipeNameSelector,
    DiameterThresholdSelector,
    ModelComponentSelector,
)
```

> Model and graph **modifiers** are not part of this package. They live in
> `hydroforge.wdn_modelling.modifiers` (see [Modifiers](#modifiers) below).
> There is no `NetworkDataAccessor` in the current source tree.

---

## Component selectors

All model selectors implement the `IComponentSelector` protocol:

```python
def select(self, wn: WNTRNetworkModel, candidates: Iterable[T] | None) -> List[T]
```

`wn` is a `wntr.network.WaterNetworkModel`. `candidates` restricts the search to
a pre-selected set; `None` means all components of the relevant type. Each
selector accepts `text_logging` and `structured_logging` flags.

| Class | Constructor fields | Selects |
|-------|--------------------|---------|
| `PipeNameSelector` | `names` | Pipes whose IDs are in `names` |
| `AttributeSelector` | `predicate`, `component_type` (`"pipe"`, `"node"`, `"valve"`) | Components for which `predicate(component)` is true |
| `DiameterThresholdSelector` | `max_diameter` | Pipes with diameter `<= max_diameter` |
| `RandomFractionSelector` | `fraction`, `random_state` | A random fraction of candidates |
| `AvoidBridgesSelector` | `iterative_search` | Pipes that are not bridges (preserves connectivity) |
| `NodeNameSelector` | `names` | Nodes whose IDs are in `names` |
| `ElevationThresholdSelector` | `min_elevation` | Nodes with elevation `>= min_elevation` |
| `MinimumDemandSelector` | `min_demand` | Nodes with base demand `>= min_demand` |
| `ValveNameSelector` | `names` | Valves whose IDs are in `names` |
| `ValveTypeSelector` | `valve_type` | Valves of a given type (e.g. `"PRV"`) |

Selectors can be chained with `ModelComponentSelector`:

```python
from hydroforge.wdn_modelling.networks.network_model_component_selectors import (
    DiameterThresholdSelector,
    ModelComponentSelector,
    PipeNameSelector,
)

selector = ModelComponentSelector(selectors=[
    PipeNameSelector(names=["P1", "P2", "P3"]),
    DiameterThresholdSelector(max_diameter=0.2),
])
selected = selector.select(wn, initial_candidates=list(wn.pipe_name_list))
```

`ModelComponentSelector` exposes `text_log`, `structured_log`,
`add_selector(...)`, and `select(wn, initial_candidates)`.

Graph component selectors are not implemented; the implemented selectors live in
`network_model_component_selectors.py`.

---

## JunctionLeaks

`JunctionLeaks` is a mutable mapping from junction name to leak size. The
default `unit` is `"m³/s"`.

```python
from hydroforge.wdn_modelling.networks.junction_leaks import JunctionLeaks

leaks = JunctionLeaks()
leaks.add_leak("J1", 0.05)      # add or increment
leaks["J2"] = 0.02              # mapping-style assignment
leaks.remove_leak("J1", 0.01)   # decrement; removes the entry when it reaches 0

print(leaks.total_leakage)
print("J1" in leaks)
print(leaks.to_dataframe())
```

| Member | Behaviour |
|--------|-----------|
| `add_leak(junction, size)` | Add or increment a leak |
| `remove_leak(junction, size)` | Decrement; deletes the entry at zero |
| `from_lists(junctions, sizes)` | Build from parallel sequences or one size for all |
| `to_dict()` | Shallow copy of the mapping |
| `to_dataframe()` | Two columns: `junction`, `leak_size` |
| `to_json(indent=2)` | Return a JSON **string** |
| `from_json(json_str)` | Parse a JSON string |
| `total_leakage` | Sum of all leak sizes |
| `is_empty()` | Return True when no leaks are stored |
| `unit` | Optional unit label |

`to_json` returns a string; write it to a file yourself if persistence is
required. There are no `to_csv` / `from_csv` methods.

---

## Modifiers

Modification classes moved to `hydroforge.wdn_modelling.modifiers`:

- `hydroforge.wdn_modelling.modifiers.network_model_modifier`:
  `WNTRNetworkModifier`, `NetworkModifierPipeline`, `PipeDiameterModifier`,
  `PipeDiameterMultiplierModifier`, `PipeRoughnessModifier`,
  `NodeDemandModifier`, `NodeDemandDataFrameModifier`, `NodeLeakageModifier`,
  `NodeEmitterModifier`, `ValveModifier`, `NetworkPipeRemover`
- `hydroforge.wdn_modelling.modifiers.network_graph_modifier`:
  `NetworkGraphPipeRemover`
- `hydroforge.wdn_modelling.modifiers.common`: `PipeNotFoundException`,
  `BridgeRemovalException`

See [`../modifiers/`](../modifiers/) for the implementation.

---

## Related documentation

- EPANET `.inp` parsing: `hydroforge.wdn_modelling.epanetfile_io`
- Graph representation: `hydroforge.wdn_modelling.graphs`
- Sensor placement: `hydroforge.wdn_modelling.measurement_placement`

---

## License

Part of the HydroForge uncertainty injection toolbox. See the repository
`LICENSE` file.
