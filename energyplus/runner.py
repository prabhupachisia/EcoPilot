from pathlib import Path
import shutil
import subprocess

from config.settings import (
    ENERGYPLUS_EXE,
    WEATHER_FILE,
    SIMULATION_TIMEOUT,
)


class EnergyPlusRunner:
    def __init__(self):
        self.energyplus_exe = Path(ENERGYPLUS_EXE)
        self.weather_file = Path(WEATHER_FILE)

    def run(
        self,
        idf_path: Path,
        output_dir: Path,
        clean: bool = True,
    ) -> bool:
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

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=SIMULATION_TIMEOUT,
            )

            if result.returncode != 0:
                print(result.stderr)
                return False

            return True

        except subprocess.TimeoutExpired:
            print("Simulation timed out.")
            return False

        except Exception as e:
            print(f"Simulation failed: {e}")
            return False

    def _validate(self, idf_path: Path):
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