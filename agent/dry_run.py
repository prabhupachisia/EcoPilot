"""Synthetic dependencies for `python main.py --dry-run`.

Lets the whole closed loop - LangGraph orchestrator, all four agents,
safety supervisor, experience memory - run end to end on a machine with
neither EnergyPlus nor Ollama installed. Everything downstream of
build_dry_run_environment() is the same code that runs with real
dependencies; only the LLM and tool responses are faked.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from agent.llm import FakeLLMClient, LLMResponse, ToolCall
from agent.memory import ExperienceStore
from agent.safety import SafetySupervisor
from agent.tools import FakeToolExecutor
from mcp_server.tools.evaluation import evaluate_snapshot
from telemetry.models import (
    BuildingMetadata,
    BuildingState,
    CarbonMetrics,
    ComfortMetrics,
    CostMetrics,
    EnergyMetrics,
    HVACMetrics,
    OccupancyMetrics,
    OptimizationMetrics,
    OptimizationSnapshot,
    SimulationInfo,
    WeatherMetrics,
)


@dataclass(slots=True)
class DryRunActionResult:
    success: bool = True
    message: str = "Applied (dry run)."


@dataclass(slots=True)
class DryRunSimulationResult:
    sql_file: str = "energyplus/outputs/dry_run/eplusout.sql"
    runtime_seconds: float = 3.5


def _make_state(cycle: int) -> BuildingState:
    # Occupancy/energy improve slightly each cycle so a multi-cycle dry
    # run has something to show trending in the dashboard/report.
    occupancy = max(5.0, 20.0 - cycle * 2)
    energy = max(60.0, 100.0 - cycle * 4)

    return BuildingState(
        metadata=BuildingMetadata(
            building_name="EcoPilot Dry Run Building",
            location="Synthetic",
            floor_area=463.6,
            weather_file=Path("energyplus/weather/weather.epw"),
            idf_file=Path("energyplus/baseline/building.idf"),
        ),
        simulation=SimulationInfo(
            simulation_id=f"dry-run-{cycle}",
            timestamp=datetime.now(),
            runtime_seconds=3.5,
            success=True,
        ),
        weather=WeatherMetrics(outdoor_temperature=30.0 - cycle * 0.5),
        occupancy=OccupancyMetrics(average_occupancy=occupancy, peak_occupancy=int(occupancy * 2)),
        energy=EnergyMetrics(total_energy_kwh=energy, cooling_energy_kwh=energy * 0.4),
        hvac=HVACMetrics(cooling_load_kw=energy * 0.05),
        comfort=ComfortMetrics(average_indoor_temperature=24.0, pmv=0.2),
        carbon=CarbonMetrics(),
        cost=CostMetrics(peak_demand_kw=energy * 0.1),
        optimization=OptimizationMetrics(iteration=cycle),
    )


def build_dry_run_tools(max_cycles: int) -> FakeToolExecutor:
    tools = FakeToolExecutor()

    tools.queue(
        "get_carbon_intensity_profile",
        {0: 0.35, 6: 0.38, 12: 0.28, 14: 0.24, 18: 0.55, 19: 0.60},
    )
    tools.queue(
        "get_hvac_setpoints",
        {"cooling_setpoint_temperature": 23.9, "heating_setpoint_temperature": 21.0},
    )
    tools.queue("save_building", "energyplus/models/dry_run_cycle.idf")
    tools.queue("run_simulation_tool", DryRunSimulationResult())
    tools.queue("begin_transaction", None)
    tools.queue("commit_transaction", None)
    tools.queue("rollback_transaction", None)
    tools.queue("restore_snapshot", None)
    tools.queue(
        "apply_building_actions",
        lambda actions: [DryRunActionResult() for _ in actions],
    )

    cycle_counter = {"n": 0}

    def next_state(**_kwargs) -> BuildingState:
        cycle_counter["n"] += 1
        return _make_state(cycle_counter["n"])

    tools.queue("read_building_state_tool", next_state)
    tools.queue("evaluate_snapshot", lambda snapshot: evaluate_snapshot(snapshot))

    return tools


def build_dry_run_llm(max_cycles: int) -> FakeLLMClient:
    responses: list[LLMResponse] = []

    for cycle in range(1, max_cycles + 1):
        responses.append(
            LLMResponse(
                content=(
                    f"Cycle {cycle}: occupancy is trending down, raising the cooling "
                    "setpoint slightly to reduce cooling energy while staying within "
                    "the safety bounds."
                ),
                tool_calls=[
                    ToolCall(
                        name="set_hvac_setpoints",
                        arguments={"cooling_c": 24.0 + cycle * 0.3, "reason": "Lower occupancy"},
                    )
                ],
            )
        )
        responses.append(
            LLMResponse(content=f"Cycle {cycle}: energy use fell as occupancy declined.")
        )
        responses.append(
            LLMResponse(content=f"Cycle {cycle}: outcome tracked the prediction closely.")
        )

    return FakeLLMClient(responses=responses)


def build_dry_run_environment(
    max_cycles: int,
    memory_path: Path | None = None,
) -> tuple[FakeLLMClient, FakeToolExecutor, ExperienceStore, SafetySupervisor, BuildingState, BuildingMetadata]:
    llm = build_dry_run_llm(max_cycles)
    tools = build_dry_run_tools(max_cycles)
    memory = ExperienceStore(path=memory_path or Path("memory") / "dry_run_experiences.json")
    memory.clear()
    safety = SafetySupervisor()

    baseline_state = _make_state(0)
    metadata = baseline_state.metadata

    return llm, tools, memory, safety, baseline_state, metadata


__all__ = [
    "build_dry_run_environment",
    "build_dry_run_llm",
    "build_dry_run_tools",
]
