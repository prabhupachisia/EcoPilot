from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


# ENUMS

class BuildingComponent(str, Enum):
    ENVELOPE = "envelope"
    PEOPLE = "people"
    LIGHTING = "lighting"
    EQUIPMENT = "equipment"
    HVAC = "hvac"
    VENTILATION = "ventilation"
    INFILTRATION = "infiltration"
    MATERIAL = "material"
    CONSTRUCTION = "construction"
    WINDOW = "window"
    SCHEDULE = "schedule"
    THERMOSTAT = "thermostat"
    BUILDING = "building"


class ActionType(str, Enum):
    SET = "set"
    SCALE = "scale"
    REPLACE = "replace"
    ENABLE = "enable"
    DISABLE = "disable"
    DELETE = "delete"
    CREATE = "create"
    RENAME = "rename"
    SHIFT = "shift"
    RESET = "reset"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


# CORE ACTION MODELS

@dataclass(slots=True)
class BuildingAction:
    component: BuildingComponent
    action: ActionType

    target: str
    parameter: str

    value: Any

    reason: str | None = None
    iteration: int = 0


@dataclass(slots=True)
class ActionResult:
    success: bool

    action: BuildingAction

    previous_value: Any = None
    current_value: Any = None

    message: str = ""


@dataclass(slots=True)
class ValidationResult:
    valid: bool = True

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


# BUILDING INFORMATION

@dataclass(slots=True)
class ZoneInfo:
    name: str

    area: float | None = None
    volume: float | None = None

    people: float | None = None
    lighting_power: float | None = None
    equipment_power: float | None = None

    infiltration_rate: float | None = None


@dataclass(slots=True)
class MaterialInfo:
    name: str

    roughness: str | None = None
    thickness: float | None = None

    conductivity: float | None = None
    density: float | None = None

    specific_heat: float | None = None


@dataclass(slots=True)
class ConstructionInfo:
    name: str

    layers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WindowInfo:
    name: str

    construction: str

    area: float | None = None

    u_value: float | None = None
    shgc: float | None = None


@dataclass(slots=True)
class ScheduleInfo:
    name: str

    schedule_type: str

    values: list[float] = field(default_factory=list)


@dataclass(slots=True)
class HVACInfo:
    name: str

    cooling_setpoint: float | None = None
    heating_setpoint: float | None = None

    supply_air_temperature: float | None = None

    outdoor_air_rate: float | None = None


# BUILDING SUMMARY

@dataclass(slots=True)
class BuildingSummary:
    building_name: str

    zones: int
    schedules: int

    materials: int
    constructions: int

    windows: int

    people_objects: int
    lighting_objects: int
    equipment_objects: int

    hvac_systems: int

@dataclass(slots=True)
class BuildingMetadata:
    building_name: str
    idf_path: Path
    weather_file: Path

    version: str | None = None

    floor_area: float | None = None

    number_of_zones: int | None = None

    created_at: datetime | None = None
    
# HISTORY

@dataclass(slots=True)
class ChangeRecord:
    timestamp: datetime

    component: BuildingComponent

    target: str

    parameter: str

    previous_value: Any
    new_value: Any

    reason: str | None = None


@dataclass(slots=True)
class BuildingDiff:
    component: BuildingComponent

    target: str

    parameter: str

    old_value: Any
    new_value: Any


# SNAPSHOTS

@dataclass(slots=True)
class BuildingSnapshot:
    name: str

    created_at: datetime

    idf_path: Path

    notes: str = ""


# TRANSACTIONS
@dataclass(slots=True)
class Transaction:
    transaction_id: str

    started_at: datetime

    status: TransactionStatus = TransactionStatus.PENDING

    actions: list[BuildingAction] = field(default_factory=list)

    history: list[ChangeRecord] = field(default_factory=list)
