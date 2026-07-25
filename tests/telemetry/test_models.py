import json
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
    OptimizationSnapshot,
    SimulationInfo,
    WeatherMetrics,
)


def create_building_state() -> BuildingState:
    return BuildingState(
        metadata=BuildingMetadata(
            building_name="Office Building",
            location="Chennai",
            floor_area=1500.0,
            weather_file=Path("weather.epw"),
            idf_file=Path("building.idf"),
        ),
        simulation=SimulationInfo(
            simulation_id="sim-001",
            timestamp=datetime.now(),
            runtime_seconds=120.5,
            success=True,
        ),
        weather=WeatherMetrics(
            outdoor_temperature=34.5,
            outdoor_humidity=68.0,
            wind_speed=3.2,
            solar_radiation=850.0,
        ),
        occupancy=OccupancyMetrics(
            average_occupancy=120,
            peak_occupancy=180,
            occupied_hours=10,
        ),
        energy=EnergyMetrics(
            total_energy_kwh=1250.0,
            cooling_energy_kwh=600.0,
        ),
        hvac=HVACMetrics(
            cooling_load_kw=80,
            cooling_cop=3.8,
        ),
        comfort=ComfortMetrics(
            average_indoor_temperature=24,
            average_relative_humidity=50,
        ),
        carbon=CarbonMetrics(
            emissions_kg_co2=720,
        ),
        cost=CostMetrics(
            electricity_cost=8200,
        ),
        optimization=OptimizationMetrics(
            iteration=1,
            baseline_energy_kwh=1500,
            optimized_energy_kwh=1250,
        ),
    )


def test_building_state_creation():
    state = create_building_state()

    assert state.metadata.building_name == "Office Building"
    assert state.energy.total_energy_kwh == 1250.0
    assert state.simulation.success is True


def test_to_dict():
    state = create_building_state()

    data = state.to_dict()

    assert isinstance(data, dict)
    assert data["metadata"]["building_name"] == "Office Building"
    assert data["energy"]["total_energy_kwh"] == 1250.0


def test_to_json():
    state = create_building_state()

    json_data = state.to_json()
    parsed = json.loads(json_data)

    assert parsed["metadata"]["building_name"] == "Office Building"
    assert parsed["optimization"]["iteration"] == 1


def test_from_dict():
    state = create_building_state()

    restored = BuildingState.from_dict(state.to_dict())

    assert restored.metadata.location == state.metadata.location
    assert restored.energy.total_energy_kwh == state.energy.total_energy_kwh
    assert restored.simulation.success == state.simulation.success


def test_from_json():
    state = create_building_state()

    restored = BuildingState.from_json(state.to_json())

    assert restored.metadata.floor_area == state.metadata.floor_area
    assert restored.cost.electricity_cost == state.cost.electricity_cost


def test_optional_fields():
    weather = WeatherMetrics()

    assert weather.outdoor_temperature is None
    assert weather.wind_speed is None


def test_optimization_snapshot():
    current = create_building_state()

    snapshot = OptimizationSnapshot(
        previous=None,
        current=current,
    )

    assert snapshot.previous is None
    assert snapshot.current.metadata.building_name == "Office Building"

def test_round_trip_serialization():
    original = create_building_state()

    restored = BuildingState.from_json(
        original.to_json()
    )

    assert restored.to_dict() == original.to_dict()