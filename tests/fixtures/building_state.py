from __future__ import annotations

from datetime import datetime
from pathlib import Path

from telemetry.models import (
    BuildingMetadata,
    BuildingState,
    CarbonMetrics,
    ComfortMetrics,
    CostMetrics,
    EnergyMetrics,
    HVACMetrics,
    OccupancyMetrics,
    OptimizationMetrics,
    SimulationInfo,
    WeatherMetrics,
)


def make_building_state(
    *,
    outdoor_temperature: float = 30.0,
    average_occupancy: float = 10.0,
    total_energy_kwh: float = 100.0,
    pmv: float | None = None,
) -> BuildingState:
    """A small, overridable BuildingState for agent-layer unit tests."""

    return BuildingState(
        metadata=BuildingMetadata(
            building_name="Test Building",
            location="Test Location",
            floor_area=1000.0,
            weather_file=Path("weather.epw"),
            idf_file=Path("building.idf"),
        ),
        simulation=SimulationInfo(
            simulation_id="sim-001",
            timestamp=datetime.now(),
            runtime_seconds=10.0,
            success=True,
        ),
        weather=WeatherMetrics(outdoor_temperature=outdoor_temperature),
        occupancy=OccupancyMetrics(average_occupancy=average_occupancy),
        energy=EnergyMetrics(total_energy_kwh=total_energy_kwh),
        hvac=HVACMetrics(),
        comfort=ComfortMetrics(pmv=pmv),
        carbon=CarbonMetrics(),
        cost=CostMetrics(),
        optimization=OptimizationMetrics(),
    )
