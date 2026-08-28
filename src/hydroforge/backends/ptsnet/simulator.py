""" """
from dataclasses import dataclass
from .model import PTSNetNetworkModel
from .results import PTSNetSimulationResults
from .config import PTSNetConfig
from ..common.simulator import Simulator


@dataclass(slots=True)
class PTSNetSimulator(Simulator[PTSNetNetworkModel, PTSNetSimulationResults, PTSNetConfig]):
    """PTSNet simulator strategy."""

    def __init__(self, config: PTSNetConfig | None = None) -> None:
        self.config = config or PTSNetConfig()

    def configure(self, config: PTSNetConfig) -> None:
        self.config = config
        
    def initialize(self) -> None:
        """Initialize the simulator before running a simulation.
        This method generally applies to dynamic simulators such as TSnet, or PTSNet"""
        pass

    def run(self, model: PTSNetNetworkModel) -> PTSNetSimulationResults:
        self.config.apply_to(model)
        model.run()
        return PTSNetSimulationResults(model)