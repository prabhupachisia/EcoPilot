from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agent.analyst import Analyst, AnalystReport
from agent.controller import Controller, ControllerResult
from agent.llm import LLMClient
from agent.memory import Experience, ExperienceStore
from agent.planner import Planner, PlannerProposal
from agent.reflection import Reflection, ReflectionResult
from agent.safety import SafetySupervisor
from agent.tools import ToolExecutor
from config.settings import MAX_OPTIMIZATION_CYCLES, MODELS_DIR, OUTPUT_DIR
from mcp_server.tools.evaluation import EvaluationResult
from telemetry.models import BuildingMetadata, BuildingState, OptimizationSnapshot


class OptimizationState(TypedDict, total=False):
    """Shared state threaded through one cycle's LangGraph node sequence.

    Node order: read metrics -> memory retrieval -> planner -> controller ->
    run simulation -> telemetry parser -> evaluation -> analyst -> reflection
    -> store experience -> satisfied check. Memory retrieval runs before the
    planner since the planner needs the retrieved cases as input.

    The repeat-until-satisfied-or-max-cycles part isn't a loop in this
    graph - run_optimization_loop() below drives that in plain Python,
    calling this per-cycle graph once per iteration. Keeps each cycle
    independently traceable (handy for the dashboard's audit trail) and
    means not having to tune LangGraph's recursion limit for what would
    otherwise be an unbounded loop-back edge.
    """

    cycle: int
    max_cycles: int
    idf_path: str
    metadata: BuildingMetadata

    baseline_state: BuildingState
    current_state: BuildingState

    carbon_profile: dict[int, float]
    similar_cases: list[tuple[Experience, float]]

    proposal: PlannerProposal
    controller_result: ControllerResult
    current_setpoints: dict[str, float]

    simulation_result: Any
    evaluation: EvaluationResult
    analyst_report: AnalystReport
    reflection: ReflectionResult

    previous_score: float | None
    satisfied: bool


def _first_carbon_intensity(carbon_profile: dict[int, float]) -> float:
    if not carbon_profile:
        return 0.0

    return next(iter(carbon_profile.values()))


def build_cycle_graph(
    llm: LLMClient,
    tools: ToolExecutor,
    memory: ExperienceStore,
    safety: SafetySupervisor,
    planner: Planner | None = None,
    analyst: Analyst | None = None,
    controller: Controller | None = None,
    reflection: Reflection | None = None,
):
    """Build and compile the LangGraph for one optimization cycle.

    Agent dependencies are constructor-injected, falling back to real ones
    built from llm/tools/safety - so the whole graph runs fine in tests
    with a FakeLLMClient/FakeToolExecutor and no live Ollama or EnergyPlus.
    """

    planner = planner or Planner(llm=llm, tools=tools)
    analyst = analyst or Analyst(llm=llm)
    controller = controller or Controller(tools=tools, safety=safety)
    reflection = reflection or Reflection(safety=safety, llm=llm)

    def read_metrics(state: OptimizationState) -> dict[str, Any]:
        return {"carbon_profile": tools.call("get_carbon_intensity_profile")}

    def memory_retrieval(state: OptimizationState) -> dict[str, Any]:
        current = state["current_state"]
        setpoints = tools.call("get_hvac_setpoints")

        similar = memory.retrieve_similar(
            weather_outdoor_temp=current.weather.outdoor_temperature or 0.0,
            occupancy=current.occupancy.average_occupancy or 0.0,
            cooling_setpoint=setpoints.get("cooling_setpoint_temperature", 0.0),
            heating_setpoint=setpoints.get("heating_setpoint_temperature", 0.0),
            carbon_intensity=_first_carbon_intensity(state["carbon_profile"]),
        )

        return {"similar_cases": similar}

    def plan(state: OptimizationState) -> dict[str, Any]:
        proposal = planner.propose(
            state["current_state"], state["similar_cases"], state["carbon_profile"]
        )

        return {"proposal": proposal}

    def control(state: OptimizationState) -> dict[str, Any]:
        current_setpoints = tools.call("get_hvac_setpoints")

        return {
            "controller_result": controller.apply(
                state["proposal"], current_setpoints=current_setpoints
            ),
            "current_setpoints": current_setpoints,
        }

    def run_simulation(state: OptimizationState) -> dict[str, Any]:
        cycle = state["cycle"]

        idf_path = str(Path(MODELS_DIR) / f"cycle_{cycle}.idf")
        tools.call("save_building", path=idf_path)

        output_dir = str(Path(OUTPUT_DIR) / f"cycle_{cycle}")
        simulation_result = tools.call(
            "run_simulation_tool",
            idf_path=idf_path,
            output_directory=output_dir,
        )

        return {"simulation_result": simulation_result, "idf_path": idf_path}

    def parse_telemetry(state: OptimizationState) -> dict[str, Any]:
        simulation_result = state["simulation_result"]

        sql_file = getattr(simulation_result, "sql_file", None)
        runtime_seconds = getattr(simulation_result, "runtime_seconds", None)

        if sql_file is None and isinstance(simulation_result, dict):
            sql_file = simulation_result.get("sql_file")
            runtime_seconds = simulation_result.get("runtime_seconds")

        current_state = tools.call(
            "read_building_state_tool",
            sql_file=str(sql_file),
            metadata=state["metadata"],
            runtime_seconds=runtime_seconds,
        )

        return {"current_state": current_state}

    def evaluate(state: OptimizationState) -> dict[str, Any]:
        snapshot = OptimizationSnapshot(
            previous=state["baseline_state"],
            current=state["current_state"],
        )

        return {"evaluation": tools.call("evaluate_snapshot", snapshot=snapshot)}

    def analyze(state: OptimizationState) -> dict[str, Any]:
        report = analyst.explain(
            state["baseline_state"], state["current_state"], state["evaluation"]
        )

        return {"analyst_report": report}

    def reflect(state: OptimizationState) -> dict[str, Any]:
        result = reflection.reflect(
            cycle=state["cycle"],
            proposal=state["proposal"],
            predicted_savings_percent=state["proposal"].predicted_savings_percent,
            evaluation=state["evaluation"],
            state=state["current_state"],
            carbon_intensity_at_decision=_first_carbon_intensity(state["carbon_profile"]),
            previous_score=state.get("previous_score"),
            current_setpoints=state.get("current_setpoints"),
        )

        if result.should_rollback:
            tools.call("restore_snapshot", name="baseline")

        return {"reflection": result}

    def store_experience(state: OptimizationState) -> dict[str, Any]:
        memory.store(state["reflection"].experience)

        return {}

    def satisfied_check(state: OptimizationState) -> dict[str, Any]:
        return {"satisfied": bool(state["evaluation"].passed)}

    graph: StateGraph[OptimizationState] = StateGraph(OptimizationState)

    graph.add_node("read_metrics", read_metrics)
    graph.add_node("memory_retrieval", memory_retrieval)
    graph.add_node("planner", plan)
    graph.add_node("controller", control)
    graph.add_node("run_simulation", run_simulation)
    graph.add_node("telemetry_parser", parse_telemetry)
    graph.add_node("evaluation", evaluate)
    graph.add_node("analyst", analyze)
    graph.add_node("reflection", reflect)
    graph.add_node("store_experience", store_experience)
    graph.add_node("satisfied_check", satisfied_check)

    graph.set_entry_point("read_metrics")
    graph.add_edge("read_metrics", "memory_retrieval")
    graph.add_edge("memory_retrieval", "planner")
    graph.add_edge("planner", "controller")
    graph.add_edge("controller", "run_simulation")
    graph.add_edge("run_simulation", "telemetry_parser")
    graph.add_edge("telemetry_parser", "evaluation")
    graph.add_edge("evaluation", "analyst")
    graph.add_edge("analyst", "reflection")
    graph.add_edge("reflection", "store_experience")
    graph.add_edge("store_experience", "satisfied_check")
    graph.add_edge("satisfied_check", END)

    return graph.compile()


def run_optimization_loop(
    graph,
    baseline_state: BuildingState,
    metadata: BuildingMetadata,
    max_cycles: int = MAX_OPTIMIZATION_CYCLES,
    on_cycle: Callable[[int, OptimizationState], None] | None = None,
) -> list[OptimizationState]:
    """Run the per-cycle graph repeatedly until satisfied or max_cycles.

    Each iteration threads the prior cycle's resulting state and evaluation
    score into the next one's input, and stops early on the first cycle
    whose evaluation passes. If given, on_cycle(cycle, result) fires right
    after each cycle completes -- lets a caller (the dashboard) show live
    progress without re-implementing this loop itself.
    """

    history: list[OptimizationState] = []

    current_state = baseline_state
    previous_score: float | None = None

    for cycle in range(1, max_cycles + 1):
        result = graph.invoke(
            {
                "cycle": cycle,
                "max_cycles": max_cycles,
                "metadata": metadata,
                "baseline_state": baseline_state,
                "current_state": current_state,
                "previous_score": previous_score,
            }
        )

        history.append(result)

        current_state = result["current_state"]
        previous_score = result["evaluation"].score.overall_score

        if on_cycle is not None:
            on_cycle(cycle, result)

        if result.get("satisfied"):
            break

    return history


__all__ = [
    "OptimizationState",
    "build_cycle_graph",
    "run_optimization_loop",
]
