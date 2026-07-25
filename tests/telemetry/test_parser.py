from pathlib import Path

import pytest

from telemetry.models import BuildingMetadata
from telemetry.parser import TelemetryParser


def test_parse_building_state(sql_database):
    metadata = BuildingMetadata(
        building_name="Test Building",
        location="Test Location",
        floor_area=1000.0,
        weather_file=Path("weather.epw"),
        idf_file=Path("building.idf"),
    )

    parser = TelemetryParser()

    state = parser.parse(
        sql_file=sql_database,
        metadata=metadata,
        runtime_seconds=10.0,
    )

    assert state is not None
    assert state.metadata == metadata
    assert state.simulation.runtime_seconds == 10.0

    assert state.weather is not None
    assert state.energy is not None
    assert state.hvac is not None
    assert state.comfort is not None
    assert state.occupancy is not None


def test_parse_invalid_database():
    parser = TelemetryParser()

    metadata = BuildingMetadata(
        building_name="Test",
        location="Test",
        floor_area=100,
        weather_file=Path("weather.epw"),
        idf_file=Path("building.idf"),
    )

    with pytest.raises(FileNotFoundError):
        parser.parse(
            sql_file="does_not_exist.sql",
            metadata=metadata,
            runtime_seconds=1.0,
        )