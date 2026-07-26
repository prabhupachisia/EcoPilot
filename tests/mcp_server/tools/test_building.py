import pytest

from mcp_server.tools.building.manager import BuildingManager
from mcp_server.tools.building.models import ActionType, BuildingAction, BuildingComponent


# ------------------------------------------------------------------
# Query name-list methods (previously missing -> ValidationMixin crashed)
# ------------------------------------------------------------------


def test_zone_names(fake_building_manager: BuildingManager) -> None:
    assert fake_building_manager.zone_names() == ["SPACE1-1"]


def test_surface_names(fake_building_manager: BuildingManager) -> None:
    assert fake_building_manager.surface_names() == ["SPACE1-1-Wall-1"]


def test_window_names(fake_building_manager: BuildingManager) -> None:
    assert fake_building_manager.window_names() == ["SPACE1-1-Window-1"]


def test_people_names(fake_building_manager: BuildingManager) -> None:
    assert fake_building_manager.people_names() == ["SPACE1-1 People"]


def test_light_names(fake_building_manager: BuildingManager) -> None:
    assert fake_building_manager.light_names() == ["SPACE1-1 Lights"]


def test_equipment_names(fake_building_manager: BuildingManager) -> None:
    assert fake_building_manager.equipment_names() == ["SPACE1-1 Equipment"]


def test_get_schedule_alias(fake_building_manager: BuildingManager) -> None:
    assert fake_building_manager.get_schedule("Clg-SetP-Sch") is not None
    assert fake_building_manager.get_schedule("does-not-exist") is None


# ------------------------------------------------------------------
# Validation (previously crashed with AttributeError)
# ------------------------------------------------------------------


def test_validate_passes_on_a_well_formed_building(fake_building_manager: BuildingManager) -> None:
    result = fake_building_manager.validate()

    assert result.valid is True
    assert result.errors == []


def test_validate_reports_missing_zones(fake_building_manager: BuildingManager) -> None:
    fake_building_manager.idf.idfobjects["ZONE"] = []

    result = fake_building_manager.validate()

    assert result.valid is False
    assert any("thermal zones" in error for error in result.errors)


# ------------------------------------------------------------------
# Numeric HVAC setpoint editing (previously impossible -- the core fix)
# ------------------------------------------------------------------


def test_zone_cooling_setpoint_temperature_reads_occupied_weekday_value(
    fake_building_manager: BuildingManager,
) -> None:
    assert fake_building_manager.zone_cooling_setpoint_temperature() == 23.9


def test_zone_heating_setpoint_temperature_reads_occupied_weekday_value(
    fake_building_manager: BuildingManager,
) -> None:
    assert fake_building_manager.zone_heating_setpoint_temperature() == 21.0


def test_set_zone_cooling_setpoint_temperature_updates_occupied_weekday_value(
    fake_building_manager: BuildingManager,
) -> None:
    fake_building_manager.set_zone_cooling_setpoint_temperature(25.5, reason="Low occupancy")

    assert fake_building_manager.zone_cooling_setpoint_temperature() == 25.5
    # The setback values around it must be untouched.
    schedule = fake_building_manager.schedule("Clg-SetP-Sch")
    assert schedule.Field_9 == "Until: 7:00"
    assert schedule.Field_10 == "40.0"


def test_set_zone_heating_setpoint_temperature_updates_occupied_weekday_value(
    fake_building_manager: BuildingManager,
) -> None:
    fake_building_manager.set_zone_heating_setpoint_temperature(19.5, reason="Energy savings")

    assert fake_building_manager.zone_heating_setpoint_temperature() == 19.5


def test_setpoint_edit_is_recorded_in_history(fake_building_manager: BuildingManager) -> None:
    fake_building_manager.set_zone_cooling_setpoint_temperature(24.0, reason="Test reason")

    change = fake_building_manager.history[-1]

    assert change.component is BuildingComponent.SCHEDULE
    assert change.target == "Clg-SetP-Sch"
    assert change.previous_value == 23.9
    assert change.new_value == 24.0
    assert change.reason == "Test reason"


def test_set_compact_schedule_period_value_unknown_period_raises(
    fake_building_manager: BuildingManager,
) -> None:
    with pytest.raises(ValueError):
        fake_building_manager.set_compact_schedule_period_value(
            "Clg-SetP-Sch", "WeekDays", "09:30", 24.0
        )


# ------------------------------------------------------------------
# Generic action dispatch, including the new THERMOSTAT entries
# ------------------------------------------------------------------


def test_apply_action_sets_cooling_setpoint_via_thermostat_component(
    fake_building_manager: BuildingManager,
) -> None:
    action = BuildingAction(
        component=BuildingComponent.THERMOSTAT,
        action=ActionType.SET,
        target="building",
        parameter="cooling_setpoint_temperature",
        value=26.0,
        reason="Precool before peak carbon hour",
    )

    result = fake_building_manager.apply_action(action)

    assert result.success is True
    assert result.previous_value == 23.9
    assert result.current_value == 26.0
    assert fake_building_manager.zone_cooling_setpoint_temperature() == 26.0


def test_apply_action_accepts_short_alias_parameter_names(
    fake_building_manager: BuildingManager,
) -> None:
    action = BuildingAction(
        component=BuildingComponent.THERMOSTAT,
        action=ActionType.SET,
        target="building",
        parameter="cooling_setpoint",
        value=25.0,
        reason=None,
    )

    result = fake_building_manager.apply_action(action)

    assert result.success is True
    assert fake_building_manager.zone_cooling_setpoint_temperature() == 25.0


def test_apply_action_unsupported_combination_fails_gracefully(
    fake_building_manager: BuildingManager,
) -> None:
    action = BuildingAction(
        component=BuildingComponent.THERMOSTAT,
        action=ActionType.DELETE,
        target="building",
        parameter="cooling_setpoint_temperature",
        value=None,
        reason=None,
    )

    result = fake_building_manager.apply_action(action)

    assert result.success is False
    assert "Unsupported action" in result.message


def test_apply_actions_applies_every_action_in_order(
    fake_building_manager: BuildingManager,
) -> None:
    actions = [
        BuildingAction(
            component=BuildingComponent.THERMOSTAT,
            action=ActionType.SET,
            target="building",
            parameter="cooling_setpoint_temperature",
            value=24.5,
        ),
        BuildingAction(
            component=BuildingComponent.THERMOSTAT,
            action=ActionType.SET,
            target="building",
            parameter="heating_setpoint_temperature",
            value=20.0,
        ),
    ]

    results = fake_building_manager.apply_actions(actions)

    assert all(result.success for result in results)
    assert fake_building_manager.zone_cooling_setpoint_temperature() == 24.5
    assert fake_building_manager.zone_heating_setpoint_temperature() == 20.0


# ------------------------------------------------------------------
# Snapshots and transactions (already-built rollback machinery)
# ------------------------------------------------------------------


def test_snapshot_round_trip(fake_building_manager: BuildingManager) -> None:
    fake_building_manager.create_snapshot("baseline")
    fake_building_manager.set_zone_cooling_setpoint_temperature(30.0)

    assert fake_building_manager.zone_cooling_setpoint_temperature() == 30.0

    fake_building_manager.restore_snapshot("baseline")

    assert fake_building_manager.zone_cooling_setpoint_temperature() == 23.9


def test_transaction_rollback_reverts_edits(fake_building_manager: BuildingManager) -> None:
    fake_building_manager.begin_transaction()
    fake_building_manager.set_zone_cooling_setpoint_temperature(28.0)

    fake_building_manager.rollback()

    assert fake_building_manager.zone_cooling_setpoint_temperature() == 23.9
    assert fake_building_manager.transaction_active() is False


def test_transaction_commit_keeps_edits(fake_building_manager: BuildingManager) -> None:
    fake_building_manager.begin_transaction()
    fake_building_manager.set_zone_cooling_setpoint_temperature(28.0)

    fake_building_manager.commit()

    assert fake_building_manager.zone_cooling_setpoint_temperature() == 28.0
    assert fake_building_manager.transaction_active() is False


# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------


def test_building_summary(fake_building_manager: BuildingManager) -> None:
    summary = fake_building_manager.summary()

    assert summary.building_name == "Fake Building"
    assert summary.zones == 1
    assert summary.hvac_systems == 1
