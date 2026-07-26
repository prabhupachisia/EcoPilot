# EcoPilot

A closed-loop building-HVAC optimizer, built for Honeywell's "Eco-Loop
BuildingAgents" hackathon.

The idea: a local, open-source LLM (Ollama, `qwen2.5:3b`) watches live
EnergyPlus telemetry through MCP tool-calling, decides on HVAC setpoint
changes, and those changes get fed straight back into EnergyPlus for the
next simulation cycle. Not a one-shot recommendation you'd have to apply
yourself — an actual loop that keeps running and adjusting.

## How it works

Four small agents share the work instead of one model trying to do
everything:

- **Planner** looks at the current building state, a handful of similar
  past cycles pulled from memory, and the grid's carbon-intensity profile,
  then proposes a setpoint change.
- **Analyst** explains what happened in plain language — why energy or
  comfort moved the way it did.
- **Controller** is the only one allowed to actually touch the building.
  Everything it applies goes through a transaction, so a failed edit rolls
  back instead of leaving things half-changed.
- **Reflection** checks the Planner's prediction against what actually
  happened and scores its own confidence — no guessing, just
  `1 - |predicted - actual| / 100`.

They're wired together as a LangGraph state machine (`agent/orchestrator.py`),
and every setpoint the Planner proposes passes through a plain-Python
safety supervisor first — no LLM call, just hard limits. Anything outside
the safe range gets clipped or rejected before it ever reaches EnergyPlus,
and if a cycle's evaluation score tanks, it rolls back automatically using
the building layer's existing snapshot/transaction machinery.

A few things beyond the basic plan worth calling out:

- **Carbon intensity, not just kWh.** A small 24-hour grid carbon-intensity
  curve gives the Planner a second axis to optimize against, and the
  dashboard shows estimated kg CO2 avoided, not just energy saved.
- **An actual audit trail.** Every change to the building — what, when,
  why — gets logged and shown in the dashboard, with a way to roll back to
  any saved cycle's IDF.
- **Case memory.** Past cycles (weather, occupancy, setpoints, outcome) are
  stored in a small FAISS index so the Planner can check "have I seen
  something like this before?" rather than starting cold every time.

See [architecture.md](architecture.md) for the full write-up: the
tool-calling design, prompt engineering, latency handling, and how it deals
with EnergyPlus's very large simulation logs without ever handing raw log
text to the model.

## Quickstart

```bash
pip install -r requirements.txt
```

There are **two separate ways to run EcoPilot** — pick based on whether you
want a terminal-only run or the visual dashboard. Both drive the exact same
`agent/orchestrator.py` closed loop underneath; neither is a prerequisite
for the other.

### Option A — CLI (`python main.py`), terminal only, no GUI

This prints a summary table to the terminal and writes logs/reports to
disk. It never opens a browser or any UI.

```bash
# Code-only smoke test — no EnergyPlus/Ollama required:
python main.py --dry-run --cycles 3

# Live run (needs EnergyPlus installed, and Ollama running with qwen2.5:3b pulled):
python main.py --cycles 10
```

### Option B — GUI (`streamlit run dashboard/app.py`), the full visual system

This is the one command you need for the whole system with a UI — it opens
a local web page (default `http://localhost:8501`) with five pages
(Overview, Setup, Simulation Runner, Closed-Loop Runner, Outputs &
Decisions).

```bash
streamlit run dashboard/app.py
```

Importantly, the **Closed-Loop Runner page runs the entire closed loop
itself** (dry-run or live, your choice, from a toggle) — it is not just a
viewer of files `python main.py` wrote. You never need to touch the CLI to
get the full system working end to end; click "▶️ Start Closed Loop" and
watch the Agent Console. If you *do* also run `python main.py` separately,
the dashboard's other pages (Overview, Outputs & Decisions) will pick up
that run's logs/reports too, since both entrypoints write to the same
`logs/`/`reports/` files.

### Live-mode prerequisites (either option)

For a live (non-`--dry-run`) run, copy `.env.example` to `.env` and fill in
`ENERGYPLUS_HOME`/`ENERGYPLUS_EXE`, and have Ollama running locally with
`qwen2.5:3b` pulled. Dry-run mode needs none of that — it's the fastest way
to see the whole loop work, in either the CLI or the dashboard.

## Tests

```bash
pytest
```

The whole suite runs green with no EnergyPlus install and no Ollama
instance anywhere nearby — see "Testing strategy" in architecture.md for
how that's arranged (mostly: fakes for the LLM and MCP tools, and a
synthetic SQLite fixture standing in for a real `eplusout.sql`).

## Project layout

- `agent/` — the multi-agent brain: `planner.py`, `analyst.py`,
  `controller.py`, `reflection.py`, `orchestrator.py` (LangGraph),
  `safety.py` (the deterministic guardrail), `memory.py` (FAISS case
  memory), `llm.py`/`tools.py` (LLM and MCP tool-calling interfaces, plus
  fakes for testing), `prompts.py`, `dry_run.py` (the synthetic `--dry-run`
  environment).
- `mcp_server/` — the MCP tool server: building manipulation (`tools/
  building/`, eppy-backed), simulation, telemetry, evaluation, case
  memory, knowledge base (document RAG), reports, carbon intensity.
- `energyplus/` — the baseline IDF/weather file and the `EnergyPlusRunner`
  subprocess wrapper.
- `telemetry/` — pulls structured `BuildingState` data out of EnergyPlus's
  `eplusout.sql`.
- `dashboard/` — the Streamlit GUI (`app.py`): its Overview/Outputs &
  Decisions pages read whatever's in `logs/`/`reports/` (via the
  data-loading layer, `data.py`), but its Closed-Loop Runner page can drive
  a full closed-loop run itself (dry-run or live) — a complete alternative
  to `main.py`, not just a viewer.
- `config/` — environment-driven settings (`settings.py`) and static
  constants (`constants.py` — safety ranges, log file names).
- `main.py` — CLI entrypoint that wires all of the above together.
- `tests/` — including `tests/fixtures/` (a fake IDF, a synthetic SQL
  database) that make the tool layer testable without EnergyPlus/Ollama
  installed anywhere.
