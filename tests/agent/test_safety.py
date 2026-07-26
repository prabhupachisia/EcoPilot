from agent.safety import SafetySupervisor, SafetyVerdict, apply_safety_decision
from mcp_server.tools.building.models import ActionType, BuildingAction, BuildingComponent


def make_action(parameter: str, value, component=BuildingComponent.THERMOSTAT) -> BuildingAction:
    return BuildingAction(
        component=component,
        action=ActionType.SET,
        target="building",
        parameter=parameter,
        value=value,
        reason="test",
    )


def test_value_within_range_is_accepted() -> None:
    supervisor = SafetySupervisor()

    decision = supervisor.validate(make_action("cooling_setpoint_temperature", 25.0))

    assert decision.verdict is SafetyVerdict.ACCEPT
    assert decision.applied_value == 25.0


def test_value_above_range_is_clipped() -> None:
    supervisor = SafetySupervisor(cooling_range=(22.0, 28.0))

    decision = supervisor.validate(make_action("cooling_setpoint_temperature", 32.0))

    assert decision.verdict is SafetyVerdict.CLIPPED
    assert decision.applied_value == 28.0
    assert decision.original_value == 32.0


def test_value_below_range_is_clipped() -> None:
    supervisor = SafetySupervisor(heating_range=(18.0, 22.0))

    decision = supervisor.validate(make_action("heating_setpoint_temperature", 10.0))

    assert decision.verdict is SafetyVerdict.CLIPPED
    assert decision.applied_value == 18.0


def test_non_numeric_value_is_rejected() -> None:
    supervisor = SafetySupervisor()

    decision = supervisor.validate(make_action("cooling_setpoint_temperature", "warm"))

    assert decision.verdict is SafetyVerdict.REJECTED
    assert decision.applied_value is None


def test_unbounded_parameter_is_accepted_as_is() -> None:
    supervisor = SafetySupervisor()

    decision = supervisor.validate(
        make_action("fan_efficiency", 0.9, component=BuildingComponent.HVAC)
    )

    assert decision.verdict is SafetyVerdict.ACCEPT
    assert decision.applied_value == 0.9


def test_validate_batch_processes_every_action() -> None:
    supervisor = SafetySupervisor()

    decisions = supervisor.validate_batch(
        [
            make_action("cooling_setpoint_temperature", 25.0),
            make_action("cooling_setpoint_temperature", 40.0),
        ]
    )

    assert [decision.verdict for decision in decisions] == [
        SafetyVerdict.ACCEPT,
        SafetyVerdict.CLIPPED,
    ]


def test_apply_safety_decision_returns_action_with_clipped_value() -> None:
    supervisor = SafetySupervisor()
    action = make_action("cooling_setpoint_temperature", 32.0)

    decision = supervisor.validate(action)
    clipped_action = apply_safety_decision(action, decision)

    assert clipped_action.value == 28.0
    assert clipped_action.target == action.target
    assert clipped_action.reason == action.reason


def test_check_regression_true_when_drop_exceeds_threshold() -> None:
    supervisor = SafetySupervisor(regression_threshold=0.10)

    assert supervisor.check_regression(baseline_score=80.0, current_score=60.0) is True


def test_check_regression_false_when_drop_within_threshold() -> None:
    supervisor = SafetySupervisor(regression_threshold=0.10)

    assert supervisor.check_regression(baseline_score=80.0, current_score=76.0) is False


def test_check_regression_false_for_improvement() -> None:
    supervisor = SafetySupervisor()

    assert supervisor.check_regression(baseline_score=70.0, current_score=90.0) is False


def test_check_regression_false_for_non_positive_baseline() -> None:
    supervisor = SafetySupervisor()

    assert supervisor.check_regression(baseline_score=0.0, current_score=-5.0) is False


def test_check_regression_accepts_explicit_threshold_override() -> None:
    supervisor = SafetySupervisor(regression_threshold=0.5)

    assert supervisor.check_regression(baseline_score=100.0, current_score=80.0, threshold=0.1) is True


def test_validate_batch_rejects_a_proposal_that_narrows_the_deadband() -> None:
    """Regression test: a live run's Planner (a small local model) proposed
    lowering cooling from 23.9 to 23.6 and raising heating from 21.1 to 21.3
    -- narrowing the deadband from 2.8C to 2.3C -- which increases HVAC
    energy even though the Planner's own prompt says to widen it. Nothing
    caught this before; it should now be rejected outright.
    """

    supervisor = SafetySupervisor()

    decisions = supervisor.validate_batch(
        [
            make_action("cooling_setpoint_temperature", 23.6),
            make_action("heating_setpoint_temperature", 21.3),
        ],
        current_setpoints={
            "cooling_setpoint_temperature": 23.9,
            "heating_setpoint_temperature": 21.1,
        },
    )

    assert all(decision.verdict is SafetyVerdict.REJECTED for decision in decisions)


def test_validate_batch_allows_a_proposal_that_widens_the_deadband() -> None:
    supervisor = SafetySupervisor()

    decisions = supervisor.validate_batch(
        [
            make_action("cooling_setpoint_temperature", 24.5),
            make_action("heating_setpoint_temperature", 20.5),
        ],
        current_setpoints={
            "cooling_setpoint_temperature": 23.9,
            "heating_setpoint_temperature": 21.1,
        },
    )

    assert all(decision.verdict is SafetyVerdict.ACCEPT for decision in decisions)


def test_validate_batch_allows_a_single_setpoint_change_that_widens_the_gap() -> None:
    supervisor = SafetySupervisor()

    decisions = supervisor.validate_batch(
        [make_action("cooling_setpoint_temperature", 24.5)],
        current_setpoints={
            "cooling_setpoint_temperature": 23.9,
            "heating_setpoint_temperature": 21.1,
        },
    )

    assert decisions[0].verdict is SafetyVerdict.ACCEPT


def test_validate_batch_ignores_deadband_check_without_current_setpoints() -> None:
    supervisor = SafetySupervisor()

    decisions = supervisor.validate_batch(
        [
            make_action("cooling_setpoint_temperature", 23.6),
            make_action("heating_setpoint_temperature", 21.3),
        ]
    )

    assert all(decision.verdict is SafetyVerdict.ACCEPT for decision in decisions)
