from __future__ import annotations

from dataclasses import dataclass

from telemetry.models import BuildingState, OptimizationSnapshot
from enum import Enum

from fastmcp import FastMCP

from mcp_server.dependencies import DependencyProvider


DEFAULT_ENERGY_WEIGHT = 0.45
DEFAULT_COMFORT_WEIGHT = 0.35
DEFAULT_CARBON_WEIGHT = 0.15
DEFAULT_PEAK_WEIGHT = 0.05

DEFAULT_PASSING_SCORE = 70.0



class EvaluationRecommendation(str, Enum):
    ACCEPT = "accept"
    REVIEW = "review"
    REJECT = "reject"


@dataclass(slots=True)
class EnergyComparison:
    baseline_energy_kwh: float
    optimized_energy_kwh: float
    savings_kwh: float
    savings_percent: float


@dataclass(slots=True)
class ComfortComparison:
    baseline_pmv: float | None
    optimized_pmv: float | None
    baseline_ppd: float | None
    optimized_ppd: float | None
    baseline_discomfort_hours: float | None
    optimized_discomfort_hours: float | None
    comfort_improved: bool


@dataclass(slots=True)
class CarbonComparison:
    baseline_emissions_kg: float
    optimized_emissions_kg: float
    reduction_kg: float
    reduction_percent: float


@dataclass(slots=True)
class PeakDemandComparison:
    baseline_peak_kw: float
    optimized_peak_kw: float
    reduction_kw: float
    reduction_percent: float


@dataclass(slots=True)
class EvaluationScore:
    energy_score: float
    comfort_score: float
    carbon_score: float
    peak_score: float
    overall_score: float


@dataclass(slots=True)
class EvaluationResult:
    energy: EnergyComparison
    comfort: ComfortComparison
    carbon: CarbonComparison
    peak: PeakDemandComparison
    score: EvaluationScore
    recommendation: EvaluationRecommendation
    passed: bool


def _safe(value: float | None) -> float:
    return 0.0 if value is None else float(value)


def _difference(
    baseline: float,
    optimized: float,
) -> float:
    return baseline - optimized


def _percentage(
    baseline: float,
    optimized: float,
) -> float:
    if baseline <= 0:
        return 0.0

    return ((baseline - optimized) / baseline) * 100.0


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(minimum, min(value, maximum))


def _pmv_score(pmv: float | None) -> float:
    if pmv is None:
        return 50.0

    return _clamp(100.0 - abs(pmv) * 100.0)


def _ppd_score(ppd: float | None) -> float:
    if ppd is None:
        return 50.0

    return _clamp(100.0 - ppd)


def _comfort_score(state: BuildingState) -> float:
    pmv = _pmv_score(state.comfort.pmv)
    ppd = _ppd_score(state.comfort.ppd)

    discomfort = _safe(state.comfort.discomfort_hours)
    discomfort_penalty = min(discomfort * 2.0, 50.0)

    return _clamp(
        (pmv * 0.5)
        + (ppd * 0.3)
        + ((100.0 - discomfort_penalty) * 0.2)
    )


def _energy_score(
    baseline: float,
    optimized: float,
) -> float:
    return _clamp(50.0 + (_percentage(baseline, optimized) * 5.0))


def _carbon_score(
    baseline: float,
    optimized: float,
) -> float:
    return _clamp(50.0 + (_percentage(baseline, optimized) * 5.0))


def _peak_score(
    baseline: float,
    optimized: float,
) -> float:
    return _clamp(50.0 + (_percentage(baseline, optimized) * 5.0))


def _validate_snapshot(
    snapshot: OptimizationSnapshot,
) -> None:
    if snapshot.previous is None:
        raise ValueError("Baseline BuildingState is missing.")

    if snapshot.current is None:
        raise ValueError("Optimized BuildingState is missing.")

def compare_energy(
    snapshot: OptimizationSnapshot,
) -> EnergyComparison:
    _validate_snapshot(snapshot)

    baseline = _safe(snapshot.previous.energy.total_energy_kwh)
    optimized = _safe(snapshot.current.energy.total_energy_kwh)

    return EnergyComparison(
        baseline_energy_kwh=baseline,
        optimized_energy_kwh=optimized,
        savings_kwh=_difference(baseline, optimized),
        savings_percent=_percentage(baseline, optimized),
    )


def compare_comfort(
    snapshot: OptimizationSnapshot,
) -> ComfortComparison:
    _validate_snapshot(snapshot)

    baseline = snapshot.previous.comfort
    optimized = snapshot.current.comfort

    baseline_discomfort = _safe(baseline.discomfort_hours)
    optimized_discomfort = _safe(optimized.discomfort_hours)

    comfort_improved = (
        optimized_discomfort <= baseline_discomfort
    )

    return ComfortComparison(
        baseline_pmv=baseline.pmv,
        optimized_pmv=optimized.pmv,
        baseline_ppd=baseline.ppd,
        optimized_ppd=optimized.ppd,
        baseline_discomfort_hours=baseline.discomfort_hours,
        optimized_discomfort_hours=optimized.discomfort_hours,
        comfort_improved=comfort_improved,
    )


def compare_carbon(
    snapshot: OptimizationSnapshot,
) -> CarbonComparison:
    _validate_snapshot(snapshot)

    baseline = _safe(snapshot.previous.carbon.emissions_kg_co2)
    optimized = _safe(snapshot.current.carbon.emissions_kg_co2)

    return CarbonComparison(
        baseline_emissions_kg=baseline,
        optimized_emissions_kg=optimized,
        reduction_kg=_difference(baseline, optimized),
        reduction_percent=_percentage(baseline, optimized),
    )


def compare_peak_demand(
    snapshot: OptimizationSnapshot,
) -> PeakDemandComparison:
    _validate_snapshot(snapshot)

    baseline = _safe(snapshot.previous.cost.peak_demand_kw)
    optimized = _safe(snapshot.current.cost.peak_demand_kw)

    return PeakDemandComparison(
        baseline_peak_kw=baseline,
        optimized_peak_kw=optimized,
        reduction_kw=_difference(baseline, optimized),
        reduction_percent=_percentage(baseline, optimized),
    )


def generate_score(
    snapshot: OptimizationSnapshot,
) -> EvaluationScore:
    _validate_snapshot(snapshot)

    energy = compare_energy(snapshot)
    carbon = compare_carbon(snapshot)
    peak = compare_peak_demand(snapshot)

    energy_score = _energy_score(
        energy.baseline_energy_kwh,
        energy.optimized_energy_kwh,
    )

    comfort_score = _comfort_score(snapshot.current)

    carbon_score = _carbon_score(
        carbon.baseline_emissions_kg,
        carbon.optimized_emissions_kg,
    )

    peak_score = _peak_score(
        peak.baseline_peak_kw,
        peak.optimized_peak_kw,
    )

    overall_score = (
        energy_score * DEFAULT_ENERGY_WEIGHT
        + comfort_score * DEFAULT_COMFORT_WEIGHT
        + carbon_score * DEFAULT_CARBON_WEIGHT
        + peak_score * DEFAULT_PEAK_WEIGHT
    )

    return EvaluationScore(
        energy_score=energy_score,
        comfort_score=comfort_score,
        carbon_score=carbon_score,
        peak_score=peak_score,
        overall_score=round(overall_score, 2),
    )

def generate_recommendation(
    score: EvaluationScore,
) -> EvaluationRecommendation:
    if score.overall_score >= DEFAULT_PASSING_SCORE:
        return EvaluationRecommendation.ACCEPT

    if score.overall_score >= DEFAULT_PASSING_SCORE * 0.7:
        return EvaluationRecommendation.REVIEW

    return EvaluationRecommendation.REJECT


def evaluate_snapshot(
    snapshot: OptimizationSnapshot,
) -> EvaluationResult:
    _validate_snapshot(snapshot)

    energy = compare_energy(snapshot)
    comfort = compare_comfort(snapshot)
    carbon = compare_carbon(snapshot)
    peak = compare_peak_demand(snapshot)

    score = generate_score(snapshot)

    recommendation = generate_recommendation(score)

    return EvaluationResult(
        energy=energy,
        comfort=comfort,
        carbon=carbon,
        peak=peak,
        score=score,
        recommendation=recommendation,
        passed=score.overall_score >= DEFAULT_PASSING_SCORE,
    )


def recommendation_value(recommendation: EvaluationRecommendation | str) -> str:
    """Normalize a recommendation to its plain string value.

    A tool result that's crossed the real MCP wire (as opposed to a
    same-process call) doesn't always come back with its
    EvaluationRecommendation field rehydrated as an Enum -- fastmcp's
    client-side reconstruction of a returned dataclass can leave it as the
    plain string it was serialized to. Safe to call on either.
    """

    if isinstance(recommendation, EvaluationRecommendation):
        return recommendation.value

    return str(recommendation)


def summarize_evaluation(
    result: EvaluationResult,
) -> str:
    return (
        f"Energy savings: {result.energy.savings_percent:.2f}% | "
        f"Carbon reduction: {result.carbon.reduction_percent:.2f}% | "
        f"Peak demand reduction: {result.peak.reduction_percent:.2f}% | "
        f"Overall score: {result.score.overall_score:.2f}/100 | "
        f"Recommendation: {recommendation_value(result.recommendation).upper()}"
    )


def register_evaluation_tools(
    server: FastMCP,
    dependencies: DependencyProvider,
) -> None:
    """
    Register evaluation tools with the MCP server.
    """

    @server.tool(
        name="evaluate_snapshot",
        description="Evaluate an optimization snapshot and generate a performance report.",
    )
    def evaluate_snapshot_tool(
        snapshot: OptimizationSnapshot,
    ) -> EvaluationResult:
        return evaluate_snapshot(snapshot)

    @server.tool(
        name="generate_evaluation_score",
        description="Generate only the evaluation score for an optimization snapshot.",
    )
    def generate_score_tool(
        snapshot: OptimizationSnapshot,
    ) -> EvaluationScore:
        return generate_score(snapshot)

    @server.tool(
        name="summarize_evaluation",
        description="Generate a human-readable summary of an evaluation result.",
    )
    def summarize_evaluation_tool(
        result: EvaluationResult,
    ) -> str:
        return summarize_evaluation(result)

__all__ = [
    "EnergyComparison",
    "ComfortComparison",
    "CarbonComparison",
    "PeakDemandComparison",
    "EvaluationScore",
    "EvaluationResult",
    "EvaluationRecommendation",
    "compare_energy",
    "compare_comfort",
    "compare_carbon",
    "compare_peak_demand",
    "generate_score",
    "generate_recommendation",
    "evaluate_snapshot",
    "summarize_evaluation",
    "recommendation_value",
    "register_evaluation_tools"
]
