from __future__ import annotations

from eppy.bunch_subclass import EpBunch

from .models import BuildingComponent


class LightingMixin:
    """Mixin for managing EnergyPlus LIGHTS objects."""

    POWER_FIELD = "Lighting_Level"
    SCHEDULE_FIELD = "Schedule_Name"

    def _require_light(self, name: str) -> EpBunch:
        """Return a LIGHTS object or raise if it does not exist."""

        light = self.light(name)

        if light is None:
            raise ValueError(f"Light object '{name}' not found.")

        return light

    def total_lighting_power(self) -> float:
        """Return the total lighting power in the model."""

        total = 0.0

        for light in self.lights():
            total += float(
                getattr(
                    light,
                    self.POWER_FIELD,
                    0.0,
                )
            )

        return total

    def set_lighting_power(
        self,
        name: str,
        value: float,
        reason: str | None = None,
    ) -> None:
        """Set the lighting power for a LIGHTS object."""

        if value < 0:
            raise ValueError("Lighting power cannot be negative.")

        light = self._require_light(name)

        previous = float(
            getattr(
                light,
                self.POWER_FIELD,
            )
        )

        self.helpers.set_field(
            light,
            self.POWER_FIELD,
            value,
        )

        self.helpers.record_change(
            component=BuildingComponent.LIGHTING,
            target=name,
            parameter=self.POWER_FIELD,
            previous_value=previous,
            new_value=value,
            reason=reason,
        )

    def scale_lighting_power(
        self,
        name: str,
        factor: float,
        reason: str | None = None,
    ) -> None:
        """Scale the lighting power by a multiplier."""

        if factor < 0:
            raise ValueError("Scale factor cannot be negative.")

        light = self._require_light(name)

        previous = float(
            getattr(
                light,
                self.POWER_FIELD,
            )
        )

        current = previous * factor

        self.helpers.set_field(
            light,
            self.POWER_FIELD,
            current,
        )

        self.helpers.record_change(
            component=BuildingComponent.LIGHTING,
            target=name,
            parameter=self.POWER_FIELD,
            previous_value=previous,
            new_value=current,
            reason=reason,
        )

    def set_lighting_schedule(
        self,
        name: str,
        schedule_name: str,
        reason: str | None = None,
    ) -> None:
        """Assign a schedule to a LIGHTS object."""

        light = self._require_light(name)

        if self.schedule(schedule_name) is None:
            raise ValueError(f"Schedule '{schedule_name}' not found.")

        previous = getattr(
            light,
            self.SCHEDULE_FIELD,
        )

        self.helpers.set_field(
            light,
            self.SCHEDULE_FIELD,
            schedule_name,
        )

        self.helpers.record_change(
            component=BuildingComponent.LIGHTING,
            target=name,
            parameter=self.SCHEDULE_FIELD,
            previous_value=previous,
            new_value=schedule_name,
            reason=reason,
        )