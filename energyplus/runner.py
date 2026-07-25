from pathlib import Path
import shutil
import subprocess
import time
import uuid
from datetime import datetime

from config.settings import (
    ENERGYPLUS_EXE,
    WEATHER_FILE,
    SIMULATION_TIMEOUT,
)

from energyplus.models import SimulationResult


class EnergyPlusRunner:
    def __init__(self) -> None:
        self.energyplus_exe = Path(ENERGYPLUS_EXE)
        self.weather_file = Path(WEATHER_FILE)

    def run(
        self,
        idf_path: Path,
        output_dir: Path,
        clean: bool = True,
    ) -> SimulationResult:
        """
        Execute an EnergyPlus simulation.
        """
        idf_path = Path(idf_path)
        output_dir = Path(output_dir)

        self._validate(idf_path)

        if clean and output_dir.exists():
            shutil.rmtree(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        command = [
            str(self.energyplus_exe),
            "-w",
            str(self.weather_file),
            "-d",
            str(output_dir),
            str(idf_path),
        ]

        sql_file = output_dir / "eplusout.sql"

        simulation_id = str(uuid.uuid4())
        timestamp = datetime.now()

        start = time.perf_counter()

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=SIMULATION_TIMEOUT,
            )

            runtime = time.perf_counter() - start

            if result.returncode != 0:
                return SimulationResult(
                    simulation_id=simulation_id,
                    timestamp=timestamp,
                    runtime_seconds=runtime,
                    success=False,
                    idf_file=idf_path,
                    output_directory=output_dir,
                    sql_file=sql_file,
                    error=result.stderr.strip()
                    or "EnergyPlus simulation failed.",
                )

            return SimulationResult(
                simulation_id=simulation_id,
                timestamp=timestamp,
                runtime_seconds=runtime,
                success=True,
                idf_file=idf_path,
                output_directory=output_dir,
                sql_file=sql_file,
            )

        except subprocess.TimeoutExpired:
            runtime = time.perf_counter() - start

            return SimulationResult(
                simulation_id=simulation_id,
                timestamp=timestamp,
                runtime_seconds=runtime,
                success=False,
                idf_file=idf_path,
                output_directory=output_dir,
                sql_file=sql_file,
                error="Simulation timed out.",
            )

        except Exception as exc:
            runtime = time.perf_counter() - start

            return SimulationResult(
                simulation_id=simulation_id,
                timestamp=timestamp,
                runtime_seconds=runtime,
                success=False,
                idf_file=idf_path,
                output_directory=output_dir,
                sql_file=sql_file,
                error=str(exc),
            )

    def _validate(self, idf_path: Path) -> None:
        """
        Validate all required files before launching EnergyPlus.
        """

        if not self.energyplus_exe.exists():
            raise FileNotFoundError(
                f"EnergyPlus executable not found: {self.energyplus_exe}"
            )

        if not self.weather_file.exists():
            raise FileNotFoundError(
                f"Weather file not found: {self.weather_file}"
            )

        if not idf_path.exists():
            raise FileNotFoundError(
                f"IDF file not found: {idf_path}"
            )