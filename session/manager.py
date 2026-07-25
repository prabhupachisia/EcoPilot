from __future__ import annotations

from energyplus.models import SimulationResult
from telemetry.models import BuildingState

from session.models import SimulationSession


class SimulationSessionManager:
    """
    Stores the active simulation session.
    """

    def __init__(self) -> None:
        self._session: SimulationSession | None = None

    @property
    def initialized(self) -> bool:
        """
        Returns True if a session has been started.
        """
        return self._session is not None

    @property
    def session(self) -> SimulationSession:
        """
        Returns the current simulation session.
        """
        if self._session is None:
            raise RuntimeError(
                "No active simulation session."
            )

        return self._session

    def start(
        self,
        simulation: SimulationResult,
    ) -> SimulationSession:
        """
        Starts a new simulation session.
        """
        self._session = SimulationSession(
            simulation=simulation,
        )

        return self._session

    def update(
        self,
        building_state: BuildingState,
    ) -> SimulationSession:
        """
        Updates the current session with telemetry data.
        """
        session = self.session
        session.building_state = building_state

        return session

    def clear(self) -> None:
        """
        Clears the current simulation session.
        """
        self._session = None