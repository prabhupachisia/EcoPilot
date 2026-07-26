"""Writes the per-run JSON logs the dashboard reads (dashboard/data.py).

Shared by main.py and the dashboard's Closed-Loop Runner page so a run
started from either place leaves the same trail behind.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent.orchestrator import OptimizationState
from config.settings import LOGS_DIR
from mcp_server.dependencies import DependencyProvider


def write_decision_and_reflection_logs(
    history: list[OptimizationState],
    logs_dir: Path | None = None,
) -> None:
    logs_dir = Path(logs_dir) if logs_dir is not None else LOGS_DIR
    logs_dir.mkdir(parents=True, exist_ok=True)

    decision_log = [
        {
            "cycle": entry["cycle"],
            "thought": entry["proposal"].rationale,
            "retrieved_memory": [
                {
                    "cycle": experience.cycle,
                    "action_summary": experience.action_summary,
                    "savings_percent": experience.savings_percent,
                    "outcome": experience.outcome,
                    "distance": distance,
                }
                for experience, distance in entry.get("similar_cases", [])
            ],
            "committed": entry["controller_result"].committed,
            "message": entry["controller_result"].message,
            "safety_decisions": [
                {
                    "parameter": decision.action.parameter,
                    "verdict": decision.verdict.value,
                    "original_value": decision.original_value,
                    "applied_value": decision.applied_value,
                    "reason": decision.reason,
                }
                for decision in entry["controller_result"].safety_decisions
            ],
        }
        for entry in history
    ]
    (logs_dir / "decision_log.json").write_text(json.dumps(decision_log, indent=2), encoding="utf-8")

    reflection_log = [
        {
            "cycle": entry["cycle"],
            "confidence": entry["reflection"].confidence,
            "should_rollback": entry["reflection"].should_rollback,
            "narrative": entry["reflection"].narrative,
        }
        for entry in history
    ]
    (logs_dir / "reflection_log.json").write_text(
        json.dumps(reflection_log, indent=2), encoding="utf-8"
    )


def write_audit_trail(
    dependencies: DependencyProvider | None,
    logs_dir: Path | None = None,
) -> None:
    """Export building change history + snapshots for the dashboard's audit trail.

    Only available in live mode -- --dry-run has no real BuildingManager to
    read history/snapshots from.
    """

    if dependencies is None:
        return

    logs_dir = Path(logs_dir) if logs_dir is not None else LOGS_DIR
    logs_dir.mkdir(parents=True, exist_ok=True)

    building = dependencies.building

    changes = [
        {
            "timestamp": change.timestamp.isoformat(),
            "component": change.component.value,
            "target": change.target,
            "parameter": change.parameter,
            "previous_value": change.previous_value,
            "new_value": change.new_value,
            "reason": change.reason,
        }
        for change in building.history
    ]

    snapshots = [
        {"name": snapshot.name, "created_at": snapshot.created_at.isoformat()}
        for snapshot in building.list_snapshots()
    ]

    (logs_dir / "audit_trail.json").write_text(
        json.dumps({"changes": changes, "snapshots": snapshots}, indent=2),
        encoding="utf-8",
    )


__all__ = ["write_decision_and_reflection_logs", "write_audit_trail"]
