"""EcoPilot Streamlit dashboard.

Reads the JSON logs/reports main.py writes (dashboard/data.py) rather than
holding a live connection to a running optimization loop -- Streamlit's
rerun model doesn't play well with a long-running LangGraph loop in the
same process. Every page degrades gracefully before any run has happened.

Run with: streamlit run dashboard/app.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from config.settings import MODELS_DIR
from dashboard.data import (
    build_reasoning_timeline,
    confidence_trend,
    estimate_carbon_reduction_kg,
    list_saved_cycle_idfs,
    load_audit_trail,
    load_decision_log,
    load_latest_report,
    load_reflection_log,
    safety_decision_counts,
)

# Categorical slot 1/2 (blue/orange) for before/after comparisons; status
# colors reserved for the safety-decision verdicts (never reused as a
# generic series color).
COLOR_BASELINE = "#2a78d6"
COLOR_OPTIMIZED = "#eb6834"
COLOR_GOOD = "#0ca30c"
COLOR_WARNING = "#fab219"
COLOR_CRITICAL = "#d03b3b"

PLOTLY_TEMPLATE = "plotly_white"

st.set_page_config(page_title="EcoPilot", page_icon="🌱", layout="wide")


def render_overview() -> None:
    st.header("Overview")

    report = load_latest_report()

    if report is None:
        st.info("No optimization run yet. Run `python main.py --dry-run` (or a real run) first.")
        return

    evaluation = report["evaluation"]
    energy = evaluation["energy"]
    comfort = evaluation["comfort"]
    carbon_kg = estimate_carbon_reduction_kg(
        energy["baseline_energy_kwh"], energy["optimized_energy_kwh"]
    )

    columns = st.columns(4)
    columns[0].metric(
        "Energy savings",
        f"{energy['savings_percent']:.1f}%",
        f"{energy['savings_kwh']:.1f} kWh",
    )
    columns[1].metric(
        "Carbon reduction",
        f"{carbon_kg:.1f} kg CO2" if carbon_kg is not None else "n/a",
    )
    columns[2].metric(
        "Comfort",
        "Improved" if comfort["comfort_improved"] else "Regressed",
        f"PMV {comfort['optimized_pmv']:.2f}" if comfort["optimized_pmv"] is not None else None,
    )
    columns[3].metric("Overall score", f"{evaluation['score']['overall_score']:.1f}/100")

    st.subheader("Baseline vs. optimized energy")

    figure = go.Figure(
        data=[
            go.Bar(
                x=["Baseline", "Optimized"],
                y=[energy["baseline_energy_kwh"], energy["optimized_energy_kwh"]],
                marker_color=[COLOR_BASELINE, COLOR_OPTIMIZED],
                text=[
                    f"{energy['baseline_energy_kwh']:.1f} kWh",
                    f"{energy['optimized_energy_kwh']:.1f} kWh",
                ],
                textposition="outside",
            )
        ]
    )
    figure.update_layout(
        template=PLOTLY_TEMPLATE,
        yaxis_title="Energy (kWh)",
        showlegend=False,
        height=350,
    )
    st.plotly_chart(figure, use_container_width=True)

    audit_trail = load_audit_trail()

    if audit_trail:
        setpoint_changes = [
            change
            for change in audit_trail["changes"]
            if change["component"] == "schedule" and "SetP-Sch" in change["target"]
        ]

        if setpoint_changes:
            st.subheader("Current HVAC setpoints")
            st.table(
                [
                    {
                        "Schedule": change["target"],
                        "Previous (°C)": change["previous_value"],
                        "Current (°C)": change["new_value"],
                        "Reason": change["reason"],
                    }
                    for change in setpoint_changes[-2:]
                ]
            )


def render_ai_reasoning() -> None:
    st.header("AI Reasoning / Timeline")

    decision_log = load_decision_log()
    reflection_log = load_reflection_log()

    if not decision_log:
        st.info("No optimization run yet.")
        return

    trend = confidence_trend(reflection_log)

    if trend:
        st.subheader("Confidence trend")
        cycles, confidences = zip(*trend)
        figure = go.Figure(
            data=[
                go.Scatter(
                    x=list(cycles),
                    y=list(confidences),
                    mode="lines+markers",
                    line=dict(color=COLOR_BASELINE, width=2),
                    marker=dict(size=9),
                )
            ]
        )
        figure.update_layout(
            template=PLOTLY_TEMPLATE,
            yaxis=dict(title="Confidence", range=[0, 1]),
            xaxis=dict(title="Cycle", dtick=1),
            showlegend=False,
            height=250,
        )
        st.plotly_chart(figure, use_container_width=True)

    timeline = build_reasoning_timeline(decision_log, reflection_log)

    for entry in reversed(timeline):
        title = f"Cycle {entry.cycle}"
        if entry.confidence is not None:
            title += f" — confidence {entry.confidence:.2f}"

        with st.expander(title, expanded=(entry.cycle == timeline[-1].cycle)):
            st.markdown(f"**Thought:** {entry.thought}")

            if entry.retrieved_memory:
                st.markdown("**Retrieved memory (nearest first):**")
                st.table(
                    [
                        {
                            "Past cycle": case["cycle"],
                            "Savings %": case["savings_percent"],
                            "Outcome": case["outcome"],
                            "Distance": round(case["distance"], 3),
                        }
                        for case in entry.retrieved_memory
                    ]
                )
            else:
                st.caption("No similar past cycles retrieved (first run or empty memory).")

            st.markdown(f"**Decision:** {entry.message}")

            if entry.narrative:
                st.markdown(f"**Reflection:** {entry.narrative}")

            if entry.should_rollback:
                st.warning("This cycle regressed enough to trigger an automatic rollback.")


def render_audit_trail() -> None:
    st.header("Audit Trail")

    audit_trail = load_audit_trail()

    if audit_trail is None:
        st.info(
            "No audit trail available yet -- this page needs a live run "
            "(`python main.py`, not --dry-run) since it reads the real "
            "building's change history."
        )
        return

    st.subheader("Change history")

    changes = audit_trail["changes"]

    if changes:
        st.dataframe(
            [
                {
                    "Time": change["timestamp"],
                    "Component": change["component"],
                    "Target": change["target"],
                    "Parameter": change["parameter"],
                    "Previous": change["previous_value"],
                    "New": change["new_value"],
                    "Reason": change["reason"],
                }
                for change in changes
            ],
            use_container_width=True,
        )
    else:
        st.caption("No changes recorded.")

    st.subheader("Snapshots")

    snapshots = audit_trail["snapshots"]

    if snapshots:
        st.table(snapshots)
    else:
        st.caption("No snapshots recorded.")

    st.subheader("Rollback to a saved cycle")
    st.caption(
        "Each cycle's modified IDF is saved to disk (energyplus/models/). "
        "Since this dashboard is a separate process from the run that "
        "produced them, 'rollback' here marks which saved file to resume "
        "from rather than mutating a live in-memory model."
    )

    saved_idfs = list_saved_cycle_idfs()

    if not saved_idfs:
        st.caption("No per-cycle IDF files found yet.")
        return

    selected = st.selectbox("Choose a cycle to roll back to", options=saved_idfs, format_func=lambda p: p.name)

    if st.button("Mark as active rollback target"):
        target = Path(MODELS_DIR) / "rollback_target.idf"
        shutil.copyfile(selected, target)
        st.success(
            f"Copied {selected.name} to {target}. Resume with: "
            f"`python main.py --idf {target}`"
        )


def render_reports() -> None:
    st.header("Reports / Evaluation")

    report = load_latest_report()

    if report is None:
        st.info("No optimization run yet.")
        return

    evaluation = report["evaluation"]

    st.subheader("Final evaluation")
    st.write(f"Recommendation: **{evaluation['recommendation'].upper()}**")

    score = evaluation["score"]
    st.table(
        [
            {"Dimension": "Energy", "Score": round(score["energy_score"], 1)},
            {"Dimension": "Comfort", "Score": round(score["comfort_score"], 1)},
            {"Dimension": "Carbon", "Score": round(score["carbon_score"], 1)},
            {"Dimension": "Peak demand", "Score": round(score["peak_score"], 1)},
            {"Dimension": "Overall", "Score": round(score["overall_score"], 1)},
        ]
    )

    st.subheader("Safety supervisor decisions")
    st.caption(
        "Every LLM-proposed setpoint is checked before it reaches EnergyPlus: "
        "accepted as-is, clipped to the safe range, or rejected outright."
    )

    decision_log = load_decision_log()
    counts = safety_decision_counts(decision_log)

    figure = go.Figure(
        data=[
            go.Bar(
                x=["Accepted", "Clipped", "Rejected"],
                y=[counts["accept"], counts["clipped"], counts["rejected"]],
                marker_color=[COLOR_GOOD, COLOR_WARNING, COLOR_CRITICAL],
            )
        ]
    )
    figure.update_layout(
        template=PLOTLY_TEMPLATE,
        yaxis_title="Count",
        showlegend=False,
        height=300,
    )
    st.plotly_chart(figure, use_container_width=True)

    st.subheader("Report files")
    st.caption(f"Latest: {report.get('cycle', '?')}")


PAGES = {
    "Overview": render_overview,
    "AI Reasoning": render_ai_reasoning,
    "Audit Trail": render_audit_trail,
    "Reports": render_reports,
}


def main() -> None:
    st.sidebar.title("🌱 EcoPilot")
    st.sidebar.caption("Closed-loop HVAC optimization")

    page = st.sidebar.radio("Page", list(PAGES.keys()))

    PAGES[page]()


main()
