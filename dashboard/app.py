"""EcoPilot Streamlit dashboard.

Reads whatever main.py last wrote to logs/ and reports/ (see
dashboard/data.py) for its read-only pages, and can also drive a real
simulation or the full closed loop itself (Simulation Runner /
Closed-Loop Runner) -- meant to be the one place you need during a demo,
no CLI or code required.

Run with: streamlit run dashboard/app.py
"""

from __future__ import annotations

import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# `streamlit run` puts this file's own directory on sys.path, not the
# project root, so plain "config.settings"/"dashboard.data" imports fail
# unless we add the root ourselves first.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import plotly.graph_objects as go
import requests
import streamlit as st

from agent.dry_run import build_dry_run_environment
from agent.environment import build_live_environment
from agent.orchestrator import build_cycle_graph, run_optimization_loop
from agent.run_logs import write_audit_trail, write_decision_and_reflection_logs
from config.settings import (
    BASELINE_IDF,
    ENERGYPLUS_EXE,
    MODELS_DIR,
    OLLAMA_BASE_URL,
    OUTPUT_DIR,
    UPLOADED_MODELS_DIR,
    UPLOADED_WEATHER_DIR,
    WEATHER_FILE,
)
from dashboard.data import (
    build_reasoning_timeline,
    confidence_trend,
    estimate_carbon_reduction_kg,
    estimate_cost_savings,
    extract_zone_temperatures,
    list_epw_presets,
    list_idf_presets,
    load_audit_trail,
    load_decision_log,
    load_latest_report,
    load_reflection_log,
    safety_decision_counts,
    save_uploaded_file,
)
from energyplus.runner import EnergyPlusRunner
from mcp_server.tools.reports import generate_report
from telemetry.models import BuildingMetadata
from telemetry.parser import TelemetryParser

# Categorical slot 1/2 (blue/orange) for before/after comparisons; status
# colors reserved for the safety-decision verdicts (never reused as a
# generic series color).
COLOR_BASELINE = "#2a78d6"
COLOR_OPTIMIZED = "#eb6834"
COLOR_GOOD = "#0ca30c"
COLOR_WARNING = "#fab219"
COLOR_CRITICAL = "#d03b3b"

PLOTLY_TEMPLATE = "plotly_white"

AGENT_AVATARS = {
    "Planner": "🧠",
    "Safety Supervisor": "🛡️",
    "Controller": "⚙️",
    "Analyst": "📊",
    "Reflection": "🔄",
}

st.set_page_config(page_title="EcoPilot", page_icon="🌱", layout="wide")

st.markdown(
    """
    <style>
    div.block-container { padding-top: 2rem; }
    section[data-testid="stSidebar"] h1 { margin-bottom: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=15, show_spinner=False)
def _ollama_reachable(base_url: str) -> bool:
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=1.5)
        return response.ok
    except requests.RequestException:
        return False


def _active_idf() -> Path:
    return Path(st.session_state.get("idf_path", BASELINE_IDF))


def _active_weather() -> Path:
    return Path(st.session_state.get("weather_path", WEATHER_FILE))


# ----------------------------------------------------------------------
# Overview
# ----------------------------------------------------------------------


def render_overview() -> None:
    st.header("Overview")

    report = load_latest_report()

    if report is None:
        st.info(
            "No optimization run yet. Head to **Closed-Loop Runner** and "
            "try a dry run -- no EnergyPlus/Ollama required."
        )
        return

    evaluation = report["evaluation"]
    energy = evaluation["energy"]
    comfort = evaluation["comfort"]
    carbon_kg = estimate_carbon_reduction_kg(
        energy["baseline_energy_kwh"], energy["optimized_energy_kwh"]
    )
    cost_saved = estimate_cost_savings(
        energy["baseline_energy_kwh"], energy["optimized_energy_kwh"]
    )

    columns = st.columns(5)
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
        "Cost savings",
        f"${cost_saved:.2f}" if cost_saved is not None else "n/a",
    )
    columns[3].metric(
        "Comfort",
        "Improved" if comfort["comfort_improved"] else "Regressed",
        f"PMV {comfort['optimized_pmv']:.2f}" if comfort["optimized_pmv"] is not None else None,
    )
    columns[4].metric("Overall score", f"{evaluation['score']['overall_score']:.1f}/100")

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


# ----------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------


def render_setup() -> None:
    st.header("Setup — Building & Weather Files")
    st.caption(
        "Pick a preset or upload your own. Simulation Runner and "
        "Closed-Loop Runner both use whatever's selected here."
    )

    idf_col, epw_col = st.columns(2)

    with idf_col:
        st.subheader("Building model (.idf)")
        idf_presets = list_idf_presets()

        if idf_presets:
            chosen = st.selectbox(
                "Preset", idf_presets, format_func=lambda p: p.name, key="idf_preset"
            )
            st.session_state.setdefault("idf_path", chosen)
            if st.session_state.get("idf_path") not in idf_presets:
                st.session_state["idf_path"] = chosen

        uploaded_idf = st.file_uploader("Or upload a .idf", type=["idf"], key="idf_upload")
        if uploaded_idf is not None:
            saved_path = save_uploaded_file(uploaded_idf, UPLOADED_MODELS_DIR)
            st.session_state["idf_path"] = saved_path
            st.success(f"Saved {saved_path.name}")

    with epw_col:
        st.subheader("Weather file (.epw)")
        epw_presets = list_epw_presets()

        if epw_presets:
            chosen = st.selectbox(
                "Preset", epw_presets, format_func=lambda p: p.name, key="epw_preset"
            )
            st.session_state.setdefault("weather_path", chosen)
            if st.session_state.get("weather_path") not in epw_presets:
                st.session_state["weather_path"] = chosen

        uploaded_epw = st.file_uploader("Or upload a .epw", type=["epw"], key="epw_upload")
        if uploaded_epw is not None:
            saved_path = save_uploaded_file(uploaded_epw, UPLOADED_WEATHER_DIR)
            st.session_state["weather_path"] = saved_path
            st.success(f"Saved {saved_path.name}")

    st.divider()

    with st.container(border=True):
        st.markdown(
            f"**Active selection:** `{_active_idf().name}` + `{_active_weather().name}`"
        )

    st.subheader("Environment status")
    status_col1, status_col2 = st.columns(2)

    with status_col1:
        if ENERGYPLUS_EXE.exists():
            st.success(f"EnergyPlus configured ({ENERGYPLUS_EXE})")
        else:
            st.warning(
                "EnergyPlus not found. Set ENERGYPLUS_EXE in .env for live "
                "simulations, or use dry-run mode."
            )

    with status_col2:
        if _ollama_reachable(OLLAMA_BASE_URL):
            st.success(f"Ollama reachable at {OLLAMA_BASE_URL}")
        else:
            st.warning(
                f"Ollama not reachable at {OLLAMA_BASE_URL}. Needed for live "
                "(non-dry-run) closed-loop runs."
            )


# ----------------------------------------------------------------------
# Simulation Runner
# ----------------------------------------------------------------------


def _render_zone_heatmap(zone_temperatures: dict[str, float]) -> None:
    zones = list(zone_temperatures.keys())
    values = list(zone_temperatures.values())

    figure = go.Figure(
        data=go.Heatmap(
            z=[values],
            x=zones,
            y=["Temperature"],
            colorscale=[[0, "#cde2fb"], [0.5, "#2a78d6"], [1, "#0d366b"]],
            colorbar=dict(title="°C"),
            text=[[f"{value:.1f}°C" for value in values]],
            texttemplate="%{text}",
            textfont=dict(color="white"),
        )
    )
    figure.update_layout(
        template=PLOTLY_TEMPLATE,
        height=220,
        xaxis=dict(side="top"),
        margin=dict(t=60, b=20),
    )
    st.plotly_chart(figure, use_container_width=True)


def _render_simulation_results(payload: dict) -> None:
    state = payload["state"]

    st.subheader("Results")
    columns = st.columns(4)
    columns[0].metric(
        "Total energy",
        f"{state.energy.total_energy_kwh:.1f} kWh" if state.energy.total_energy_kwh is not None else "n/a",
    )
    columns[1].metric(
        "Avg indoor temp",
        f"{state.comfort.average_indoor_temperature:.1f} °C"
        if state.comfort.average_indoor_temperature is not None
        else "n/a",
    )
    columns[2].metric(
        "Peak demand",
        f"{state.cost.peak_demand_kw:.1f} kW" if state.cost.peak_demand_kw is not None else "n/a",
    )
    columns[3].metric(
        "Avg occupancy",
        f"{state.occupancy.average_occupancy:.0f}"
        if state.occupancy.average_occupancy is not None
        else "n/a",
    )

    zone_temperatures = payload.get("zone_temperatures") or {}

    if zone_temperatures:
        st.subheader("🌡️ Zone Temperature Heatmap")
        _render_zone_heatmap(zone_temperatures)


def render_simulation_runner() -> None:
    st.header("Simulation Runner")

    idf_path = _active_idf()
    weather_path = _active_weather()
    st.caption(f"Using `{idf_path.name}` + `{weather_path.name}` — change this on Setup.")

    if not ENERGYPLUS_EXE.exists():
        st.warning(
            "EnergyPlus isn't configured (`ENERGYPLUS_EXE`), so a real "
            "simulation can't run in this environment. Set it in `.env`, "
            "or try Closed-Loop Runner's dry-run mode instead."
        )
    elif st.button("▶️ Run Simulation", type="primary"):
        output_dir = OUTPUT_DIR / f"manual_{datetime.now():%Y%m%d_%H%M%S}"

        with st.status("Running EnergyPlus simulation...", expanded=True) as status:
            status.write(f"Simulating `{idf_path.name}` with `{weather_path.name}`...")

            result = EnergyPlusRunner().run(
                idf_path=idf_path, output_dir=output_dir, weather_file=weather_path
            )

            if not result.success:
                status.update(label="Simulation failed", state="error")
                st.error(result.error)
            else:
                status.write("Parsing telemetry...")

                metadata = BuildingMetadata(
                    building_name=idf_path.stem,
                    location="Manual run",
                    floor_area=0.0,
                    weather_file=weather_path,
                    idf_file=idf_path,
                )
                state = TelemetryParser().parse(result.sql_file, metadata, result.runtime_seconds)
                zone_temperatures = extract_zone_temperatures(result.sql_file)

                st.session_state["last_simulation"] = {
                    "state": state,
                    "zone_temperatures": zone_temperatures,
                }
                status.update(label="Simulation complete", state="complete")

    if "last_simulation" in st.session_state:
        _render_simulation_results(st.session_state["last_simulation"])


# ----------------------------------------------------------------------
# Closed-Loop Runner
# ----------------------------------------------------------------------


def _agent_message(container, speaker: str, text: str) -> None:
    with container:
        st.chat_message(speaker, avatar=AGENT_AVATARS.get(speaker, "🤖")).markdown(
            f"**{speaker}**\n\n{text}"
        )


def render_closed_loop_runner() -> None:
    st.header("Closed-Loop Runner")

    energyplus_ready = ENERGYPLUS_EXE.exists()
    dry_run = st.toggle(
        "Dry run (synthetic responses, no EnergyPlus/Ollama needed)",
        value=not energyplus_ready,
        key="loop_dry_run",
    )
    cycles = st.number_input("Max cycles", min_value=1, max_value=20, value=5, key="loop_cycles")
    demo_pacing = st.checkbox(
        "Demo pacing (short pause between agent messages)", value=True, key="loop_demo_pacing"
    )

    idf_path = _active_idf()
    weather_path = _active_weather()

    if not dry_run:
        st.caption(f"Live mode using `{idf_path.name}` + `{weather_path.name}` — change on Setup.")

    if st.button("▶️ Start Closed Loop", type="primary"):
        console = st.container(border=True)
        console.subheader("🗣️ Agent Console")

        def on_cycle(cycle: int, result: dict) -> None:
            console.markdown(f"**— Cycle {cycle} —**")

            _agent_message(console, "Planner", result["proposal"].rationale)
            if demo_pacing:
                time.sleep(0.4)

            for decision in result["controller_result"].safety_decisions:
                verdict_emoji = {"accept": "✅", "clipped": "✂️", "rejected": "🚫"}.get(
                    decision.verdict.value, ""
                )
                _agent_message(
                    console,
                    "Safety Supervisor",
                    f"{verdict_emoji} `{decision.action.parameter}` — {decision.reason}",
                )
            if demo_pacing:
                time.sleep(0.3)

            _agent_message(console, "Controller", result["controller_result"].message)
            if demo_pacing:
                time.sleep(0.3)

            _agent_message(console, "Analyst", result["analyst_report"].narrative)
            if demo_pacing:
                time.sleep(0.3)

            reflection = result["reflection"]
            narrative = reflection.narrative or "No narrative generated for this cycle."
            _agent_message(
                console,
                "Reflection",
                f"Confidence **{reflection.confidence:.2f}**. {narrative}",
            )

            if reflection.should_rollback:
                _agent_message(
                    console,
                    "Safety Supervisor",
                    "⚠️ This cycle regressed enough to trigger an automatic rollback.",
                )
            if demo_pacing:
                time.sleep(0.3)

        with st.status("Starting closed loop...", expanded=True) as status:
            if dry_run:
                status.write("Using synthetic dependencies (same as `--dry-run`).")
                llm, tools, memory, safety, baseline_state, metadata = build_dry_run_environment(
                    cycles
                )
                dependencies = None
            else:
                status.write("Loading building model and running the baseline simulation...")
                environment = build_live_environment(idf_path, weather_path)
                llm = environment.llm
                tools = environment.tools
                memory = environment.memory
                safety = environment.safety
                baseline_state = environment.baseline_state
                metadata = environment.metadata
                dependencies = environment.dependencies

            graph = build_cycle_graph(llm=llm, tools=tools, memory=memory, safety=safety)

            status.update(label="Running optimization cycles...")

            history = run_optimization_loop(
                graph,
                baseline_state=baseline_state,
                metadata=metadata,
                max_cycles=cycles,
                on_cycle=on_cycle,
            )

            status.write("Writing logs and generating report...")
            write_decision_and_reflection_logs(history)
            write_audit_trail(dependencies)

            if history:
                generate_report(
                    history[-1]["evaluation"],
                    cycle=history[-1]["cycle"],
                    decisions=[
                        {"cycle": entry["cycle"], "rationale": entry["proposal"].rationale}
                        for entry in history
                    ],
                )

            st.session_state["last_run_history"] = history
            status.update(label=f"Completed {len(history)} cycle(s)", state="complete")

        st.success(
            f"Done — {len(history)} cycle(s) completed. See **Outputs & Decisions** "
            "for the full breakdown."
        )

    if "last_run_history" in st.session_state and st.session_state["last_run_history"]:
        history = st.session_state["last_run_history"]
        st.subheader("Last run summary")

        columns = st.columns(3)
        columns[0].metric("Cycles run", len(history))
        columns[1].metric("Final energy savings", f"{history[-1]['evaluation'].energy.savings_percent:.1f}%")
        columns[2].metric("Final confidence", f"{history[-1]['reflection'].confidence:.2f}")


# ----------------------------------------------------------------------
# Outputs & Decisions
# ----------------------------------------------------------------------


def _render_reasoning_timeline_tab() -> None:
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


def _render_audit_trail_tab() -> None:
    audit_trail = load_audit_trail()

    if audit_trail is None:
        st.info(
            "No audit trail available yet -- this needs a live run "
            "(`python main.py` or Closed-Loop Runner with dry-run off), "
            "since it reads the real building's change history."
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
        "Each cycle's modified IDF is saved to disk under energyplus/models/. "
        "This dashboard runs in its own process, so 'rollback' here just "
        "marks which saved file to resume from, rather than reaching into "
        "a live model in memory."
    )

    saved_idfs = list_idf_presets()

    if not saved_idfs:
        st.caption("No per-cycle IDF files found yet.")
        return

    selected = st.selectbox(
        "Choose a cycle to roll back to", options=saved_idfs, format_func=lambda p: p.name
    )

    if st.button("Mark as active rollback target"):
        target = Path(MODELS_DIR) / "rollback_target.idf"
        shutil.copyfile(selected, target)
        st.success(
            f"Copied {selected.name} to {target}. Resume with: "
            f"`python main.py --idf {target}`"
        )


def _render_reports_tab() -> None:
    report = load_latest_report()

    if report is None:
        st.info("No optimization run yet.")
        return

    evaluation = report["evaluation"]

    st.subheader("Final evaluation")
    st.write(f"Recommendation: **{evaluation['recommendation'].upper()}**")

    energy = evaluation["energy"]
    cost_saved = estimate_cost_savings(energy["baseline_energy_kwh"], energy["optimized_energy_kwh"])

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

    if cost_saved is not None:
        st.metric("Estimated cost savings", f"${cost_saved:.2f}")

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

    st.subheader("Report file")

    from dashboard.data import latest_report_path

    report_path = latest_report_path()

    if report_path is not None:
        markdown_path = report_path.with_suffix(".md")

        if markdown_path.exists():
            st.download_button(
                "⬇️ Download report (Markdown)",
                data=markdown_path.read_text(encoding="utf-8"),
                file_name=markdown_path.name,
                mime="text/markdown",
            )


def render_outputs_and_decisions() -> None:
    st.header("Outputs & Decisions")

    reasoning_tab, audit_tab, reports_tab = st.tabs(
        ["🗣️ Reasoning Timeline", "📜 Audit Trail", "📈 Reports & Scores"]
    )

    with reasoning_tab:
        _render_reasoning_timeline_tab()

    with audit_tab:
        _render_audit_trail_tab()

    with reports_tab:
        _render_reports_tab()


PAGES = {
    "🏠 Overview": render_overview,
    "📁 Setup": render_setup,
    "▶️ Simulation Runner": render_simulation_runner,
    "🔁 Closed-Loop Runner": render_closed_loop_runner,
    "📊 Outputs & Decisions": render_outputs_and_decisions,
}


def main() -> None:
    st.sidebar.title("🌱 EcoPilot")
    st.sidebar.caption("Closed-loop HVAC optimization")

    page = st.sidebar.radio("Page", list(PAGES.keys()))

    PAGES[page]()


main()
