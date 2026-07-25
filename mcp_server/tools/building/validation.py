from __future__ import annotations

from collections import Counter
from typing import Any

from .models import BuildingComponent


class ValidationMixin:
    """
    Validation utilities for EnergyPlus models.

    These checks are intended to catch common mistakes introduced while
    modifying the building through the SDK. They are not a replacement
    for EnergyPlus's own IDF validation.
    """

    # ------------------------------------------------------------------
    # Internal Report Helpers
    # ------------------------------------------------------------------

    def _new_validation_report(self) -> dict[str, Any]:
        """
        Create an empty validation report.
        """

        return {
            "valid": True,
            "errors": [],
            "warnings": [],
            "statistics": {},
        }

    def _add_error(
        self,
        report: dict[str, Any],
        message: str,
    ) -> None:
        report["errors"].append(message)
        report["valid"] = False

    def _add_warning(
        self,
        report: dict[str, Any],
        message: str,
    ) -> None:
        report["warnings"].append(message)

    # ------------------------------------------------------------------
    # General Validation
    # ------------------------------------------------------------------

    def validate_building(self) -> dict[str, Any]:
        """
        Validate the overall building.
        """

        report = self._new_validation_report()

        if self.idf is None:
            self._add_error(
                report,
                "No IDF model is currently loaded.",
            )
            return report

        if len(self.zone_names()) == 0:
            self._add_error(
                report,
                "Building contains no thermal zones.",
            )

        if len(self.surface_names()) == 0:
            self._add_error(
                report,
                "Building contains no building surfaces.",
            )

        return report

    def validate_duplicate_names(self) -> dict[str, Any]:
        """
        Detect duplicate object names.
        """

        report = self._new_validation_report()

        names = []

        for object_list in self.idf.idfobjects.values():

            for obj in object_list:

                if hasattr(obj, "Name"):
                    names.append(obj.Name)

        duplicates = [
            name
            for name, count in Counter(names).items()
            if count > 1
        ]

        for duplicate in duplicates:
            self._add_error(
                report,
                f"Duplicate object name: '{duplicate}'"
            )

        return report

    def validate_missing_references(self) -> dict[str, Any]:
        """
        Validate that important schedules and constructions exist.
        """

        report = self._new_validation_report()

        # Construction references

        for surface in self.idf.idfobjects.get(
            "BUILDINGSURFACE:DETAILED",
            [],
        ):

            construction = getattr(
                surface,
                "Construction_Name",
                "",
            )

            if (
                construction
                and self.get_object(
                    "CONSTRUCTION",
                    construction,
                )
                is None
            ):
                self._add_error(
                    report,
                    (
                        f"Surface '{surface.Name}' references "
                        f"missing construction '{construction}'."
                    ),
                )

        # Schedule references

        schedule_types = {
            "PEOPLE",
            "LIGHTS",
            "ELECTRICEQUIPMENT",
        }

        for object_type in schedule_types:

            for obj in self.idf.idfobjects.get(
                object_type,
                [],
            ):

                schedule = getattr(
                    obj,
                    "Schedule_Name",
                    "",
                )

                if (
                    schedule
                    and self.get_schedule(schedule)
                    is None
                ):
                    self._add_error(
                        report,
                        (
                            f"{object_type} '{obj.Name}' "
                            f"references missing schedule "
                            f"'{schedule}'."
                        ),
                    )

        return report

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def validation_statistics(self) -> dict[str, int]:
        """
        Return model statistics.
        """

        return {
            "zones": len(self.zone_names()),
            "surfaces": len(self.surface_names()),
            "windows": len(self.window_names()),
            "people": len(self.people_names()),
            "lights": len(self.light_names()),
            "equipment": len(self.equipment_names()),
            "thermostats": len(self.thermostat_names()),
            "fans": len(self.fan_names()),
            "cooling_coils": len(
                self.cooling_coil_names()
            ),
            "heating_coils": len(
                self.heating_coil_names()
            ),
        }
        # ------------------------------------------------------------------
    # Geometry Validation
    # ------------------------------------------------------------------

    def validate_zones(self) -> dict[str, Any]:
        """
        Validate thermal zones.
        """

        report = self._new_validation_report()

        zones = self.zone_names()

        if not zones:
            self._add_error(
                report,
                "No thermal zones found."
            )

        for zone in zones:

            obj = self.get_object("ZONE", zone)

            if obj is None:
                self._add_error(
                    report,
                    f"Zone '{zone}' could not be located."
                )

        return report

    def validate_surfaces(self) -> dict[str, Any]:
        """
        Validate building surfaces.
        """

        report = self._new_validation_report()

        for surface in self.idf.idfobjects.get(
            "BUILDINGSURFACE:DETAILED",
            [],
        ):

            if float(surface.Number_of_Vertices) < 3:
                self._add_error(
                    report,
                    f"Surface '{surface.Name}' has fewer than three vertices."
                )

            if not surface.Construction_Name:
                self._add_error(
                    report,
                    f"Surface '{surface.Name}' has no construction."
                )

            if not surface.Zone_Name:
                self._add_error(
                    report,
                    f"Surface '{surface.Name}' is not assigned to a zone."
                )

        return report

    def validate_windows(self) -> dict[str, Any]:
        """
        Validate all fenestration surfaces.
        """

        report = self._new_validation_report()

        for window in self.idf.idfobjects.get(
            "FENESTRATIONSURFACE:DETAILED",
            [],
        ):

            if not window.Building_Surface_Name:
                self._add_error(
                    report,
                    f"Window '{window.Name}' is not attached to a surface."
                )

            if not window.Construction_Name:
                self._add_error(
                    report,
                    f"Window '{window.Name}' has no construction."
                )

        return report

    # ------------------------------------------------------------------
    # Occupancy Validation
    # ------------------------------------------------------------------

    def validate_people(self) -> dict[str, Any]:
        """
        Validate PEOPLE objects.
        """

        report = self._new_validation_report()

        for people in self.idf.idfobjects.get(
            "PEOPLE",
            [],
        ):

            if hasattr(
                people,
                "Number_of_People"
            ):

                value = people.Number_of_People

                if (
                    str(value).lower() != "autosize"
                    and float(value) < 0
                ):
                    self._add_error(
                        report,
                        f"People object '{people.Name}' has a negative population."
                    )

            if (
                people.Schedule_Name
                and self.get_schedule(
                    people.Schedule_Name
                ) is None
            ):
                self._add_error(
                    report,
                    f"People object '{people.Name}' references missing schedule '{people.Schedule_Name}'."
                )

        return report

    # ------------------------------------------------------------------
    # Lighting Validation
    # ------------------------------------------------------------------

    def validate_lighting(self) -> dict[str, Any]:
        """
        Validate LIGHTS objects.
        """

        report = self._new_validation_report()

        for light in self.idf.idfobjects.get(
            "LIGHTS",
            [],
        ):

            if hasattr(
                light,
                "Lighting_Level"
            ):

                value = light.Lighting_Level

                if (
                    str(value).lower() != "autosize"
                    and float(value) < 0
                ):
                    self._add_error(
                        report,
                        f"Lighting object '{light.Name}' has a negative lighting level."
                    )

            if (
                light.Schedule_Name
                and self.get_schedule(
                    light.Schedule_Name
                ) is None
            ):
                self._add_error(
                    report,
                    f"Lighting object '{light.Name}' references missing schedule '{light.Schedule_Name}'."
                )

        return report

    # ------------------------------------------------------------------
    # Equipment Validation
    # ------------------------------------------------------------------

    def validate_equipment(self) -> dict[str, Any]:
        """
        Validate ElectricEquipment objects.
        """

        report = self._new_validation_report()

        for equipment in self.idf.idfobjects.get(
            "ELECTRICEQUIPMENT",
            [],
        ):

            if hasattr(
                equipment,
                "Design_Level"
            ):

                value = equipment.Design_Level

                if (
                    str(value).lower() != "autosize"
                    and float(value) < 0
                ):
                    self._add_error(
                        report,
                        f"Equipment '{equipment.Name}' has a negative design level."
                    )

            if (
                equipment.Schedule_Name
                and self.get_schedule(
                    equipment.Schedule_Name
                ) is None
            ):
                self._add_error(
                    report,
                    f"Equipment '{equipment.Name}' references missing schedule '{equipment.Schedule_Name}'."
                )

        return report

    # ------------------------------------------------------------------
    # HVAC Validation
    # ------------------------------------------------------------------

    def validate_hvac(self) -> dict[str, Any]:
        """
        Validate HVAC components.
        """

        report = self._new_validation_report()

        # Fans

        for fan in self.idf.idfobjects.get(
            "FAN:VARIABLEVOLUME",
            [],
        ):

            if float(fan.Fan_Total_Efficiency) <= 0:
                self._add_error(
                    report,
                    f"Fan '{fan.Name}' has invalid efficiency."
                )

            if float(fan.Pressure_Rise) <= 0:
                self._add_error(
                    report,
                    f"Fan '{fan.Name}' has invalid pressure rise."
                )

        # Cooling coils

        for coil in self.idf.idfobjects.get(
            "COIL:COOLING:DX:TWOSPEED",
            [],
        ):

            if (
                float(
                    coil.High_Speed_Gross_Rated_Cooling_COP
                )
                <= 0
            ):
                self._add_error(
                    report,
                    f"Cooling coil '{coil.Name}' has invalid COP."
                )

        # Heating coils

        for coil in self.idf.idfobjects.get(
            "COIL:HEATING:FUEL",
            [],
        ):

            efficiency = float(
                coil.Burner_Efficiency
            )

            if not (0 < efficiency <= 1):
                self._add_error(
                    report,
                    f"Heating coil '{coil.Name}' has invalid burner efficiency."
                )

        return report

        # ------------------------------------------------------------------
    # Schedule Validation
    # ------------------------------------------------------------------

    def validate_schedules(self) -> dict[str, Any]:
        """
        Validate all schedules in the model.
        """

        report = self._new_validation_report()

        schedules = self.idf.idfobjects.get(
            "SCHEDULE:COMPACT",
            []
        )

        if not schedules:
            self._add_warning(
                report,
                "No Schedule:Compact objects found."
            )

        names = set()

        for schedule in schedules:

            if schedule.Name in names:
                self._add_error(
                    report,
                    f"Duplicate schedule '{schedule.Name}'."
                )

            names.add(schedule.Name)

            if not schedule.Name.strip():
                self._add_error(
                    report,
                    "Found schedule with empty name."
                )

        return report

    # ------------------------------------------------------------------
    # Report Utilities
    # ------------------------------------------------------------------

    def validation_summary(self) -> dict[str, Any]:
        """
        Run validation and return the report.
        """

        return self.validate()

    def is_valid(self) -> bool:
        """
        Return True if the building passes validation.
        """

        return self.validate()["valid"]

    # ------------------------------------------------------------------
    # Master Validation
    # ------------------------------------------------------------------

    def validate(self) -> dict[str, Any]:
        """
        Run every validation routine.

        Returns
        -------
        dict
            Complete validation report.
        """

        report = self._new_validation_report()

        validators = [
            self.validate_building,
            self.validate_duplicate_names,
            self.validate_missing_references,
            self.validate_zones,
            self.validate_surfaces,
            self.validate_windows,
            self.validate_people,
            self.validate_lighting,
            self.validate_equipment,
            self.validate_hvac,
            self.validate_schedules,
        ]

        for validator in validators:

            result = validator()

            report["errors"].extend(
                result["errors"]
            )

            report["warnings"].extend(
                result["warnings"]
            )

        report["statistics"] = (
            self.validation_statistics()
        )

        report["valid"] = (
            len(report["errors"]) == 0
        )

        return report
