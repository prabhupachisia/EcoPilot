from agent.memory import ExperienceStore
from config.settings import BASELINE_IDF, IDD_PATH, WEATHER_FILE
from energyplus.runner import EnergyPlusRunner
from mcp_server.tools.building.manager import BuildingManager
from mcp_server.tools.carbon import CarbonIntensityProfile
from mcp_server.tools.knowledge_base import KnowledgeBase
from telemetry.parser import TelemetryParser
from session import SimulationSessionManager


class DependencyProvider:
    """Constructs and shares the runtime dependencies used by MCP tools.

    building, knowledge_base, experience_memory, and carbon_profile are all
    built lazily on first access instead of in __init__: a BuildingManager
    needs a real IDD file, a KnowledgeBase downloads its embedding model
    over the network, and the other two touch disk. None of that should
    happen just because someone instantiated a DependencyProvider in a test
    that only cares about energyplus_runner.
    """

    def __init__(
        self,
        energyplus_runner: EnergyPlusRunner | None = None,
        telemetry_parser: TelemetryParser | None = None,
        session_manager: SimulationSessionManager | None = None,
        building: BuildingManager | None = None,
        knowledge_base: KnowledgeBase | None = None,
        experience_memory: ExperienceStore | None = None,
        carbon_profile: CarbonIntensityProfile | None = None,
    ) -> None:
        self._energyplus_runner = energyplus_runner or EnergyPlusRunner()
        self._telemetry_parser = telemetry_parser or TelemetryParser()
        self._session_manager = session_manager or SimulationSessionManager()
        self._building = building
        self._knowledge_base = knowledge_base
        self._experience_memory = experience_memory
        self._carbon_profile = carbon_profile

    @property
    def energyplus_runner(self) -> EnergyPlusRunner:
        return self._energyplus_runner

    @property
    def telemetry_parser(self) -> TelemetryParser:
        return self._telemetry_parser

    @property
    def session_manager(self) -> SimulationSessionManager:
        return self._session_manager

    @property
    def building(self) -> BuildingManager:
        if self._building is None:
            self._building = BuildingManager(
                idd_path=IDD_PATH,
                idf_path=BASELINE_IDF,
                weather_file=WEATHER_FILE,
            )
        return self._building

    @property
    def knowledge_base(self) -> KnowledgeBase:
        if self._knowledge_base is None:
            self._knowledge_base = KnowledgeBase()
        return self._knowledge_base

    @property
    def experience_memory(self) -> ExperienceStore:
        if self._experience_memory is None:
            self._experience_memory = ExperienceStore()
        return self._experience_memory

    @property
    def carbon_profile(self) -> CarbonIntensityProfile:
        if self._carbon_profile is None:
            self._carbon_profile = CarbonIntensityProfile()
        return self._carbon_profile