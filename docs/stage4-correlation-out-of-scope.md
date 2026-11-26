# Stage 4 out of scope: correlated uncertainty

Stage 3 samples each uncertain parameter from its own marginal distribution.
The scenario's parameter values are therefore independent unless a caller
constructs a custom sampler outside the Stage 3 specification workflow.

Stage 3 does **not** define or persist a correlation matrix, dependence
structure, copula, multivariate distribution, conditional marginal, or
correlation-aware sampler. A seed makes the selected sampler reproducible; it
does not create or imply dependence between parameters.

Correlated and dependent uncertainty is deferred to Stage 4. That work should
first specify the dependency representation and validation rules, then define
supported sampling transformations and serialization, and finally add
statistical tests for marginal preservation, target dependence, and replay.
Until then, users should not interpret independent Stage 3 realizations as
correlated or physically dependent parameter scenarios.
