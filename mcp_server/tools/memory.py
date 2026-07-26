from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp import FastMCP

from agent.memory import Experience

if TYPE_CHECKING:
    from mcp_server.dependencies import DependencyProvider


def store_experience(dependencies: "DependencyProvider", experience: Experience) -> str:
    return dependencies.experience_memory.store(experience)


def retrieve_similar_cases(
    dependencies: "DependencyProvider",
    weather_outdoor_temp: float,
    occupancy: float,
    cooling_setpoint: float = 0.0,
    heating_setpoint: float = 0.0,
    carbon_intensity: float = 0.0,
    top_k: int = 3,
) -> list[tuple[Experience, float]]:
    return dependencies.experience_memory.retrieve_similar(
        weather_outdoor_temp=weather_outdoor_temp,
        occupancy=occupancy,
        cooling_setpoint=cooling_setpoint,
        heating_setpoint=heating_setpoint,
        carbon_intensity=carbon_intensity,
        top_k=top_k,
    )


def get_decision_history(
    dependencies: "DependencyProvider",
    limit: int | None = None,
) -> list[Experience]:
    return dependencies.experience_memory.history(limit=limit)


def get_confidence_trend(dependencies: "DependencyProvider") -> list[float]:
    return dependencies.experience_memory.confidence_trend()


def register_memory_tools(
    server: FastMCP,
    dependencies: "DependencyProvider",
) -> None:
    """Register case-based experience-memory tools with the MCP server.

    This is a thin wrapper over ``agent.memory.ExperienceStore`` -- the
    numeric-feature FAISS case memory the Planner consults before deciding
    (per the project's "Planner retrieves similar historical situations"
    design). Distinct from ``mcp_server.tools.knowledge_base``, which is
    document RAG over ASHRAE/EnergyPlus reference material, not experience.
    """

    @server.tool(
        name="store_experience",
        description="Record one optimization cycle's situation and outcome in case memory.",
    )
    def store_experience_tool(experience: Experience) -> str:
        return store_experience(dependencies, experience)

    @server.tool(
        name="retrieve_similar_cases",
        description=(
            "Retrieve the most similar past optimization cycles given the "
            "current weather/occupancy/setpoints/carbon intensity, nearest "
            "first."
        ),
    )
    def retrieve_similar_cases_tool(
        weather_outdoor_temp: float,
        occupancy: float,
        cooling_setpoint: float = 0.0,
        heating_setpoint: float = 0.0,
        carbon_intensity: float = 0.0,
        top_k: int = 3,
    ) -> list[tuple[Experience, float]]:
        return retrieve_similar_cases(
            dependencies,
            weather_outdoor_temp=weather_outdoor_temp,
            occupancy=occupancy,
            cooling_setpoint=cooling_setpoint,
            heating_setpoint=heating_setpoint,
            carbon_intensity=carbon_intensity,
            top_k=top_k,
        )

    @server.tool(
        name="get_decision_history",
        description="Return recorded optimization-cycle experiences, oldest first.",
    )
    def get_decision_history_tool(limit: int | None = None) -> list[Experience]:
        return get_decision_history(dependencies, limit=limit)

    @server.tool(
        name="get_confidence_trend",
        description="Return the Reflection agent's confidence score for each cycle that recorded one.",
    )
    def get_confidence_trend_tool() -> list[float]:
        return get_confidence_trend(dependencies)


__all__ = [
    "store_experience",
    "retrieve_similar_cases",
    "get_decision_history",
    "get_confidence_trend",
    "register_memory_tools",
]
