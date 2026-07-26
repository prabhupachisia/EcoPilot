"""EcoPilot CLI entrypoint.

Runs the closed loop: a baseline simulation, then up to --cycles
LangGraph-orchestrated optimization cycles (Planner -> Analyst ->
Controller -> Reflection), writing a summary report and per-cycle logs.

--dry-run swaps in the synthetic dependencies from agent/dry_run.py, so
the whole loop - tool-calling and all - can be smoke-tested without
EnergyPlus or Ollama installed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.table import Table

from agent.dry_run import build_dry_run_environment
from agent.environment import build_live_environment
from agent.orchestrator import OptimizationState, build_cycle_graph, run_optimization_loop
from agent.run_logs import write_audit_trail, write_decision_and_reflection_logs
from config.settings import BASELINE_IDF, MAX_OPTIMIZATION_CYCLES, REPORTS_DIR, WEATHER_FILE
from mcp_server.dependencies import DependencyProvider
from mcp_server.tools.reports import generate_report

console = Console()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EcoPilot closed-loop HVAC optimizer.")
    parser.add_argument("--cycles", type=int, default=None, help="Max optimization cycles.")
    parser.add_argument("--idf", type=str, default=None, help="Baseline IDF path.")
    parser.add_argument("--weather", type=str, default=None, help="Weather (.epw) path.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use synthetic LLM/tool responses; runs with no EnergyPlus/Ollama installed.",
    )
    return parser.parse_args(argv)


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
        weather_path = Path(args.weather) if args.weather else WEATHER_FILE
        environment = build_live_environment(idf_path, weather_path)
        llm = environment.llm
        tools = environment.tools
        memory = environment.memory
        safety = environment.safety
        baseline_state = environment.baseline_state
        metadata = environment.metadata
        dependencies = environment.dependencies

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

    write_decision_and_reflection_logs(history)
    write_audit_trail(dependencies)
    _print_summary(history)

    logger.info(f"Completed {len(history)} cycle(s).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
