from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Change:

    object_type: str

    object_name: str

    field: str

    before: Any

    after: Any


class DiffMixin:
    """
    Utilities for comparing two EnergyPlus models.
    """

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _idf_to_lookup(
        self,
        idf,
    ) -> dict:

        lookup = {}

        for object_type, objects in idf.idfobjects.items():

            table = {}

            for obj in objects:

                if hasattr(obj, "Name"):

                    table[obj.Name] = obj

            lookup[object_type] = table

        return lookup

    def _object_fields(
        self,
        obj,
    ) -> list[str]:

        fields = []

        for field in obj.fieldnames:

            if field == "key":
                continue

            fields.append(field)

        return fields

    # ------------------------------------------------------------
    # Object Diff
    # ------------------------------------------------------------

    def _compare_objects(
        self,
        before,
        after,
        object_type: str,
    ) -> list[Change]:

        changes: list[Change] = []

        for field in self._object_fields(before):

            before_value = getattr(
                before,
                field,
                None,
            )

            after_value = getattr(
                after,
                field,
                None,
            )

            if before_value != after_value:

                changes.append(
                    Change(
                        object_type=object_type,
                        object_name=before.Name,
                        field=field,
                        before=before_value,
                        after=after_value,
                    )
                )

        return changes

        # ------------------------------------------------------------
    # Model Diff
    # ------------------------------------------------------------

    def diff_models(
        self,
        before_idf,
        after_idf,
    ) -> list[Change]:
        """
        Compare two IDF models.

        Returns
        -------
        list[Change]
            List of detected changes.
        """

        before_lookup = self._idf_to_lookup(before_idf)
        after_lookup = self._idf_to_lookup(after_idf)

        changes: list[Change] = []

        object_types = set(before_lookup.keys()) | set(after_lookup.keys())

        for object_type in sorted(object_types):

            before_objects = before_lookup.get(object_type, {})
            after_objects = after_lookup.get(object_type, {})

            names = (
                set(before_objects.keys())
                | set(after_objects.keys())
            )

            for name in sorted(names):

                before = before_objects.get(name)
                after = after_objects.get(name)

                # Object created

                if before is None:

                    changes.append(
                        Change(
                            object_type=object_type,
                            object_name=name,
                            field="__created__",
                            before=None,
                            after="Created",
                        )
                    )

                    continue

                # Object deleted

                if after is None:

                    changes.append(
                        Change(
                            object_type=object_type,
                            object_name=name,
                            field="__deleted__",
                            before="Deleted",
                            after=None,
                        )
                    )

                    continue

                # Object modified

                changes.extend(
                    self._compare_objects(
                        before,
                        after,
                        object_type,
                    )
                )

        return changes

    # ------------------------------------------------------------
    # Snapshot Diff
    # ------------------------------------------------------------

    def diff_snapshots(
        self,
        before_snapshot: str,
        after_snapshot: str,
    ) -> list[Change]:
        """
        Compare two stored snapshots.
        """

        before = self.get_snapshot(before_snapshot)

        after = self.get_snapshot(after_snapshot)

        return self.diff_models(
            before.idf,
            after.idf,
        )

    # ------------------------------------------------------------
    # Current Model Diff
    # ------------------------------------------------------------

    def diff_current(
        self,
        snapshot_name: str,
    ) -> list[Change]:
        """
        Compare the current model against a snapshot.
        """

        snapshot = self.get_snapshot(snapshot_name)

        return self.diff_models(
            snapshot.idf,
            self.idf,
        )

        # ------------------------------------------------------------
    # Grouping
    # ------------------------------------------------------------

    def group_changes_by_object(
        self,
        changes: list[Change],
    ) -> dict[tuple[str, str], list[Change]]:
        """
        Group changes by (object type, object name).
        """

        grouped: dict[tuple[str, str], list[Change]] = {}

        for change in changes:

            key = (
                change.object_type,
                change.object_name,
            )

            grouped.setdefault(key, []).append(change)

        return grouped

    def group_changes_by_type(
        self,
        changes: list[Change],
    ) -> dict[str, list[Change]]:
        """
        Group changes by EnergyPlus object type.
        """

        grouped: dict[str, list[Change]] = {}

        for change in changes:

            grouped.setdefault(
                change.object_type,
                [],
            ).append(change)

        return grouped

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    def diff_summary(
        self,
        changes: list[Change],
    ) -> dict:
        """
        Return summary statistics for a diff.
        """

        grouped_objects = self.group_changes_by_object(changes)
        grouped_types = self.group_changes_by_type(changes)

        created = sum(
            change.field == "__created__"
            for change in changes
        )

        deleted = sum(
            change.field == "__deleted__"
            for change in changes
        )

        modified = len(changes) - created - deleted

        return {
            "total_changes": len(changes),
            "changed_objects": len(grouped_objects),
            "object_types": len(grouped_types),
            "created": created,
            "deleted": deleted,
            "modified_fields": modified,
            "types": {
                object_type: len(object_changes)
                for object_type, object_changes in grouped_types.items()
            },
        }

    # ------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------

    def print_diff(
        self,
        changes: list[Change],
    ) -> None:
        """
        Pretty-print a list of changes.
        """

        if not changes:
            print("No differences found.")
            return

        for change in changes:

            print(
                f"[{change.object_type}] "
                f"{change.object_name} :: "
                f"{change.field}"
            )

            print(
                f"    Before : {change.before}"
            )

            print(
                f"    After  : {change.after}"
            )

            print()