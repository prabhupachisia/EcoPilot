from unittest.mock import Mock

from mcp_server.dependencies import DependencyProvider
from mcp_server.tools.building.manager import BuildingManager
from mcp_server.tools.knowledge_base import KnowledgeBase


def test_energyplus_runner_and_session_manager_are_default_constructed() -> None:
    dependencies = DependencyProvider()

    assert dependencies.energyplus_runner is not None
    assert dependencies.telemetry_parser is not None
    assert dependencies.session_manager is not None


def test_injected_dependencies_are_returned_as_is() -> None:
    runner = Mock()
    parser = Mock()
    session_manager = Mock()
    building = Mock(spec=BuildingManager)
    knowledge_base = Mock(spec=KnowledgeBase)

    dependencies = DependencyProvider(
        energyplus_runner=runner,
        telemetry_parser=parser,
        session_manager=session_manager,
        building=building,
        knowledge_base=knowledge_base,
    )

    assert dependencies.energyplus_runner is runner
    assert dependencies.telemetry_parser is parser
    assert dependencies.session_manager is session_manager
    assert dependencies.building is building
    assert dependencies.knowledge_base is knowledge_base


def test_building_is_not_constructed_until_first_access() -> None:
    dependencies = DependencyProvider()

    assert dependencies._building is None

    building = dependencies.building

    assert isinstance(building, BuildingManager)
    # Same instance is reused on subsequent access.
    assert dependencies.building is building


def test_knowledge_base_is_not_constructed_until_first_access() -> None:
    dependencies = DependencyProvider()

    assert dependencies._knowledge_base is None

    knowledge_base = dependencies.knowledge_base

    assert isinstance(knowledge_base, KnowledgeBase)
    assert dependencies.knowledge_base is knowledge_base


def test_knowledge_base_construction_does_not_load_embedding_model() -> None:
    """Constructing a KnowledgeBase must not trigger a network call.

    ``SentenceTransformer`` is only built lazily on first embed -- this
    guards the regression where ``KnowledgeBase.__init__`` used to build it
    unconditionally.
    """

    knowledge_base = DependencyProvider().knowledge_base

    assert knowledge_base._model is None
