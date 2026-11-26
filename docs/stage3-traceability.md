# Stage 3 acceptance traceability

This matrix links the approved Stage 3 acceptance criteria published in the
Stage 3 GitHub issues to their owning tickets, automated evidence, user
documentation, and examples. “Verified” means the
linked local test or example was executed in the listed environment; it does
not imply that optional dependencies are installed in every environment.

| AC | Acceptance criterion | Issues | Test evidence | Documentation | Example evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-01 | Versioned generic specification supports typed parameters, sensor definitions, and sensor-parameter references without backend locations. | [#57](https://github.com/tomjanus/HydroForge/issues/57) | `tests/test_uncertainty_specification_sensors.py`; `tests/test_uncertainty_specification_io.py` | [Workflow](uncertainty-to-simulation.md#1-define-uncertainty-and-sensors) | [WNTR](../examples/wntr_static_uncertainty.py); [PTSNET](../examples/ptsnet_dynamic_uncertainty.py) | Verified |
| AC-02 | Informative uncertainty domains infer parameter type; conflicting explicit types fail. | [#56](https://github.com/tomjanus/HydroForge/issues/56) | `tests/test_uncertainty_parameters.py`; `tests/test_uncertainty_specification_parameters.py` | [Workflow](uncertainty-to-simulation.md#1-define-uncertainty-and-sensors) | [WNTR](../examples/wntr_static_uncertainty.py) | Verified |
| AC-03 | Seeded Sobol/LHS sampling produces repeatable continuous, discrete, categorical, and binary values with metadata. | [#58](https://github.com/tomjanus/HydroForge/issues/58) | `tests/test_sampling_strategies.py` | [Sampling](uncertainty-to-simulation.md#2-sample-reproducible-scenarios) | [WNTR LHS](../examples/wntr_static_uncertainty.py); [PTSNET Sobol](../examples/ptsnet_dynamic_uncertainty.py) | Verified |
| AC-04 | Typed mapper runtime validates mappings, isolates realizations, and returns simulation-ready instances. | [#59](https://github.com/tomjanus/HydroForge/issues/59) | `tests/test_wdn_model_mapping.py`; `tests/test_wdn_parameter_application.py` | [Mapping](uncertainty-to-simulation.md#3-map-each-scenario-to-a-fresh-model) | Both end-to-end examples | Verified |
| AC-05 | WNTR applies supported parameter/status mappings and produces pressure/flow sensor results. | [#60](https://github.com/tomjanus/HydroForge/issues/60), [#61](https://github.com/tomjanus/HydroForge/issues/61) | `tests/test_wntr_model_mapping.py`; `tests/test_wdn_sensor_application.py`; `tests/test_wntr_static_example.py` | [Supported quantities](uncertainty-to-simulation.md#4-run-sensors-against-supported-results) | [WNTR script](../examples/wntr_static_uncertainty.py) and [notebook](../examples/wntr_static_uncertainty.ipynb) | Verified |
| AC-06 | TSNetPlus maps wave speed/surge and captures selected interior quantities. | [#62](https://github.com/tomjanus/HydroForge/issues/62), [#63](https://github.com/tomjanus/HydroForge/issues/63) | `tests/test_tsnetplus_uncertain_model.py`; `tests/test_tsnetplus_interior_measurements.py` | [Dynamic quantities](uncertainty-to-simulation.md#4-run-sensors-against-supported-results) | [TSNetPlus backend example](../examples/simulation/ex2_dynamic_simulation.py) (backend reference; uncertainty path is covered by tests) | Verified |
| AC-07 | PTSNET maps wave speed/surge and selected interior outputs using the common result/sensor contract. | [#64](https://github.com/tomjanus/HydroForge/issues/64), [#65](https://github.com/tomjanus/HydroForge/issues/65) | `tests/test_ptsnet_uncertain_model.py`; [PTSNET feature tests](https://github.com/tomjanus/ptsnet/tree/development/tests); [fork PR #1](https://github.com/tomjanus/ptsnet/pull/1) | [PTSNET support](uncertainty-to-simulation.md#limitations) | [PTSNET script](../examples/ptsnet_dynamic_uncertainty.py) and [notebook](../examples/ptsnet_dynamic_uncertainty.ipynb) | Verified |
| AC-08 | Saved realizations reload as runnable instances with mapping, sensor, settings, and provenance intact. | [#66](https://github.com/tomjanus/HydroForge/issues/66), [#67](https://github.com/tomjanus/HydroForge/issues/67) | `tests/test_uncertain_model_persistence.py`; dynamic PTSNET execution tests in `tests/test_ptsnet_dynamic_example.py` | [Persistence](uncertainty-to-simulation.md#5-save-and-reload-a-realization) | Both examples save and rerun one bundle | Verified |
| AC-09 | WNTR and PTSNET Python/notebook pairs run multiple realizations and plot raw versus measured flow. | [#68](https://github.com/tomjanus/HydroForge/issues/68), [#69](https://github.com/tomjanus/HydroForge/issues/69) | `tests/test_wntr_static_example.py`; `tests/test_ptsnet_dynamic_example.py` | [Examples](uncertainty-to-simulation.md) | Both `.py` and `.ipynb` pairs; PTSNET notebook executed in a compatible kernel | Verified |
| AC-10 | Every acceptance criterion has ticket, test, documentation, and example evidence. | [#70](https://github.com/tomjanus/HydroForge/issues/70) | This matrix | This matrix and [workflow guide](uncertainty-to-simulation.md) | Linked per criterion above | Verified |
| AC-11 | Local quality gates pass; Stage 3 issues are closed; work is pushed and CI is green. | [#70](https://github.com/tomjanus/HydroForge/issues/70) | Final command and CI results recorded below | This matrix | Both end-to-end examples executed | Verified |

## Local verification record

On Python 3.11/NumPy 2.4, `PYTHONPATH=src pytest -o addopts=''` completed with
**497 passed** and two upstream PTSNET `RankWarning`s. The PTSNET script tests
ran real simulations and persistence round trips. The upstream PTSNET suite
passed **19 tests** in both Python 3.11/NumPy 2 and Python 3.9 integration
environments.

Local quality gates passed: `black --check .` (144 Python files; notebooks are
validated/executed separately), `flake8 --config=.flake8 .`, `mypy .`, and
`python -m build`. Distribution metadata validation and a relative Markdown
link check also passed. Both notebooks were executed in compatible Jupyter
kernels and displayed their flow comparisons; PTSNET used Python 3.10.
HydroForge [PR #71](https://github.com/tomjanus/HydroForge/pull/71) is pushed;
its [required CI checks](https://github.com/tomjanus/HydroForge/pull/71/checks)
pass lint/type checks, tests on Python 3.10–3.13, and package build/metadata
checks. PTSNET feature commit `d8b0855` is merged into
[`tomjanus/ptsnet:development`](https://github.com/tomjanus/ptsnet/tree/development)
by [fork PR #1](https://github.com/tomjanus/ptsnet/pull/1). The mistaken PR on
the original repository was closed in favor of the fork PR; its `development`
branch was not changed.
