from pathlib import Path
from unittest.mock import Mock
from datetime import datetime
from pathlib import Path

from energyplus.models import SimulationResult
from mcp_server.dependencies import DependencyProvider
from mcp_server.tools.simulation import run_simulation

def make_result(
    success: bool = True,
    error: str | None = None,
) -> SimulationResult:
    return SimulationResult(
        simulation_id="test-id",
        timestamp=datetime.now(),
        runtime_seconds=12.5,
        success=success,
        idf_file=Path("building.idf"),
        output_directory=Path("output"),
        sql_file=Path("output/eplusout.sql"),
        error=error,
    )

def test_run_simulation_calls_runner() -> None:
    runner = Mock()

    expected = make_result()

    runner.run.return_value = expected

    dependencies = DependencyProvider(
        energyplus_runner=runner,
    )

    result = run_simulation(
        dependencies=dependencies,
        idf_path="building.idf",
        output_directory="output",
    )

    runner.run.assert_called_once_with(
        idf_path=Path("building.idf"),
        output_dir=Path("output"),
        clean=True,
    )

    assert result == expected


def test_run_simulation_returns_failure_result() -> None:
    runner = Mock()

    expected = make_result()

    runner.run.return_value = expected

    dependencies = DependencyProvider(
        energyplus_runner=runner,
    )

    result = run_simulation(
        dependencies=dependencies,
        idf_path="building.idf",
        output_directory="output",
    )

    assert result == expected