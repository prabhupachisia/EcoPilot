"""Read-only data loaders for the Streamlit dashboard.

The dashboard runs as a separate process from whatever ran the
optimization loop (main.py) - Streamlit's rerun model and a long-running
LangGraph loop don't mix well in the same process. So instead of holding a
live connection, it just reads the JSON logs/reports main.py writes.
Every loader here degrades gracefully to an empty/None result before any
run has happened, so the dashboard isn't broken on a fresh clone.

Split out from app.py so the actual logic can be unit-tested without
spinning up a Streamlit runtime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.constants import ELECTRICITY_RATE_PER_KWH
from config.settings import (
    BASELINE_IDF,
    LOGS_DIR,
    MODELS_DIR,
    REPORTS_DIR,
    UPLOADED_MODELS_DIR,
    UPLOADED_WEATHER_DIR,
    WEATHER_FILE,
)
from mcp_server.tools.carbon import CarbonIntensityProfile
from telemetry.extractor import BuildingStateExtractor
from telemetry.reader import SQLiteReader


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    return json.loads(path.read_text(encoding="utf-8"))


def load_decision_log(logs_dir: Path | None = None) -> list[dict[str, Any]]:
    logs_dir = logs_dir or LOGS_DIR
    return _load_json(logs_dir / "decision_log.json", [])


def load_reflection_log(logs_dir: Path | None = None) -> list[dict[str, Any]]:
    logs_dir = logs_dir or LOGS_DIR
    return _load_json(logs_dir / "reflection_log.json", [])


def load_audit_trail(logs_dir: Path | None = None) -> dict[str, Any] | None:
    logs_dir = logs_dir or LOGS_DIR
    path = logs_dir / "audit_trail.json"

    if not path.exists():
        return None

    return _load_json(path, None)


def latest_report_path(reports_dir: Path | None = None) -> Path | None:
    reports_dir = reports_dir or REPORTS_DIR

    if not reports_dir.exists():
        return None

    reports = sorted(reports_dir.glob("report_cycle_*.json"))

    return reports[-1] if reports else None


def load_latest_report(reports_dir: Path | None = None) -> dict[str, Any] | None:
    path = latest_report_path(reports_dir or REPORTS_DIR)

    if path is None:
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def list_saved_cycle_idfs(models_dir: Path | None = None) -> list[Path]:
    models_dir = models_dir or MODELS_DIR

    if not models_dir.exists():
        return []

    return sorted(models_dir.glob("cycle_*.idf"))


@dataclass(slots=True)
class ReasoningEntry:
    cycle: int
    thought: str
    retrieved_memory: list[dict[str, Any]]
    committed: bool
    message: str
    safety_decisions: list[dict[str, Any]]
    confidence: float | None
    should_rollback: bool | None
    narrative: str | None


def build_reasoning_timeline(
    decision_log: list[dict[str, Any]],
    reflection_log: list[dict[str, Any]],
) -> list[ReasoningEntry]:
    """Zip the decision and reflection logs into one per-cycle timeline."""

    reflections_by_cycle = {entry["cycle"]: entry for entry in reflection_log}

    timeline = []

    for entry in decision_log:
        reflection = reflections_by_cycle.get(entry["cycle"], {})

        timeline.append(
            ReasoningEntry(
                cycle=entry["cycle"],
                thought=entry.get("thought", ""),
                retrieved_memory=entry.get("retrieved_memory", []),
                committed=entry.get("committed", False),
                message=entry.get("message", ""),
                safety_decisions=entry.get("safety_decisions", []),
                confidence=reflection.get("confidence"),
                should_rollback=reflection.get("should_rollback"),
                narrative=reflection.get("narrative"),
            )
        )

    return timeline


def confidence_trend(reflection_log: list[dict[str, Any]]) -> list[tuple[int, float]]:
    return [
        (entry["cycle"], entry["confidence"])
        for entry in reflection_log
        if entry.get("confidence") is not None
    ]


def safety_decision_counts(decision_log: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"accept": 0, "clipped": 0, "rejected": 0}

    for entry in decision_log:
        for decision in entry.get("safety_decisions", []):
            verdict = decision.get("verdict")
            if verdict in counts:
                counts[verdict] += 1

    return counts


def estimate_carbon_reduction_kg(
    baseline_energy_kwh: float | None,
    optimized_energy_kwh: float | None,
    carbon_profile: CarbonIntensityProfile | None = None,
) -> float | None:
    """Approximate kg CO2 avoided using the average grid carbon intensity.

    A simple, explainable estimate (baseline/optimized energy x average
    intensity) rather than a full hourly-weighted calculation -- the
    hourly-precise version needs per-hour energy breakdowns that aren't in
    the persisted report JSON, only available mid-run via
    extract_hourly_energy().
    """

    if baseline_energy_kwh is None or optimized_energy_kwh is None:
        return None

    profile = carbon_profile or CarbonIntensityProfile()

    baseline_kg = profile.estimate_emissions_kg(baseline_energy_kwh)
    optimized_kg = profile.estimate_emissions_kg(optimized_energy_kwh)

    if baseline_kg is None or optimized_kg is None:
        return None

    return baseline_kg - optimized_kg


def estimate_cost_savings(
    baseline_energy_kwh: float | None,
    optimized_energy_kwh: float | None,
    rate: float = ELECTRICITY_RATE_PER_KWH,
) -> float | None:
    """Approximate $ saved using a representative electricity rate.

    Same shape as estimate_carbon_reduction_kg -- turns "X% energy saved"
    into a dollar figure, using a flat rate rather than a real tariff feed.
    """

    if baseline_energy_kwh is None or optimized_energy_kwh is None:
        return None

    return (baseline_energy_kwh - optimized_energy_kwh) * rate


def list_idf_presets(
    models_dir: Path | None = None,
    baseline_idf: Path | None = None,
) -> list[Path]:
    """Baseline IDF + anything already saved under energyplus/models/ (past
    optimization cycles, plus anything uploaded through Setup)."""

    models_dir = models_dir or MODELS_DIR
    baseline_idf = baseline_idf or BASELINE_IDF

    presets = [baseline_idf] if baseline_idf.exists() else []

    if models_dir.exists():
        presets.extend(sorted(models_dir.glob("*.idf")))

    return presets


def list_epw_presets(weather_dir: Path | None = None, baseline_epw: Path | None = None) -> list[Path]:
    """Baseline weather file + anything uploaded through Setup."""

    baseline_epw = baseline_epw or WEATHER_FILE
    weather_dir = weather_dir or UPLOADED_WEATHER_DIR

    presets = [baseline_epw] if baseline_epw.exists() else []

    if weather_dir.exists():
        presets.extend(sorted(weather_dir.glob("*.epw")))

    return presets


def save_uploaded_file(uploaded_file: Any, dest_dir: Path) -> Path:
    """Write a Streamlit UploadedFile's bytes to dest_dir, returning the path."""

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    destination = dest_dir / uploaded_file.name
    destination.write_bytes(uploaded_file.getvalue())

    return destination


def extract_zone_temperatures(sql_file: Path) -> dict[str, float]:
    """Fresh per-zone temperature extraction from a just-completed simulation's
    eplusout.sql -- feeds the Simulation Runner page's building heatmap."""

    with SQLiteReader(sql_file) as reader:
        return BuildingStateExtractor(reader).extract_zone_temperatures()
