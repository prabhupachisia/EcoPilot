from pathlib import Path

from agent.llm import FakeLLMClient, LLMResponse, ToolCall
from agent.memory import ExperienceStore
from agent.orchestrator import build_cycle_graph, run_optimization_loop
from agent.safety import SafetySupervisor
from agent.tools import FakeToolExecutor
from mcp_server.tools.evaluation import (
    CarbonComparison,
    ComfortComparison,
    EnergyComparison,
    EvaluationRecommendation,
    EvaluationResult,
    EvaluationScore,
    PeakDemandComparison,
)
from telemetry.models import BuildingMetadata
from tests.fixtures.building_state import make_building_state


class FakeActionResult:
    def __init__(self, success: bool = True) -> None:
        self.success = success


class FakeSimulationResult:
    def __init__(self, sql_file: str = "output/eplusout.sql", runtime_seconds: float = 12.0) -> None:
        self.sql_file = sql_file
        self.runtime_seconds = runtime_seconds


def make_evaluation(passed: bool, overall_score: float, savings_percent: float = 5.0) -> EvaluationResult:
    return EvaluationResult(
        energy=EnergyComparison(100.0, 100.0 * (1 - savings_percent / 100), 0.0, savings_percent),
        comfort=ComfortComparison(0.4, 0.3, 8.0, 6.0, 1.0, 0.5, True),
        carbon=CarbonComparison(40.0, 35.0, 5.0, 12.5),
        peak=PeakDemandComparison(10.0, 9.0, 1.0, 10.0),
        score=EvaluationScore(80.0, 85.0, 82.0, 75.0, overall_score),
        recommendation=EvaluationRecommendation.ACCEPT if passed else EvaluationRecommendation.REVIEW,
        passed=passed,
    )


def make_tools(evaluation: EvaluationResult) -> FakeToolExecutor:
    """A FakeToolExecutor wired with sensible defaults for a full cycle.

    Queued responses are NOT consumed (unlike FakeLLMClient) -- calling the
    same tool repeatedly across multiple cycles just returns the same
    queued value each time, so one instance can drive a multi-cycle loop.
    """

    tools = FakeToolExecutor()
    tools.queue("get_carbon_intensity_profile", {0: 0.3, 12: 0.2, 18: 0.5})
    tools.queue(
        "get_hvac_setpoints",
        {"cooling_setpoint_temperature": 23.9, "heating_setpoint_temperature": 21.0},
    )
    tools.queue("save_building", "energyplus/models/cycle.idf")
    tools.queue("run_simulation_tool", FakeSimulationResult())
    tools.queue("read_building_state_tool", make_building_state(average_occupancy=8.0))
    tools.queue("evaluate_snapshot", evaluation)
    tools.queue("restore_snapshot", None)
    tools.queue(
        "apply_building_actions",
        lambda actions: [FakeActionResult(success=True) for _ in actions],
    )
    tools.queue("begin_transaction", None)
    tools.queue("commit_transaction", None)
    tools.queue("rollback_transaction", None)
    return tools


def make_llm_with_proposals(count: int = 1) -> FakeLLMClient:
    """Each cycle makes three LLM calls in order: Planner, Analyst, Reflection."""

    responses: list[LLMResponse] = []

    for _ in range(count):
        responses.append(
            LLMResponse(
                content="Occupancy dropped, raising cooling setpoint.",
                tool_calls=[ToolCall(name="set_hvac_setpoints", arguments={"cooling_c": 25.0})],
            )
        )
        responses.append(LLMResponse(content="Energy fell because occupancy dropped."))
        responses.append(LLMResponse(content="Prediction was close to the actual outcome."))

    return FakeLLMClient(responses=responses)


def make_metadata() -> BuildingMetadata:
    return BuildingMetadata(
        building_name="Test",
        location="Test",
        floor_area=1000.0,
        weather_file=Path("weather.epw"),
        idf_file=Path("building.idf"),
    )


def test_single_cycle_populates_the_full_state(tmp_path: Path) -> None:
    evaluation = make_evaluation(passed=True, overall_score=90.0)
    tools = make_tools(evaluation)
    memory = ExperienceStore(path=tmp_path / "experiences.json")

    graph = build_cycle_graph(
        llm=make_llm_with_proposals(), tools=tools, memory=memory, safety=SafetySupervisor()
    )

    result = graph.invoke(
        {
            "cycle": 1,
            "max_cycles": 5,
            "metadata": make_metadata(),
            "baseline_state": make_building_state(average_occupancy=40.0),
            "current_state": make_building_state(average_occupancy=40.0),
            "previous_score": None,
        }
    )

    assert result["carbon_profile"] == {0: 0.3, 12: 0.2, 18: 0.5}
    assert result["proposal"].actions
    assert result["controller_result"].committed is True
    assert result["evaluation"] is evaluation
    assert result["analyst_report"].narrative
    assert result["reflection"].experience.cycle == 1
    assert result["satisfied"] is True
    assert memory.count == 1


def test_run_optimization_loop_stops_early_when_satisfied(tmp_path: Path) -> None:
    evaluation = make_evaluation(passed=True, overall_score=90.0)
    tools = make_tools(evaluation)
    memory = ExperienceStore(path=tmp_path / "experiences.json")

    graph = build_cycle_graph(
        llm=make_llm_with_proposals(), tools=tools, memory=memory, safety=SafetySupervisor()
    )

    history = run_optimization_loop(
        graph,
        baseline_state=make_building_state(),
        metadata=make_metadata(),
        max_cycles=5,
    )

    assert len(history) == 1
    assert history[0]["satisfied"] is True


def test_run_optimization_loop_runs_to_max_cycles_when_never_satisfied(tmp_path: Path) -> None:
    max_cycles = 3
    evaluation = make_evaluation(passed=False, overall_score=80.0)
    tools = make_tools(evaluation)
    memory = ExperienceStore(path=tmp_path / "experiences.json")

    graph = build_cycle_graph(
        llm=make_llm_with_proposals(max_cycles),
        tools=tools,
        memory=memory,
        safety=SafetySupervisor(),
    )

    history = run_optimization_loop(
        graph,
        baseline_state=make_building_state(),
        metadata=make_metadata(),
        max_cycles=max_cycles,
    )

    assert len(history) == max_cycles
    assert all(not entry["satisfied"] for entry in history)
    assert memory.count == max_cycles


def test_run_optimization_loop_calls_on_cycle_once_per_cycle(tmp_path: Path) -> None:
    max_cycles = 3
    evaluation = make_evaluation(passed=False, overall_score=80.0)
    tools = make_tools(evaluation)
    memory = ExperienceStore(path=tmp_path / "experiences.json")

    graph = build_cycle_graph(
        llm=make_llm_with_proposals(max_cycles),
        tools=tools,
        memory=memory,
        safety=SafetySupervisor(),
    )

    seen_cycles = []
    run_optimization_loop(
        graph,
        baseline_state=make_building_state(),
        metadata=make_metadata(),
        max_cycles=max_cycles,
        on_cycle=lambda cycle, result: seen_cycles.append((cycle, result["cycle"])),
    )

    assert seen_cycles == [(1, 1), (2, 2), (3, 3)]


def test_run_optimization_loop_threads_previous_score_between_cycles(tmp_path: Path) -> None:
    max_cycles = 2
    evaluation = make_evaluation(passed=False, overall_score=80.0)
    tools = make_tools(evaluation)
    memory = ExperienceStore(path=tmp_path / "experiences.json")

    graph = build_cycle_graph(
        llm=make_llm_with_proposals(max_cycles),
        tools=tools,
        memory=memory,
        safety=SafetySupervisor(),
    )

    history = run_optimization_loop(
        graph,
        baseline_state=make_building_state(),
        metadata=make_metadata(),
        max_cycles=max_cycles,
    )

    assert history[0]["previous_score"] is None
    assert history[1]["previous_score"] == 80.0


def test_regression_triggers_rollback(tmp_path: Path) -> None:
    evaluation = make_evaluation(passed=False, overall_score=50.0)
    tools = make_tools(evaluation)
    memory = ExperienceStore(path=tmp_path / "experiences.json")

    graph = build_cycle_graph(
        llm=make_llm_with_proposals(),
        tools=tools,
        memory=memory,
        safety=SafetySupervisor(regression_threshold=0.10),
    )

    result = graph.invoke(
        {
            "cycle": 2,
            "max_cycles": 5,
            "metadata": make_metadata(),
            "baseline_state": make_building_state(),
            "current_state": make_building_state(),
            "previous_score": 90.0,
        }
    )

    assert result["reflection"].should_rollback is True
    assert ("restore_snapshot", {"name": "baseline"}) in tools.calls


def test_reflection_confidence_uses_planners_own_predicted_savings(tmp_path: Path) -> None:
    """Regression test: predicted_savings_percent used to be hardcoded to
    0.0 in the reflect node regardless of what the Planner actually said,
    which made the confidence score meaningless. It should now be computed
    against the Planner's own expected_savings_percent tool-call argument.
    """

    evaluation = make_evaluation(passed=True, overall_score=90.0, savings_percent=5.0)
    tools = make_tools(evaluation)
    memory = ExperienceStore(path=tmp_path / "experiences.json")

    llm = FakeLLMClient(
        responses=[
            LLMResponse(
                content="Raising cooling setpoint should save about 5%.",
                tool_calls=[
                    ToolCall(
                        name="set_hvac_setpoints",
                        arguments={"cooling_c": 25.0, "expected_savings_percent": 5.0},
                    )
                ],
            ),
            LLMResponse(content="Energy fell because occupancy dropped."),
            LLMResponse(content="Prediction matched the actual outcome."),
        ]
    )

    graph = build_cycle_graph(llm=llm, tools=tools, memory=memory, safety=SafetySupervisor())

    result = graph.invoke(
        {
            "cycle": 1,
            "max_cycles": 5,
            "metadata": make_metadata(),
            "baseline_state": make_building_state(average_occupancy=40.0),
            "current_state": make_building_state(average_occupancy=40.0),
            "previous_score": None,
        }
    )

    assert result["proposal"].predicted_savings_percent == 5.0
    assert result["reflection"].confidence == 1.0


def test_no_rollback_when_regression_within_threshold(tmp_path: Path) -> None:
    evaluation = make_evaluation(passed=True, overall_score=85.0)
    tools = make_tools(evaluation)
    memory = ExperienceStore(path=tmp_path / "experiences.json")

    graph = build_cycle_graph(
        llm=make_llm_with_proposals(),
        tools=tools,
        memory=memory,
        safety=SafetySupervisor(regression_threshold=0.10),
    )

    result = graph.invoke(
        {
            "cycle": 2,
            "max_cycles": 5,
            "metadata": make_metadata(),
            "baseline_state": make_building_state(),
            "current_state": make_building_state(),
            "previous_score": 90.0,
        }
    )

    assert result["reflection"].should_rollback is False
    assert ("restore_snapshot", {"name": "baseline"}) not in tools.calls
