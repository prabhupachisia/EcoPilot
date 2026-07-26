from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from eppy.bunch_subclass import EpBunch

from .models import ChangeRecord


class BuildingHelpers:
    def __init__(self, manager) -> None:
        self.manager = manager

        self._zone_cache: dict[str, EpBunch] = {}
        self._schedule_cache: dict[str, EpBunch] = {}
        self._material_cache: dict[str, EpBunch] = {}
        self._construction_cache: dict[str, EpBunch] = {}

    def require_loaded(self) -> None:
        if not self.manager.is_loaded or self.manager.idf is None:
            raise RuntimeError("No building model has been loaded.")

    def mark_dirty(self) -> None:
        self.manager._mark_dirty()

    def clear_dirty(self) -> None:
        self.manager._mark_clean()

    def invalidate_cache(self) -> None:
        self._zone_cache.clear()
        self._schedule_cache.clear()
        self._material_cache.clear()
        self._construction_cache.clear()

    def find_object(
        self,
        object_type: str,
        name: str,
    ) -> EpBunch | None:
        self.require_loaded()

        objects = self.manager.idf.idfobjects.get(object_type.upper(), [])

        for obj in objects:
            if getattr(obj, "Name", None) == name:
                return obj

        return None

    def find_objects(self, object_type: str) -> list[EpBunch]:
        self.require_loaded()
        return list(self.manager.idf.idfobjects.get(object_type.upper(), []))

    def object_exists(
        self,
        object_type: str,
        name: str,
    ) -> bool:
        return self.find_object(object_type, name) is not None

    def set_field(
        self,
        obj: EpBunch,
        field: str,
        value: Any,
    ) -> None:
        setattr(obj, field, value)
        self.mark_dirty()

    def get_field(
        self,
        obj: EpBunch,
        field: str,
        default: Any = None,
    ) -> Any:
        return getattr(obj, field, default)

    def rename_object(
        self,
        obj: EpBunch,
        new_name: str,
    ) -> None:
        obj.Name = new_name
        self.mark_dirty()

    def delete_object(
        self,
        object_type: str,
        obj: EpBunch,
    ) -> None:
        self.manager.idf.removeidfobject(obj)
        self.mark_dirty()

    def duplicate_object(self, obj: EpBunch) -> EpBunch:
        new_obj = deepcopy(obj)
        self.manager.idf.copyidfobject(new_obj)
        self.mark_dirty()
        return new_obj

    def iter_objects(self, object_type: str):
        yield from self.find_objects(object_type)

    def record_change(
        self,
        component,
        target: str | None = None,
        parameter: str | None = None,
        previous_value: Any = None,
        new_value: Any = None,
        reason: str | None = None,
        **legacy: Any,
    ) -> None:
        """Record either the current or legacy mixin change argument shape."""
        target = target or legacy.pop("object_name", None)
        parameter = parameter or legacy.pop("field", None)
        previous_value = legacy.pop("old_value", previous_value)
        new_value = legacy.pop("new_value", new_value)
        # Older HVAC/ventilation mixins provide this as extra context.  The
        # public ChangeRecord does not expose an object type, so it is safely
        # retained by the mixin call contract but not duplicated in the model.
        legacy.pop("object_type", None)
        if legacy:
            raise TypeError(f"Unexpected change fields: {', '.join(legacy)}")
        if target is None or parameter is None:
            raise ValueError("Change records require a target and parameter.")
        change = ChangeRecord(
            timestamp=datetime.now(),
            component=component,
            target=target,
            parameter=parameter,
            previous_value=previous_value,
            new_value=new_value,
            reason=reason,
        )

        self.manager.history.append(change)
