from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def sql_database():
    db = (
        Path(__file__).parent.parent
        / "energyplus"
        / "outputs"
        / "pytest_run"
        / "eplusout.sql"
    )

    assert db.exists(), f"Database not found: {db}"

    return db