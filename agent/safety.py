from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from config.constants import (
    COOLING_SETPOINT_SAFE_RANGE,
    HEATING_SETPOINT_SAFE_RANGE,
    REGRESSION_ROLLBACK_THRESHOLD,
)
from mcp_server.tools.building.models import BuildingAction, BuildingComponent


class SafetyVerdict(str, Enum):
    ACCEPT = "accept"
    CLIPPED = "clipped"
    REJECTED = "rejected"


@dataclass(slots=True)
class SafetyDecision:
    action: BuildingAction
    verdict: SafetyVerdict
    original_value: Any
    applied_value: Any
    reason: str


class SafetySupervisor:
    """Deterministic guardrail over LLM-proposed ``BuildingAction``s.

    This is plain Python, not an LLM call and not itself an MCP tool an LLM
    could route around -- the Controller runs every proposed action
    through ``validate``/``validate_batch`` before it is ever dispatched to
    EnergyPlus, clipping out-of-range numeric setpoints and rejecting
    anything it can't reason about safely. ``check_regression`` is the
    separate, complementary guard: if a completed cycle's evaluation score
    drops too far versus the prior cycle, the orchestrator auto-rolls-back
    via the already-built snapshot/transaction machinery instead of
    silently accepting a bad cycle.
    """

    def __init__(
        self,
        cooling_range: tuple[float, float] = COOLING_SETPOINT_SAFE_RANGE,
        heating_range: tuple[float, float] = HEATING_SETPOINT_SAFE_RANGE,
        regression_threshold: float = REGRESSION_ROLLBACK_THRESHOLD,
    ) -> None:
        self.cooling_range = cooling_range
        self.heating_range = heating_range
        self.regression_threshold = regression_threshold

    def _range_for(self, action: BuildingAction) -> tuple[float, float] | None:
        if action.component is not BuildingComponent.THERMOSTAT:
            return None

        if action.parameter == "cooling_setpoint_temperature":
            return self.cooling_range

        if action.parameter == "heating_setpoint_temperature":
            return self.heating_range

        return None

    def validate(self, action: BuildingAction) -> SafetyDecision:
        bounds = self._range_for(action)

        if bounds is None:
            return SafetyDecision(
                action=action,
                verdict=SafetyVerdict.ACCEPT,
                original_value=action.value,
                applied_value=action.value,
                reason="No safety bound configured for this parameter.",
            )

        low, high = bounds

        try:
            value = float(action.value)
        except (TypeError, ValueError):
            return SafetyDecision(
                action=action,
                verdict=SafetyVerdict.REJECTED,
                original_value=action.value,
                applied_value=None,
                reason=f"Value '{action.value}' is not numeric.",
            )

        if value < low or value > high:
            clipped = max(low, min(value, high))

            return SafetyDecision(
                action=action,
                verdict=SafetyVerdict.CLIPPED,
                original_value=value,
                applied_value=clipped,
                reason=(
                    f"{value} is outside the safe range [{low}, {high}]; "
                    f"clipped to {clipped}."
                ),
            )

        return SafetyDecision(
            action=action,
            verdict=SafetyVerdict.ACCEPT,
            original_value=value,
            applied_value=value,
            reason="Within safe range.",
        )

    def validate_batch(self, actions: list[BuildingAction]) -> list[SafetyDecision]:
        return [self.validate(action) for action in actions]

    def check_regression(
        self,
        baseline_score: float,
        current_score: float,
        threshold: float | None = None,
    ) -> bool:
        """Return True if ``current_score`` regressed enough to roll back.

        Compares evaluation.score.overall_score between cycles (already a
        weighted blend of energy/comfort/carbon/peak) rather than any
        single metric, so one bad dimension doesn't need its own bespoke
        threshold.
        """

        threshold = self.regression_threshold if threshold is None else threshold

        if baseline_score <= 0:
            return False

        drop = (baseline_score - current_score) / baseline_score

        return drop >= threshold


def apply_safety_decision(action: BuildingAction, decision: SafetyDecision) -> BuildingAction:
    """Return a copy of ``action`` with its value replaced by the clipped value."""

    return BuildingAction(
        component=action.component,
        action=action.action,
        target=action.target,
        parameter=action.parameter,
        value=decision.applied_value,
        reason=action.reason,
        iteration=action.iteration,
    )


__all__ = [
    "SafetyVerdict",
    "SafetyDecision",
    "SafetySupervisor",
    "apply_safety_decision",
]
