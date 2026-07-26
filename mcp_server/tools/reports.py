from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP

from config.settings import REPORTS_DIR
from mcp_server.tools.evaluation import EvaluationResult, summarize_evaluation

if TYPE_CHECKING:
    from mcp_server.dependencies import DependencyProvider


def _evaluation_to_dict(result: EvaluationResult) -> dict[str, Any]:
    data = asdict(result)
    data["recommendation"] = result.recommendation.value
    return data


def _render_markdown(
    evaluation: EvaluationResult,
    cycle: int,
    generated_at: str,
    decisions: list[dict[str, Any]],
) -> str:
    decision_lines = (
        "\n".join(f"- {decision}" for decision in decisions)
        if decisions
        else "_None recorded._"
    )

    return (
        f"# EcoPilot Optimization Report -- Cycle {cycle}\n\n"
        f"Generated: {generated_at}\n\n"
        f"## Summary\n\n{summarize_evaluation(evaluation)}\n\n"
        f"## Energy\n\n"
        f"- Baseline: {evaluation.energy.baseline_energy_kwh:.2f} kWh\n"
        f"- Optimized: {evaluation.energy.optimized_energy_kwh:.2f} kWh\n"
        f"- Savings: {evaluation.energy.savings_kwh:.2f} kWh "
        f"({evaluation.energy.savings_percent:.2f}%)\n\n"
        f"## Comfort\n\n"
        f"- Baseline PMV: {evaluation.comfort.baseline_pmv}\n"
        f"- Optimized PMV: {evaluation.comfort.optimized_pmv}\n"
        f"- Comfort improved: {evaluation.comfort.comfort_improved}\n\n"
        f"## Carbon\n\n"
        f"- Reduction: {evaluation.carbon.reduction_kg:.2f} kg CO2 "
        f"({evaluation.carbon.reduction_percent:.2f}%)\n\n"
        f"## Peak Demand\n\n"
        f"- Reduction: {evaluation.peak.reduction_kw:.2f} kW "
        f"({evaluation.peak.reduction_percent:.2f}%)\n\n"
        f"## Decisions\n\n{decision_lines}\n"
    )


def generate_report(
    evaluation: EvaluationResult,
    cycle: int,
    decisions: list[dict[str, Any]] | None = None,
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    """Write a markdown + JSON report for one evaluated optimization cycle.

    Returns the markdown file's path.
    """

    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_at = datetime.now().isoformat()
    decisions = decisions or []

    json_path = reports_dir / f"report_cycle_{cycle}_{timestamp}.json"
    markdown_path = reports_dir / f"report_cycle_{cycle}_{timestamp}.md"

    payload = {
        "cycle": cycle,
        "generated_at": generated_at,
        "evaluation": _evaluation_to_dict(evaluation),
        "decisions": decisions,
    }

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path.write_text(
        _render_markdown(evaluation, cycle, generated_at, decisions),
        encoding="utf-8",
    )

    return markdown_path


def list_reports(reports_dir: Path = REPORTS_DIR) -> list[str]:
    """Return previously generated markdown report paths, sorted."""

    reports_dir = Path(reports_dir)

    if not reports_dir.exists():
        return []

    return sorted(str(path) for path in reports_dir.glob("*.md"))


def register_report_tools(
    server: FastMCP,
    dependencies: "DependencyProvider",
) -> None:
    """Register report-generation tools with the MCP server."""

    @server.tool(
        name="generate_report",
        description="Generate a markdown+JSON report for an evaluated optimization cycle.",
    )
    def generate_report_tool(
        evaluation: EvaluationResult,
        cycle: int,
        decisions: list[dict[str, Any]] | None = None,
    ) -> str:
        return str(generate_report(evaluation, cycle, decisions))

    @server.tool(
        name="list_reports",
        description="List previously generated report files.",
    )
    def list_reports_tool() -> list[str]:
        return list_reports()


__all__ = [
    "generate_report",
    "list_reports",
    "register_report_tools",
]
