from pathlib import Path

from pydantic import BaseModel


class SimulationResult(BaseModel):
    success: bool
    output_directory: Path
    sql_file: Path
    stdout: str
    stderr: str
    runtime_seconds: float