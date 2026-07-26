from agent.prompts import (
    ANALYST_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    REFLECTION_SYSTEM_PROMPT,
    format_planner_prompt,
)


def test_format_planner_prompt_fills_in_safety_bounds() -> None:
    prompt = format_planner_prompt(
        cooling_range=(22.0, 28.0),
        heating_range=(18.0, 22.0),
    )

    assert "22.0" in prompt
    assert "28.0" in prompt
    assert "18.0" in prompt
    assert "22.0" in prompt
    assert "{cooling_low}" not in prompt


def test_prompts_mention_carbon_and_safety_concepts() -> None:
    assert "carbon" in PLANNER_SYSTEM_PROMPT.lower()
    assert "safety" in PLANNER_SYSTEM_PROMPT.lower()


def test_analyst_prompt_forbids_proposing_actions() -> None:
    assert "planner" in ANALYST_SYSTEM_PROMPT.lower()


def test_reflection_prompt_defers_confidence_computation() -> None:
    assert "deterministically" in REFLECTION_SYSTEM_PROMPT.lower()


def test_planner_prompt_says_to_widen_not_narrow_the_deadband() -> None:
    assert "widen" in PLANNER_SYSTEM_PROMPT.lower()


def test_planner_prompt_asks_for_a_real_savings_estimate() -> None:
    assert "expected_savings_percent" in PLANNER_SYSTEM_PROMPT


def test_reflection_prompt_forbids_inventing_ungrounded_causes() -> None:
    assert "invent" in REFLECTION_SYSTEM_PROMPT.lower()
