"""Builds the real (non-dry-run) set of dependencies the closed loop needs.

Shared by main.py and the dashboard's Simulation/Closed-Loop Runner pages
so both wire up a DependencyProvider, FastMCP server, and baseline
simulation the same way instead of each keeping their own copy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastmcp import FastMCP

from agent.llm import LLMClient, OllamaLLMClient
from agent.memory import ExperienceStore
from agent.safety import SafetySupervisor
from agent.tools import FastMCPToolExecutor, ToolExecutor
from config.settings import OUTPUT_DIR
from mcp_server.dependencies import DependencyProvider
from mcp_server.registry import register_tools
from telemetry.models import BuildingMetadata, BuildingState


@dataclass(slots=True)
class LiveEnvironment:
    llm: LLMClient
    tools: ToolExecutor
    memory: ExperienceStore
    safety: SafetySupervisor
    baseline_state: BuildingState
    metadata: BuildingMetadata
    dependencies: DependencyProvider


def build_live_environment(
    idf_path: Path,
    weather_path: Path | None = None,
    output_dir_name: str = "baseline",
) -> LiveEnvironment:
    """Load idf_path, run its baseline simulation, and wire up everything
    the closed loop needs to run against it.

    weather_path overrides config.settings.WEATHER_FILE for both the
    building's metadata and the actual EnergyPlus run -- lets a caller
    (the dashboard's Setup page) point at an uploaded .epw instead of the
    project's default.
    """

    dependencies = DependencyProvider()

    if weather_path is not None:
        dependencies.building.weather_file = weather_path

    dependencies.building.idf_path = idf_path
    dependencies.building.load()
    dependencies.building.save_baseline()

    server = FastMCP("EcoPilot")
    register_tools(server, dependencies)

    tools: ToolExecutor = FastMCPToolExecutor(server)
    llm: LLMClient = OllamaLLMClient()
    memory = ExperienceStore()
    safety = SafetySupervisor()

    simulation_result = tools.call(
        "run_simulation_tool",
        idf_path=str(idf_path),
        output_directory=str(OUTPUT_DIR / output_dir_name),
        weather_file=str(weather_path) if weather_path is not None else None,
    )

    metadata = BuildingMetadata(
        building_name=dependencies.building.summary().building_name,
        location="Unknown",
        floor_area=0.0,
        weather_file=dependencies.building.weather_file or Path(),
        idf_file=idf_path,
    )

    baseline_state = tools.call(
        "read_building_state_tool",
        sql_file=str(simulation_result.sql_file),
        metadata=metadata,
        runtime_seconds=simulation_result.runtime_seconds,
    )

    return LiveEnvironment(
        llm=llm,
        tools=tools,
        memory=memory,
        safety=safety,
        baseline_state=baseline_state,
        metadata=metadata,
        dependencies=dependencies,
    )


__all__ = ["LiveEnvironment", "build_live_environment"]
