# Uncertainty specification serialization and validation

HydroForge needs a model-independent way to describe sensor uncertainty (and, later,
parameter uncertainty) in `.json`/`.yaml` documents. We decided on 2026-11-18 to
represent a specification as Pydantic v2 models (`UncertaintySpecification`,
`SensorDefinition`) with an explicit registry mapping `type` names to
`hydroforge.measurements` sensor classes, a required `schema_version`, and
dictionary/JSON/YAML I/O behind `load_specification`/`save_specification`.
Validation runs at construction and load time and raises a `SpecificationError`
hierarchy with dotted paths; Pydantic's own `ValidationError` is wrapped at the
boundary so callers only see the public exception family.

## Considered options

- Plain dataclasses with hand-written `to_dict`/`from_dict`: no new dependency, but
  more boilerplate and no JSON Schema generation.
- Pydantic v2: validated models, `model_validate`/`model_dump`, and JSON Schema;
  adds a mandatory runtime dependency.
- Pydantic plus Pandera: Pandera targets tabular data validation, not nested
  documents, so it would not remove any of the custom registry or parameter
  validation logic.

## Consequences

- `pydantic>=2.0,<3` is a mandatory runtime dependency declared in `pyproject.toml`
  and `requirements.txt`.
- The specification stores declarative definitions, not live `Sensor` instances;
  `SensorDefinition.create_sensor()` is the construction seam.
- The registry is an explicit allowlist; a document can never import an arbitrary
  class.
- Canonical output uses the `sensors` key and short type names; `measurements` and
  full class names (`FixedPrecisionSensor`) are accepted input aliases.
