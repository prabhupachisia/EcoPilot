import json
from pathlib import Path

import agent.run_logs as run_logs
import main


def test_dry_run_completes_and_writes_logs_and_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_logs, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(main, "REPORTS_DIR", tmp_path / "reports")

    exit_code = main.main(["--dry-run", "--cycles", "2"])

    assert exit_code == 0

    decision_log = json.loads((tmp_path / "logs" / "decision_log.json").read_text())
    reflection_log = json.loads((tmp_path / "logs" / "reflection_log.json").read_text())

    assert len(decision_log) >= 1
    assert len(reflection_log) >= 1
    assert reflection_log[0]["confidence"] is not None
    assert "thought" in decision_log[0]
    assert "retrieved_memory" in decision_log[0]
    assert "safety_decisions" in decision_log[0]

    # --dry-run has no real BuildingManager, so no audit trail is written.
    assert not (tmp_path / "logs" / "audit_trail.json").exists()

    reports = list((tmp_path / "reports").glob("*.md"))
    assert len(reports) == 1


def test_dry_run_stops_early_once_satisfied(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_logs, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(main, "REPORTS_DIR", tmp_path / "reports")

    main.main(["--dry-run", "--cycles", "10"])

    decision_log = json.loads((tmp_path / "logs" / "decision_log.json").read_text())

    # The synthetic dry-run data is engineered to satisfy the evaluation
    # threshold well before 10 cycles.
    assert len(decision_log) < 10
