from fastmcp import FastMCP

from mcp_server.dependencies import DependencyProvider
from mcp_server.tools.building import register_building_tools
from mcp_server.tools.evaluation import register_evaluation_tools
from mcp_server.tools.knowledge import register_knowledge_tools
from mcp_server.tools.memory import register_memory_tools
from mcp_server.tools.reports import register_report_tools
from mcp_server.tools.simulation import register_simulation_tools
from mcp_server.tools.telemetry import register_telemetry_tools


def register_tools(
    server: FastMCP,
    dependencies: DependencyProvider,
) -> None:
    """
    Register every MCP tool with the server.
    """

    register_simulation_tools(server, dependencies)
    register_telemetry_tools(server, dependencies)
    register_building_tools(server, dependencies)
    register_evaluation_tools(server, dependencies)
    register_memory_tools(server, dependencies)
    register_knowledge_tools(server, dependencies)
    register_report_tools(server, dependencies)