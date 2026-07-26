from dataclasses import dataclass

from agent.controller import Controller
from agent.planner import PlannerProposal
from agent.safety import SafetySupervisor
from agent.tools import FakeToolExecutor
from mcp_server.tools.building.models import ActionType, BuildingAction, BuildingComponent


@dataclass
class FakeActionResult:
    success: bool
    message: str = ""


def make_action(parameter: str = "cooling_setpoint_temperature", value: float = 25.0) -> BuildingAction:
    return BuildingAction(
        component=BuildingComponent.THERMOSTAT,
        action=ActionType.SET,
        target="building",
        parameter=parameter,
        value=value,
        reason="test",
    )


def test_apply_with_no_actions_returns_early_without_touching_tools() -> None:
    tools = FakeToolExecutor()
    controller = Controller(tools=tools, safety=SafetySupervisor())

    result = controller.apply(PlannerProposal(actions=[], rationale="nothing to do"))

    assert result.committed is False
    assert tools.calls == []


def test_apply_commits_when_all_actions_succeed() -> None:
    tools = FakeToolExecutor()
    tools.queue("begin_transaction", None)
    tools.queue("apply_building_actions", [FakeActionResult(success=True)])
    tools.queue("commit_transaction", None)

    controller = Controller(tools=tools, safety=SafetySupervisor())
    proposal = PlannerProposal(actions=[make_action()], rationale="raise cooling setpoint")

    result = controller.apply(proposal)

    assert result.committed is True
    called_tools = [name for name, _ in tools.calls]
    assert called_tools == ["begin_transaction", "apply_building_actions", "commit_transaction"]


def test_apply_rolls_back_when_an_action_fails() -> None:
    tools = FakeToolExecutor()
    tools.queue("begin_transaction", None)
    tools.queue(
        "apply_building_actions",
        [FakeActionResult(success=True), FakeActionResult(success=False, message="boom")],
    )
    tools.queue("rollback_transaction", None)

    controller = Controller(tools=tools, safety=SafetySupervisor())
    proposal = PlannerProposal(
        actions=[make_action(), make_action("heating_setpoint_temperature", 20.0)],
        rationale="test",
    )

    result = controller.apply(proposal)

    assert result.committed is False
    called_tools = [name for name, _ in tools.calls]
    assert called_tools == ["begin_transaction", "apply_building_actions", "rollback_transaction"]


def test_apply_rolls_back_on_exception() -> None:
    tools = FakeToolExecutor()
    tools.queue("begin_transaction", None)

    def raise_error(**kwargs):
        raise RuntimeError("MCP call failed")

    tools.queue("apply_building_actions", raise_error)
    tools.queue("rollback_transaction", None)

    controller = Controller(tools=tools, safety=SafetySupervisor())
    proposal = PlannerProposal(actions=[make_action()], rationale="test")

    result = controller.apply(proposal)

    assert result.committed is False
    assert "MCP call failed" in result.message


def test_apply_clips_out_of_range_setpoint_before_dispatch() -> None:
    tools = FakeToolExecutor()
    tools.queue("begin_transaction", None)

    captured = {}

    def capture_actions(actions):
        captured["actions"] = actions
        return [FakeActionResult(success=True) for _ in actions]

    tools.queue("apply_building_actions", capture_actions)
    tools.queue("commit_transaction", None)

    controller = Controller(
        tools=tools,
        safety=SafetySupervisor(cooling_range=(22.0, 28.0)),
    )
    proposal = PlannerProposal(actions=[make_action(value=35.0)], rationale="too hot")

    result = controller.apply(proposal)

    assert result.committed is True
    assert captured["actions"][0].value == 28.0
    assert result.safety_decisions[0].verdict.value == "clipped"


def test_apply_returns_early_when_all_actions_rejected() -> None:
    tools = FakeToolExecutor()
    controller = Controller(tools=tools, safety=SafetySupervisor())

    proposal = PlannerProposal(
        actions=[make_action(value="not-a-number")],
        rationale="bad value",
    )

    result = controller.apply(proposal)

    assert result.committed is False
    assert tools.calls == []
    assert result.safety_decisions[0].verdict.value == "rejected"


def test_apply_rejects_actions_that_narrow_the_deadband() -> None:
    tools = FakeToolExecutor()
    controller = Controller(tools=tools, safety=SafetySupervisor())

    proposal = PlannerProposal(
        actions=[
            make_action("cooling_setpoint_temperature", 23.6),
            make_action("heating_setpoint_temperature", 21.3),
        ],
        rationale="narrow the deadband",
    )

    result = controller.apply(
        proposal,
        current_setpoints={
            "cooling_setpoint_temperature": 23.9,
            "heating_setpoint_temperature": 21.1,
        },
    )

    assert result.committed is False
    assert tools.calls == []
    assert all(decision.verdict.value == "rejected" for decision in result.safety_decisions)
