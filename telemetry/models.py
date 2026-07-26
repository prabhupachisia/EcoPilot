from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SimulationInfo:
    simulation_id: str
    timestamp: datetime
    runtime_seconds: float
    success: bool


@dataclass(slots=True)
class BuildingMetadata:
    building_name: str
    location: str
    floor_area: float
    weather_file: Path
    idf_file: Path


@dataclass(slots=True)
class WeatherMetrics:
    outdoor_temperature: float | None = None
    outdoor_humidity: float | None = None
    wind_speed: float | None = None
    solar_radiation: float | None = None


@dataclass(slots=True)
class OccupancyMetrics:
    average_occupancy: float | None = None
    peak_occupancy: int | None = None
    occupied_hours: float | None = None


@dataclass(slots=True)
class EnergyMetrics:
    total_energy_kwh: float | None = None

    heating_energy_kwh: float | None = None
    cooling_energy_kwh: float | None = None

    lighting_energy_kwh: float | None = None
    equipment_energy_kwh: float | None = None

    fan_energy_kwh: float | None = None
    pump_energy_kwh: float | None = None

    renewable_generation_kwh: float | None = None
    net_energy_kwh: float | None = None


@dataclass(slots=True)
class HVACMetrics:
    heating_load_kw: float | None = None
    cooling_load_kw: float | None = None

    heating_cop: float | None = None
    cooling_cop: float | None = None

    hvac_efficiency: float | None = None


@dataclass(slots=True)
class ComfortMetrics:
    average_indoor_temperature: float | None = None
    average_relative_humidity: float | None = None

    pmv: float | None = None
    ppd: float | None = None

    discomfort_hours: float | None = None


@dataclass(slots=True)
class CarbonMetrics:
    emissions_kg_co2: float | None = None
    carbon_intensity: float | None = None


@dataclass(slots=True)
class CostMetrics:
    electricity_cost: float | None = None
    peak_demand_kw: float | None = None


@dataclass(slots=True)
class OptimizationMetrics:
    iteration: int = 0

    baseline_energy_kwh: float | None = None
    optimized_energy_kwh: float | None = None
    objective_value: float | None = None


@dataclass(slots=True)
class BuildingState:
    metadata: BuildingMetadata
    simulation: SimulationInfo

    weather: WeatherMetrics
    occupancy: OccupancyMetrics

    energy: EnergyMetrics
    hvac: HVACMetrics
    comfort: ComfortMetrics

    carbon: CarbonMetrics
    cost: CostMetrics

    optimization: OptimizationMetrics

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        data["metadata"]["weather_file"] = str(self.metadata.weather_file)
        data["metadata"]["idf_file"] = str(self.metadata.idf_file)
        data["simulation"]["timestamp"] = self.simulation.timestamp.isoformat()

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildingState":
        metadata = data["metadata"]
        simulation = data["simulation"]

        return cls(
            metadata=BuildingMetadata(
                building_name=metadata["building_name"],
                location=metadata["location"],
                floor_area=metadata["floor_area"],
                weather_file=Path(metadata["weather_file"]),
                idf_file=Path(metadata["idf_file"]),
            ),
            simulation=SimulationInfo(
                simulation_id=simulation["simulation_id"],
                timestamp=datetime.fromisoformat(
                    simulation["timestamp"]
                ),
                runtime_seconds=simulation["runtime_seconds"],
                success=simulation["success"],
            ),
            weather=WeatherMetrics(**data["weather"]),
            occupancy=OccupancyMetrics(**data["occupancy"]),
            energy=EnergyMetrics(**data["energy"]),
            hvac=HVACMetrics(**data["hvac"]),
            comfort=ComfortMetrics(**data["comfort"]),
            carbon=CarbonMetrics(**data["carbon"]),
            cost=CostMetrics(**data["cost"]),
            optimization=OptimizationMetrics(**data["optimization"]),
        )

    def to_json(self, indent: int = 4) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, data: str) -> "BuildingState":
        return cls.from_dict(json.loads(data))


@dataclass(slots=True)
class OptimizationSnapshot:
    previous: BuildingState | None
    current: BuildingState