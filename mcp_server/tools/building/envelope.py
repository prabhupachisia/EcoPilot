from __future__ import annotations

from eppy.bunch_subclass import EpBunch

from .models import BuildingComponent


class EnvelopeMixin:
    """Mixin for managing EnergyPlus materials, constructions, and windows."""

    THICKNESS_FIELD = "Thickness"
    CONDUCTIVITY_FIELD = "Conductivity"
    CONSTRUCTION_FIELD = "Construction_Name"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_material(self, name: str) -> EpBunch:
        material = self.material(name)

        if material is None:
            raise ValueError(f"Material '{name}' not found.")

        return material

    def _require_construction(self, name: str) -> EpBunch:
        construction = self.construction(name)

        if construction is None:
            raise ValueError(f"Construction '{name}' not found.")

        return construction

    def _require_window(self, name: str) -> EpBunch:
        window = self.window(name)

        if window is None:
            raise ValueError(f"Window '{name}' not found.")

        return window

    # ------------------------------------------------------------------
    # Materials
    # ------------------------------------------------------------------

    def set_material_thickness(
        self,
        name: str,
        thickness: float,
        reason: str | None = None,
    ) -> None:
        """Update a material's thickness."""

        if thickness <= 0:
            raise ValueError("Thickness must be greater than zero.")

        material = self._require_material(name)

        previous = float(
            getattr(
                material,
                self.THICKNESS_FIELD,
            )
        )

        self.helpers.set_field(
            material,
            self.THICKNESS_FIELD,
            thickness,
        )

        self.helpers.record_change(
            component=BuildingComponent.ENVELOPE,
            target=name,
            parameter=self.THICKNESS_FIELD,
            previous_value=previous,
            new_value=thickness,
            reason=reason,
        )

    def set_material_conductivity(
        self,
        name: str,
        conductivity: float,
        reason: str | None = None,
    ) -> None:
        """Update a material's thermal conductivity."""

        if conductivity <= 0:
            raise ValueError(
                "Conductivity must be greater than zero."
            )

        material = self._require_material(name)

        previous = float(
            getattr(
                material,
                self.CONDUCTIVITY_FIELD,
            )
        )

        self.helpers.set_field(
            material,
            self.CONDUCTIVITY_FIELD,
            conductivity,
        )

        self.helpers.record_change(
            component=BuildingComponent.ENVELOPE,
            target=name,
            parameter=self.CONDUCTIVITY_FIELD,
            previous_value=previous,
            new_value=conductivity,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Constructions
    # ------------------------------------------------------------------

    def replace_construction_layer(
        self,
        construction_name: str,
        layer_number: int,
        material_name: str,
        reason: str | None = None,
    ) -> None:
        """Replace a material layer in a construction."""

        construction = self._require_construction(
            construction_name
        )

        self._require_material(material_name)

        field = f"Layer_{layer_number}"

        if not hasattr(construction, field):
            raise ValueError(
                f"Construction has no '{field}'."
            )

        previous = getattr(construction, field)

        self.helpers.set_field(
            construction,
            field,
            material_name,
        )

        self.helpers.record_change(
            component=BuildingComponent.ENVELOPE,
            target=construction_name,
            parameter=field,
            previous_value=previous,
            new_value=material_name,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Windows
    # ------------------------------------------------------------------

    def set_window_construction(
        self,
        window_name: str,
        construction_name: str,
        reason: str | None = None,
    ) -> None:
        """Assign a new construction to a window."""

        window = self._require_window(window_name)

        self._require_construction(construction_name)

        previous = getattr(
            window,
            self.CONSTRUCTION_FIELD,
        )

        self.helpers.set_field(
            window,
            self.CONSTRUCTION_FIELD,
            construction_name,
        )

        self.helpers.record_change(
            component=BuildingComponent.ENVELOPE,
            target=window_name,
            parameter=self.CONSTRUCTION_FIELD,
            previous_value=previous,
            new_value=construction_name,
            reason=reason,
        )