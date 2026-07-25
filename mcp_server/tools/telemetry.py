from pathlib import Path

from fastmcp import FastMCP

from mcp_server.dependencies import DependencyProvider
from telemetry.models import BuildingMetadata, BuildingState


def read_building_state(
    dependencies: DependencyProvider,
    sql_file: str | Path,
    metadata: BuildingMetadata,
    runtime_seconds: float,
) -> BuildingState:
    """
    Read and parse the building telemetry from an EnergyPlus SQLite output.
    """
    return dependencies.telemetry_parser.parse(
        sql_file=sql_file,
        metadata=metadata,
        runtime_seconds=runtime_seconds,
    )


def register_telemetry_tools(
    server: FastMCP,
    dependencies: DependencyProvider,
) -> None:
    """Register telemetry-related MCP tools."""

    @server.tool
    def read_building_state_tool(
        sql_file: str,
        metadata: BuildingMetadata,
        runtime_seconds: float,
    ) -> BuildingState:
        return read_building_state(
            dependencies=dependencies,
            sql_file=sql_file,
            metadata=metadata,
            runtime_seconds=runtime_seconds,
        )