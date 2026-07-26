import json
from pathlib import Path

import pytest

from dashboard.data import (
    build_reasoning_timeline,
    confidence_trend,
    estimate_carbon_reduction_kg,
    estimate_cost_savings,
    extract_zone_temperatures,
    list_epw_presets,
    list_idf_presets,
    list_saved_cycle_idfs,
    load_audit_trail,
    load_decision_log,
    load_latest_report,
    load_reflection_log,
    safety_decision_counts,
    save_uploaded_file,
)
from mcp_server.tools.carbon import CarbonIntensityProfile
from tests.fixtures.synthetic_sql import build_synthetic_eplus_sql


def test_load_decision_log_returns_empty_list_when_missing(tmp_path: Path) -> None:
    assert load_decision_log(logs_dir=tmp_path) == []


def test_load_decision_log_reads_existing_file(tmp_path: Path) -> None:
    (tmp_path / "decision_log.json").write_text(json.dumps([{"cycle": 1}]), encoding="utf-8")

    assert load_decision_log(logs_dir=tmp_path) == [{"cycle": 1}]


def test_load_reflection_log_returns_empty_list_when_missing(tmp_path: Path) -> None:
    assert load_reflection_log(logs_dir=tmp_path) == []


def test_load_audit_trail_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_audit_trail(logs_dir=tmp_path) is None


def test_load_audit_trail_reads_existing_file(tmp_path: Path) -> None:
    payload = {"changes": [{"target": "Clg-SetP-Sch"}], "snapshots": []}
    (tmp_path / "audit_trail.json").write_text(json.dumps(payload), encoding="utf-8")

    assert load_audit_trail(logs_dir=tmp_path) == payload


def test_load_latest_report_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_latest_report(reports_dir=tmp_path) is None


def test_load_latest_report_picks_the_most_recent_by_name(tmp_path: Path) -> None:
    (tmp_path / "report_cycle_1_20260101_000000.json").write_text(
        json.dumps({"cycle": 1}), encoding="utf-8"
    )
    (tmp_path / "report_cycle_2_20260102_000000.json").write_text(
        json.dumps({"cycle": 2}), encoding="utf-8"
    )

    assert load_latest_report(reports_dir=tmp_path) == {"cycle": 2}


def test_list_saved_cycle_idfs_returns_empty_when_missing(tmp_path: Path) -> None:
    assert list_saved_cycle_idfs(models_dir=tmp_path / "does_not_exist") == []


def test_list_saved_cycle_idfs_returns_sorted_paths(tmp_path: Path) -> None:
    (tmp_path / "cycle_2.idf").write_text("", encoding="utf-8")
    (tmp_path / "cycle_1.idf").write_text("", encoding="utf-8")

    result = list_saved_cycle_idfs(models_dir=tmp_path)

    assert [path.name for path in result] == ["cycle_1.idf", "cycle_2.idf"]


def test_build_reasoning_timeline_zips_decision_and_reflection_logs() -> None:
    decision_log = [
        {
            "cycle": 1,
            "thought": "Raising cooling setpoint.",
            "retrieved_memory": [{"cycle": 0, "distance": 0.1}],
            "committed": True,
            "message": "Applied.",
            "safety_decisions": [{"verdict": "accept"}],
        }
    ]
    reflection_log = [{"cycle": 1, "confidence": 0.9, "should_rollback": False, "narrative": "Close match."}]

    timeline = build_reasoning_timeline(decision_log, reflection_log)

    assert len(timeline) == 1
    entry = timeline[0]
    assert entry.cycle == 1
    assert entry.thought == "Raising cooling setpoint."
    assert entry.confidence == 0.9
    assert entry.should_rollback is False
    assert entry.narrative == "Close match."


def test_build_reasoning_timeline_handles_missing_reflection() -> None:
    decision_log = [{"cycle": 1, "thought": "x", "retrieved_memory": [], "committed": True, "message": "", "safety_decisions": []}]

    timeline = build_reasoning_timeline(decision_log, [])

    assert timeline[0].confidence is None
    assert timeline[0].should_rollback is None


def test_confidence_trend_extracts_cycle_confidence_pairs() -> None:
    reflection_log = [
        {"cycle": 1, "confidence": 0.9},
        {"cycle": 2, "confidence": None},
        {"cycle": 3, "confidence": 0.7},
    ]

    assert confidence_trend(reflection_log) == [(1, 0.9), (3, 0.7)]


def test_safety_decision_counts_tallies_each_verdict() -> None:
    decision_log = [
        {"safety_decisions": [{"verdict": "accept"}, {"verdict": "clipped"}]},
        {"safety_decisions": [{"verdict": "rejected"}, {"verdict": "accept"}]},
    ]

    assert safety_decision_counts(decision_log) == {"accept": 2, "clipped": 1, "rejected": 1}


def test_safety_decision_counts_defaults_to_zero() -> None:
    assert safety_decision_counts([]) == {"accept": 0, "clipped": 0, "rejected": 0}


def test_estimate_carbon_reduction_kg_returns_none_without_energy_figures() -> None:
    assert estimate_carbon_reduction_kg(None, 100.0) is None
    assert estimate_carbon_reduction_kg(100.0, None) is None


def test_estimate_carbon_reduction_kg_computes_positive_savings() -> None:
    profile = CarbonIntensityProfile(profile={hour: 0.4 for hour in range(24)})

    reduction = estimate_carbon_reduction_kg(120.0, 100.0, carbon_profile=profile)

    assert reduction == 8.0  # (120 - 100) * 0.4


def test_estimate_cost_savings_returns_none_without_energy_figures() -> None:
    assert estimate_cost_savings(None, 100.0) is None
    assert estimate_cost_savings(100.0, None) is None


def test_estimate_cost_savings_computes_positive_savings() -> None:
    assert estimate_cost_savings(120.0, 100.0, rate=0.20) == pytest.approx(4.0)


def test_list_idf_presets_includes_baseline_and_models_dir(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.idf"
    baseline.write_text("", encoding="utf-8")

    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "cycle_1.idf").write_text("", encoding="utf-8")

    presets = list_idf_presets(models_dir=models_dir, baseline_idf=baseline)

    assert presets[0] == baseline
    assert models_dir / "cycle_1.idf" in presets


def test_list_idf_presets_skips_missing_baseline(tmp_path: Path) -> None:
    presets = list_idf_presets(
        models_dir=tmp_path / "does_not_exist", baseline_idf=tmp_path / "missing.idf"
    )

    assert presets == []


def test_list_epw_presets_includes_baseline_and_uploaded(tmp_path: Path) -> None:
    baseline = tmp_path / "weather.epw"
    baseline.write_text("", encoding="utf-8")

    uploaded_dir = tmp_path / "uploaded"
    uploaded_dir.mkdir()
    (uploaded_dir / "custom.epw").write_text("", encoding="utf-8")

    presets = list_epw_presets(weather_dir=uploaded_dir, baseline_epw=baseline)

    assert presets[0] == baseline
    assert uploaded_dir / "custom.epw" in presets


class FakeUploadedFile:
    def __init__(self, name: str, content: bytes) -> None:
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def test_save_uploaded_file_writes_bytes_to_dest_dir(tmp_path: Path) -> None:
    uploaded = FakeUploadedFile("custom.idf", b"! comment line")
    dest_dir = tmp_path / "uploaded"

    destination = save_uploaded_file(uploaded, dest_dir)

    assert destination == dest_dir / "custom.idf"
    assert destination.read_bytes() == b"! comment line"


def test_extract_zone_temperatures_reads_a_real_sql_file(tmp_path: Path) -> None:
    sql_path = build_synthetic_eplus_sql(tmp_path / "eplusout.sql")

    zone_temperatures = extract_zone_temperatures(sql_path)

    assert isinstance(zone_temperatures, dict)
    assert len(zone_temperatures) > 0
    assert all(isinstance(value, float) for value in zone_temperatures.values())
