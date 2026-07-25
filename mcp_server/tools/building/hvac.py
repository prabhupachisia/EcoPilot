from __future__ import annotations

from eppy.bunch_subclass import EpBunch

from .models import BuildingComponent


class HVACMixin:
    """
    HVAC manipulation utilities.

    Implemented for the EnergyPlus reference model:
        5ZoneAutoDXVAV.idf
    """

    # ------------------------------------------------------------------
    # Object Types
    # ------------------------------------------------------------------

    THERMOSTAT_OBJECT = "ZoneControl:Thermostat"
    FAN_OBJECT = "Fan:VariableVolume"
    COOLING_COIL_OBJECT = "Coil:Cooling:DX:TwoSpeed"
    HEATING_COIL_OBJECT = "Coil:Heating:Fuel"
    OA_CONTROLLER_OBJECT = "Controller:OutdoorAir"

    # ------------------------------------------------------------------
    # Internal lookup helpers
    # ------------------------------------------------------------------

    def _require_thermostat(self, name: str) -> EpBunch:
        thermostat = self.get_object(self.THERMOSTAT_OBJECT, name)

        if thermostat is None:
            raise ValueError(f"Thermostat '{name}' not found.")

        return thermostat

    def _require_fan(self, name: str) -> EpBunch:
        fan = self.get_object(self.FAN_OBJECT, name)

        if fan is None:
            raise ValueError(f"Fan '{name}' not found.")

        return fan

    def _require_cooling_coil(self, name: str) -> EpBunch:
        coil = self.get_object(self.COOLING_COIL_OBJECT, name)

        if coil is None:
            raise ValueError(f"Cooling coil '{name}' not found.")

        return coil

    def _require_heating_coil(self, name: str) -> EpBunch:
        coil = self.get_object(self.HEATING_COIL_OBJECT, name)

        if coil is None:
            raise ValueError(f"Heating coil '{name}' not found.")

        return coil

    def _require_outdoor_air_controller(self, name: str) -> EpBunch:
        controller = self.get_object(self.OA_CONTROLLER_OBJECT, name)

        if controller is None:
            raise ValueError(
                f"Outdoor air controller '{name}' not found."
            )

        return controller

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def thermostat_names(self) -> list[str]:
        """
        Return all thermostat names.
        """
        return self.object_names(self.THERMOSTAT_OBJECT)

    def fan_names(self) -> list[str]:
        """
        Return all VAV fan names.
        """
        return self.object_names(self.FAN_OBJECT)

    def cooling_coil_names(self) -> list[str]:
        """
        Return all DX cooling coils.
        """
        return self.object_names(self.COOLING_COIL_OBJECT)

    def heating_coil_names(self) -> list[str]:
        """
        Return all heating coils.
        """
        return self.object_names(self.HEATING_COIL_OBJECT)

    def outdoor_air_controller_names(self) -> list[str]:
        """
        Return all outdoor air controllers.
        """
        return self.object_names(self.OA_CONTROLLER_OBJECT)

    # ------------------------------------------------------------------
    # Thermostat Helpers
    # ------------------------------------------------------------------

    def get_heating_setpoint(self, thermostat_name: str) -> str:
        """
        Returns the heating setpoint object assigned to the thermostat.
        """

        thermostat = self._require_thermostat(thermostat_name)

        return getattr(
            thermostat,
            "Control_1_Name",
            "",
        )

    def get_cooling_setpoint(self, thermostat_name: str) -> str:
        """
        Returns the cooling setpoint object assigned to the thermostat.
        """

        thermostat = self._require_thermostat(thermostat_name)

        if hasattr(thermostat, "Control_2_Name"):
            return thermostat.Control_2_Name

        return getattr(
            thermostat,
            "Control_1_Name",
            "",
        )

    # ------------------------------------------------------------------
    # Thermostat Editing
    # ------------------------------------------------------------------

    def set_heating_setpoint(
        self,
        thermostat_name: str,
        setpoint_name: str,
        reason: str | None = None,
    ) -> None:
        """
        Assign a heating setpoint object.
        """

        thermostat = self._require_thermostat(thermostat_name)

        previous = getattr(
            thermostat,
            "Control_1_Name",
            "",
        )

        self.helpers.set_field(
            thermostat,
            "Control_1_Name",
            setpoint_name,
        )

        self.helpers.record_change(
            component=BuildingComponent.HVAC,
            object_type=self.THERMOSTAT_OBJECT,
            object_name=thermostat_name,
            field="Control_1_Name",
            old_value=previous,
            new_value=setpoint_name,
            reason=reason,
        )

        self._mark_dirty()

    def set_cooling_setpoint(
        self,
        thermostat_name: str,
        setpoint_name: str,
        reason: str | None = None,
    ) -> None:
        """
        Assign a cooling setpoint object.
        """

        thermostat = self._require_thermostat(thermostat_name)

        if not hasattr(thermostat, "Control_2_Name"):
            raise ValueError(
                "Cooling control does not exist for this thermostat."
            )

        previous = thermostat.Control_2_Name

        self.helpers.set_field(
            thermostat,
            "Control_2_Name",
            setpoint_name,
        )

        self.helpers.record_change(
            component=BuildingComponent.HVAC,
            object_type=self.THERMOSTAT_OBJECT,
            object_name=thermostat_name,
            field="Control_2_Name",
            old_value=previous,
            new_value=setpoint_name,
            reason=reason,
        )

        self._mark_dirty()

    def set_dual_setpoint(
        self,
        thermostat_name: str,
        heating_setpoint: str,
        cooling_setpoint: str,
        reason: str | None = None,
    ) -> None:
        """
        Assign both heating and cooling setpoint objects.
        """

        self.set_heating_setpoint(
            thermostat_name,
            heating_setpoint,
            reason,
        )

        self.set_cooling_setpoint(
            thermostat_name,
            cooling_setpoint,
            reason,
        )

    def set_thermostat_schedule(
        self,
        thermostat_name: str,
        heating_schedule: str,
        cooling_schedule: str,
        reason: str | None = None,
    ) -> None:
        """
        Convenience wrapper for assigning both schedules.
        """

        self.set_dual_setpoint(
            thermostat_name,
            heating_schedule,
            cooling_schedule,
            reason,
        )
        # ------------------------------------------------------------------
    # Fan Queries
    # ------------------------------------------------------------------

    def fan_efficiency(self, fan_name: str) -> float:
        """Return the total fan efficiency."""

        fan = self._require_fan(fan_name)
        return float(fan.Fan_Total_Efficiency)

    def fan_pressure_rise(self, fan_name: str) -> float:
        """Return the fan pressure rise (Pa)."""

        fan = self._require_fan(fan_name)
        return float(fan.Pressure_Rise)

    def fan_max_flow_rate(self, fan_name: str) -> float:
        """Return the maximum air flow rate (m3/s)."""

        fan = self._require_fan(fan_name)
        return float(fan.Maximum_Flow_Rate)

    # ------------------------------------------------------------------
    # Fan Editing
    # ------------------------------------------------------------------

    def set_fan_efficiency(
        self,
        fan_name: str,
        efficiency: float,
        reason: str | None = None,
    ) -> None:
        """
        Set the fan total efficiency.

        Parameters
        ----------
        efficiency :
            Value between 0 and 1.
        """

        if not 0 < efficiency <= 1:
            raise ValueError(
                "Fan efficiency must be between 0 and 1."
            )

        fan = self._require_fan(fan_name)

        previous = float(fan.Fan_Total_Efficiency)

        self.helpers.set_field(
            fan,
            "Fan_Total_Efficiency",
            efficiency,
        )

        self.helpers.record_change(
            component=BuildingComponent.HVAC,
            object_type=self.FAN_OBJECT,
            object_name=fan_name,
            field="Fan_Total_Efficiency",
            old_value=previous,
            new_value=efficiency,
            reason=reason,
        )

        self._mark_dirty()

    def set_fan_pressure_rise(
        self,
        fan_name: str,
        pressure_rise: float,
        reason: str | None = None,
    ) -> None:
        """
        Set fan pressure rise (Pa).
        """

        if pressure_rise <= 0:
            raise ValueError(
                "Pressure rise must be positive."
            )

        fan = self._require_fan(fan_name)

        previous = float(fan.Pressure_Rise)

        self.helpers.set_field(
            fan,
            "Pressure_Rise",
            pressure_rise,
        )

        self.helpers.record_change(
            component=BuildingComponent.HVAC,
            object_type=self.FAN_OBJECT,
            object_name=fan_name,
            field="Pressure_Rise",
            old_value=previous,
            new_value=pressure_rise,
            reason=reason,
        )

        self._mark_dirty()

    def set_fan_max_flow_rate(
        self,
        fan_name: str,
        flow_rate: float,
        reason: str | None = None,
    ) -> None:
        """
        Set the maximum fan flow rate.
        """

        if flow_rate <= 0:
            raise ValueError(
                "Maximum flow rate must be positive."
            )

        fan = self._require_fan(fan_name)

        previous = float(fan.Maximum_Flow_Rate)

        self.helpers.set_field(
            fan,
            "Maximum_Flow_Rate",
            flow_rate,
        )

        self.helpers.record_change(
            component=BuildingComponent.HVAC,
            object_type=self.FAN_OBJECT,
            object_name=fan_name,
            field="Maximum_Flow_Rate",
            old_value=previous,
            new_value=flow_rate,
            reason=reason,
        )

        self._mark_dirty()

    def scale_fan_flow_rate(
        self,
        fan_name: str,
        factor: float,
        reason: str | None = None,
    ) -> None:
        """
        Scale the maximum fan flow rate.

        Example
        -------
        factor=1.10 increases flow by 10%.
        """

        if factor <= 0:
            raise ValueError(
                "Scale factor must be positive."
            )

        current = self.fan_max_flow_rate(fan_name)

        self.set_fan_max_flow_rate(
            fan_name=fan_name,
            flow_rate=current * factor,
            reason=reason,
        )

    def increase_fan_flow_rate(
        self,
        fan_name: str,
        percent: float,
        reason: str | None = None,
    ) -> None:
        """
        Increase fan flow by a percentage.
        """

        self.scale_fan_flow_rate(
            fan_name,
            1 + percent / 100,
            reason,
        )

    def decrease_fan_flow_rate(
        self,
        fan_name: str,
        percent: float,
        reason: str | None = None,
    ) -> None:
        """
        Decrease fan flow by a percentage.
        """

        self.scale_fan_flow_rate(
            fan_name,
            1 - percent / 100,
            reason,
        )

    def fan_summary(self, fan_name: str) -> dict:
        """
        Return a summary of a fan.
        """

        fan = self._require_fan(fan_name)

        return {
            "name": fan.Name,
            "availability_schedule": fan.Availability_Schedule_Name,
            "efficiency": float(fan.Fan_Total_Efficiency),
            "pressure_rise": float(fan.Pressure_Rise),
            "maximum_flow_rate": float(fan.Maximum_Flow_Rate),
            "motor_efficiency": float(fan.Motor_Efficiency),
            "motor_in_airstream_fraction": float(
                fan.Motor_In_Airstream_Fraction
            ),
        }
        # ------------------------------------------------------------------
    # Cooling Coil Queries
    # ------------------------------------------------------------------

    def cooling_cop(self, coil_name: str) -> float:
        """
        Return the high-speed cooling COP.
        """

        coil = self._require_cooling_coil(coil_name)
        return float(coil.High_Speed_Gross_Rated_Cooling_COP)

    def cooling_capacity(self, coil_name: str):
        """
        Return the high-speed rated cooling capacity.
        """

        coil = self._require_cooling_coil(coil_name)
        return coil.High_Speed_Gross_Rated_Total_Cooling_Capacity

    def condenser_type(self, coil_name: str) -> str:
        """
        Return condenser type.
        """

        coil = self._require_cooling_coil(coil_name)
        return coil.Condenser_Type

    # ------------------------------------------------------------------
    # Cooling Coil Editing
    # ------------------------------------------------------------------

    def set_cooling_cop(
        self,
        coil_name: str,
        cop: float,
        reason: str | None = None,
    ) -> None:
        """
        Set cooling COP.
        """

        if cop <= 0:
            raise ValueError("COP must be positive.")

        coil = self._require_cooling_coil(coil_name)

        previous = float(
            coil.High_Speed_Gross_Rated_Cooling_COP
        )

        self.helpers.set_field(
            coil,
            "High_Speed_Gross_Rated_Cooling_COP",
            cop,
        )

        self.helpers.record_change(
            component=BuildingComponent.HVAC,
            object_type=self.COOLING_COIL_OBJECT,
            object_name=coil_name,
            field="High_Speed_Gross_Rated_Cooling_COP",
            old_value=previous,
            new_value=cop,
            reason=reason,
        )

        self._mark_dirty()

    def set_condenser_type(
        self,
        coil_name: str,
        condenser_type: str,
        reason: str | None = None,
    ) -> None:
        """
        Change condenser type.
        """

        allowed = {
            "AirCooled",
            "EvaporativelyCooled",
        }

        if condenser_type not in allowed:
            raise ValueError(
                f"Expected one of {allowed}"
            )

        coil = self._require_cooling_coil(coil_name)

        previous = coil.Condenser_Type

        self.helpers.set_field(
            coil,
            "Condenser_Type",
            condenser_type,
        )

        self.helpers.record_change(
            component=BuildingComponent.HVAC,
            object_type=self.COOLING_COIL_OBJECT,
            object_name=coil_name,
            field="Condenser_Type",
            old_value=previous,
            new_value=condenser_type,
            reason=reason,
        )

        self._mark_dirty()

    def scale_cooling_capacity(
        self,
        coil_name: str,
        factor: float,
        reason: str | None = None,
    ) -> None:
        """
        Scale cooling capacity.
        """

        if factor <= 0:
            raise ValueError(
                "Scale factor must be positive."
            )

        coil = self._require_cooling_coil(coil_name)

        current = coil.High_Speed_Gross_Rated_Total_Cooling_Capacity

        if str(current).lower() == "autosize":
            raise ValueError(
                "Cooling capacity is autosized."
            )

        new_value = float(current) * factor

        self.helpers.set_field(
            coil,
            "High_Speed_Gross_Rated_Total_Cooling_Capacity",
            new_value,
        )

        self.helpers.record_change(
            component=BuildingComponent.HVAC,
            object_type=self.COOLING_COIL_OBJECT,
            object_name=coil_name,
            field="High_Speed_Gross_Rated_Total_Cooling_Capacity",
            old_value=current,
            new_value=new_value,
            reason=reason,
        )

        self._mark_dirty()

    # ------------------------------------------------------------------
    # Heating Coil Queries
    # ------------------------------------------------------------------

    def heating_efficiency(
        self,
        coil_name: str,
    ) -> float:
        """
        Return burner efficiency.
        """

        coil = self._require_heating_coil(coil_name)

        return float(coil.Burner_Efficiency)

    def heating_capacity(
        self,
        coil_name: str,
    ):
        """
        Return nominal heating capacity.
        """

        coil = self._require_heating_coil(coil_name)

        return coil.Nominal_Capacity

    # ------------------------------------------------------------------
    # Heating Coil Editing
    # ------------------------------------------------------------------

    def set_heating_efficiency(
        self,
        coil_name: str,
        efficiency: float,
        reason: str | None = None,
    ) -> None:
        """
        Set burner efficiency.
        """

        if not 0 < efficiency <= 1:
            raise ValueError(
                "Efficiency must be between 0 and 1."
            )

        coil = self._require_heating_coil(coil_name)

        previous = float(coil.Burner_Efficiency)

        self.helpers.set_field(
            coil,
            "Burner_Efficiency",
            efficiency,
        )

        self.helpers.record_change(
            component=BuildingComponent.HVAC,
            object_type=self.HEATING_COIL_OBJECT,
            object_name=coil_name,
            field="Burner_Efficiency",
            old_value=previous,
            new_value=efficiency,
            reason=reason,
        )

        self._mark_dirty()

    def scale_heating_capacity(
        self,
        coil_name: str,
        factor: float,
        reason: str | None = None,
    ) -> None:
        """
        Scale nominal heating capacity.
        """

        if factor <= 0:
            raise ValueError(
                "Scale factor must be positive."
            )

        coil = self._require_heating_coil(coil_name)

        current = coil.Nominal_Capacity

        if str(current).lower() == "autosize":
            raise ValueError(
                "Heating capacity is autosized."
            )

        new_capacity = float(current) * factor

        self.helpers.set_field(
            coil,
            "Nominal_Capacity",
            new_capacity,
        )

        self.helpers.record_change(
            component=BuildingComponent.HVAC,
            object_type=self.HEATING_COIL_OBJECT,
            object_name=coil_name,
            field="Nominal_Capacity",
            old_value=current,
            new_value=new_capacity,
            reason=reason,
        )

        self._mark_dirty()

    # ------------------------------------------------------------------
    # Coil Summary
    # ------------------------------------------------------------------

    def cooling_coil_summary(
        self,
        coil_name: str,
    ) -> dict:

        coil = self._require_cooling_coil(coil_name)

        return {
            "name": coil.Name,
            "cop": float(
                coil.High_Speed_Gross_Rated_Cooling_COP
            ),
            "capacity": coil.High_Speed_Gross_Rated_Total_Cooling_Capacity,
            "condenser_type": coil.Condenser_Type,
        }

    def heating_coil_summary(
        self,
        coil_name: str,
    ) -> dict:

        coil = self._require_heating_coil(coil_name)

        return {
            "name": coil.Name,
            "fuel_type": coil.Fuel_Type,
            "efficiency": float(
                coil.Burner_Efficiency
            ),
            "capacity": coil.Nominal_Capacity,
        }
    
    # ------------------------------------------------------------------
    # Air Loop Queries
    # ------------------------------------------------------------------

    def total_fans(self) -> int:
        """Return the total number of fans."""

        return len(self.fan_names())

    def total_cooling_coils(self) -> int:
        """Return the total number of cooling coils."""

        return len(self.cooling_coil_names())

    def total_heating_coils(self) -> int:
        """Return the total number of heating coils."""

        return len(self.heating_coil_names())

    def total_airloops(self) -> int:
        """
        Return the number of AirLoopHVAC objects.
        """

        return len(self.idf.idfobjects["AIRLOOPHVAC"])

    # ------------------------------------------------------------------
    # HVAC Summary
    # ------------------------------------------------------------------

    def hvac_summary(self) -> dict:
        """
        Return a high-level summary of the HVAC system.
        """

        return {
            "thermostats": self.thermostat_names(),
            "fans": self.fan_names(),
            "cooling_coils": self.cooling_coil_names(),
            "heating_coils": self.heating_coil_names(),
            "outdoor_air_controllers": (
                self.outdoor_air_controller_names()
            ),
            "fan_count": self.total_fans(),
            "cooling_coil_count": (
                self.total_cooling_coils()
            ),
            "heating_coil_count": (
                self.total_heating_coils()
            ),
            "airloop_count": self.total_airloops(),
        }