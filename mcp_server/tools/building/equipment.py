from __future__ import annotations

from eppy.bunch_subclass import EpBunch

from .models import BuildingComponent


class EquipmentMixin:
    """Mixin for managing EnergyPlus ELECTRICEQUIPMENT objects."""

    POWER_FIELD = "Design_Level"
    SCHEDULE_FIELD = "Schedule_Name"

    def _require_equipment(self, name: str) -> EpBunch:
        """Return an ELECTRICEQUIPMENT object or raise if it does not exist."""

        equipment = self.equipment_object(name)

        if equipment is None:
            raise ValueError(
                f"Equipment object '{name}' not found."
            )

        return equipment

    def total_equipment_power(self) -> float:
        """Return the total equipment power in the model."""

        total = 0.0

        for equipment in self.equipment():
            total += float(
                getattr(
                    equipment,
                    self.POWER_FIELD,
                    0.0,
                )
            )

        return total

    def set_equipment_power(
        self,
        name: str,
        value: float,
        reason: str | None = None,
    ) -> None:
        """Set the equipment power."""

        if value < 0:
            raise ValueError(
                "Equipment power cannot be negative."
            )

        equipment = self._require_equipment(name)

        previous = float(
            getattr(
                equipment,
                self.POWER_FIELD,
            )
        )

        self.helpers.set_field(
            equipment,
            self.POWER_FIELD,
            value,
        )

        self.helpers.record_change(
            component=BuildingComponent.EQUIPMENT,
            target=name,
            parameter=self.POWER_FIELD,
            previous_value=previous,
            new_value=value,
            reason=reason,
        )

    def scale_equipment_power(
        self,
        name: str,
        factor: float,
        reason: str | None = None,
    ) -> None:
        """Scale the equipment power."""

        if factor < 0:
            raise ValueError(
                "Scale factor cannot be negative."
            )

        equipment = self._require_equipment(name)

        previous = float(
            getattr(
                equipment,
                self.POWER_FIELD,
            )
        )

        current = previous * factor

        self.helpers.set_field(
            equipment,
            self.POWER_FIELD,
            current,
        )

        self.helpers.record_change(
            component=BuildingComponent.EQUIPMENT,
            target=name,
            parameter=self.POWER_FIELD,
            previous_value=previous,
            new_value=current,
            reason=reason,
        )

    def set_equipment_schedule(
        self,
        name: str,
        schedule_name: str,
        reason: str | None = None,
    ) -> None:
        """Assign a schedule to an ELECTRICEQUIPMENT object."""

        equipment = self._require_equipment(name)

        if self.schedule(schedule_name) is None:
            raise ValueError(
                f"Schedule '{schedule_name}' not found."
            )

        previous = getattr(
            equipment,
            self.SCHEDULE_FIELD,
        )

        self.helpers.set_field(
            equipment,
            self.SCHEDULE_FIELD,
            schedule_name,
        )

        self.helpers.record_change(
            component=BuildingComponent.EQUIPMENT,
            target=name,
            parameter=self.SCHEDULE_FIELD,
            previous_value=previous,
            new_value=schedule_name,
            reason=reason,
        )