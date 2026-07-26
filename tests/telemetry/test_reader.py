from pathlib import Path

import pytest

from telemetry.reader import SQLiteReader


@pytest.fixture
def sql_file(sql_database: Path) -> Path:
    return sql_database


def test_reader_initialization(sql_file: Path):
    reader = SQLiteReader(sql_file)

    assert reader.database == sql_file
    assert reader.connection is None


def test_connect(sql_file: Path):
    reader = SQLiteReader(sql_file)

    reader.connect()

    assert reader.connection is not None

    reader.close()


def test_invalid_database():
    reader = SQLiteReader("does_not_exist.db")

    with pytest.raises(FileNotFoundError):
        reader.connect()


def test_fetchone(sql_file: Path):
    with SQLiteReader(sql_file) as reader:
        row = reader.fetchone(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table';
            """
        )

    assert row is not None
    assert "name" in row


def test_fetchall(sql_file: Path):
    with SQLiteReader(sql_file) as reader:
        rows = reader.fetchall(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table';
            """
        )

    assert isinstance(rows, list)
    assert len(rows) > 0
    assert isinstance(rows[0], dict)


def test_table_exists(sql_file: Path):
    with SQLiteReader(sql_file) as reader:
        assert reader.table_exists("ReportData")
        assert reader.table_exists("ReportDataDictionary")
        assert reader.table_exists("TabularData")


def test_table_does_not_exist(sql_file: Path):
    with SQLiteReader(sql_file) as reader:
        assert not reader.table_exists("SomeRandomTable")


def test_context_manager(sql_file: Path):
    with SQLiteReader(sql_file) as reader:
        assert reader.connection is not None

    assert reader.connection is None

def test_query_without_connection(sql_file: Path):
    reader = SQLiteReader(sql_file)

    with pytest.raises(RuntimeError):
        reader.fetchall("SELECT 1;")