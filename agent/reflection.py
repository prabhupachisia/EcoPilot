from __future__ import annotations

from dataclasses import dataclass

from agent.llm import LLMClient
from agent.memory import Experience
from agent.planner import PlannerProposal
from agent.prompts import REFLECTION_SYSTEM_PROMPT
from agent.safety import SafetySupervisor
from mcp_server.tools.building.models import BuildingAction
from mcp_server.tools.evaluation import EvaluationResult
from telemetry.models import BuildingState


@dataclass(slots=True)
class ReflectionResult:
    confidence: float
    experience: Experience
    should_rollback: bool
    narrative: str | None = None


def _compute_confidence(predicted_percent: float, actual_percent: float) -> float:
    """1.0 = prediction matched reality exactly; 0.0 = off by 100 points or more."""

    diff = abs(predicted_percent - actual_percent)

    return max(0.0, min(1.0, 1.0 - diff / 100.0))


def _extract_setpoint_value(actions: list[BuildingAction], parameter: str) -> float | None:
    for action in actions:
        if action.parameter == parameter:
            try:
                return float(action.value)
            except (TypeError, ValueError):
                return None

    return None


class Reflection:
    """Compares predicted vs. actual outcomes and records the experience.

    The confidence score is a deterministic calculation (not LLM-guessed),
    which is what makes it trustworthy enough to trend on the dashboard and
    to unit test precisely. An optional LLM call can add a qualitative
    narrative on top, but never touches the number itself.
    """

    def __init__(self, safety: SafetySupervisor, llm: LLMClient | None = None) -> None:
        self.safety = safety
        self.llm = llm

    def reflect(
        self,
        cycle: int,
        proposal: PlannerProposal,
        predicted_savings_percent: float,
        evaluation: EvaluationResult,
        state: BuildingState,
        carbon_intensity_at_decision: float,
        previous_score: float | None = None,
        current_setpoints: dict[str, float] | None = None,
    ) -> ReflectionResult:
        actual_savings_percent = evaluation.energy.savings_percent
        confidence = _compute_confidence(predicted_savings_percent, actual_savings_percent)

        should_rollback = (
            previous_score is not None
            and self.safety.check_regression(previous_score, evaluation.score.overall_score)
        )

        narrative = None

        if self.llm is not None:
            prompt = (
                f"Planner's reasoning for this cycle: {proposal.rationale}\n\n"
                f"Predicted savings: {predicted_savings_percent:.2f}%\n"
                f"Actual savings: {actual_savings_percent:.2f}%\n"
                f"Confidence: {confidence:.2f}\n"
            )

            narrative = self.llm.complete(
                system_prompt=REFLECTION_SYSTEM_PROMPT,
                user_prompt=prompt,
            ).content

        outcome = "rollback" if should_rollback else ("success" if evaluation.passed else "neutral")

        current_setpoints = current_setpoints or {}
        cooling_setpoint = _extract_setpoint_value(proposal.actions, "cooling_setpoint_temperature")
        if cooling_setpoint is None:
            cooling_setpoint = current_setpoints.get("cooling_setpoint_temperature", 0.0)

        heating_setpoint = _extract_setpoint_value(proposal.actions, "heating_setpoint_temperature")
        if heating_setpoint is None:
            heating_setpoint = current_setpoints.get("heating_setpoint_temperature", 0.0)

        experience = Experience(
            cycle=cycle,
            weather_outdoor_temp=state.weather.outdoor_temperature or 0.0,
            occupancy=state.occupancy.average_occupancy or 0.0,
            cooling_setpoint=cooling_setpoint,
            heating_setpoint=heating_setpoint,
            carbon_intensity=carbon_intensity_at_decision,
            energy_kwh=state.energy.total_energy_kwh or 0.0,
            savings_percent=actual_savings_percent,
            action_summary=proposal.rationale,
            pmv=state.comfort.pmv,
            confidence=confidence,
            outcome=outcome,
        )

        return ReflectionResult(
            confidence=confidence,
            experience=experience,
            should_rollback=should_rollback,
            narrative=narrative,
        )


__all__ = ["Reflection", "ReflectionResult"]
