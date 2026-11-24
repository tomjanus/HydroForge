"""WNTR implementation of the Stage 3 model mapper."""

from __future__ import annotations

import copy
from typing import Any, Callable, Sequence

from wntr.network import WaterNetworkModel as WNTRModel

from hydroforge.wdn_modelling.backends.wntr import WNTRSimulator
from hydroforge.wdn_modelling.backends.wntr.results import WNTRSimulationResults
from hydroforge.wdn_modelling.mapping import (
    GenericModelMapper,
    UncertainModel,
)
from hydroforge.uncertainty.specification import UncertaintySpecification
from .parameters import (
    WNTRParameterAdapter,
    WNTRParameterBinding,
)


class WNTRModelMapper(GenericModelMapper[WNTRModel, WNTRSimulationResults]):
    """Map one sampled scenario to a fresh WNTR model."""

    def __init__(
        self,
        parameter_bindings: Sequence[WNTRParameterBinding] = (),
        bindings: Sequence[WNTRParameterBinding] = (),
        simulator: Any | None = None,
        clone_model: Callable[[WNTRModel], WNTRModel] | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_bindings = tuple(
            parameter_bindings or bindings or kwargs.get("bindings", ())
        )
        self.parameter_bindings = resolved_bindings
        self._simulator = simulator
        self._parameter_adapter = WNTRParameterAdapter(self.parameter_bindings)

        def apply(
            model: WNTRModel, scenario: Any, specification: UncertaintySpecification
        ) -> None:
            values = getattr(scenario, "values", scenario)
            self._parameter_adapter.apply(model, values)

        def run(model: WNTRModel) -> WNTRSimulationResults:
            active_simulator = self._simulator
            if active_simulator is None:
                active_simulator = WNTRSimulator()
            return active_simulator.run(model)

        super().__init__(
            clone_model=clone_model or copy.deepcopy,
            apply_parameters=apply,
            run_model=run,
        )

    def map(
        self,
        specification: UncertaintySpecification,
        model: WNTRModel,
    ) -> UncertainModel[WNTRModel, WNTRSimulationResults]:
        return super().map(specification, model)


__all__ = [
    "WNTRModel",
    "WNTRModelMapper",
]
