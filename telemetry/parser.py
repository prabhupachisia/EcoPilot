from pathlib import Path

from telemetry.extractor import BuildingStateExtractor
from telemetry.models import (
    BuildingMetadata,
    BuildingState,
    CarbonMetrics,
    CostMetrics,
    OptimizationMetrics,
)
from telemetry.reader import SQLiteReader


class TelemetryParser:

    def parse(
        self,
        sql_file: str | Path,
        metadata: BuildingMetadata,
        runtime_seconds: float,
    ) -> BuildingState:

        with SQLiteReader(sql_file) as reader:

            extractor = BuildingStateExtractor(reader)

            return BuildingState(
                metadata=metadata,
                simulation=extractor.extract_simulation(runtime_seconds),
                weather=extractor.extract_weather(),
                occupancy=extractor.extract_occupancy(),
                energy=extractor.extract_energy(),
                hvac=extractor.extract_hvac(),
                comfort=extractor.extract_comfort(),
                carbon=CarbonMetrics(),
                cost=CostMetrics(),
                optimization=OptimizationMetrics(),
            )