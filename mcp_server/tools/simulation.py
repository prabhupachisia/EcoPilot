from pathlib import Path

from fastmcp import FastMCP

from energyplus.models import SimulationResult
from mcp_server.dependencies import DependencyProvider


def run_simulation(
    dependencies: DependencyProvider,
    idf_path: str | Path,
    output_directory: str | Path,
    clean: bool = True,
) -> SimulationResult:
    """
    Execute an EnergyPlus simulation.
    """
    return dependencies.energyplus_runner.run(
        idf_path=Path(idf_path),
        output_dir=Path(output_directory),
        clean=clean,
    )


def register_simulation_tools(
    server: FastMCP,
    dependencies: DependencyProvider,
) -> None:
    """Register simulation-related MCP tools."""

    @server.tool
    def run_simulation_tool(
        idf_path: str,
        output_directory: str,
        clean: bool = True,
    ) -> SimulationResult:
        return run_simulation(
            dependencies=dependencies,
            idf_path=idf_path,
            output_directory=output_directory,
            clean=clean,
        )