from __future__ import annotations

from eppy.bunch_subclass import EpBunch

from .models import BuildingComponent


class VentilationMixin:
    """
    Ventilation manipulation utilities.

    Implemented for the EnergyPlus reference model:
        5ZoneAutoDXVAV.idf
    """

    # ------------------------------------------------------------------
    # Object Types
    # ------------------------------------------------------------------

    OA_CONTROLLER_OBJECT = "Controller:OutdoorAir"
    OA_SYSTEM_OBJECT = "AirLoopHVAC:OutdoorAirSystem"
    OA_MIXER_OBJECT = "OutdoorAir:Mixer"
    ERV_OBJECT = "HeatExchanger:AirToAir:SensibleAndLatent"

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _require_outdoor_air_controller(
        self,
        name: str,
    ) -> EpBunch:

        controller = self.get_object(
            self.OA_CONTROLLER_OBJECT,
            name,
        )

        if controller is None:
            raise ValueError(
                f"Outdoor air controller '{name}' not found."
            )

        return controller

    def _require_outdoor_air_system(
        self,
        name: str,
    ) -> EpBunch:

        system = self.get_object(
            self.OA_SYSTEM_OBJECT,
            name,
        )

        if system is None:
            raise ValueError(
                f"Outdoor air system '{name}' not found."
            )

        return system

    def _require_heat_recovery(
        self,
        name: str,
    ) -> EpBunch:

        exchanger = self.get_object(
            self.ERV_OBJECT,
            name,
        )

        if exchanger is None:
            raise ValueError(
                f"Heat exchanger '{name}' not found."
            )

        return exchanger

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def outdoor_air_controller_names(
        self,
    ) -> list[str]:
        """
        Return all outdoor air controllers.
        """

        return self.object_names(
            self.OA_CONTROLLER_OBJECT
        )

    def outdoor_air_system_names(
        self,
    ) -> list[str]:
        """
        Return all outdoor air systems.
        """

        return self.object_names(
            self.OA_SYSTEM_OBJECT
        )

    def heat_recovery_names(
        self,
    ) -> list[str]:
        """
        Return all heat recovery units.
        """

        return self.object_names(
            self.ERV_OBJECT
        )

    # ------------------------------------------------------------------
    # Outdoor Air Queries
    # ------------------------------------------------------------------

    def minimum_outdoor_air(
        self,
        controller_name: str,
    ):
        """
        Return minimum outdoor air flow rate.
        """

        controller = self._require_outdoor_air_controller(
            controller_name
        )

        return controller.Minimum_Outdoor_Air_Flow_Rate

    def maximum_outdoor_air(
        self,
        controller_name: str,
    ):
        """
        Return maximum outdoor air flow rate.
        """

        controller = self._require_outdoor_air_controller(
            controller_name
        )

        return controller.Maximum_Outdoor_Air_Flow_Rate
        # ------------------------------------------------------------------
    # Outdoor Air Editing
    # ------------------------------------------------------------------

    def set_minimum_outdoor_air(
        self,
        controller_name: str,
        flow_rate: float,
        reason: str | None = None,
    ) -> None:
        """
        Set the minimum outdoor air flow rate (m3/s).
        """

        if flow_rate < 0:
            raise ValueError(
                "Minimum outdoor air flow rate cannot be negative."
            )

        controller = self._require_outdoor_air_controller(
            controller_name
        )

        previous = controller.Minimum_Outdoor_Air_Flow_Rate

        self.helpers.set_field(
            controller,
            "Minimum_Outdoor_Air_Flow_Rate",
            flow_rate,
        )

        self.helpers.record_change(
            component=BuildingComponent.VENTILATION,
            object_type=self.OA_CONTROLLER_OBJECT,
            object_name=controller_name,
            field="Minimum_Outdoor_Air_Flow_Rate",
            old_value=previous,
            new_value=flow_rate,
            reason=reason,
        )

        self._mark_dirty()

    def set_maximum_outdoor_air(
        self,
        controller_name: str,
        flow_rate: float,
        reason: str | None = None,
    ) -> None:
        """
        Set the maximum outdoor air flow rate (m3/s).
        """

        if flow_rate <= 0:
            raise ValueError(
                "Maximum outdoor air flow rate must be positive."
            )

        controller = self._require_outdoor_air_controller(
            controller_name
        )

        previous = controller.Maximum_Outdoor_Air_Flow_Rate

        self.helpers.set_field(
            controller,
            "Maximum_Outdoor_Air_Flow_Rate",
            flow_rate,
        )

        self.helpers.record_change(
            component=BuildingComponent.VENTILATION,
            object_type=self.OA_CONTROLLER_OBJECT,
            object_name=controller_name,
            field="Maximum_Outdoor_Air_Flow_Rate",
            old_value=previous,
            new_value=flow_rate,
            reason=reason,
        )

        self._mark_dirty()

    def scale_outdoor_air(
        self,
        controller_name: str,
        factor: float,
        reason: str | None = None,
    ) -> None:
        """
        Scale both the minimum and maximum outdoor air flow rates.
        """

        if factor <= 0:
            raise ValueError(
                "Scale factor must be positive."
            )

        controller = self._require_outdoor_air_controller(
            controller_name
        )

        minimum = controller.Minimum_Outdoor_Air_Flow_Rate
        maximum = controller.Maximum_Outdoor_Air_Flow_Rate

        if str(minimum).lower() != "autosize":
            self.helpers.set_field(
                controller,
                "Minimum_Outdoor_Air_Flow_Rate",
                float(minimum) * factor,
            )

        if str(maximum).lower() != "autosize":
            self.helpers.set_field(
                controller,
                "Maximum_Outdoor_Air_Flow_Rate",
                float(maximum) * factor,
            )

        self.helpers.record_change(
            component=BuildingComponent.VENTILATION,
            object_type=self.OA_CONTROLLER_OBJECT,
            object_name=controller_name,
            field="OutdoorAirFlowRates",
            old_value=(minimum, maximum),
            new_value=(
                controller.Minimum_Outdoor_Air_Flow_Rate,
                controller.Maximum_Outdoor_Air_Flow_Rate,
            ),
            reason=reason,
        )

        self._mark_dirty()

    def increase_outdoor_air(
        self,
        controller_name: str,
        percent: float,
        reason: str | None = None,
    ) -> None:
        """
        Increase outdoor air flow by a percentage.
        """

        self.scale_outdoor_air(
            controller_name,
            1 + percent / 100,
            reason,
        )

    def decrease_outdoor_air(
        self,
        controller_name: str,
        percent: float,
        reason: str | None = None,
    ) -> None:
        """
        Decrease outdoor air flow by a percentage.
        """

        self.scale_outdoor_air(
            controller_name,
            1 - percent / 100,
            reason,
        )

        # ------------------------------------------------------------------
    # Economizer Control
    # ------------------------------------------------------------------

    def economizer_control_type(
        self,
        controller_name: str,
    ) -> str:
        """
        Return the economizer control type.
        """

        controller = self._require_outdoor_air_controller(
            controller_name
        )

        return controller.Economizer_Control_Type

    def set_economizer_control(
        self,
        controller_name: str,
        control_type: str,
        reason: str | None = None,
    ) -> None:
        """
        Set the economizer control strategy.

        Allowed values include:
            - NoEconomizer
            - FixedDryBulb
            - FixedEnthalpy
            - DifferentialDryBulb
            - DifferentialEnthalpy
            - DifferentialDryBulbAndEnthalpy
            - ElectronicEnthalpy
        """

        allowed = {
            "NoEconomizer",
            "FixedDryBulb",
            "FixedEnthalpy",
            "DifferentialDryBulb",
            "DifferentialEnthalpy",
            "DifferentialDryBulbAndEnthalpy",
            "ElectronicEnthalpy",
        }

        if control_type not in allowed:
            raise ValueError(
                f"Economizer type must be one of {allowed}."
            )

        controller = self._require_outdoor_air_controller(
            controller_name
        )

        previous = controller.Economizer_Control_Type

        self.helpers.set_field(
            controller,
            "Economizer_Control_Type",
            control_type,
        )

        self.helpers.record_change(
            component=BuildingComponent.VENTILATION,
            object_type=self.OA_CONTROLLER_OBJECT,
            object_name=controller_name,
            field="Economizer_Control_Type",
            old_value=previous,
            new_value=control_type,
            reason=reason,
        )

        self._mark_dirty()

    # ------------------------------------------------------------------
    # Demand Controlled Ventilation
    # ------------------------------------------------------------------

    def enable_demand_control_ventilation(
        self,
        controller_name: str,
        reason: str | None = None,
    ) -> None:
        """
        Enable Demand Controlled Ventilation (DCV).
        """

        controller = self._require_outdoor_air_controller(
            controller_name
        )

        previous = controller.Demand_Controlled_Ventilation_Type

        self.helpers.set_field(
            controller,
            "Demand_Controlled_Ventilation_Type",
            "OccupancySchedule"
        )

        self.helpers.record_change(
            component=BuildingComponent.VENTILATION,
            object_type=self.OA_CONTROLLER_OBJECT,
            object_name=controller_name,
            field="Demand_Controlled_Ventilation_Type",
            old_value=previous,
            new_value="OccupancySchedule",
            reason=reason,
        )

        self._mark_dirty()

    def disable_demand_control_ventilation(
        self,
        controller_name: str,
        reason: str | None = None,
    ) -> None:
        """
        Disable Demand Controlled Ventilation.
        """

        controller = self._require_outdoor_air_controller(
            controller_name
        )

        previous = controller.Demand_Controlled_Ventilation_Type

        self.helpers.set_field(
            controller,
            "Demand_Controlled_Ventilation_Type",
            "None"
        )

        self.helpers.record_change(
            component=BuildingComponent.VENTILATION,
            object_type=self.OA_CONTROLLER_OBJECT,
            object_name=controller_name,
            field="Demand_Controlled_Ventilation_Type",
            old_value=previous,
            new_value="None",
            reason=reason,
        )

        self._mark_dirty()

    # ------------------------------------------------------------------
    # Heat Recovery
    # ------------------------------------------------------------------

    def heat_recovery_effectiveness(
        self,
        exchanger_name: str,
    ) -> float:
        """
        Return sensible effectiveness at 100% airflow.
        """

        exchanger = self._require_heat_recovery(
            exchanger_name
        )

        return float(
            exchanger.Sensible_Effectiveness_at_100_Heating_Air_Flow
        )

    def set_heat_recovery_effectiveness(
        self,
        exchanger_name: str,
        effectiveness: float,
        reason: str | None = None,
    ) -> None:
        """
        Set sensible heat recovery effectiveness.

        Value should be between 0 and 1.
        """

        if not 0 <= effectiveness <= 1:
            raise ValueError(
                "Heat recovery effectiveness must be between 0 and 1."
            )

        exchanger = self._require_heat_recovery(
            exchanger_name
        )

        previous = float(
            exchanger.Sensible_Effectiveness_at_100_Heating_Air_Flow
        )

        self.helpers.set_field(
            exchanger,
            "Sensible_Effectiveness_at_100_Heating_Air_Flow",
            effectiveness,
        )

        self.helpers.record_change(
            component=BuildingComponent.VENTILATION,
            object_type=self.ERV_OBJECT,
            object_name=exchanger_name,
            field="Sensible_Effectiveness_at_100_Heating_Air_Flow",
            old_value=previous,
            new_value=effectiveness,
            reason=reason,
        )

        self._mark_dirty()

        # ------------------------------------------------------------------
    # Outdoor Air System Queries
    # ------------------------------------------------------------------

    def outdoor_air_system_summary(
        self,
        system_name: str,
    ) -> dict:
        """
        Return information about an OutdoorAirSystem.
        """

        system = self._require_outdoor_air_system(
            system_name
        )

        return {
            "name": system.Name,
            "controller_list": (
                system.Controller_List_Name
            ),
            "equipment_list": (
                system.Outdoor_Air_Equipment_List_Name
            ),
        }

    # ------------------------------------------------------------------
    # Counts
    # ------------------------------------------------------------------

    def total_outdoor_air_controllers(
        self,
    ) -> int:
        """
        Return the number of outdoor air controllers.
        """

        return len(
            self.outdoor_air_controller_names()
        )

    def total_outdoor_air_systems(
        self,
    ) -> int:
        """
        Return the number of outdoor air systems.
        """

        return len(
            self.outdoor_air_system_names()
        )

    def total_heat_recovery_units(
        self,
    ) -> int:
        """
        Return the number of heat recovery units.
        """

        return len(
            self.heat_recovery_names()
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def ventilation_summary(
        self,
    ) -> dict:
        """
        Return a high-level summary of the ventilation system.
        """

        controllers = (
            self.outdoor_air_controller_names()
        )

        systems = (
            self.outdoor_air_system_names()
        )

        heat_recovery = (
            self.heat_recovery_names()
        )

        return {
            "outdoor_air_controllers": controllers,
            "outdoor_air_systems": systems,
            "heat_recovery_units": heat_recovery,
            "controller_count": len(
                controllers
            ),
            "system_count": len(
                systems
            ),
            "heat_recovery_count": len(
                heat_recovery
            ),
        }

    # ------------------------------------------------------------------
    # Convenience Helpers
    # ------------------------------------------------------------------

    def has_heat_recovery(self) -> bool:
        """
        Return True if at least one heat recovery
        unit exists.
        """

        return (
            self.total_heat_recovery_units() > 0
        )

    def has_economizer(
        self,
        controller_name: str,
    ) -> bool:
        """
        Return True if an economizer is enabled.
        """

        controller = (
            self._require_outdoor_air_controller(
                controller_name
            )
        )

        return (
            controller.Economizer_Control_Type
            != "NoEconomizer"
        )

    def demand_controlled_ventilation_enabled(
        self,
        controller_name: str,
    ) -> bool:
        """
        Return whether DCV is enabled.
        """

        controller = (
            self._require_outdoor_air_controller(
                controller_name
            )
        )

        return (
            controller.Demand_Controlled_Ventilation_Type
            != "None"
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def ventilation_diagnostics(
        self,
    ) -> dict:
        """
        Return useful diagnostics for the
        ventilation subsystem.
        """

        return {
            "controllers": (
                self.total_outdoor_air_controllers()
            ),
            "systems": (
                self.total_outdoor_air_systems()
            ),
            "heat_recovery": (
                self.total_heat_recovery_units()
            ),
            "has_heat_recovery": (
                self.has_heat_recovery()
            ),
        }