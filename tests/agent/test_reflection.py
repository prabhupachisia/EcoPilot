import pytest

from agent.llm import FakeLLMClient, LLMResponse
from agent.planner import PlannerProposal
from agent.reflection import Reflection
from agent.safety import SafetySupervisor
from mcp_server.tools.building.models import ActionType, BuildingAction, BuildingComponent
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


def make_evaluation(savings_percent: float = 5.0, overall_score: float = 80.0, passed: bool = True) -> EvaluationResult:
    return EvaluationResult(
        energy=EnergyComparison(100.0, 100.0 * (1 - savings_percent / 100), 0.0, savings_percent),
        comfort=ComfortComparison(0.4, 0.3, 8.0, 6.0, 1.0, 0.5, True),
        carbon=CarbonComparison(40.0, 35.0, 5.0, 12.5),
        peak=PeakDemandComparison(10.0, 9.0, 1.0, 10.0),
        score=EvaluationScore(80.0, 85.0, 82.0, 75.0, overall_score),
        recommendation=EvaluationRecommendation.ACCEPT,
        passed=passed,
    )


def make_proposal() -> PlannerProposal:
    return PlannerProposal(
        actions=[
            BuildingAction(
                component=BuildingComponent.THERMOSTAT,
                action=ActionType.SET,
                target="building",
                parameter="cooling_setpoint_temperature",
                value=25.0,
                reason="Low occupancy",
            )
        ],
        rationale="Raised cooling setpoint due to low occupancy.",
    )


def test_confidence_is_high_when_prediction_matches_actual() -> None:
    reflection = Reflection(safety=SafetySupervisor())

    result = reflection.reflect(
        cycle=1,
        proposal=make_proposal(),
        predicted_savings_percent=5.0,
        evaluation=make_evaluation(savings_percent=5.0),
        state=make_building_state(),
        carbon_intensity_at_decision=0.4,
    )

    assert result.confidence == 1.0


def test_confidence_drops_with_larger_prediction_error() -> None:
    reflection = Reflection(safety=SafetySupervisor())

    result = reflection.reflect(
        cycle=1,
        proposal=make_proposal(),
        predicted_savings_percent=5.0,
        evaluation=make_evaluation(savings_percent=25.0),
        state=make_building_state(),
        carbon_intensity_at_decision=0.4,
    )

    assert result.confidence == pytest.approx(0.8)


def test_experience_captures_situation_and_outcome() -> None:
    reflection = Reflection(safety=SafetySupervisor())

    result = reflection.reflect(
        cycle=2,
        proposal=make_proposal(),
        predicted_savings_percent=5.0,
        evaluation=make_evaluation(savings_percent=5.0),
        state=make_building_state(outdoor_temperature=31.0, average_occupancy=8.0),
        carbon_intensity_at_decision=0.35,
    )

    experience = result.experience
    assert experience.cycle == 2
    assert experience.weather_outdoor_temp == 31.0
    assert experience.occupancy == 8.0
    assert experience.cooling_setpoint == 25.0
    assert experience.carbon_intensity == 0.35
    assert experience.savings_percent == 5.0
    assert experience.action_summary == "Raised cooling setpoint due to low occupancy."
    assert experience.confidence == 1.0
    assert experience.outcome == "success"


def test_should_rollback_true_on_regression() -> None:
    reflection = Reflection(safety=SafetySupervisor(regression_threshold=0.10))

    result = reflection.reflect(
        cycle=3,
        proposal=make_proposal(),
        predicted_savings_percent=5.0,
        evaluation=make_evaluation(savings_percent=5.0, overall_score=50.0, passed=False),
        state=make_building_state(),
        carbon_intensity_at_decision=0.4,
        previous_score=80.0,
    )

    assert result.should_rollback is True
    assert result.experience.outcome == "rollback"


def test_should_rollback_false_without_previous_score() -> None:
    reflection = Reflection(safety=SafetySupervisor())

    result = reflection.reflect(
        cycle=1,
        proposal=make_proposal(),
        predicted_savings_percent=5.0,
        evaluation=make_evaluation(savings_percent=5.0),
        state=make_building_state(),
        carbon_intensity_at_decision=0.4,
        previous_score=None,
    )

    assert result.should_rollback is False


def test_narrative_is_none_without_an_llm() -> None:
    reflection = Reflection(safety=SafetySupervisor())

    result = reflection.reflect(
        cycle=1,
        proposal=make_proposal(),
        predicted_savings_percent=5.0,
        evaluation=make_evaluation(),
        state=make_building_state(),
        carbon_intensity_at_decision=0.4,
    )

    assert result.narrative is None


def test_narrative_uses_llm_when_provided() -> None:
    llm = FakeLLMClient(responses=[LLMResponse(content="Slightly outperformed the prediction.")])
    reflection = Reflection(safety=SafetySupervisor(), llm=llm)

    result = reflection.reflect(
        cycle=1,
        proposal=make_proposal(),
        predicted_savings_percent=5.0,
        evaluation=make_evaluation(savings_percent=6.0),
        state=make_building_state(),
        carbon_intensity_at_decision=0.4,
    )

    assert result.narrative == "Slightly outperformed the prediction."
    assert "Raised cooling setpoint due to low occupancy." in llm.calls[0]["user_prompt"]
