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
    """Guardrail over LLM-proposed BuildingActions. Plain Python, no model call.

    The Controller runs every proposed action through validate()/
    validate_batch() before anything reaches EnergyPlus - out-of-range
    numeric setpoints get clipped, anything it can't reason about safely
    gets rejected. check_regression() is the other half: if a cycle's
    evaluation score drops too far from the previous one, the orchestrator
    rolls back using the snapshot/transaction machinery instead of just
    accepting a bad cycle and moving on.
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

    def validate_batch(
        self,
        actions: list[BuildingAction],
        current_setpoints: dict[str, float] | None = None,
    ) -> list[SafetyDecision]:
        decisions = [self.validate(action) for action in actions]

        if current_setpoints:
            decisions = self._enforce_deadband_widening(decisions, current_setpoints)

        return decisions

    def _enforce_deadband_widening(
        self,
        decisions: list[SafetyDecision],
        current_setpoints: dict[str, float],
    ) -> list[SafetyDecision]:
        """Reject a batch that narrows the cooling/heating deadband.

        The Planner's own system prompt calls widening the deadband (not
        narrowing it) "the single most important rule" for cutting HVAC
        energy - narrowing it makes the equipment run more, not less. A 3B
        local model doesn't reliably follow that instruction on its own
        (this is what let a live run's Planner narrow 23.9/21.1 to 23.6/21.3
        and made energy use go up), so this is enforced deterministically
        here instead of trusted to the prompt alone.
        """

        current_cooling = current_setpoints.get("cooling_setpoint_temperature")
        current_heating = current_setpoints.get("heating_setpoint_temperature")

        if current_cooling is None or current_heating is None:
            return decisions

        proposed_cooling = current_cooling
        proposed_heating = current_heating

        for decision in decisions:
            if decision.verdict is SafetyVerdict.REJECTED:
                continue

            if decision.action.parameter == "cooling_setpoint_temperature":
                proposed_cooling = decision.applied_value
            elif decision.action.parameter == "heating_setpoint_temperature":
                proposed_heating = decision.applied_value

        current_gap = current_cooling - current_heating
        proposed_gap = proposed_cooling - proposed_heating

        if proposed_gap >= current_gap - 1e-9:
            return decisions

        reason = (
            f"Would narrow the cooling/heating deadband from {current_gap:.1f}C to "
            f"{proposed_gap:.1f}C, which increases HVAC energy use rather than "
            "reducing it; rejected."
        )

        return [
            SafetyDecision(
                action=decision.action,
                verdict=SafetyVerdict.REJECTED,
                original_value=decision.original_value,
                applied_value=None,
                reason=reason,
            )
            if decision.verdict is not SafetyVerdict.REJECTED
            and decision.action.parameter
            in ("cooling_setpoint_temperature", "heating_setpoint_temperature")
            else decision
            for decision in decisions
        ]

    def check_regression(
        self,
        baseline_score: float,
        current_score: float,
        threshold: float | None = None,
    ) -> bool:
        """True if current_score dropped enough from baseline_score to roll back.

        Compares the overall evaluation score (already a blend of energy,
        comfort, carbon, peak) rather than picking apart individual
        metrics - simpler, and one bad dimension doesn't need its own
        threshold to tune.
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
