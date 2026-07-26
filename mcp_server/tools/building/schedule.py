from __future__ import annotations

from eppy.bunch_subclass import EpBunch

from .models import BuildingComponent


class ScheduleMixin:
    """Mixin for managing EnergyPlus schedules."""

    def _require_schedule(self, name: str) -> EpBunch:
        schedule = self.schedule(name)

        if schedule is None:
            raise ValueError(f"Schedule '{name}' not found.")

        return schedule

    def list_schedule_names(self) -> list[str]:
        """Return the names of all schedules."""

        return [
            schedule.Name
            for schedule in self.schedules()
            if hasattr(schedule, "Name")
        ]

    def rename_schedule(
        self,
        name: str,
        new_name: str,
        reason: str | None = None,
    ) -> None:
        """Rename a schedule."""

        schedule = self._require_schedule(name)

        if self.schedule(new_name) is not None:
            raise ValueError(
                f"Schedule '{new_name}' already exists."
            )

        previous = schedule.Name

        self.helpers.set_field(
            schedule,
            "Name",
            new_name,
        )

        self.helpers.record_change(
            component=BuildingComponent.SCHEDULE,
            target=previous,
            parameter="Name",
            previous_value=previous,
            new_value=new_name,
            reason=reason,
        )

    def _locate_compact_schedule_value_field(
        self,
        schedule: EpBunch,
        day_type: str,
        until_time: str,
    ) -> str:
        """Return the fieldname holding the numeric value for a For:/Until: period.

        ``Schedule:Compact`` objects are a flat, repeating list of fields —
        "Through:" markers, "For: <day_type>" block headers, and
        "Until: <HH:MM>" / value pairs within each block. eppy exposes each
        comma-separated token as its own field (``Field_1``, ``Field_2``,
        ...); the numeric value for an "Until:" token is always the field
        immediately after it.
        """

        fieldnames = schedule.fieldnames
        normalized_day_type = " ".join(day_type.strip().lower().split())
        normalized_until = f"until: {until_time.strip()}".lower()

        in_target_block = False

        for index, fieldname in enumerate(fieldnames):
            raw_value = getattr(schedule, fieldname, None)

            if raw_value is None:
                continue

            text = str(raw_value).strip().lower()

            if text.startswith("for:"):
                block_days = " ".join(text[len("for:"):].strip().split())
                in_target_block = block_days == normalized_day_type
                continue

            if in_target_block and text == normalized_until:
                if index + 1 >= len(fieldnames):
                    raise ValueError(
                        f"Schedule '{schedule.Name}' has no value field "
                        f"after 'Until: {until_time}'."
                    )

                return fieldnames[index + 1]

        raise ValueError(
            f"Could not find 'For: {day_type}' / 'Until: {until_time}' "
            f"in schedule '{schedule.Name}'."
        )

    def get_compact_schedule_period_value(
        self,
        name: str,
        day_type: str,
        until_time: str,
    ) -> float:
        """Read the numeric value for a For:/Until: period in a Schedule:Compact."""

        schedule = self._require_schedule(name)
        field = self._locate_compact_schedule_value_field(schedule, day_type, until_time)

        return float(getattr(schedule, field))

    def set_compact_schedule_period_value(
        self,
        name: str,
        day_type: str,
        until_time: str,
        value: float,
        reason: str | None = None,
    ) -> float:
        """Set the numeric value for a For:/Until: period in a Schedule:Compact.

        Example
        -------
        ``set_compact_schedule_period_value("Clg-SetP-Sch", "WeekDays", "18:00", 25.0)``
        changes the occupied weekday cooling setpoint to 25.0.
        """

        schedule = self._require_schedule(name)
        field = self._locate_compact_schedule_value_field(schedule, day_type, until_time)

        previous = float(getattr(schedule, field))

        self.helpers.set_field(schedule, field, value)

        self.helpers.record_change(
            component=BuildingComponent.SCHEDULE,
            target=name,
            parameter=f"{day_type}/Until: {until_time}",
            previous_value=previous,
            new_value=value,
            reason=reason,
        )

        return value

    def set_schedule_type(
        self,
        name: str,
        schedule_type: str,
        reason: str | None = None,
    ) -> None:
        """Update the Schedule Type Limits."""

        schedule = self._require_schedule(name)

        previous = getattr(
            schedule,
            "Schedule_Type_Limits_Name",
            "",
        )

        self.helpers.set_field(
            schedule,
            "Schedule_Type_Limits_Name",
            schedule_type,
        )

        self.helpers.record_change(
            component=BuildingComponent.SCHEDULE,
            target=name,
            parameter="Schedule_Type_Limits_Name",
            previous_value=previous,
            new_value=schedule_type,
            reason=reason,
        )