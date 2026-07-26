from pathlib import Path

import pytest

from agent.memory import Experience, ExperienceStore


def make_experience(cycle: int, **overrides) -> Experience:
    defaults = dict(
        cycle=cycle,
        weather_outdoor_temp=30.0,
        occupancy=10.0,
        cooling_setpoint=24.0,
        heating_setpoint=20.0,
        carbon_intensity=0.4,
        energy_kwh=100.0,
        savings_percent=5.0,
        action_summary="Raised cooling setpoint to 24C",
    )
    defaults.update(overrides)
    return Experience(**defaults)


@pytest.fixture
def store(tmp_path: Path) -> ExperienceStore:
    return ExperienceStore(path=tmp_path / "experiences.json")


def test_empty_store_retrieves_nothing(store: ExperienceStore) -> None:
    assert store.count == 0
    assert store.retrieve_similar(weather_outdoor_temp=30.0, occupancy=10.0) == []


def test_store_persists_to_disk(tmp_path: Path) -> None:
    path = tmp_path / "experiences.json"
    store = ExperienceStore(path=path)

    store.store(make_experience(cycle=1))

    assert path.exists()

    reloaded = ExperienceStore(path=path)
    assert reloaded.count == 1
    assert reloaded.history()[0].action_summary == "Raised cooling setpoint to 24C"


def test_retrieve_similar_returns_nearest_first(store: ExperienceStore) -> None:
    close = make_experience(cycle=1, weather_outdoor_temp=30.0, occupancy=10.0)
    far = make_experience(cycle=2, weather_outdoor_temp=5.0, occupancy=0.0)

    store.store(far)
    store.store(close)

    results = store.retrieve_similar(weather_outdoor_temp=31.0, occupancy=9.0, top_k=2)

    assert len(results) == 2
    assert results[0][0] is close
    assert results[0][1] < results[1][1]


def test_retrieve_similar_caps_top_k_to_available_experiences(store: ExperienceStore) -> None:
    store.store(make_experience(cycle=1))

    results = store.retrieve_similar(weather_outdoor_temp=30.0, occupancy=10.0, top_k=5)

    assert len(results) == 1


def test_history_is_sorted_by_cycle(store: ExperienceStore) -> None:
    store.store(make_experience(cycle=3))
    store.store(make_experience(cycle=1))
    store.store(make_experience(cycle=2))

    assert [experience.cycle for experience in store.history()] == [1, 2, 3]


def test_history_limit_returns_most_recent(store: ExperienceStore) -> None:
    for cycle in range(1, 6):
        store.store(make_experience(cycle=cycle))

    recent = store.history(limit=2)

    assert [experience.cycle for experience in recent] == [4, 5]


def test_confidence_trend_skips_missing_confidence(store: ExperienceStore) -> None:
    store.store(make_experience(cycle=1, confidence=0.9))
    store.store(make_experience(cycle=2, confidence=None))
    store.store(make_experience(cycle=3, confidence=0.7))

    assert store.confidence_trend() == [0.9, 0.7]


def test_clear_removes_all_experiences(store: ExperienceStore) -> None:
    store.store(make_experience(cycle=1))
    store.clear()

    assert store.count == 0


def test_experience_ids_are_unique() -> None:
    first = make_experience(cycle=1)
    second = make_experience(cycle=2)

    assert first.id != second.id
