from agent.llm import FakeLLMClient, LLMResponse, ToolCall
from agent.memory import Experience
from agent.planner import Planner
from agent.tools import FakeToolExecutor
from mcp_server.tools.building.models import BuildingComponent
from tests.fixtures.building_state import make_building_state


def make_planner(llm_response: LLMResponse) -> tuple[Planner, FakeLLMClient, FakeToolExecutor]:
    llm = FakeLLMClient(responses=[llm_response])
    tools = FakeToolExecutor()
    tools.queue(
        "get_hvac_setpoints",
        {"cooling_setpoint_temperature": 23.9, "heating_setpoint_temperature": 21.0},
    )
    return Planner(llm=llm, tools=tools), llm, tools


def test_propose_parses_set_hvac_setpoints_tool_call_into_actions() -> None:
    response = LLMResponse(
        content="Occupancy is low, raising the cooling setpoint to save energy.",
        tool_calls=[
            ToolCall(
                name="set_hvac_setpoints",
                arguments={"cooling_c": 26.0, "reason": "Low occupancy"},
            )
        ],
    )
    planner, _, _ = make_planner(response)

    proposal = planner.propose(
        state=make_building_state(),
        similar_cases=[],
        carbon_profile={},
    )

    assert len(proposal.actions) == 1
    action = proposal.actions[0]
    assert action.component is BuildingComponent.THERMOSTAT
    assert action.parameter == "cooling_setpoint_temperature"
    assert action.value == 26.0
    assert action.reason == "Low occupancy"
    assert proposal.rationale == response.content


def test_propose_handles_both_setpoints_in_one_call() -> None:
    response = LLMResponse(
        content="Adjusting both setpoints.",
        tool_calls=[
            ToolCall(name="set_hvac_setpoints", arguments={"cooling_c": 25.0, "heating_c": 19.0})
        ],
    )
    planner, _, _ = make_planner(response)

    proposal = planner.propose(make_building_state(), [], {})

    parameters = {action.parameter for action in proposal.actions}
    assert parameters == {"cooling_setpoint_temperature", "heating_setpoint_temperature"}


def test_propose_ignores_unrelated_tool_calls() -> None:
    response = LLMResponse(
        content="No change needed.",
        tool_calls=[ToolCall(name="some_other_tool", arguments={})],
    )
    planner, _, _ = make_planner(response)

    proposal = planner.propose(make_building_state(), [], {})

    assert proposal.actions == []


def test_propose_computes_target_hours_from_carbon_profile() -> None:
    response = LLMResponse(content="No change.", tool_calls=[])
    planner, _, _ = make_planner(response)

    carbon_profile = {0: 0.3, 6: 0.1, 12: 0.5, 18: 0.6, 20: 0.2}

    proposal = planner.propose(make_building_state(), [], carbon_profile)

    assert proposal.target_hours_for_precool == [6, 20, 0, 12]


def test_propose_reads_current_setpoints_before_calling_llm() -> None:
    response = LLMResponse(content="ok", tool_calls=[])
    planner, llm, tools = make_planner(response)

    planner.propose(make_building_state(), [], {})

    assert tools.calls == [("get_hvac_setpoints", {})]
    assert "23.9" in llm.calls[0]["user_prompt"]


def test_propose_includes_similar_cases_in_the_prompt() -> None:
    response = LLMResponse(content="ok", tool_calls=[])
    planner, llm, _ = make_planner(response)

    experience = Experience(
        cycle=3,
        weather_outdoor_temp=29.0,
        occupancy=8.0,
        cooling_setpoint=25.0,
        heating_setpoint=20.0,
        carbon_intensity=0.3,
        energy_kwh=90.0,
        savings_percent=6.5,
        action_summary="Raised cooling setpoint",
        outcome="success",
    )

    planner.propose(make_building_state(), [(experience, 0.05)], {})

    prompt = llm.calls[0]["user_prompt"]
    assert "cycle 3" in prompt
    assert "6.5" in prompt
