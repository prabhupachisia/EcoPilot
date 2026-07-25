from energyplus.runner import EnergyPlusRunner
from telemetry.parser import TelemetryParser
from session import SimulationSessionManager


class DependencyProvider:
    def __init__(
        self,
        energyplus_runner: EnergyPlusRunner | None = None,
        telemetry_parser: TelemetryParser | None = None,
        session_manager: SimulationSessionManager | None = None,
    ) -> None:
        self._energyplus_runner = energyplus_runner or EnergyPlusRunner()
        self._telemetry_parser = telemetry_parser or TelemetryParser()
        self._session_manager = session_manager or SimulationSessionManager()
        

    @property
    def energyplus_runner(self) -> EnergyPlusRunner:
        return self._energyplus_runner

    @property
    def telemetry_parser(self) -> TelemetryParser:
        return self._telemetry_parser

    @property
    def session_manager(self) -> SimulationSessionManager:
        return self._session_manager