from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.planner import PlannerProposal
from agent.safety import SafetyDecision, SafetySupervisor, SafetyVerdict, apply_safety_decision
from agent.tools import ToolExecutor


@dataclass(slots=True)
class ControllerResult:
    safety_decisions: list[SafetyDecision]
    action_results: list[Any] = field(default_factory=list)
    committed: bool = False
    message: str = ""


def _is_success(result: Any) -> bool:
    if hasattr(result, "success"):
        return bool(result.success)

    if isinstance(result, dict):
        return bool(result.get("success"))

    return False


class Controller:
    """The only component allowed to execute building modifications.

    Every proposed action gets safety-checked (clipped/rejected) before
    dispatch, and the whole batch runs inside a transaction so a partial
    failure rolls back cleanly instead of leaving the building half-edited.
    No LLM call here - execution should be a disciplined, deterministic
    step, not another round of reasoning.
    """

    def __init__(self, tools: ToolExecutor, safety: SafetySupervisor) -> None:
        self.tools = tools
        self.safety = safety

    def apply(self, proposal: PlannerProposal) -> ControllerResult:
        if not proposal.actions:
            return ControllerResult(
                safety_decisions=[],
                message="No actions proposed.",
            )

        decisions = self.safety.validate_batch(proposal.actions)

        applied_actions = [
            apply_safety_decision(decision.action, decision)
            if decision.verdict is SafetyVerdict.CLIPPED
            else decision.action
            for decision in decisions
            if decision.verdict is not SafetyVerdict.REJECTED
        ]

        if not applied_actions:
            return ControllerResult(
                safety_decisions=decisions,
                message="Every proposed action was rejected by the safety supervisor.",
            )

        self.tools.call("begin_transaction")

        try:
            results = self.tools.call("apply_building_actions", actions=applied_actions)
        except Exception as error:
            self.tools.call("rollback_transaction")
            return ControllerResult(
                safety_decisions=decisions,
                committed=False,
                message=f"Error applying actions: {error}; transaction rolled back.",
            )

        failed = [result for result in results if not _is_success(result)]

        if failed:
            self.tools.call("rollback_transaction")
            return ControllerResult(
                safety_decisions=decisions,
                action_results=results,
                committed=False,
                message=f"{len(failed)} action(s) failed; transaction rolled back.",
            )

        self.tools.call("commit_transaction")

        return ControllerResult(
            safety_decisions=decisions,
            action_results=results,
            committed=True,
            message="Actions applied and committed.",
        )


__all__ = ["Controller", "ControllerResult"]
