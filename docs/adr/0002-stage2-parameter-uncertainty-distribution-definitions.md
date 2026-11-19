# Stage 2: parameter, uncertainty, and distribution definitions in specification documents

## Status

Accepted (2026-11-19). Extends ADR-0001; resolves the design questions recorded in issue #28.

## Context

Stage 1 established model-independent uncertainty specification documents for
sensors: Pydantic v2 declarative models, allow-listed type registries, the
`SpecificationError` validation family with dotted paths, and dict/JSON/YAML
round-tripping (ADR-0001). The Stage 2 fix phase (#35) repaired the runtime
`hydroforge.uncertainty` defects that blocked extension. A design session then
settled the following decisions, which this record captures.

## Decision

1. **Definition-only boundary.** Documents serialize declarative definitions
   only. Runtime state — sampled values, locks, empirical caches, generator
   objects — is never serialized in either direction. Live objects are built
   through registries, mirroring `SensorDefinition.create_sensor()`.
2. **Registry granularity.** One registry entry per concrete class. Canonical
   short names drop the class suffix (`NormalDistribution` → `Normal`,
   `AdditiveUncertainty` → `Additive`); full class names are accepted as input
   aliases. The generic `DiracDeltaDistribution` is **not** exposed
   (unserializable without a type tag); only `ContinuousDiracDelta`,
   `DiscreteDiracDelta`, and `CategoricalDiracDelta` enter the registry.
3. **Nesting.** `ParameterDefinition` nests an uncertainty definition, which
   nests distribution definitions — tagged `{type, parameters}` objects
   validated recursively, reusing the `Composite`-sensor pattern. No
   hand-written typed Pydantic models per nesting level.
4. **Canonicalization.** Documents carry JSON-native values only: lists where
   `tuple` fields are accepted; `ParameterType` as member-name strings; NumPy
   scalars coerced to Python scalars on load; int-where-float accepted; bools
   and numeric strings rejected in numeric constructor slots — except
   `nominal_value`, where a JSON bool is legitimate (infers `BINARY`, #30).
   `rtol` stays a `ClassVar` and is not a document parameter; the misleading
   `rtol`/`mean` docstrings (findings A2/A3) are corrected.
5. **Seed policy.** Uncertainty definitions whose constructors take a live
   `Generator` (`BinaryStateFlipUncertainty.rng`) expose `seed: int | null`
   in documents instead; the registry adapter builds
   `numpy.random.default_rng(seed)` at construction (`null`/absent →
   nondeterministic). No runtime constructor signatures change. Precedent:
   `RandomNoiseSensor.seed` from Stage 1.
6. **Schema version.** No version bump: parameter sections are validated
   under `schema_version: "1.0"` like everything else. Documents that
   previously had a pass-through `parameters` section now interpret it;
   that strictification is accepted.
7. **Arithmetic rule symmetry.** Discrete-parameter rules (division, integer
   multiplier) are enforced on `Parameter` operands in either position,
   matching the categorical/binary handling ("regardless of operand order").
   Lands as a runtime fix ticket within the Stage 2 ticket set.
8. **Sampling consistency.** Locked sampling (per-parameter value until
   `reset()`) is the only consistency model. Per-evaluation-context caching
   (the deleted `SampleCache` idea) is dropped; if scenario generation ever
   needs coordinated multi-parameter sessions, that belongs to the scenario
   layer.
9. **Exception families stay layered.** Document/load failures use the
   `SpecificationError` family with dotted paths. Runtime
   `TheoreticalCDFAbsent`/`CDFNotAvailable` stay runtime-only. No split of
   the runtime `Parameter` dataclass (A6) and no equality changes (T4) —
   the spec-layer definition *is* the declarative model.
10. **Public API.** `UncertaintySpecification.parameters:
    dict[str, ParameterDefinition]`; `create_parameter(name)` is the
    construction seam; distribution/uncertainty construction stays
    package-internal; `load_specification`/`save_specification`/
    `json_schema()` entry points unchanged in shape.
11. **`model` stays a pass-through.** The component→property mapping is
    scenario-layer data (spec/0001); Stage 2 makes only `parameters` real.
    Authors can already stage bindings in `model` because it is echoed
    verbatim.
12. **Canonicalization over preservation.** Histogram-like distributions
    normalize probabilities and sort values at construction; document output
    is canonical, not input-representation-preserving. The round-trip
    guarantee: load → object → dict is equality-stable, and save → load →
    save is byte-stable from the first canonical save onward.
13. **No named definition pools.** All distribution/uncertainty definitions
    are inline; reuse is the author's concern (e.g. YAML anchors).
14. **`ParameterDefinition` field contract.** Mapping key is the parameter
    name. Required: `nominal_value` (`string | number | bool`). Optional:
    `uncertainty` (defaults to `No`), `type` (absent → construction-time
    inference; explicit → honored), `infer_type_from_data`, `metadata`
    (accepted verbatim). Python `Enum` nominal values are not documentable.
15. **Validation depth mirrors Stage 1.** Load validates document shape —
    keys, types, required-ness, registry membership — via constructor
    introspection. Semantic rules (`std_dev > 0`, `flip_prob ∈ [0, 1]`,
    distinct states) live in runtime `__post_init__` and fire at
    `create_parameter`, unwrapped. This avoids duplicating every numeric
    constraint in the validator.

## Consequences

- The extension phase reuses every Stage 1 mechanism; the new surface is the
  three registries, the recursive tagged-definition validator, the seed
  adapter, and `ParameterDefinition`/`create_parameter`.
- Existing documents carrying an inert `parameters` section start validating
  (possibly failing) on load — accepted under decision 6.
- The arithmetic-symmetry change (7) and docstring corrections (4) ride in
  the Stage 2 ticket set, keeping runtime fixes traceable with the design
  that motivated them.
- Scenario generation remains a separate initiative; it will decide what the
  `model` section means.
