from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from fastmcp import FastMCP

from config.settings import CARBON_INTENSITY_PROFILE_PATH

if TYPE_CHECKING:
    from mcp_server.dependencies import DependencyProvider

HOURS_PER_DAY = 24


class CarbonIntensityProfile:
    """Hourly grid carbon-intensity curve (kg CO2 per kWh of electricity).

    The problem statement explicitly names "local carbon grid intensity" as
    an optimization target, but nothing upstream of this module tracks it.
    This is a small, hand-authored, documented-as-representative 24-hour
    curve (see ``config/carbon_intensity.json``) rather than a live grid
    API -- the goal is to make carbon intensity a first-class signal the
    Planner reasons about, not to source real-time grid data.
    """

    def __init__(
        self,
        path: Path = CARBON_INTENSITY_PROFILE_PATH,
        profile: dict[int, float] | None = None,
    ) -> None:
        self.path = Path(path)
        self._profile = dict(profile) if profile is not None else self._load(self.path)

    @staticmethod
    def _load(path: Path) -> dict[int, float]:
        raw = json.loads(path.read_text(encoding="utf-8"))

        profile: dict[int, float] = {}

        for key, value in raw.items():
            try:
                hour = int(key)
            except ValueError:
                continue

            profile[hour] = float(value)

        return profile

    def intensity_at(self, hour: int) -> float:
        return self._profile[hour % HOURS_PER_DAY]

    def as_dict(self) -> dict[int, float]:
        return dict(self._profile)

    def lowest_intensity_hours(self, count: int = 4) -> list[int]:
        ranked = sorted(self._profile.items(), key=lambda item: item[1])
        return [hour for hour, _ in ranked[:count]]

    def highest_intensity_hours(self, count: int = 4) -> list[int]:
        ranked = sorted(self._profile.items(), key=lambda item: item[1], reverse=True)
        return [hour for hour, _ in ranked[:count]]

    def average_intensity(self) -> float:
        return sum(self._profile.values()) / len(self._profile)

    def compute_emissions_kg(self, hourly_energy_kwh: dict[int, float]) -> float:
        """Total kg CO2 for a set of (hour -> kWh) readings."""

        return sum(
            kwh * self.intensity_at(hour) for hour, kwh in hourly_energy_kwh.items()
        )

    def estimate_emissions_kg(self, total_energy_kwh: float | None) -> float | None:
        """Approximate kg CO2 for a run-period total using the average intensity.

        Used when only a single run-period energy total is available (no
        hourly breakdown), e.g. for a quick baseline-vs-optimized carbon
        comparison.
        """

        if total_energy_kwh is None:
            return None

        return total_energy_kwh * self.average_intensity()


def register_carbon_tools(
    server: FastMCP,
    dependencies: "DependencyProvider",
) -> None:
    """Register grid carbon-intensity tools with the MCP server."""

    @server.tool(
        name="get_carbon_intensity",
        description="Return the grid carbon intensity (kg CO2/kWh) for a given hour of day (0-23).",
    )
    def get_carbon_intensity(hour: int) -> float:
        return dependencies.carbon_profile.intensity_at(hour)

    @server.tool(
        name="get_carbon_intensity_profile",
        description="Return the full 24-hour grid carbon-intensity profile (kg CO2/kWh).",
    )
    def get_carbon_intensity_profile() -> dict[int, float]:
        return dependencies.carbon_profile.as_dict()

    @server.tool(
        name="get_low_carbon_hours",
        description=(
            "Return the N lowest-carbon-intensity hours of the day -- useful "
            "for scheduling precooling/preheating to shift load onto a "
            "cleaner part of the grid."
        ),
    )
    def get_low_carbon_hours(count: int = 4) -> list[int]:
        return dependencies.carbon_profile.lowest_intensity_hours(count)

    @server.tool(
        name="get_high_carbon_hours",
        description="Return the N highest-carbon-intensity hours of the day.",
    )
    def get_high_carbon_hours(count: int = 4) -> list[int]:
        return dependencies.carbon_profile.highest_intensity_hours(count)

    @server.tool(
        name="compute_carbon_emissions",
        description="Compute total kg CO2 given hourly energy use (kWh keyed by hour 0-23).",
    )
    def compute_carbon_emissions(hourly_energy_kwh: dict[int, float]) -> float:
        return dependencies.carbon_profile.compute_emissions_kg(hourly_energy_kwh)


__all__ = [
    "CarbonIntensityProfile",
    "register_carbon_tools",
]
