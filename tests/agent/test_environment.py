from pathlib import Path
from unittest.mock import MagicMock, patch

from agent.environment import build_live_environment
from mcp_server.tools.building.manager import BuildingManager
from tests.fixtures.building_state import make_building_state


class FakeSimulationResult:
    def __init__(self) -> None:
        self.sql_file = Path("output/eplusout.sql")
        self.runtime_seconds = 12.0


def test_build_live_environment_loads_the_given_idf_and_weather(tmp_path: Path) -> None:
    idf_path = tmp_path / "custom.idf"
    weather_path = tmp_path / "custom.epw"

    fake_building = MagicMock(spec=BuildingManager)
    fake_building.summary.return_value.building_name = "Custom Building"
    fake_building.weather_file = weather_path

    fake_dependencies = MagicMock()
    fake_dependencies.building = fake_building

    with patch("agent.environment.DependencyProvider", return_value=fake_dependencies), \
         patch("agent.environment.FastMCP"), \
         patch("agent.environment.register_tools"), \
         patch("agent.environment.FastMCPToolExecutor") as fake_executor_cls:
        fake_tools = MagicMock()
        fake_tools.call.side_effect = [
            FakeSimulationResult(),  # run_simulation_tool
            make_building_state(),  # read_building_state_tool
        ]
        fake_executor_cls.return_value = fake_tools

        environment = build_live_environment(idf_path, weather_path)

    # The building's idf_path/weather_file are overridden before load(),
    # not left pointing at the default baseline.
    assert fake_building.idf_path == idf_path
    assert fake_building.weather_file == weather_path
    fake_building.load.assert_called_once()
    fake_building.save_baseline.assert_called_once()

    run_call_kwargs = fake_tools.call.call_args_list[0].kwargs
    assert run_call_kwargs["idf_path"] == str(idf_path)
    assert run_call_kwargs["weather_file"] == str(weather_path)

    assert environment.metadata.building_name == "Custom Building"
    assert environment.metadata.idf_file == idf_path
    assert environment.dependencies is fake_dependencies


def test_build_live_environment_omits_weather_override_when_not_given(tmp_path: Path) -> None:
    idf_path = tmp_path / "custom.idf"

    fake_building = MagicMock(spec=BuildingManager)
    fake_building.summary.return_value.building_name = "Custom Building"
    fake_building.weather_file = Path("default.epw")

    fake_dependencies = MagicMock()
    fake_dependencies.building = fake_building

    with patch("agent.environment.DependencyProvider", return_value=fake_dependencies), \
         patch("agent.environment.FastMCP"), \
         patch("agent.environment.register_tools"), \
         patch("agent.environment.FastMCPToolExecutor") as fake_executor_cls:
        fake_tools = MagicMock()
        fake_tools.call.side_effect = [FakeSimulationResult(), make_building_state()]
        fake_executor_cls.return_value = fake_tools

        build_live_environment(idf_path)

    run_call_kwargs = fake_tools.call.call_args_list[0].kwargs
    assert run_call_kwargs["weather_file"] is None
