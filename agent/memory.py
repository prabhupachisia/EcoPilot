from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from config.settings import EXPERIENCE_MEMORY_PATH

FEATURE_DIMENSIONS = 5


@dataclass(slots=True)
class Experience:
    """A single optimization cycle's situation and outcome.

    Case memory, not document RAG - the planner looks for past cycles with
    a numerically similar situation (weather, occupancy, setpoints, carbon
    intensity), not semantically similar text. See knowledge_base.py for
    the actual document search over ASHRAE/EnergyPlus references.
    """

    cycle: int

    weather_outdoor_temp: float
    occupancy: float
    cooling_setpoint: float
    heating_setpoint: float
    carbon_intensity: float

    energy_kwh: float
    savings_percent: float
    action_summary: str

    pmv: float | None = None
    confidence: float | None = None
    outcome: str | None = None

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    def feature_vector(self) -> np.ndarray:
        return np.array(
            [
                self.weather_outdoor_temp,
                self.occupancy,
                self.cooling_setpoint,
                self.heating_setpoint,
                self.carbon_intensity,
            ],
            dtype=np.float32,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Experience":
        data = dict(data)
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class ExperienceStore:
    """FAISS-backed case memory of past optimization cycles.

    Numeric features only, no sentence-transformers/torch. Rebuilds the
    index from the in-memory list on every retrieval instead of maintaining
    an incremental one - fine at this scale (a run is tens, maybe low
    hundreds of cycles) and one less thing to keep in sync with the JSON
    file on disk.
    """

    def __init__(self, path: Path = EXPERIENCE_MEMORY_PATH) -> None:
        self.path = Path(path)
        self._experiences: list[Experience] = []

        if self.path.exists():
            self.load()

    @property
    def count(self) -> int:
        return len(self._experiences)

    def store(self, experience: Experience) -> str:
        self._experiences.append(experience)
        self.save()
        return experience.id

    def history(self, limit: int | None = None) -> list[Experience]:
        ordered = sorted(self._experiences, key=lambda experience: experience.cycle)

        if limit is not None:
            return ordered[-limit:]

        return ordered

    def confidence_trend(self) -> list[float]:
        return [
            experience.confidence
            for experience in self.history()
            if experience.confidence is not None
        ]

    def _build_index(self) -> faiss.IndexFlatL2 | None:
        if not self._experiences:
            return None

        vectors = np.stack(
            [experience.feature_vector() for experience in self._experiences]
        )

        index = faiss.IndexFlatL2(FEATURE_DIMENSIONS)
        index.add(vectors)

        return index

    def retrieve_similar(
        self,
        weather_outdoor_temp: float,
        occupancy: float,
        cooling_setpoint: float = 0.0,
        heating_setpoint: float = 0.0,
        carbon_intensity: float = 0.0,
        top_k: int = 3,
    ) -> list[tuple[Experience, float]]:
        """Return the ``top_k`` most similar past experiences, nearest first.

        The returned float is the squared L2 distance in feature space
        (smaller = more similar), not a normalized similarity score.
        """

        index = self._build_index()

        if index is None:
            return []

        query = np.array(
            [
                [
                    weather_outdoor_temp,
                    occupancy,
                    cooling_setpoint,
                    heating_setpoint,
                    carbon_intensity,
                ]
            ],
            dtype=np.float32,
        )

        top_k = min(top_k, len(self._experiences))
        distances, indices = index.search(query, top_k)

        results: list[tuple[Experience, float]] = []

        for distance, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue

            results.append((self._experiences[idx], float(distance)))

        return results

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        payload = [experience.to_dict() for experience in self._experiences]

        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))

        self._experiences = [Experience.from_dict(item) for item in payload]

    def clear(self) -> None:
        self._experiences.clear()
