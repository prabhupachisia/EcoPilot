from __future__ import annotations

from datetime import datetime

from telemetry.models import (
    ComfortMetrics,
    EnergyMetrics,
    HVACMetrics,
    OccupancyMetrics,
    SimulationInfo,
    WeatherMetrics,
)
from telemetry.reader import SQLiteReader


class BuildingStateExtractor:
    """Extract telemetry metrics from an EnergyPlus SQLite database."""

    def __init__(self, reader: SQLiteReader):
        self.reader = reader

    @staticmethod
    def _joules_to_kwh(value: float | None) -> float | None:
        if value is None:
            return None

        return value / 3_600_000

    def _get_metric(
        self,
        name: str,
        aggregate: str = "AVG",
        frequency: str | None = None,
    ) -> float | None:
        query = f"""
        SELECT {aggregate}(rd.Value) AS value
        FROM ReportData rd
        JOIN ReportDataDictionary rdd
            ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        WHERE rdd.Name = ?
        """

        parameters: list[str] = [name]

        if frequency is not None:
            query += " AND rdd.ReportingFrequency = ?"
            parameters.append(frequency)

        row = self.reader.fetchone(query, tuple(parameters))

        if row is None:
            return None

        return row["value"]

    def extract_simulation(
        self,
        runtime_seconds: float,
    ) -> SimulationInfo:
        row = self.reader.fetchone(
            """
            SELECT
                SimulationIndex,
                TimeStamp,
                CompletedSuccessfully
            FROM Simulations
            LIMIT 1;
            """
        )

        if row is None:
            raise ValueError("Simulation information not found.")

        return SimulationInfo(
            simulation_id=str(row["SimulationIndex"]),
            timestamp=datetime.strptime(
                row["TimeStamp"].strip(),
                "YMD=%Y.%m.%d %H:%M",
            ),
            runtime_seconds=runtime_seconds,
            success=row["CompletedSuccessfully"] == "TRUE",
        )

    def extract_weather(self) -> WeatherMetrics:
        return WeatherMetrics(
            outdoor_temperature=self._get_metric(
                "Site Outdoor Air Drybulb Temperature"
            ),
            outdoor_humidity=None,
            wind_speed=None,
            solar_radiation=None,
        )

    def extract_occupancy(self) -> OccupancyMetrics:
        average = self._get_metric(
            "People Occupant Count",
            aggregate="AVG",
        )

        peak = self._get_metric(
            "People Occupant Count",
            aggregate="MAX",
        )

        return OccupancyMetrics(
            average_occupancy=average,
            peak_occupancy=int(peak) if peak is not None else None,
            occupied_hours=None,
        )

    def extract_energy(self) -> EnergyMetrics:
        return EnergyMetrics(
            total_energy_kwh=self._joules_to_kwh(
                self._get_metric(
                    "Electricity:Facility",
                    aggregate="SUM",
                    frequency="Run Period",
                )
            ),
            heating_energy_kwh=self._joules_to_kwh(
                self._get_metric(
                    "Heating:NaturalGas",
                    aggregate="SUM",
                    frequency="Run Period",
                )
            ),
            cooling_energy_kwh=self._joules_to_kwh(
                self._get_metric(
                    "Cooling:Electricity",
                    aggregate="SUM",
                    frequency="Run Period",
                )
            ),
            lighting_energy_kwh=self._joules_to_kwh(
                self._get_metric(
                    "InteriorLights:Electricity",
                    aggregate="SUM",
                    frequency="Run Period",
                )
            ),
            equipment_energy_kwh=self._joules_to_kwh(
                self._get_metric(
                    "InteriorEquipment:Electricity",
                    aggregate="SUM",
                    frequency="Run Period",
                )
            ),
            fan_energy_kwh=self._joules_to_kwh(
                self._get_metric(
                    "Fans:Electricity",
                    aggregate="SUM",
                    frequency="Run Period",
                )
            ),
        )

    def extract_hvac(self) -> HVACMetrics:
        heating = self._get_metric(
            "Zone Air System Sensible Heating Rate"
        )

        cooling = self._get_metric(
            "Zone Air System Sensible Cooling Rate"
        )

        return HVACMetrics(
            heating_load_kw=heating / 1000 if heating is not None else None,
            cooling_load_kw=cooling / 1000 if cooling is not None else None,
            heating_cop=None,
            cooling_cop=None,
            hvac_efficiency=None,
        )

    def extract_comfort(self) -> ComfortMetrics:
        return ComfortMetrics(
            average_indoor_temperature=self._get_metric(
                "Zone Air Temperature"
            ),
            average_relative_humidity=None,
            pmv=None,
            ppd=None,
            discomfort_hours=None,
        )

    def extract_peak_demand(self) -> float | None:
        """Return the peak hourly electricity demand (kW).

        Each hourly meter reading is energy (J) consumed during that hour,
        so converting to kWh gives the average kW for that hour - taking
        the MAX across all hours gives the peak demand.
        """

        peak_joules = self._get_metric(
            "Electricity:Facility",
            aggregate="MAX",
            frequency="Hourly",
        )

        return self._joules_to_kwh(peak_joules)

    def extract_hourly_energy(
        self,
        name: str = "Electricity:Facility",
        frequency: str = "Hourly",
    ) -> dict[int, float]:
        """Return {hour_of_day: kWh} for an hourly-frequency meter/variable.

        Used to weight energy use against an hourly grid carbon-intensity
        profile (see ``mcp_server/tools/carbon.py``) instead of only a
        single run-period total.
        """

        query = """
        SELECT t.Hour AS hour, rd.Value AS value
        FROM ReportData rd
        JOIN ReportDataDictionary rdd
            ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        JOIN Time t
            ON rd.TimeIndex = t.TimeIndex
        WHERE rdd.Name = ?
        AND rdd.ReportingFrequency = ?
        """

        rows = self.reader.fetchall(query, (name, frequency))

        return {
            int(row["hour"]): self._joules_to_kwh(row["value"]) or 0.0
            for row in rows
        }