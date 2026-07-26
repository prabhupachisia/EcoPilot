from fastmcp import FastMCP

from agent.tools import FastMCPToolExecutor
from mcp_server.dependencies import DependencyProvider
from mcp_server.tools.evaluation import (
    EvaluationRecommendation,
    evaluate_snapshot,
    recommendation_value,
    register_evaluation_tools,
    summarize_evaluation,
)
from telemetry.models import OptimizationSnapshot
from tests.fixtures.building_state import make_building_state


def make_snapshot() -> OptimizationSnapshot:
    return OptimizationSnapshot(
        previous=make_building_state(total_energy_kwh=120.0),
        current=make_building_state(total_energy_kwh=100.0),
    )


def test_recommendation_value_accepts_the_enum() -> None:
    assert recommendation_value(EvaluationRecommendation.ACCEPT) == "accept"


def test_recommendation_value_accepts_a_plain_string() -> None:
    """This is the shape fastmcp's client hands back after a real MCP round
    trip -- the whole point of this function existing."""

    assert recommendation_value("accept") == "accept"


def test_summarize_evaluation_handles_a_string_recommendation() -> None:
    """Regression test: summarize_evaluation used to do
    result.recommendation.value.upper() unconditionally, which crashed with
    AttributeError the moment `recommendation` was a plain string rather
    than an EvaluationRecommendation -- exactly what happens after a real
    (non-dry-run) evaluate_snapshot call, see the round-trip test below.
    """

    evaluation = evaluate_snapshot(make_snapshot())
    evaluation.recommendation = evaluation.recommendation.value  # simulate the round trip

    summary = summarize_evaluation(evaluation)

    assert "Recommendation: ACCEPT" in summary or "Recommendation: REVIEW" in summary or "Recommendation: REJECT" in summary


def test_evaluate_snapshot_recommendation_survives_a_real_mcp_round_trip() -> None:
    """The actual bug: fastmcp's client-side reconstruction of a dataclass
    returned from a real tool call doesn't always rehydrate a nested Enum
    field back into the Enum type -- it can come back as the plain string
    it was serialized to. This only shows up going through the real wire
    (agent.tools.FastMCPToolExecutor), not a same-process call or a
    FakeToolExecutor, which is exactly why it wasn't caught until a live
    (non-dry-run) run hit it.
    """

    server = FastMCP("test-evaluation")
    register_evaluation_tools(server, DependencyProvider())

    executor = FastMCPToolExecutor(server)

    result = executor.call("evaluate_snapshot", snapshot=make_snapshot())

    # Whatever shape `recommendation` came back as, this must not raise.
    summary = summarize_evaluation(result)

    assert "Recommendation:" in summary
