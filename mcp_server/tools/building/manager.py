from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from eppy.modeleditor import IDF

from .diff import DiffMixin
from .envelope import EnvelopeMixin
from .equipment import EquipmentMixin
from .helpers import BuildingHelpers
from .hvac import HVACMixin
from .lifecycle import LifecycleMixin
from .lighting import LightingMixin
from .models import (
    ActionResult,
    ActionType,
    BuildingAction,
    BuildingComponent,
    BuildingMetadata,
    BuildingSummary,
    ChangeRecord,
    ValidationResult,
)
from .occupancy import OccupancyMixin
from .queries import QueryMixin
from .schedule import ScheduleMixin
from .snapshots import SnapshotMixin
from .transactions import TransactionMixin
from .validation import ValidationMixin
from .ventilation import VentilationMixin


class BuildingManager(
    QueryMixin,
    EnvelopeMixin,
    HVACMixin,
    VentilationMixin,
    LightingMixin,
    EquipmentMixin,
    OccupancyMixin,
    ScheduleMixin,
    SnapshotMixin,
    TransactionMixin,
    ValidationMixin,
    LifecycleMixin,
    DiffMixin,
):
    """The single public interface for an EnergyPlus building model.

    The manager owns model lifecycle and translates generic ``BuildingAction``
    requests into the existing, component-specific mixin operations.  Mixins
    remain the sole implementation of IDF manipulation logic.
    """

    def __init__(
        self,
        idd_path: Path,
        idf_path: Path | None = None,
        weather_file: Path | None = None,
    ) -> None:
        self.idd_path = Path(idd_path)
        self.idf_path = Path(idf_path) if idf_path is not None else None
        self.weather_file = Path(weather_file) if weather_file is not None else None

        self.idf: IDF | None = None
        self.metadata: BuildingMetadata | None = None
        self.is_loaded = False
        self.history: list[ChangeRecord] = []

        # Shared services must exist before any mixin method is invoked.
        self.helpers = BuildingHelpers(self)
        self._initialize_lifecycle()
        self._initialize_snapshots()
        self._initialize_transactions()

    # ------------------------------------------------------------------
    # Lifecycle and persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load the configured IDF and initialise its runtime metadata."""
        if self.idf_path is None:
            raise ValueError("An IDF path is required to load a building.")
        if not self.idd_path.is_file():
            raise FileNotFoundError(f"IDD file not found: {self.idd_path}")
        if not self.idf_path.is_file():
            raise FileNotFoundError(f"IDF file not found: {self.idf_path}")

        IDF.setiddname(str(self.idd_path))
        self.idf = IDF(str(self.idf_path))
        self.is_loaded = True
        self.helpers.invalidate_cache()
        self._initialize_lifecycle()
        self.metadata = BuildingMetadata(
            building_name=self.building().Name,
            idf_path=self.idf_path,
            weather_file=self.weather_file or Path(),
        )

    def save(self, path: Path | None = None) -> None:
        """Save the loaded IDF and mark it clean only after a successful write."""
        self.helpers.require_loaded()
        destination = Path(path) if path is not None else self.idf_path
        if destination is None:
            raise ValueError("A destination path is required to save a building.")

        self.idf.saveas(str(destination))
        self.idf_path = destination
        if self.metadata is not None:
            self.metadata.idf_path = destination
        self._mark_clean()

    def reload(self) -> None:
        """Discard in-memory edits and reload the configured IDF from disk."""
        if self.idf_path is None:
            raise ValueError("An IDF path is required to reload a building.")
        self.close()
        self.load()

    def close(self) -> None:
        """Release the loaded model while retaining configuration and history."""
        self.idf = None
        self.metadata = None
        self.is_loaded = False
        self.helpers.invalidate_cache()
        self.clear_snapshots()
        if self.transaction_active():
            self.discard()

    # ------------------------------------------------------------------
    # Mixin delegates with manager-level lifecycle handling
    # ------------------------------------------------------------------

    def summary(self) -> BuildingSummary:
        return QueryMixin.summary(self)

    def validate(self) -> ValidationResult:
        """Run the validation mixin and expose its stable public dataclass."""
        report = ValidationMixin.validate(self)
        result = ValidationResult(
            valid=report["valid"],
            errors=list(report["errors"]),
            warnings=list(report["warnings"]),
        )
        if result.valid:
            self._mark_validated()
        return result

    # ------------------------------------------------------------------
    # Generic action dispatch
    # ------------------------------------------------------------------

    def apply_action(self, action: BuildingAction) -> ActionResult:
        """Apply one action through the appropriate existing mixin method."""
        try:
            handler = self._action_handler(action)
            previous = self._action_value(action)
            handler()
            current = self._action_value(action)
            return ActionResult(True, action, previous, current, "Action applied.")
        except (KeyError, TypeError, ValueError, RuntimeError) as error:
            return ActionResult(False, action, message=str(error))

    def apply_actions(self, actions: list[BuildingAction]) -> list[ActionResult]:
        """Apply actions in order, returning one result for every request."""
        return [self.apply_action(action) for action in actions]

    def _action_handler(self, action: BuildingAction) -> Callable[[], None]:
        """Build a no-argument call to the mixin method for ``action``."""
        component = self._dispatch_component(action.component)
        parameter = self._canonical_parameter(component, action.parameter)
        key = (component, action.action, parameter)
        handlers: dict[tuple[BuildingComponent, ActionType, str], Callable[[], None]] = {
            (BuildingComponent.PEOPLE, ActionType.SET, "people"): lambda: self.set_people(action.target, float(action.value), action.reason),
            (BuildingComponent.PEOPLE, ActionType.SCALE, "people"): lambda: self.scale_people(action.target, float(action.value), action.reason),
            (BuildingComponent.PEOPLE, ActionType.SET, "schedule"): lambda: self.set_people_schedule(action.target, str(action.value), action.reason),
            (BuildingComponent.LIGHTING, ActionType.SET, "power"): lambda: self.set_lighting_power(action.target, float(action.value), action.reason),
            (BuildingComponent.LIGHTING, ActionType.SCALE, "power"): lambda: self.scale_lighting_power(action.target, float(action.value), action.reason),
            (BuildingComponent.LIGHTING, ActionType.SET, "schedule"): lambda: self.set_lighting_schedule(action.target, str(action.value), action.reason),
            (BuildingComponent.EQUIPMENT, ActionType.SET, "power"): lambda: self.set_equipment_power(action.target, float(action.value), action.reason),
            (BuildingComponent.EQUIPMENT, ActionType.SCALE, "power"): lambda: self.scale_equipment_power(action.target, float(action.value), action.reason),
            (BuildingComponent.EQUIPMENT, ActionType.SET, "schedule"): lambda: self.set_equipment_schedule(action.target, str(action.value), action.reason),
            (BuildingComponent.SCHEDULE, ActionType.RENAME, "name"): lambda: self.rename_schedule(action.target, str(action.value), action.reason),
            (BuildingComponent.SCHEDULE, ActionType.SET, "type"): lambda: self.set_schedule_type(action.target, str(action.value), action.reason),
            (BuildingComponent.MATERIAL, ActionType.SET, "thickness"): lambda: self.set_material_thickness(action.target, float(action.value), action.reason),
            (BuildingComponent.MATERIAL, ActionType.SET, "conductivity"): lambda: self.set_material_conductivity(action.target, float(action.value), action.reason),
            (BuildingComponent.CONSTRUCTION, ActionType.REPLACE, "layer"): lambda: self.replace_construction_layer(action.target, int(action.value[0]), str(action.value[1]), action.reason),
            (BuildingComponent.WINDOW, ActionType.SET, "construction"): lambda: self.set_window_construction(action.target, str(action.value), action.reason),
            (BuildingComponent.HVAC, ActionType.SET, "fan_efficiency"): lambda: self.set_fan_efficiency(action.target, float(action.value), action.reason),
            (BuildingComponent.HVAC, ActionType.SET, "fan_pressure_rise"): lambda: self.set_fan_pressure_rise(action.target, float(action.value), action.reason),
            (BuildingComponent.HVAC, ActionType.SET, "fan_max_flow_rate"): lambda: self.set_fan_max_flow_rate(action.target, float(action.value), action.reason),
            (BuildingComponent.HVAC, ActionType.SCALE, "fan_flow_rate"): lambda: self.scale_fan_flow_rate(action.target, float(action.value), action.reason),
            (BuildingComponent.HVAC, ActionType.SET, "cooling_cop"): lambda: self.set_cooling_cop(action.target, float(action.value), action.reason),
            (BuildingComponent.HVAC, ActionType.SET, "heating_efficiency"): lambda: self.set_heating_efficiency(action.target, float(action.value), action.reason),
            (BuildingComponent.INFILTRATION, ActionType.SET, "minimum_outdoor_air"): lambda: self.set_minimum_outdoor_air(action.target, float(action.value), action.reason),
            (BuildingComponent.INFILTRATION, ActionType.SET, "maximum_outdoor_air"): lambda: self.set_maximum_outdoor_air(action.target, float(action.value), action.reason),
            (BuildingComponent.INFILTRATION, ActionType.SCALE, "outdoor_air"): lambda: self.scale_outdoor_air(action.target, float(action.value), action.reason),
        }
        try:
            return handlers[key]
        except KeyError as error:
            raise ValueError(
                f"Unsupported action: {action.component.value}/{action.action.value}/{action.parameter}."
            ) from error

    def _action_value(self, action: BuildingAction) -> Any:
        """Return the value represented by an action when a getter exists."""
        getters: dict[tuple[BuildingComponent, str], Callable[[], Any]] = {
            (BuildingComponent.PEOPLE, "people"): lambda: float(getattr(self._require_people(action.target), self.PEOPLE_FIELD)),
            (BuildingComponent.LIGHTING, "power"): lambda: float(getattr(self._require_light(action.target), self.POWER_FIELD)),
            (BuildingComponent.EQUIPMENT, "power"): lambda: float(getattr(self._require_equipment(action.target), self.POWER_FIELD)),
            (BuildingComponent.HVAC, "fan_efficiency"): lambda: self.fan_efficiency(action.target),
            (BuildingComponent.HVAC, "fan_pressure_rise"): lambda: self.fan_pressure_rise(action.target),
            (BuildingComponent.HVAC, "fan_max_flow_rate"): lambda: self.fan_max_flow_rate(action.target),
            (BuildingComponent.INFILTRATION, "minimum_outdoor_air"): lambda: self.minimum_outdoor_air(action.target),
            (BuildingComponent.INFILTRATION, "maximum_outdoor_air"): lambda: self.maximum_outdoor_air(action.target),
        }
        component = self._dispatch_component(action.component)
        parameter = self._canonical_parameter(component, action.parameter)
        getter = getters.get((component, parameter))
        return getter() if getter is not None else None

    @staticmethod
    def _dispatch_component(component: BuildingComponent) -> BuildingComponent:
        """Map the legacy infiltration action category to ventilation edits."""
        if component is BuildingComponent.VENTILATION:
            return BuildingComponent.INFILTRATION
        return component

    @staticmethod
    def _canonical_parameter(
        component: BuildingComponent,
        parameter: str,
    ) -> str:
        """Accept IDF field names as well as concise MCP parameter names."""
        name = parameter.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            (BuildingComponent.PEOPLE, "number_of_people"): "people",
            (BuildingComponent.PEOPLE, "count"): "people",
            (BuildingComponent.LIGHTING, "lighting_level"): "power",
            (BuildingComponent.LIGHTING, "lighting_power"): "power",
            (BuildingComponent.EQUIPMENT, "design_level"): "power",
            (BuildingComponent.EQUIPMENT, "equipment_power"): "power",
            (BuildingComponent.SCHEDULE, "new_name"): "name",
            (BuildingComponent.SCHEDULE, "schedule_type_limits_name"): "type",
            (BuildingComponent.HVAC, "efficiency"): "fan_efficiency",
            (BuildingComponent.HVAC, "pressure_rise"): "fan_pressure_rise",
            (BuildingComponent.HVAC, "maximum_flow_rate"): "fan_max_flow_rate",
            (BuildingComponent.INFILTRATION, "minimum_outdoor_air_flow_rate"): "minimum_outdoor_air",
            (BuildingComponent.INFILTRATION, "maximum_outdoor_air_flow_rate"): "maximum_outdoor_air",
        }
        return aliases.get((component, name), name)

    # The HVAC/ventilation/validation mixins use these generic query helpers.
    def get_object(self, object_type: str, name: str) -> Any | None:
        return self.helpers.find_object(object_type, name)

    def object_names(self, object_type: str) -> list[str]:
        return [obj.Name for obj in self.helpers.find_objects(object_type) if hasattr(obj, "Name")]
