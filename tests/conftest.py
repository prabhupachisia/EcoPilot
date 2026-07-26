from pathlib import Path

import pytest

from tests.fixtures.fake_building import build_fake_building_manager
from tests.fixtures.synthetic_sql import build_synthetic_eplus_sql


@pytest.fixture(scope="session")
def sql_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An EnergyPlus-shaped SQLite database usable without EnergyPlus installed.

    Uses a real, pre-generated ``eplusout.sql`` if one is present (e.g. a
    developer has actually run a simulation locally), otherwise builds a
    synthetic database with the same tables/columns so the test suite stays
    hermetic on a fresh clone.
    """

    real_db = (
        Path(__file__).parent.parent
        / "energyplus"
        / "outputs"
        / "pytest_run"
        / "eplusout.sql"
    )

    if real_db.exists():
        return real_db

    synthetic_path = tmp_path_factory.mktemp("eplus_sql") / "eplusout.sql"

    return build_synthetic_eplus_sql(synthetic_path)


@pytest.fixture
def fake_building_manager():
    """A ``BuildingManager`` with a small fake IDF already "loaded".

    See ``tests/fixtures/fake_building.py`` for why this doesn't use real
    eppy: eppy needs a real, EnergyPlus-install-only IDD file to parse any
    IDF, which isn't available on every machine running this test suite.
    """

    return build_fake_building_manager()
