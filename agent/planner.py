from __future__ import annotations

from dataclasses import dataclass, field

from agent.llm import LLMClient, ToolCall
from agent.memory import Experience
from agent.prompts import format_planner_prompt
from agent.tools import ToolExecutor
from mcp_server.tools.building.models import ActionType, BuildingAction, BuildingComponent
from telemetry.models import BuildingState

# Advertised to the LLM as an Ollama/OpenAI-style function schema. Kept to a
# single tool (mirroring mcp_server's set_hvac_setpoints convenience tool)
# rather than exposing the full apply_building_action surface -- a smaller
# tool surface is easier for a 3B model to use reliably.
PLANNER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_hvac_setpoints",
            "description": (
                "Set the building's occupied cooling and/or heating setpoint "
                "temperature (C). Provide only the setpoint(s) you want to "
                "change."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cooling_c": {"type": "number"},
                    "heating_c": {"type": "number"},
                    "reason": {"type": "string"},
                },
            },
        },
    }
]


@dataclass(slots=True)
class PlannerProposal:
    actions: list[BuildingAction]
    rationale: str
    target_hours_for_precool: list[int] = field(default_factory=list)


class Planner:
    """Reads the current situation and proposes HVAC setpoint changes.

    Retrieval happens first (memory of similar past cycles), then a single
    LLM call proposes actions -- matching plan.txt's "Planner retrieves
    similar historical situations before making decisions" design, just
    implemented as one call that takes the retrieved cases as input rather
    than two separate round-trips.
    """

    def __init__(self, llm: LLMClient, tools: ToolExecutor) -> None:
        self.llm = llm
        self.tools = tools

    def propose(
        self,
        state: BuildingState,
        similar_cases: list[tuple[Experience, float]],
        carbon_profile: dict[int, float],
    ) -> PlannerProposal:
        current_setpoints = self.tools.call("get_hvac_setpoints")

        prompt = self._build_prompt(state, similar_cases, carbon_profile, current_setpoints)

        response = self.llm.complete(
            system_prompt=format_planner_prompt(),
            user_prompt=prompt,
            tools=PLANNER_TOOLS,
        )

        actions = self._parse_actions(response.tool_calls)

        target_hours = (
            sorted(carbon_profile, key=carbon_profile.get)[:4] if carbon_profile else []
        )

        return PlannerProposal(
            actions=actions,
            rationale=response.content,
            target_hours_for_precool=target_hours,
        )

    def _build_prompt(
        self,
        state: BuildingState,
        similar_cases: list[tuple[Experience, float]],
        carbon_profile: dict[int, float],
        current_setpoints: dict[str, float],
    ) -> str:
        lines = [
            "Current building state:",
            f"- Outdoor temperature: {state.weather.outdoor_temperature} C",
            f"- Average occupancy: {state.occupancy.average_occupancy}",
            f"- Total energy use: {state.energy.total_energy_kwh} kWh",
            f"- Current cooling setpoint: {current_setpoints.get('cooling_setpoint_temperature')} C",
            f"- Current heating setpoint: {current_setpoints.get('heating_setpoint_temperature')} C",
            "",
        ]

        if carbon_profile:
            low_hours = sorted(carbon_profile, key=carbon_profile.get)[:4]
            lines.append(f"Lowest-carbon-intensity hours of the day: {low_hours}")
            lines.append("")

        if similar_cases:
            lines.append("Similar past cycles (nearest first):")
            for experience, distance in similar_cases:
                lines.append(
                    f"- cycle {experience.cycle}: cooling={experience.cooling_setpoint}C, "
                    f"heating={experience.heating_setpoint}C, savings={experience.savings_percent:.1f}%, "
                    f"outcome={experience.outcome}, distance={distance:.2f}"
                )
            lines.append("")

        lines.append(
            "Decide whether to adjust the cooling and/or heating setpoint, and by how much."
        )

        return "\n".join(lines)

    def _parse_actions(self, tool_calls: list[ToolCall]) -> list[BuildingAction]:
        actions: list[BuildingAction] = []

        for call in tool_calls:
            if call.name != "set_hvac_setpoints":
                continue

            reason = call.arguments.get("reason")
            cooling_c = call.arguments.get("cooling_c")
            heating_c = call.arguments.get("heating_c")

            if cooling_c is not None:
                actions.append(
                    BuildingAction(
                        component=BuildingComponent.THERMOSTAT,
                        action=ActionType.SET,
                        target="building",
                        parameter="cooling_setpoint_temperature",
                        value=float(cooling_c),
                        reason=reason,
                    )
                )

            if heating_c is not None:
                actions.append(
                    BuildingAction(
                        component=BuildingComponent.THERMOSTAT,
                        action=ActionType.SET,
                        target="building",
                        parameter="heating_setpoint_temperature",
                        value=float(heating_c),
                        reason=reason,
                    )
                )

        return actions


__all__ = ["Planner", "PlannerProposal", "PLANNER_TOOLS"]
