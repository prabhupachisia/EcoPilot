"""EcoPilot CLI entrypoint.

Runs the closed-loop HVAC optimization: a baseline simulation, then up to
``--cycles`` LangGraph-orchestrated optimization cycles (Planner -> Analyst
-> Controller -> Reflection), writing a summary report and per-cycle logs.

``--dry-run`` swaps in synthetic dependencies (agent/dry_run.py) so the
whole loop -- including tool-calling and LangGraph control flow -- can be
smoke-tested with no EnergyPlus or Ollama installed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from fastmcp import FastMCP
from loguru import logger
from rich.console import Console
from rich.table import Table

from agent.dry_run import build_dry_run_environment
from agent.llm import LLMClient, OllamaLLMClient
from agent.memory import ExperienceStore
from agent.orchestrator import OptimizationState, build_cycle_graph, run_optimization_loop
from agent.safety import SafetySupervisor
from agent.tools import FastMCPToolExecutor, ToolExecutor
from config.settings import BASELINE_IDF, LOGS_DIR, MAX_OPTIMIZATION_CYCLES, OUTPUT_DIR, REPORTS_DIR
from mcp_server.dependencies import DependencyProvider
from mcp_server.registry import register_tools
from mcp_server.tools.reports import generate_report
from telemetry.models import BuildingMetadata, BuildingState

console = Console()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EcoPilot closed-loop HVAC optimizer.")
    parser.add_argument("--cycles", type=int, default=None, help="Max optimization cycles.")
    parser.add_argument("--idf", type=str, default=None, help="Baseline IDF path.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use synthetic LLM/tool responses; runs with no EnergyPlus/Ollama installed.",
    )
    return parser.parse_args(argv)


def _build_live_environment(
    idf_path: Path,
) -> tuple[
    LLMClient, ToolExecutor, ExperienceStore, SafetySupervisor, BuildingState, BuildingMetadata, DependencyProvider
]:
    dependencies = DependencyProvider()
    dependencies.building.load()
    dependencies.building.save_baseline()

    server = FastMCP("EcoPilot")
    register_tools(server, dependencies)

    tools: ToolExecutor = FastMCPToolExecutor(server)
    llm: LLMClient = OllamaLLMClient()
    memory = ExperienceStore()
    safety = SafetySupervisor()

    baseline_output_dir = str(OUTPUT_DIR / "baseline")
    simulation_result = tools.call(
        "run_simulation_tool",
        idf_path=str(idf_path),
        output_directory=baseline_output_dir,
    )

    metadata = BuildingMetadata(
        building_name=dependencies.building.summary().building_name,
        location="Unknown",
        floor_area=0.0,
        weather_file=dependencies.building.weather_file or Path(),
        idf_file=idf_path,
    )

    baseline_state = tools.call(
        "read_building_state_tool",
        sql_file=str(simulation_result.sql_file),
        metadata=metadata,
        runtime_seconds=simulation_result.runtime_seconds,
    )

    return llm, tools, memory, safety, baseline_state, metadata, dependencies


def _print_summary(history: list[OptimizationState]) -> None:
    table = Table(title="EcoPilot Optimization Summary")
    table.add_column("Cycle")
    table.add_column("Energy Savings %")
    table.add_column("Carbon Reduction %")
    table.add_column("Confidence")
    table.add_column("Satisfied")

    for entry in history:
        evaluation = entry["evaluation"]
        reflection = entry["reflection"]
        table.add_row(
            str(entry["cycle"]),
            f"{evaluation.energy.savings_percent:.2f}",
            f"{evaluation.carbon.reduction_percent:.2f}",
            f"{reflection.confidence:.2f}",
            "yes" if entry.get("satisfied") else "no",
        )

    console.print(table)


def _write_logs(history: list[OptimizationState]) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

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
    (LOGS_DIR / "decision_log.json").write_text(json.dumps(decision_log, indent=2), encoding="utf-8")

    reflection_log = [
        {
            "cycle": entry["cycle"],
            "confidence": entry["reflection"].confidence,
            "should_rollback": entry["reflection"].should_rollback,
            "narrative": entry["reflection"].narrative,
        }
        for entry in history
    ]
    (LOGS_DIR / "reflection_log.json").write_text(
        json.dumps(reflection_log, indent=2), encoding="utf-8"
    )


def _write_audit_trail(dependencies: DependencyProvider | None) -> None:
    """Export building change history + snapshots for the dashboard's audit trail.

    Only available in live mode -- --dry-run has no real BuildingManager to
    read history/snapshots from.
    """

    if dependencies is None:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

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

    (LOGS_DIR / "audit_trail.json").write_text(
        json.dumps({"changes": changes, "snapshots": snapshots}, indent=2),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    max_cycles = args.cycles or MAX_OPTIMIZATION_CYCLES

    dependencies: DependencyProvider | None

    if args.dry_run:
        logger.info("Running in --dry-run mode (synthetic LLM/tool responses).")
        llm, tools, memory, safety, baseline_state, metadata = build_dry_run_environment(max_cycles)
        dependencies = None
    else:
        idf_path = Path(args.idf) if args.idf else BASELINE_IDF
        llm, tools, memory, safety, baseline_state, metadata, dependencies = _build_live_environment(
            idf_path
        )

    graph = build_cycle_graph(llm=llm, tools=tools, memory=memory, safety=safety)

    history = run_optimization_loop(
        graph,
        baseline_state=baseline_state,
        metadata=metadata,
        max_cycles=max_cycles,
    )

    if history:
        final_evaluation = history[-1]["evaluation"]
        generate_report(
            final_evaluation,
            cycle=history[-1]["cycle"],
            decisions=[
                {"cycle": entry["cycle"], "rationale": entry["proposal"].rationale}
                for entry in history
            ],
            reports_dir=REPORTS_DIR,
        )

    _write_logs(history)
    _write_audit_trail(dependencies)
    _print_summary(history)

    logger.info(f"Completed {len(history)} cycle(s).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
