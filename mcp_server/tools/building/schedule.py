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