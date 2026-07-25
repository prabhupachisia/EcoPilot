from __future__ import annotations

from dataclasses import dataclass

from energyplus.models import SimulationResult
from telemetry.models import BuildingState


@dataclass(slots=True)
class SimulationSession:
    """
    Represents the current simulation session.

    A session begins after an EnergyPlus simulation completes and is
    progressively enriched as additional processing (telemetry parsing,
    optimization, reporting, etc.) is performed.
    """

    simulation: SimulationResult
    building_state: BuildingState | None = None

    @property
    def parsed(self) -> bool:
        return self.building_state is not None