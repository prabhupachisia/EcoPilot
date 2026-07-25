# from unittest.mock import Mock, patch

# from fastmcp import FastMCP

# from mcp_server.dependencies import DependencyProvider
# from mcp_server.registry import register_tools


# @patch("mcp_server.registry.register_simulation_tools")
# @patch("mcp_server.registry.register_telemetry_tools")
# def test_register_tools_calls_all_registrations(
#     mock_register_telemetry: Mock,
#     mock_register_simulation: Mock,
# ) -> None:
#     server = Mock(spec=FastMCP)
#     dependencies = Mock(spec=DependencyProvider)

#     register_tools(server, dependencies)

#     mock_register_simulation.assert_called_once_with(
#         server,
#         dependencies,
#     )

#     mock_register_telemetry.assert_called_once_with(
#         server,
#         dependencies,
#     )