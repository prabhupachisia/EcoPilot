from pathlib import Path

import pytest

from telemetry.extractor import BuildingStateExtractor
from telemetry.reader import SQLiteReader


@pytest.fixture
def extractor(sql_database):
    with SQLiteReader(sql_database) as reader:
        yield BuildingStateExtractor(reader)


def test_extract_simulation(extractor):
    simulation = extractor.extract_simulation(runtime_seconds=12.5)

    assert simulation is not None
    assert simulation.simulation_id
    assert simulation.runtime_seconds == 12.5
    assert simulation.timestamp is not None
    assert isinstance(simulation.success, bool)


def test_extract_weather(extractor):
    weather = extractor.extract_weather()

    assert weather is not None
    assert weather.outdoor_temperature is not None


def test_extract_occupancy(extractor):
    occupancy = extractor.extract_occupancy()

    assert occupancy is not None

    if occupancy.average_occupancy is not None:
        assert occupancy.average_occupancy >= 0

    if occupancy.peak_occupancy is not None:
        assert occupancy.peak_occupancy >= 0


def test_extract_energy(extractor):
    energy = extractor.extract_energy()

    assert energy is not None

    fields = [
        energy.total_energy_kwh,
        energy.heating_energy_kwh,
        energy.cooling_energy_kwh,
        energy.lighting_energy_kwh,
        energy.equipment_energy_kwh,
        energy.fan_energy_kwh,
    ]

    for value in fields:
        if value is not None:
            assert value >= 0


def test_extract_hvac(extractor):
    hvac = extractor.extract_hvac()

    assert hvac is not None

    if hvac.heating_load_kw is not None:
        assert hvac.heating_load_kw >= 0

    if hvac.cooling_load_kw is not None:
        assert hvac.cooling_load_kw >= 0


def test_extract_comfort(extractor):
    comfort = extractor.extract_comfort()

    assert comfort is not None

    if comfort.average_indoor_temperature is not None:
        assert -20 <= comfort.average_indoor_temperature <= 60
