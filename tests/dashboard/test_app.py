import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).parent.parent.parent / "dashboard" / "app.py")


def _point_at_empty_dirs(monkeypatch, tmp_path: Path) -> None:
    """Isolate a test from whatever real logs/reports/models happen to
    exist in the actual project directories (e.g. from a developer's own
    earlier `python main.py` run) -- these tests want a guaranteed-empty
    state, not "whatever's on disk right now"."""

    import dashboard.data as data

    monkeypatch.setattr(data, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(data, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(data, "MODELS_DIR", tmp_path / "models")


def test_overview_renders_empty_state_with_no_data(tmp_path: Path, monkeypatch) -> None:
    _point_at_empty_dirs(monkeypatch, tmp_path)

    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)

    assert not at.exception
    assert any("No optimization run yet" in info.value for info in at.info)


@pytest.mark.parametrize("page_label", ["AI Reasoning", "Audit Trail", "Reports"])
def test_each_page_renders_without_exception(page_label: str, tmp_path: Path, monkeypatch) -> None:
    _point_at_empty_dirs(monkeypatch, tmp_path)

    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)

    at.sidebar.radio[0].set_value(page_label).run(timeout=30)

    assert not at.exception


def _write_sample_report(reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "cycle": 1,
        "evaluation": {
            "energy": {
                "baseline_energy_kwh": 120.0,
                "optimized_energy_kwh": 100.0,
                "savings_kwh": 20.0,
                "savings_percent": 16.67,
            },
            "comfort": {
                "baseline_pmv": 0.4,
                "optimized_pmv": 0.3,
                "baseline_ppd": 8.0,
                "optimized_ppd": 6.0,
                "baseline_discomfort_hours": 1.0,
                "optimized_discomfort_hours": 0.5,
                "comfort_improved": True,
            },
            "carbon": {
                "baseline_emissions_kg": 40.0,
                "optimized_emissions_kg": 35.0,
                "reduction_kg": 5.0,
                "reduction_percent": 12.5,
            },
            "peak": {
                "baseline_peak_kw": 10.0,
                "optimized_peak_kw": 9.0,
                "reduction_kw": 1.0,
                "reduction_percent": 10.0,
            },
            "score": {
                "energy_score": 80.0,
                "comfort_score": 85.0,
                "carbon_score": 82.0,
                "peak_score": 75.0,
                "overall_score": 81.2,
            },
            "recommendation": "accept",
            "passed": True,
        },
        "decisions": [{"cycle": 1, "rationale": "Raised cooling setpoint."}],
    }
    (reports_dir / "report_cycle_1_20260101_000000.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _write_sample_logs(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)

    decision_log = [
        {
            "cycle": 1,
            "thought": "Occupancy dropped, raising cooling setpoint.",
            "retrieved_memory": [
                {"cycle": 0, "action_summary": "baseline", "savings_percent": 0.0, "outcome": "neutral", "distance": 0.2}
            ],
            "committed": True,
            "message": "Actions applied and committed.",
            "safety_decisions": [
                {"parameter": "cooling_setpoint_temperature", "verdict": "accept", "original_value": 25.0, "applied_value": 25.0, "reason": "test"}
            ],
        }
    ]
    (logs_dir / "decision_log.json").write_text(json.dumps(decision_log), encoding="utf-8")

    reflection_log = [
        {"cycle": 1, "confidence": 0.92, "should_rollback": False, "narrative": "Close to prediction."}
    ]
    (logs_dir / "reflection_log.json").write_text(json.dumps(reflection_log), encoding="utf-8")


def test_pages_render_with_populated_data(tmp_path: Path, monkeypatch) -> None:
    import dashboard.data as data

    reports_dir = tmp_path / "reports"
    logs_dir = tmp_path / "logs"
    _write_sample_report(reports_dir)
    _write_sample_logs(logs_dir)

    monkeypatch.setattr(data, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(data, "LOGS_DIR", logs_dir)

    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert not at.exception

    at.sidebar.radio[0].set_value("AI Reasoning").run(timeout=30)
    assert not at.exception

    at.sidebar.radio[0].set_value("Reports").run(timeout=30)
    assert not at.exception
