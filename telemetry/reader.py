from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class SQLiteReader:
    def __init__(self, database: str | Path):
        self.database = Path(database)
        self.connection: sqlite3.Connection | None = None

    def connect(self) -> None:
        if not self.database.exists():
            raise FileNotFoundError(f"Database not found: {self.database}")

        self.connection = sqlite3.connect(self.database)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def execute(
        self,
        query: str,
        parameters: tuple[Any, ...] = (),
    ) -> sqlite3.Cursor:
        if self.connection is None:
            raise RuntimeError("Database connection has not been established.")

        return self.connection.execute(query, parameters)

    def fetchone(
        self,
        query: str,
        parameters: tuple[Any, ...] = (),
    ) -> dict[str, Any] | None:
        row = self.execute(query, parameters).fetchone()

        return dict(row) if row else None

    def fetchall(
        self,
        query: str,
        parameters: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        rows = self.execute(query, parameters).fetchall()

        return [dict(row) for row in rows]

    def __enter__(self) -> "SQLiteReader":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def table_exists(self, table: str) -> bool:
        result = self.fetchone(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name = ?;
            """,
            (table,),
        )

        return result is not None