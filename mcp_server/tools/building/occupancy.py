from __future__ import annotations

from eppy.bunch_subclass import EpBunch

from .models import BuildingComponent


class OccupancyMixin:
    """Mixin for managing EnergyPlus PEOPLE objects."""

    PEOPLE_FIELD = "Number_of_People"
    SCHEDULE_FIELD = "Number_of_People_Schedule_Name"

    def _require_people(self, name: str) -> EpBunch:
        """Return a PEOPLE object or raise if it does not exist."""

        people = self.person(name)

        if people is None:
            raise ValueError(f"People object '{name}' not found.")

        return people

    def total_people(self) -> float:
        """Return the total number of occupants in the model."""

        total = 0.0

        for people in self.people():
            total += float(
                getattr(
                    people,
                    self.PEOPLE_FIELD,
                    0.0,
                )
            )

        return total

    def set_people(
        self,
        name: str,
        value: float,
        reason: str | None = None,
    ) -> None:
        """Set the number of occupants for a PEOPLE object."""

        if value < 0:
            raise ValueError("Number of people cannot be negative.")

        people = self._require_people(name)

        previous = float(
            getattr(
                people,
                self.PEOPLE_FIELD,
            )
        )

        self.helpers.set_field(
            people,
            self.PEOPLE_FIELD,
            value,
        )

        self.helpers.record_change(
            component=BuildingComponent.PEOPLE,
            target=name,
            parameter=self.PEOPLE_FIELD,
            previous_value=previous,
            new_value=value,
            reason=reason,
        )

    def scale_people(
        self,
        name: str,
        factor: float,
        reason: str | None = None,
    ) -> None:
        """Scale the number of occupants by a multiplier."""

        if factor < 0:
            raise ValueError("Scale factor cannot be negative.")

        people = self._require_people(name)

        previous = float(
            getattr(
                people,
                self.PEOPLE_FIELD,
            )
        )

        current = previous * factor

        self.helpers.set_field(
            people,
            self.PEOPLE_FIELD,
            current,
        )

        self.helpers.record_change(
            component=BuildingComponent.PEOPLE,
            target=name,
            parameter=self.PEOPLE_FIELD,
            previous_value=previous,
            new_value=current,
            reason=reason,
        )

    def set_people_schedule(
        self,
        name: str,
        schedule_name: str,
        reason: str | None = None,
    ) -> None:
        """Assign a schedule to a PEOPLE object."""

        people = self._require_people(name)

        if self.schedule(schedule_name) is None:
            raise ValueError(f"Schedule '{schedule_name}' not found.")

        previous = getattr(
            people,
            self.SCHEDULE_FIELD,
        )

        self.helpers.set_field(
            people,
            self.SCHEDULE_FIELD,
            schedule_name,
        )

        self.helpers.record_change(
            component=BuildingComponent.PEOPLE,
            target=name,
            parameter=self.SCHEDULE_FIELD,
            previous_value=previous,
            new_value=schedule_name,
            reason=reason,
        )