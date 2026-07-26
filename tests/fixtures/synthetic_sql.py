from __future__ import annotations

import sqlite3
from pathlib import Path

# Mirrors just the tables/columns SQLiteReader/BuildingStateExtractor query
# from a real EnergyPlus ``eplusout.sql`` -- enough to exercise every
# extractor method (including hourly peak-demand queries) without needing
# EnergyPlus installed. Each entry is:
#   (dictionary_index, variable_name, reporting_frequency, [(hour, value), ...])
# ``hour`` is only meaningful for hourly-frequency rows; other frequencies
# use ``None``.
_VARIABLES: list[tuple[int, str, str, list[tuple[int | None, float]]]] = [
    (1, "Site Outdoor Air Drybulb Temperature", "Zone Timestep", [(None, 28.5), (None, 30.2), (None, 26.1)]),
    (2, "People Occupant Count", "Zone Timestep", [(None, 5.0), (None, 12.0), (None, 8.0)]),
    (3, "Electricity:Facility", "Run Period", [(None, 365_000_000.0)]),
    (4, "Heating:NaturalGas", "Run Period", [(None, 50_000_000.0)]),
    (5, "Cooling:Electricity", "Run Period", [(None, 180_000_000.0)]),
    (6, "InteriorLights:Electricity", "Run Period", [(None, 40_000_000.0)]),
    (7, "InteriorEquipment:Electricity", "Run Period", [(None, 60_000_000.0)]),
    (8, "Fans:Electricity", "Run Period", [(None, 15_000_000.0)]),
    (9, "Zone Air System Sensible Heating Rate", "Zone Timestep", [(None, 1200.0), (None, 900.0)]),
    (10, "Zone Air System Sensible Cooling Rate", "Zone Timestep", [(None, 2200.0), (None, 1800.0)]),
    (11, "Zone Air Temperature", "Zone Timestep", [(None, 22.0), (None, 23.5), (None, 21.8)]),
    (
        12,
        "Electricity:Facility",
        "Hourly",
        [(hour, value) for hour, value in enumerate(
            [12_000_000.0, 10_500_000.0, 9_800_000.0, 9_500_000.0, 10_200_000.0,
             13_400_000.0, 18_600_000.0, 24_200_000.0, 27_800_000.0, 29_100_000.0,
             30_500_000.0, 31_200_000.0, 31_800_000.0, 32_400_000.0, 33_100_000.0,
             45_000_000.0, 38_200_000.0, 30_900_000.0, 24_600_000.0, 20_300_000.0,
             17_800_000.0, 15_600_000.0, 14_100_000.0, 12_900_000.0]
        )],
    ),
]

# Per-zone variables (real EnergyPlus keys these by KeyValue = zone name;
# one ReportDataDictionary row per zone rather than one shared row).
_ZONE_VARIABLES: list[tuple[int, str, str, str, list[float]]] = [
    (13, "Zone Mean Air Temperature", "SPACE1-1", "Zone Timestep", [22.5, 23.0, 23.8]),
    (14, "Zone Mean Air Temperature", "SPACE2-1", "Zone Timestep", [21.8, 22.4, 23.1]),
    (15, "Zone Mean Air Temperature", "SPACE3-1", "Zone Timestep", [24.2, 24.8, 25.0]),
    (16, "Zone Mean Air Temperature", "SPACE4-1", "Zone Timestep", [23.0, 23.5, 23.9]),
    (17, "Zone Mean Air Temperature", "SPACE5-1", "Zone Timestep", [22.0, 22.6, 22.9]),
    (18, "Zone Mean Air Temperature", "PLENUM-1", "Zone Timestep", [25.5, 26.0, 26.2]),
]


def build_synthetic_eplus_sql(path: Path) -> Path:
    """Create a minimal EnergyPlus-shaped SQLite database at ``path``.

    Returns ``path`` for convenience so this can be used directly as a
    fixture return value.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        path.unlink()

    connection = sqlite3.connect(path)

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE Simulations (
                SimulationIndex INTEGER PRIMARY KEY,
                TimeStamp TEXT,
                CompletedSuccessfully TEXT
            )
            """
        )
        cursor.execute(
            "INSERT INTO Simulations VALUES (1, 'YMD=2026.07.26 00:00', 'TRUE')"
        )

        cursor.execute(
            """
            CREATE TABLE Time (
                TimeIndex INTEGER PRIMARY KEY,
                Hour INTEGER
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE ReportDataDictionary (
                ReportDataDictionaryIndex INTEGER PRIMARY KEY,
                Name TEXT,
                ReportingFrequency TEXT,
                KeyValue TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE ReportData (
                ReportDataIndex INTEGER PRIMARY KEY AUTOINCREMENT,
                TimeIndex INTEGER,
                ReportDataDictionaryIndex INTEGER,
                Value REAL
            )
            """
        )

        # Present (empty) purely so ``table_exists("TabularData")`` checks pass,
        # matching what a real eplusout.sql also contains.
        cursor.execute("CREATE TABLE TabularData (Value TEXT)")

        time_index = 0

        for dictionary_index, name, frequency, samples in _VARIABLES:
            cursor.execute(
                "INSERT INTO ReportDataDictionary VALUES (?, ?, ?, ?)",
                (dictionary_index, name, frequency, None),
            )

            for hour, value in samples:
                row_time_index = None

                if hour is not None:
                    time_index += 1
                    row_time_index = time_index
                    cursor.execute(
                        "INSERT INTO Time VALUES (?, ?)",
                        (row_time_index, hour),
                    )

                cursor.execute(
                    "INSERT INTO ReportData (TimeIndex, ReportDataDictionaryIndex, Value) "
                    "VALUES (?, ?, ?)",
                    (row_time_index, dictionary_index, value),
                )

        for dictionary_index, name, key_value, frequency, samples in _ZONE_VARIABLES:
            cursor.execute(
                "INSERT INTO ReportDataDictionary VALUES (?, ?, ?, ?)",
                (dictionary_index, name, frequency, key_value),
            )

            for value in samples:
                cursor.execute(
                    "INSERT INTO ReportData (TimeIndex, ReportDataDictionaryIndex, Value) "
                    "VALUES (?, ?, ?)",
                    (None, dictionary_index, value),
                )

        connection.commit()
    finally:
        connection.close()

    return path
