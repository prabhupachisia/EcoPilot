import json
from pathlib import Path

from mcp_server.tools.evaluation import (
    CarbonComparison,
    ComfortComparison,
    EnergyComparison,
    EvaluationRecommendation,
    EvaluationResult,
    EvaluationScore,
    PeakDemandComparison,
)
from mcp_server.tools.reports import generate_report, list_reports


def make_evaluation() -> EvaluationResult:
    return EvaluationResult(
        energy=EnergyComparison(
            baseline_energy_kwh=120.0,
            optimized_energy_kwh=100.0,
            savings_kwh=20.0,
            savings_percent=16.67,
        ),
        comfort=ComfortComparison(
            baseline_pmv=0.5,
            optimized_pmv=0.3,
            baseline_ppd=10.0,
            optimized_ppd=7.0,
            baseline_discomfort_hours=2.0,
            optimized_discomfort_hours=1.0,
            comfort_improved=True,
        ),
        carbon=CarbonComparison(
            baseline_emissions_kg=50.0,
            optimized_emissions_kg=40.0,
            reduction_kg=10.0,
            reduction_percent=20.0,
        ),
        peak=PeakDemandComparison(
            baseline_peak_kw=15.0,
            optimized_peak_kw=12.0,
            reduction_kw=3.0,
            reduction_percent=20.0,
        ),
        score=EvaluationScore(
            energy_score=80.0,
            comfort_score=85.0,
            carbon_score=82.0,
            peak_score=75.0,
            overall_score=81.2,
        ),
        recommendation=EvaluationRecommendation.ACCEPT,
        passed=True,
    )


def test_generate_report_writes_markdown_and_json(tmp_path: Path) -> None:
    evaluation = make_evaluation()

    markdown_path = generate_report(
        evaluation,
        cycle=1,
        decisions=[{"action": "raised cooling setpoint"}],
        reports_dir=tmp_path,
    )

    assert markdown_path.exists()
    assert markdown_path.suffix == ".md"

    content = markdown_path.read_text(encoding="utf-8")
    assert "Cycle 1" in content
    assert "16.67%" in content
    assert "raised cooling setpoint" in content

    json_path = markdown_path.with_suffix(".json")
    assert json_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["cycle"] == 1
    assert payload["evaluation"]["recommendation"] == "accept"
    assert payload["decisions"] == [{"action": "raised cooling setpoint"}]


def test_generate_report_without_decisions_notes_none_recorded(tmp_path: Path) -> None:
    markdown_path = generate_report(make_evaluation(), cycle=2, reports_dir=tmp_path)

    content = markdown_path.read_text(encoding="utf-8")
    assert "_None recorded._" in content


def test_list_reports_returns_sorted_markdown_paths(tmp_path: Path) -> None:
    generate_report(make_evaluation(), cycle=1, reports_dir=tmp_path)
    generate_report(make_evaluation(), cycle=2, reports_dir=tmp_path)

    reports = list_reports(reports_dir=tmp_path)

    assert len(reports) == 2
    assert reports == sorted(reports)
    assert all(path.endswith(".md") for path in reports)


def test_list_reports_returns_empty_list_when_directory_missing(tmp_path: Path) -> None:
    missing_dir = tmp_path / "does_not_exist"

    assert list_reports(reports_dir=missing_dir) == []
