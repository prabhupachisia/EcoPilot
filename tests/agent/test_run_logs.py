import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from agent.reflection import ReflectionResult
from agent.run_logs import write_audit_trail, write_decision_and_reflection_logs
from agent.safety import SafetyDecision, SafetyVerdict
from mcp_server.tools.building.models import (
    ActionType,
    BuildingAction,
    BuildingComponent,
    ChangeRecord,
)
from tests.agent.test_memory import make_experience


def make_history_entry(cycle: int) -> dict:
    action = BuildingAction(
        component=BuildingComponent.THERMOSTAT,
        action=ActionType.SET,
        target="building",
        parameter="cooling_setpoint_temperature",
        value=25.0,
        reason="test",
    )
    safety_decision = SafetyDecision(
        action=action,
        verdict=SafetyVerdict.ACCEPT,
        original_value=25.0,
        applied_value=25.0,
        reason="Within safe range.",
    )
    controller_result = MagicMock(committed=True, message="Applied.", safety_decisions=[safety_decision])
    proposal = MagicMock(rationale="Raised cooling setpoint.")
    reflection = ReflectionResult(
        confidence=0.9,
        experience=make_experience(cycle=cycle),
        should_rollback=False,
        narrative="Close to prediction.",
    )

    return {
        "cycle": cycle,
        "proposal": proposal,
        "controller_result": controller_result,
        "reflection": reflection,
        "similar_cases": [(make_experience(cycle=cycle - 1), 0.1)] if cycle > 1 else [],
    }


def test_write_decision_and_reflection_logs(tmp_path: Path) -> None:
    history = [make_history_entry(1), make_history_entry(2)]

    write_decision_and_reflection_logs(history, logs_dir=tmp_path)

    decision_log = json.loads((tmp_path / "decision_log.json").read_text())
    reflection_log = json.loads((tmp_path / "reflection_log.json").read_text())

    assert len(decision_log) == 2
    assert decision_log[0]["thought"] == "Raised cooling setpoint."
    assert decision_log[0]["safety_decisions"][0]["verdict"] == "accept"
    assert decision_log[1]["retrieved_memory"][0]["cycle"] == 1

    assert len(reflection_log) == 2
    assert reflection_log[0]["confidence"] == 0.9
    assert reflection_log[0]["narrative"] == "Close to prediction."


def test_write_audit_trail_does_nothing_without_dependencies(tmp_path: Path) -> None:
    write_audit_trail(None, logs_dir=tmp_path)

    assert not (tmp_path / "audit_trail.json").exists()


def test_write_audit_trail_exports_changes_and_snapshots(tmp_path: Path) -> None:
    change = ChangeRecord(
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
        component=BuildingComponent.THERMOSTAT,
        target="Clg-SetP-Sch",
        parameter="cooling_setpoint_temperature",
        previous_value=23.9,
        new_value=25.0,
        reason="Low occupancy",
    )
    snapshot = MagicMock(name="baseline", created_at=datetime(2026, 1, 1, 11, 0, 0))
    snapshot.name = "baseline"

    dependencies = MagicMock()
    dependencies.building.history = [change]
    dependencies.building.list_snapshots.return_value = [snapshot]

    write_audit_trail(dependencies, logs_dir=tmp_path)

    payload = json.loads((tmp_path / "audit_trail.json").read_text())

    assert payload["changes"][0]["target"] == "Clg-SetP-Sch"
    assert payload["changes"][0]["new_value"] == 25.0
    assert payload["snapshots"][0]["name"] == "baseline"
