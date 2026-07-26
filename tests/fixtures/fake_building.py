from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp_server.tools.building.manager import BuildingManager

# eppy's IDD only ships inside a real EnergyPlus install, which isn't a
# safe thing to assume every test box has. So instead of loading an actual
# IDF through eppy, BuildingManager tests run against this lightweight
# stand-in for IDF/EpBunch. The manager and its mixins only ever touch
# idf.idfobjects (a dict of lists) and getattr/setattr on whatever comes
# back, and FakeEpBunch/FakeIDF reproduce exactly that, so the real mixin
# code runs against them unmodified.


class FakeEpBunch:
    """Minimal stand-in for ``eppy.bunch_subclass.EpBunch``."""

    def __init__(self, key: str, **fields: Any) -> None:
        self.key = key
        self._fieldnames = ["key", *fields.keys()]

        for name, value in fields.items():
            setattr(self, name, value)

    @property
    def fieldnames(self) -> list[str]:
        return list(self._fieldnames)

    @property
    def fieldvalues(self) -> list[Any]:
        return [getattr(self, name) for name in self._fieldnames]


class FakeIDF:
    """Minimal stand-in for ``eppy.modeleditor.IDF``."""

    def __init__(self, idfobjects: dict[str, list[FakeEpBunch]]) -> None:
        self.idfobjects = idfobjects

    def removeidfobject(self, obj: FakeEpBunch) -> None:
        for objects in self.idfobjects.values():
            if obj in objects:
                objects.remove(obj)
                return

    def copyidfobject(self, obj: FakeEpBunch) -> None:
        self.idfobjects.setdefault(obj.key, []).append(obj)


def _compact_schedule_fields(*tokens: str) -> dict[str, str]:
    return {f"Field_{i + 1}": token for i, token in enumerate(tokens)}


def build_fake_idf() -> FakeIDF:
    """Build a tiny, structurally-faithful stand-in for the 5-zone reference model.

    Only a single zone/schedule/thermostat/fan/coil is included -- enough to
    exercise every mixin method without the size of the real
    ``5ZoneAutoDXVAV.idf``.
    """

    cooling_schedule = FakeEpBunch(
        "SCHEDULE:COMPACT",
        Name="Clg-SetP-Sch",
        Schedule_Type_Limits_Name="Temperature",
        **_compact_schedule_fields(
            "Through: 12/31",
            "For: SummerDesignDay",
            "Until: 24:00", "23.9",
            "For: WinterDesignDay",
            "Until: 24:00", "40.0",
            "For: WeekDays",
            "Until: 7:00", "40.0",
            "Until: 18:00", "23.9",
            "Until: 24:00", "40.0",
            "For: WeekEnds Holiday",
            "Until: 24:00", "40.0",
            "For: AllOtherDays",
            "Until: 24:00", "40.0",
        ),
    )

    heating_schedule = FakeEpBunch(
        "SCHEDULE:COMPACT",
        Name="Htg-SetP-Sch",
        Schedule_Type_Limits_Name="Temperature",
        **_compact_schedule_fields(
            "Through: 12/31",
            "For: SummerDesignDay",
            "Until: 24:00", "15.0",
            "For: WinterDesignDay",
            "Until: 24:00", "21.0",
            "For: WeekDays",
            "Until: 7:00", "15.0",
            "Until: 18:00", "21.0",
            "Until: 24:00", "15.0",
            "For: WeekEnds Holiday",
            "Until: 24:00", "15.0",
            "For: AllOtherDays",
            "Until: 24:00", "15.0",
        ),
    )

    occupancy_schedule = FakeEpBunch(
        "SCHEDULE:CONSTANT", Name="Office Occupancy", Schedule_Type_Limits_Name="Fraction", Hourly_Value=1.0
    )
    lighting_schedule = FakeEpBunch(
        "SCHEDULE:CONSTANT", Name="Office Lighting", Schedule_Type_Limits_Name="Fraction", Hourly_Value=1.0
    )
    equipment_schedule = FakeEpBunch(
        "SCHEDULE:CONSTANT", Name="Office Equipment", Schedule_Type_Limits_Name="Fraction", Hourly_Value=1.0
    )

    zone = FakeEpBunch("ZONE", Name="SPACE1-1")

    surface = FakeEpBunch(
        "BUILDINGSURFACE:DETAILED",
        Name="SPACE1-1-Wall-1",
        Construction_Name="EXTWALL",
        Zone_Name="SPACE1-1",
        Number_of_Vertices=4,
    )

    window = FakeEpBunch(
        "FENESTRATIONSURFACE:DETAILED",
        Name="SPACE1-1-Window-1",
        Building_Surface_Name="SPACE1-1-Wall-1",
        Construction_Name="WINDOW",
    )

    people = FakeEpBunch(
        "PEOPLE",
        Name="SPACE1-1 People",
        Zone_or_ZoneList_Name="SPACE1-1",
        Number_of_People_Schedule_Name="Office Occupancy",
        Number_of_People=11.0,
        Schedule_Name="Office Occupancy",
    )

    lights = FakeEpBunch(
        "LIGHTS",
        Name="SPACE1-1 Lights",
        Zone_or_ZoneList_Name="SPACE1-1",
        Lighting_Level=1584.0,
        Schedule_Name="Office Lighting",
    )

    equipment = FakeEpBunch(
        "ELECTRICEQUIPMENT",
        Name="SPACE1-1 Equipment",
        Zone_or_ZoneList_Name="SPACE1-1",
        Design_Level=1056.0,
        Schedule_Name="Office Equipment",
    )

    material = FakeEpBunch(
        "MATERIAL",
        Name="A1 - 1 IN STUCCO",
        Thickness=0.0253,
        Conductivity=0.6918,
    )

    construction = FakeEpBunch(
        "CONSTRUCTION",
        Name="EXTWALL",
        Outside_Layer="A1 - 1 IN STUCCO",
    )

    thermostat = FakeEpBunch(
        "ZONECONTROL:THERMOSTAT",
        Name="SPACE1-1 Thermostat",
        Zone_or_ZoneList_Name="SPACE1-1",
        Control_1_Name="HeatingSetpoint",
        Control_2_Name="CoolingSetpoint",
    )

    dual_setpoint = FakeEpBunch(
        "THERMOSTATSETPOINT:DUALSETPOINT",
        Name="DualSetPoint",
        Heating_Setpoint_Temperature_Schedule_Name="Htg-SetP-Sch",
        Cooling_Setpoint_Temperature_Schedule_Name="Clg-SetP-Sch",
    )

    fan = FakeEpBunch(
        "FAN:VARIABLEVOLUME",
        Name="Supply Fan",
        Fan_Total_Efficiency=0.7,
        Pressure_Rise=1000.0,
        Maximum_Flow_Rate=1.0,
        Motor_Efficiency=0.9,
        Motor_In_Airstream_Fraction=1.0,
    )

    cooling_coil = FakeEpBunch(
        "COIL:COOLING:DX:TWOSPEED",
        Name="Cooling Coil",
        High_Speed_Gross_Rated_Cooling_COP=3.0,
        High_Speed_Gross_Rated_Total_Cooling_Capacity=10000.0,
        Condenser_Type="AirCooled",
    )

    heating_coil = FakeEpBunch(
        "COIL:HEATING:FUEL",
        Name="Heating Coil",
        Burner_Efficiency=0.8,
        Nominal_Capacity=10000.0,
        Fuel_Type="NaturalGas",
    )

    building = FakeEpBunch("BUILDING", Name="Fake Building")

    return FakeIDF(
        {
            "BUILDING": [building],
            "ZONE": [zone],
            "BUILDINGSURFACE:DETAILED": [surface],
            "FENESTRATIONSURFACE:DETAILED": [window],
            "SCHEDULE:COMPACT": [cooling_schedule, heating_schedule],
            "SCHEDULE:CONSTANT": [occupancy_schedule, lighting_schedule, equipment_schedule],
            "PEOPLE": [people],
            "LIGHTS": [lights],
            "ELECTRICEQUIPMENT": [equipment],
            "MATERIAL": [material],
            "CONSTRUCTION": [construction],
            "ZONECONTROL:THERMOSTAT": [thermostat],
            "THERMOSTATSETPOINT:DUALSETPOINT": [dual_setpoint],
            "FAN:VARIABLEVOLUME": [fan],
            "COIL:COOLING:DX:TWOSPEED": [cooling_coil],
            "COIL:HEATING:FUEL": [heating_coil],
            "AIRLOOPHVAC": [],
        }
    )


def build_fake_building_manager() -> BuildingManager:
    """Build a ``BuildingManager`` with a fake IDF already "loaded".

    Bypasses ``BuildingManager.load()`` (which needs a real IDD file from an
    EnergyPlus install) by assigning ``idf``/``is_loaded`` directly -- every
    mixin method only cares that those are set, not how.
    """

    manager = BuildingManager(
        idd_path=Path("unused.idd"),
        idf_path=Path("unused.idf"),
        weather_file=Path("unused.epw"),
    )

    manager.idf = build_fake_idf()
    manager.is_loaded = True

    return manager
