from __future__ import annotations

from datetime import datetime


class LifecycleMixin:
    """
    Tracks the lifecycle state of the building model.

    This includes whether the model has been modified,
    validated, saved, or requires further processing.
    """

    # ------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------

    def _initialize_lifecycle(self) -> None:

        now = datetime.utcnow()

        self._dirty = False

        self._loaded_at = now

        self._modified_at = now

        self._saved_at = None

        self._validated_at = None

        self._edit_count = 0

    # ------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------

    def _mark_dirty(self) -> None:
        """
        Mark the building as modified.
        """

        self._dirty = True

        self._modified_at = datetime.utcnow()

        self._edit_count += 1

    def _mark_clean(self) -> None:
        """
        Mark the building as synchronized with disk.
        """

        self._dirty = False

        self._saved_at = datetime.utcnow()

    def _mark_validated(self) -> None:
        """
        Record the last successful validation.
        """

        self._validated_at = datetime.utcnow()

    def touch(self) -> None:
        """
        Update the modification timestamp without
        increasing the edit counter.
        """

        self._modified_at = datetime.utcnow()
        # ------------------------------------------------------------
    # State Queries
    # ------------------------------------------------------------

    def is_dirty(self) -> bool:
        """
        Return True if the building has unsaved changes.
        """

        return self._dirty

    def edit_count(self) -> int:
        """
        Return the number of recorded edits.
        """

        return self._edit_count

    def loaded_at(self) -> datetime:
        """
        Return when the building was loaded.
        """

        return self._loaded_at

    def modified_at(self) -> datetime:
        """
        Return the last modification timestamp.
        """

        return self._modified_at

    def saved_at(self) -> datetime | None:
        """
        Return the last save timestamp.
        """

        return self._saved_at

    def validated_at(self) -> datetime | None:
        """
        Return the last validation timestamp.
        """

        return self._validated_at

    def validation_required(self) -> bool:
        """
        Return True if the building should be validated.
        """

        if self._validated_at is None:
            return True

        return self._modified_at > self._validated_at

    # ------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------

    def reset_lifecycle(self) -> None:
        """
        Reset lifecycle information while preserving the
        currently loaded building.
        """

        now = datetime.utcnow()

        self._dirty = False

        self._modified_at = now

        self._saved_at = None

        self._validated_at = None

        self._edit_count = 0
        # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    def lifecycle_summary(self) -> dict:
        """
        Return a summary of the current lifecycle state.
        """

        return {
            "dirty": self.is_dirty(),
            "loaded_at": self.loaded_at().isoformat(),
            "modified_at": self.modified_at().isoformat(),
            "saved_at": (
                self.saved_at().isoformat()
                if self.saved_at() is not None
                else None
            ),
            "validated_at": (
                self.validated_at().isoformat()
                if self.validated_at() is not None
                else None
            ),
            "validation_required": self.validation_required(),
            "edit_count": self.edit_count(),
        }

    def lifecycle_status(self) -> str:
        """
        Return a human-readable lifecycle status.
        """

        if self.is_dirty():
            return "Modified"

        if self.validation_required():
            return "Validation Required"

        return "Clean"

    # ------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------

    def mark_saved(self) -> None:
        """
        Mark the current model as saved.
        """

        self._mark_clean()

    def mark_validated(self) -> None:
        """
        Record a successful validation.
        """

        self._mark_validated()

    def mark_dirty(self) -> None:
        """
        Public wrapper for marking the model as modified.
        """

        self._mark_dirty()

    def mark_clean(self) -> None:
        """
        Public wrapper for marking the model as clean.
        """

        self._mark_clean()