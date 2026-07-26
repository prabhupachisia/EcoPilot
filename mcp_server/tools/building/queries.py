from __future__ import annotations

from eppy.bunch_subclass import EpBunch

from .models import BuildingSummary


class QueryMixin:
    def building(self) -> EpBunch:
        self.helpers.require_loaded()
        return self.idf.idfobjects["BUILDING"][0]

    def zones(self) -> list[EpBunch]:
        self.helpers.require_loaded()
        return list(self.idf.idfobjects.get("ZONE", []))

    def zone(self, name: str) -> EpBunch | None:
        for zone in self.zones():
            if zone.Name == name:
                return zone
        return None

    def zone_names(self) -> list[str]:
        return [zone.Name for zone in self.zones() if hasattr(zone, "Name")]

    def surfaces(self) -> list[EpBunch]:
        self.helpers.require_loaded()
        return list(self.idf.idfobjects.get("BUILDINGSURFACE:DETAILED", []))

    def surface_names(self) -> list[str]:
        return [surface.Name for surface in self.surfaces() if hasattr(surface, "Name")]

    def schedules(self, schedule_type: str | None = None) -> list[EpBunch]:
        self.helpers.require_loaded()

        if schedule_type:
            return list(self.idf.idfobjects.get(schedule_type.upper(), []))

        schedules = []

        for object_type, objects in self.idf.idfobjects.items():
            if object_type.startswith("SCHEDULE"):
                schedules.extend(objects)

        return schedules

    def schedule(self, name: str) -> EpBunch | None:
        for schedule in self.schedules():
            if getattr(schedule, "Name", None) == name:
                return schedule
        return None

    def get_schedule(self, name: str) -> EpBunch | None:
        """Alias for ``schedule`` used by the validation mixin."""
        return self.schedule(name)

    def people(self) -> list[EpBunch]:
        return list(self.idf.idfobjects.get("PEOPLE", []))

    def person(self, name: str) -> EpBunch | None:
        for person in self.people():
            if person.Name == name:
                return person
        return None

    def people_names(self) -> list[str]:
        return [person.Name for person in self.people() if hasattr(person, "Name")]

    def lights(self) -> list[EpBunch]:
        return list(self.idf.idfobjects.get("LIGHTS", []))

    def light(self, name: str) -> EpBunch | None:
        for light in self.lights():
            if light.Name == name:
                return light
        return None

    def light_names(self) -> list[str]:
        return [light.Name for light in self.lights() if hasattr(light, "Name")]

    def equipment(self) -> list[EpBunch]:
        return list(self.idf.idfobjects.get("ELECTRICEQUIPMENT", []))

    def equipment_object(self, name: str) -> EpBunch | None:
        for equipment in self.equipment():
            if equipment.Name == name:
                return equipment
        return None

    def equipment_names(self) -> list[str]:
        return [item.Name for item in self.equipment() if hasattr(item, "Name")]

    def materials(self) -> list[EpBunch]:
        return list(self.idf.idfobjects.get("MATERIAL", []))

    def material(self, name: str) -> EpBunch | None:
        for material in self.materials():
            if material.Name == name:
                return material
        return None

    def constructions(self) -> list[EpBunch]:
        return list(self.idf.idfobjects.get("CONSTRUCTION", []))

    def construction(self, name: str) -> EpBunch | None:
        for construction in self.constructions():
            if construction.Name == name:
                return construction
        return None

    def windows(self) -> list[EpBunch]:
        return list(
            self.idf.idfobjects.get(
                "FENESTRATIONSURFACE:DETAILED",
                [],
            )
        )

    def window(self, name: str) -> EpBunch | None:
        for window in self.windows():
            if window.Name == name:
                return window
        return None

    def window_names(self) -> list[str]:
        return [window.Name for window in self.windows() if hasattr(window, "Name")]

    def thermostats(self) -> list[EpBunch]:
        return list(
            self.idf.idfobjects.get(
                "THERMOSTATSETPOINT:DUALSETPOINT",
                [],
            )
        )

    def thermostat(self, name: str) -> EpBunch | None:
        for thermostat in self.thermostats():
            if thermostat.Name == name:
                return thermostat
        return None

    def object_counts(self) -> dict[str, int]:
        return {
            object_type: len(objects)
            for object_type, objects in self.idf.idfobjects.items()
        }

    def summary(self) -> BuildingSummary:
        return BuildingSummary(
            building_name=self.building().Name,
            zones=len(self.zones()),
            schedules=len(self.schedules()),
            materials=len(self.materials()),
            constructions=len(self.constructions()),
            windows=len(self.windows()),
            people_objects=len(self.people()),
            lighting_objects=len(self.lights()),
            equipment_objects=len(self.equipment()),
            hvac_systems=len(self.thermostats()),
        )