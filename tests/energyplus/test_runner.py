from pathlib import Path

import pytest

from config.settings import BASELINE_IDF, OUTPUT_DIR
from energyplus.runner import EnergyPlusRunner


def test_runner_initialization():
    runner = EnergyPlusRunner()

    assert runner.energyplus_exe.exists()
    assert runner.weather_file.exists()


def test_baseline_idf_exists():
    assert BASELINE_IDF.exists()


def test_invalid_idf_raises():
    runner = EnergyPlusRunner()

    with pytest.raises(FileNotFoundError):
        runner.run(
            idf_path=Path("invalid.idf"),
            output_dir=OUTPUT_DIR / "invalid",
        )


def test_energyplus_simulation():
    runner = EnergyPlusRunner()

    output_dir = OUTPUT_DIR / "pytest_run"

    success = runner.run(
        idf_path=BASELINE_IDF,
        output_dir=output_dir,
    )

    assert success

    assert output_dir.exists()
    assert (output_dir / "eplusout.err").exists()
    assert (output_dir / "eplusout.end").exists()
    assert (output_dir / "eplusout.eso").exists()