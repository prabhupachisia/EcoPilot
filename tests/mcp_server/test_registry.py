from unittest.mock import Mock, patch

from fastmcp import FastMCP

from mcp_server.dependencies import DependencyProvider
from mcp_server.registry import register_tools


@patch("mcp_server.registry.register_carbon_tools")
@patch("mcp_server.registry.register_report_tools")
@patch("mcp_server.registry.register_knowledge_tools")
@patch("mcp_server.registry.register_memory_tools")
@patch("mcp_server.registry.register_evaluation_tools")
@patch("mcp_server.registry.register_building_tools")
@patch("mcp_server.registry.register_telemetry_tools")
@patch("mcp_server.registry.register_simulation_tools")
def test_register_tools_calls_every_registration_function(
    mock_register_simulation: Mock,
    mock_register_telemetry: Mock,
    mock_register_building: Mock,
    mock_register_evaluation: Mock,
    mock_register_memory: Mock,
    mock_register_knowledge: Mock,
    mock_register_report: Mock,
    mock_register_carbon: Mock,
) -> None:
    server = Mock(spec=FastMCP)
    dependencies = Mock(spec=DependencyProvider)

    register_tools(server, dependencies)

    for mock_register in (
        mock_register_simulation,
        mock_register_telemetry,
        mock_register_building,
        mock_register_evaluation,
        mock_register_memory,
        mock_register_knowledge,
        mock_register_report,
        mock_register_carbon,
    ):
        mock_register.assert_called_once_with(server, dependencies)
