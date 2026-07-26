from pathlib import Path

import pytest

from config.settings import BASELINE_IDF, ENERGYPLUS_EXE, OUTPUT_DIR
from energyplus.models import SimulationResult
from energyplus.runner import EnergyPlusRunner

requires_energyplus = pytest.mark.skipif(
    not ENERGYPLUS_EXE.exists(),
    reason="EnergyPlus is not installed on this machine.",
)


@requires_energyplus
def test_runner_initialization() -> None:
    runner = EnergyPlusRunner()

    assert runner.energyplus_exe.exists()
    assert runner.weather_file.exists()


def test_baseline_idf_exists() -> None:
    assert BASELINE_IDF.exists()


def test_invalid_idf_raises() -> None:
    runner = EnergyPlusRunner()

    with pytest.raises(FileNotFoundError):
        runner.run(
            idf_path=Path("invalid.idf"),
            output_dir=OUTPUT_DIR / "invalid",
        )


def test_validate_falls_back_to_default_weather_file_when_none_given(tmp_path: Path) -> None:
    runner = EnergyPlusRunner()
    runner.energyplus_exe = tmp_path / "energyplus.exe"
    runner.energyplus_exe.touch()
    runner.weather_file = tmp_path / "does_not_exist.epw"

    idf_path = tmp_path / "building.idf"
    idf_path.touch()

    with pytest.raises(FileNotFoundError, match="does_not_exist.epw"):
        runner._validate(idf_path, weather_file=None)


def test_validate_checks_the_overridden_weather_file_instead_of_the_default(tmp_path: Path) -> None:
    runner = EnergyPlusRunner()
    runner.energyplus_exe = tmp_path / "energyplus.exe"
    runner.energyplus_exe.touch()
    runner.weather_file = tmp_path / "default.epw"
    runner.weather_file.touch()

    idf_path = tmp_path / "building.idf"
    idf_path.touch()

    override = tmp_path / "custom.epw"

    with pytest.raises(FileNotFoundError, match="custom.epw"):
        runner._validate(idf_path, weather_file=override)


@requires_energyplus
def test_energyplus_simulation() -> None:
    runner = EnergyPlusRunner()

    output_dir = OUTPUT_DIR / "pytest_run"

    result = runner.run(
        idf_path=BASELINE_IDF,
        output_dir=output_dir,
    )

    assert isinstance(result, SimulationResult)

    assert result.success is True
    assert result.error is None

    assert result.idf_file == BASELINE_IDF
    assert result.output_directory == output_dir
    assert result.sql_file == output_dir / "eplusout.sql"

    assert output_dir.exists()
    assert result.sql_file.exists()
    assert (output_dir / "eplusout.err").exists()
    assert (output_dir / "eplusout.end").exists()
    assert (output_dir / "eplusout.eso").exists()