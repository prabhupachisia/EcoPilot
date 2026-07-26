from unittest.mock import Mock

from agent.memory import Experience, ExperienceStore
from mcp_server.dependencies import DependencyProvider
from mcp_server.tools.memory import (
    get_confidence_trend,
    get_decision_history,
    retrieve_similar_cases,
    store_experience,
)


def make_experience(cycle: int = 1) -> Experience:
    return Experience(
        cycle=cycle,
        weather_outdoor_temp=30.0,
        occupancy=10.0,
        cooling_setpoint=24.0,
        heating_setpoint=20.0,
        carbon_intensity=0.4,
        energy_kwh=100.0,
        savings_percent=5.0,
        action_summary="Raised cooling setpoint",
    )


def test_store_experience_delegates_to_experience_memory() -> None:
    memory = Mock(spec=ExperienceStore)
    memory.store.return_value = "experience-id"

    dependencies = DependencyProvider(experience_memory=memory)
    experience = make_experience()

    result = store_experience(dependencies, experience)

    memory.store.assert_called_once_with(experience)
    assert result == "experience-id"


def test_retrieve_similar_cases_delegates_with_all_arguments() -> None:
    memory = Mock(spec=ExperienceStore)
    memory.retrieve_similar.return_value = [(make_experience(), 0.1)]

    dependencies = DependencyProvider(experience_memory=memory)

    result = retrieve_similar_cases(
        dependencies,
        weather_outdoor_temp=28.0,
        occupancy=8.0,
        cooling_setpoint=25.0,
        heating_setpoint=19.0,
        carbon_intensity=0.5,
        top_k=2,
    )

    memory.retrieve_similar.assert_called_once_with(
        weather_outdoor_temp=28.0,
        occupancy=8.0,
        cooling_setpoint=25.0,
        heating_setpoint=19.0,
        carbon_intensity=0.5,
        top_k=2,
    )
    assert len(result) == 1


def test_get_decision_history_delegates_with_limit() -> None:
    memory = Mock(spec=ExperienceStore)
    memory.history.return_value = [make_experience()]

    dependencies = DependencyProvider(experience_memory=memory)

    result = get_decision_history(dependencies, limit=5)

    memory.history.assert_called_once_with(limit=5)
    assert len(result) == 1


def test_get_confidence_trend_delegates() -> None:
    memory = Mock(spec=ExperienceStore)
    memory.confidence_trend.return_value = [0.8, 0.9]

    dependencies = DependencyProvider(experience_memory=memory)

    result = get_confidence_trend(dependencies)

    memory.confidence_trend.assert_called_once_with()
    assert result == [0.8, 0.9]
