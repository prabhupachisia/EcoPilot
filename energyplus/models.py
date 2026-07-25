from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class SimulationResult:
    """
    Represents a completed EnergyPlus simulation.
    """

    simulation_id: str

    timestamp: datetime
    runtime_seconds: float

    success: bool

    idf_file: Path
    output_directory: Path
    sql_file: Path

    error: str | None = None