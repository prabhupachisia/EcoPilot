"""Regression tests for config/settings.py's env-var-driven constants.

settings.py computes its constants at import time from os.environ, so
testing a specific env combination means reloading the already-imported
module with the environment monkeypatched first.
"""

import importlib
from pathlib import Path

import config.settings as settings


def _reload_with_env(monkeypatch, **env: str) -> None:
    for key in ("IDD_PATH", "ENERGYPLUS_HOME"):
        monkeypatch.delenv(key, raising=False)

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    importlib.reload(settings)


def test_idd_path_falls_back_to_energyplus_home_when_unset(monkeypatch) -> None:
    """Regression test: Path("") == Path("."), which is truthy, so a naive
    `Path(os.getenv("IDD_PATH", "")) or fallback` never actually falls
    back -- this silently resolved to the current working directory on
    any machine that only sets ENERGYPLUS_HOME (the documented, common
    case), instead of ENERGYPLUS_HOME/Energy+.idd.
    """

    try:
        _reload_with_env(monkeypatch, ENERGYPLUS_HOME=r"C:\EnergyPlusV26-1-0")

        assert settings.IDD_PATH == Path(r"C:\EnergyPlusV26-1-0") / "Energy+.idd"
    finally:
        importlib.reload(settings)


def test_idd_path_uses_explicit_override_when_set(monkeypatch) -> None:
    try:
        _reload_with_env(
            monkeypatch,
            ENERGYPLUS_HOME=r"C:\EnergyPlusV26-1-0",
            IDD_PATH=r"D:\custom\Energy+.idd",
        )

        assert settings.IDD_PATH == Path(r"D:\custom\Energy+.idd")
    finally:
        importlib.reload(settings)
