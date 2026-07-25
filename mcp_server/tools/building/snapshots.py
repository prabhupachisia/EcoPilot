from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Snapshot:
    name: str
    created_at: datetime
    idf: Any
    metadata: dict[str, Any] = field(default_factory=dict)

    # AI optimization information
    reward: float | None = None
    objective: float | None = None
    episode: int | None = None


class SnapshotMixin:
    """
    Snapshot management for EnergyPlus models.

    Snapshots provide persistent restore points that allow the
    building to be restored to a previous state.
    """

    # ------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------

    def _initialize_snapshots(self) -> None:

        if not hasattr(self, "_snapshots"):

            self._snapshots: dict[str, Snapshot] = {}

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def snapshot_names(self) -> list[str]:
        """
        Return all snapshot names.
        """

        self._initialize_snapshots()

        return sorted(self._snapshots.keys())

    def snapshot_exists(
        self,
        name: str,
    ) -> bool:

        self._initialize_snapshots()

        return name in self._snapshots

    def get_snapshot(
        self,
        name: str,
    ) -> Snapshot:

        self._initialize_snapshots()

        if name not in self._snapshots:

            raise ValueError(
                f"Snapshot '{name}' does not exist."
            )

        return self._snapshots[name]

    # ------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------

    def create_snapshot(
        self,
        name: str,
        **metadata,
    ) -> Snapshot:
        """
        Create a named snapshot of the current building.
        """

        self._initialize_snapshots()

        if self.snapshot_exists(name):

            raise ValueError(
                f"Snapshot '{name}' already exists."
            )

        snapshot = Snapshot(
            name=name,
            created_at=datetime.utcnow(),
            idf=deepcopy(self.idf),
            metadata=dict(metadata),
        )

        self._snapshots[name] = snapshot

        return snapshot
        # ------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------

    def restore_snapshot(
        self,
        name: str,
    ) -> Snapshot:
        """
        Restore the building to a previously saved snapshot.
        """

        snapshot = self.get_snapshot(name)

        self.idf = deepcopy(snapshot.idf)

        self._mark_dirty()

        return snapshot

    # ------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------

    def delete_snapshot(
        self,
        name: str,
    ) -> Snapshot:
        """
        Delete a snapshot.
        """

        snapshot = self.get_snapshot(name)

        del self._snapshots[name]

        return snapshot

    def clear_snapshots(
        self,
    ) -> None:
        """
        Remove every stored snapshot.
        """

        self._initialize_snapshots()

        self._snapshots.clear()

    # ------------------------------------------------------------
    # Rename
    # ------------------------------------------------------------

    def rename_snapshot(
        self,
        old_name: str,
        new_name: str,
    ) -> Snapshot:
        """
        Rename an existing snapshot.
        """

        if not self.snapshot_exists(old_name):
            raise ValueError(
                f"Snapshot '{old_name}' does not exist."
            )

        if self.snapshot_exists(new_name):
            raise ValueError(
                f"Snapshot '{new_name}' already exists."
            )

        snapshot = self._snapshots.pop(old_name)

        snapshot.name = new_name

        self._snapshots[new_name] = snapshot

        return snapshot

    # ------------------------------------------------------------
    # Overwrite
    # ------------------------------------------------------------

    def overwrite_snapshot(
        self,
        name: str,
        **metadata,
    ) -> Snapshot:
        """
        Replace an existing snapshot with the current model.
        """

        self._initialize_snapshots()

        snapshot = Snapshot(
            name=name,
            created_at=datetime.utcnow(),
            idf=deepcopy(self.idf),
            metadata=dict(metadata),
        )

        self._snapshots[name] = snapshot

        return snapshot
        # ------------------------------------------------------------
    # Information
    # ------------------------------------------------------------

    def snapshot_count(self) -> int:
        """
        Return the number of stored snapshots.
        """

        self._initialize_snapshots()

        return len(self._snapshots)

    def latest_snapshot(self) -> Snapshot | None:
        """
        Return the most recently created snapshot.
        """

        self._initialize_snapshots()

        if not self._snapshots:
            return None

        return max(
            self._snapshots.values(),
            key=lambda snapshot: snapshot.created_at,
        )

    def list_snapshots(self) -> list[Snapshot]:
        """
        Return all snapshots ordered by creation time.
        """

        self._initialize_snapshots()

        return sorted(
            self._snapshots.values(),
            key=lambda snapshot: snapshot.created_at,
        )

    # ------------------------------------------------------------
    # Copy
    # ------------------------------------------------------------

    def copy_snapshot(
        self,
        source_name: str,
        target_name: str,
    ) -> Snapshot:
        """
        Duplicate an existing snapshot.
        """

        if self.snapshot_exists(target_name):
            raise ValueError(
                f"Snapshot '{target_name}' already exists."
            )

        source = self.get_snapshot(source_name)

        copied = Snapshot(
            name=target_name,
            created_at=datetime.utcnow(),
            idf=deepcopy(source.idf),
            metadata=deepcopy(source.metadata),
        )

        self._snapshots[target_name] = copied

        return copied

    # ------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------

    def update_snapshot_metadata(
        self,
        name: str,
        **metadata,
    ) -> Snapshot:
        """
        Update snapshot metadata.
        """

        snapshot = self.get_snapshot(name)

        snapshot.metadata.update(metadata)

        return snapshot

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    def snapshot_summary(self) -> dict:
        """
        Return summary information about stored snapshots.
        """

        latest = self.latest_snapshot()

        return {
            "count": self.snapshot_count(),
            "names": self.snapshot_names(),
            "latest": (
                latest.name
                if latest is not None
                else None
            ),
            "latest_timestamp": (
                latest.created_at.isoformat()
                if latest is not None
                else None
            ),
        }

    # ------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------

    def save_baseline(self) -> Snapshot:
        """
        Save the current building as the baseline snapshot.
        """

        if self.snapshot_exists("baseline"):
            return self.overwrite_snapshot("baseline")

        return self.create_snapshot("baseline")

    def restore_baseline(self) -> Snapshot:
        """
        Restore the baseline snapshot.
        """

        return self.restore_snapshot("baseline")