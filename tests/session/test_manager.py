import pytest

from energyplus.models import SimulationResult
from session import SimulationSessionManager


@pytest.fixture
def simulation():
    from datetime import datetime
    from pathlib import Path

    return SimulationResult(
        simulation_id="test",
        timestamp=datetime.now(),
        runtime_seconds=10.0,
        success=True,
        idf_file=Path("building.idf"),
        output_directory=Path("output"),
        sql_file=Path("output/eplusout.sql"),
    )


def test_manager_initially_empty():
    manager = SimulationSessionManager()

    assert not manager.initialized


def test_start_session(simulation):
    manager = SimulationSessionManager()

    session = manager.start(simulation)

    assert manager.initialized
    assert manager.session is session
    assert session.simulation == simulation
    assert session.building_state is None


def test_clear_session(simulation):
    manager = SimulationSessionManager()

    manager.start(simulation)
    manager.clear()

    assert not manager.initialized


def test_access_without_session():
    manager = SimulationSessionManager()

    with pytest.raises(RuntimeError):
        _ = manager.session