from __future__ import annotations

from dataclasses import dataclass

from agent.llm import LLMClient
from agent.prompts import ANALYST_SYSTEM_PROMPT
from mcp_server.tools.evaluation import EvaluationResult
from telemetry.models import BuildingState


@dataclass(slots=True)
class AnalystReport:
    narrative: str


class Analyst:
    """Explains *why* the metrics changed between baseline and current state.

    Pure interpretation, no action proposal (that's the Planner's job) and
    no execution (that's the Controller's) -- keeps each agent's
    responsibility narrow and independently testable.
    """

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def explain(
        self,
        baseline: BuildingState,
        current: BuildingState,
        evaluation: EvaluationResult,
    ) -> AnalystReport:
        prompt = self._build_prompt(baseline, current, evaluation)

        response = self.llm.complete(
            system_prompt=ANALYST_SYSTEM_PROMPT,
            user_prompt=prompt,
        )

        return AnalystReport(narrative=response.content)

    def _build_prompt(
        self,
        baseline: BuildingState,
        current: BuildingState,
        evaluation: EvaluationResult,
    ) -> str:
        return "\n".join(
            [
                f"Baseline outdoor temperature: {baseline.weather.outdoor_temperature} C",
                f"Current outdoor temperature: {current.weather.outdoor_temperature} C",
                f"Baseline occupancy: {baseline.occupancy.average_occupancy}",
                f"Current occupancy: {current.occupancy.average_occupancy}",
                f"Baseline energy: {evaluation.energy.baseline_energy_kwh:.2f} kWh",
                f"Optimized energy: {evaluation.energy.optimized_energy_kwh:.2f} kWh",
                f"Energy savings: {evaluation.energy.savings_percent:.2f}%",
                f"Baseline PMV: {evaluation.comfort.baseline_pmv}",
                f"Optimized PMV: {evaluation.comfort.optimized_pmv}",
                f"Comfort improved: {evaluation.comfort.comfort_improved}",
                f"Carbon reduction: {evaluation.carbon.reduction_percent:.2f}%",
                f"Peak demand reduction: {evaluation.peak.reduction_percent:.2f}%",
            ]
        )


__all__ = ["Analyst", "AnalystReport"]
