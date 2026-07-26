from agent.analyst import Analyst
from agent.llm import FakeLLMClient, LLMResponse
from mcp_server.tools.evaluation import (
    CarbonComparison,
    ComfortComparison,
    EnergyComparison,
    EvaluationRecommendation,
    EvaluationResult,
    EvaluationScore,
    PeakDemandComparison,
)
from tests.fixtures.building_state import make_building_state


def make_evaluation() -> EvaluationResult:
    return EvaluationResult(
        energy=EnergyComparison(120.0, 100.0, 20.0, 16.67),
        comfort=ComfortComparison(0.5, 0.3, 10.0, 7.0, 2.0, 1.0, True),
        carbon=CarbonComparison(50.0, 40.0, 10.0, 20.0),
        peak=PeakDemandComparison(15.0, 12.0, 3.0, 20.0),
        score=EvaluationScore(80.0, 85.0, 82.0, 75.0, 81.2),
        recommendation=EvaluationRecommendation.ACCEPT,
        passed=True,
    )


def test_explain_returns_llm_narrative() -> None:
    llm = FakeLLMClient(responses=[LLMResponse(content="Energy fell because occupancy dropped.")])
    analyst = Analyst(llm=llm)

    report = analyst.explain(
        baseline=make_building_state(average_occupancy=40.0),
        current=make_building_state(average_occupancy=10.0),
        evaluation=make_evaluation(),
    )

    assert report.narrative == "Energy fell because occupancy dropped."


def test_explain_includes_key_metrics_in_the_prompt() -> None:
    llm = FakeLLMClient(responses=[LLMResponse(content="ok")])
    analyst = Analyst(llm=llm)

    analyst.explain(
        baseline=make_building_state(average_occupancy=40.0),
        current=make_building_state(average_occupancy=10.0),
        evaluation=make_evaluation(),
    )

    prompt = llm.calls[0]["user_prompt"]
    assert "16.67" in prompt
    assert "120.00" in prompt
    assert "40.0" in prompt
    assert "10.0" in prompt
