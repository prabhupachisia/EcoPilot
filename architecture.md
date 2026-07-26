# EcoPilot Architecture

EcoPilot is a closed-loop building-HVAC optimizer built for Honeywell's
"Eco-Loop BuildingAgents" hackathon: a local, open-source LLM (Ollama,
`qwen2.5:3b` by default) reasons over live EnergyPlus telemetry through MCP
tool-calling, proposes HVAC setpoint changes, and those changes are fed back
into EnergyPlus for the next simulation cycle — a genuine closed loop, not a
one-shot recommendation.

Two front-ends sit on top of the same closed-loop core and neither depends
on the other: `main.py` is a terminal-only CLI (prints a summary table, no
UI); `dashboard/app.py`'s Closed-Loop Runner page is a self-contained GUI
that can drive the identical loop from a button click. Both call
`build_cycle_graph()`/`run_optimization_loop()` directly.

```text
        main.py                          dashboard/app.py
      (CLI, no UI --                 (Streamlit GUI -- the
    prints a summary                Closed-Loop Runner page
     table, no browser)             drives this loop itself)
              │                                │
              └────────────────┬───────────────┘
                                │
                     build the closed-loop graph
                                 │
 ┌───────────────────────────────────────────────────────────────────┐
 │                    agent/orchestrator.py (LangGraph)               │
 │                                                                     │
 │  read_metrics → memory_retrieval → planner → controller →          │
 │  run_simulation → telemetry_parser → evaluation → analyst →        │
 │  reflection → store_experience → satisfied_check                   │
 │                                                                     │
 │  (repeated by run_optimization_loop() until satisfied or            │
 │   MAX_OPTIMIZATION_CYCLES, in plain Python — see "Why the repeat    │
 │   loop isn't a LangGraph edge" below)                               │
 └───────────────────────────────────────────────────────────────────┘
        │            │              │              │            │
   Planner       Analyst       Controller      Reflection   SafetySupervisor
  (proposes)   (explains)     (only agent    (confidence,    (deterministic
                              allowed to      case memory)     guardrail,
                               execute)                       no LLM call)
        │            │              │              │            │
        └────────────┴──────────────┴──────────────┴────────────┘
                                 │
                    agent/tools.py: ToolExecutor
              (FastMCPToolExecutor -- in-memory MCP transport,
               or FakeToolExecutor for tests/--dry-run)
                                 │
                        mcp_server/server.py (FastMCP)
                                 │
      ┌──────────┬──────────┬──────────┬──────────┬──────────┬─────────┐
      │          │          │          │          │          │         │
  building/*  simulation telemetry  evaluation   memory     carbon   reports
  (eppy/IDF)  (EnergyPlus (SQLite   (energy/     (FAISS     (grid    (markdown
              runner)     extract)  comfort/     case       intensity +JSON)
                                    carbon/peak) memory)     profile)
      │          │          │
      └──────────┴──────────┴──── EnergyPlus (subprocess) ── eplusout.sql
                                                                    │
                                                          dashboard/app.py
                                                          (Streamlit, reads
                                                           persisted logs)
```

## Tech stack

| Concern | Choice |
|---|---|
| Simulation engine | EnergyPlus 26.1, via `eppy` (IDF read/write) and a `subprocess` runner |
| LLM | Ollama, `qwen2.5:3b` by default (any tool-calling Ollama model works) |
| Agent protocol | MCP, via `fastmcp` (server) + `fastmcp.Client` in-memory transport (agent-side calls) |
| Orchestration | LangGraph `StateGraph` (one compiled graph per optimization cycle) |
| Backend/tools | FastAPI-style tool functions registered on a `FastMCP` server |
| Dashboard | Streamlit + Plotly, reading persisted JSON logs |
| Case memory | FAISS (`IndexFlatL2`) over small numeric feature vectors, JSON-persisted |
| Knowledge base | FAISS + `sentence-transformers`, document RAG over ASHRAE/EnergyPlus references |
| Config | `python-dotenv` + plain module constants (`config/settings.py`, `config/constants.py`) |
| Logging | `loguru` + `rich` (console tables) |
| Testing | `pytest`, entirely hermetic (see "Testing strategy") |

## Tool-calling architecture

Every capability the agents can use is an MCP tool registered on a single
`FastMCP` server (`mcp_server/server.py` → `mcp_server/registry.py`):
building manipulation (`mcp_server/tools/building/`, an `eppy`-backed IDF
wrapper with snapshot/transaction rollback built in), simulation execution,
telemetry extraction, evaluation scoring, case memory, the knowledge base,
report generation, and the grid carbon-intensity profile.

Agents never import `fastmcp` directly. They depend on `agent.tools.ToolExecutor`
— a one-method interface (`call(tool_name, **kwargs)`). Two implementations:

- **`FastMCPToolExecutor`** — wraps `fastmcp.Client(server)` against the
  live `FastMCP` server instance using fastmcp's *in-memory transport*.
  This is genuine MCP protocol usage (the same `call_tool` RPC a
  network-connected client would use), just without a subprocess or socket
  for a single-machine PoC.
- **`FakeToolExecutor`** — records calls and returns scripted results, so
  every agent and the full LangGraph orchestrator are unit-testable with no
  MCP server, EnergyPlus, or Ollama running at all.

The same split exists for the LLM: `agent.llm.LLMClient` is implemented by
`OllamaLLMClient` (real) and `FakeLLMClient` (scripted, records every
prompt sent). `python main.py --dry-run` swaps in `agent/dry_run.py`'s
synthetic environment (fake LLM + fake tools, still running the *real*
LangGraph graph and *real* agent code) — a genuine smoke test of the control
flow without either external dependency installed.

### Why a smaller tool surface for the Planner

The building layer exposes a generic `apply_building_action`/
`apply_building_actions` dispatcher plus one convenience tool,
`set_hvac_setpoints(cooling_c, heating_c, reason)`. The Planner is only
advertised `set_hvac_setpoints` (see `agent/planner.py`'s `PLANNER_TOOLS`) —
a 3B model reliably filling in two optional floats and a reason string is a
much safer bet than reliably constructing the full generic
`{component, action, target, parameter, value}` action schema. Every other
building capability (envelope, lighting, equipment, ventilation, schedules,
materials) remains reachable through the generic dispatcher for direct
tool-protocol testing, just not offered to the Planner in this PoC's scope.

## Multi-agent design

Four narrowly-scoped agents (`agent/planner.py`, `analyst.py`,
`controller.py`, `reflection.py`), each independently unit-testable:

- **Planner** — reads the current `BuildingState`, retrieved similar past
  cycles (case memory), and the grid carbon-intensity profile; makes one
  LLM call with `set_hvac_setpoints` as its only tool, and parses the
  resulting tool call(s) into `BuildingAction`s. Also derives the day's
  lowest-carbon hours deterministically (not LLM-derived) for display.
- **Analyst** — pure interpretation: explains *why* metrics changed
  (baseline vs. current state, evaluation scores) in natural language. No
  action proposal, no execution.
- **Controller** — the *only* component allowed to execute. Every proposed
  action passes through `SafetySupervisor` first (clip/reject), then the
  whole batch runs inside a `begin_transaction`/`commit_transaction`/
  `rollback_transaction` block so a partial tool failure reverts cleanly.
  Makes no LLM call — execution is deterministic, not a reasoning step.
- **Reflection** — computes a deterministic confidence score
  (`1 - |predicted% - actual%| / 100`, clamped to [0, 1]) comparing the
  Planner's implied prediction to the actual measured outcome, decides
  `should_rollback` via `SafetySupervisor.check_regression` against the
  prior cycle's evaluation score, and builds the `Experience` record stored
  in case memory. An optional LLM call can add a qualitative narrative on
  top, but never touches the confidence number itself.

`agent/orchestrator.py` wires these into a LangGraph `StateGraph` for one
cycle: `read_metrics → memory_retrieval → planner → controller →
run_simulation → telemetry_parser → evaluation → analyst → reflection →
store_experience → satisfied_check`. (Memory retrieval runs before the
Planner node in the actual wiring — the Planner needs retrieved cases as an
input — which is a data-dependency detail, not a deviation from the
project's original "Planner retrieves similar historical situations"
design.)

### Why the repeat loop isn't a LangGraph edge

The compiled graph above ends at `satisfied_check`, full stop — no edge
loops back to `read_metrics`. `run_optimization_loop()` (plain Python) calls
`graph.invoke()` once per cycle instead, threading the resulting state and
evaluation score forward as the next call's input, stopping early the first
cycle that passes evaluation or at `MAX_OPTIMIZATION_CYCLES`. This keeps
every cycle's graph run independently traceable (useful for the dashboard's
audit trail and for debugging a single cycle in isolation) and avoids
tuning LangGraph's recursion limit for what would otherwise be an unbounded
cycle count.

## Novelty beyond the base multi-agent design

1. **Grid carbon-intensity-aware scheduling** — most HVAC optimizers only
   chase kWh. `CarbonIntensityProfile` adds a second axis: a small,
   hand-authored 24-hour kg CO2/kWh curve (`config/carbon_intensity.json`,
   not a live grid feed) that the Planner is explicitly prompted to reason
   about via `get_low_carbon_hours`/`get_carbon_intensity`, and that the
   dashboard uses to estimate baseline-vs-optimized kg CO2.
2. **Deterministic Safety Supervisor** (`agent/safety.py`) — a non-LLM
   guardrail. Every LLM-proposed setpoint is clipped to
   `COOLING_SETPOINT_SAFE_RANGE`/`HEATING_SETPOINT_SAFE_RANGE`
   (`config/constants.py`) or rejected outright before it ever reaches
   EnergyPlus, and a cycle whose evaluation score regresses more than
   `REGRESSION_ROLLBACK_THRESHOLD` triggers an automatic
   `restore_snapshot` — reusing the building layer's existing
   snapshot/transaction machinery rather than adding a new rollback path.
   It also enforces the Planner's own optimization principle in code, not
   just in the prompt: `_enforce_deadband_widening` rejects any proposal
   that narrows the cooling/heating deadband (which increases HVAC energy
   even though a smaller model can be talked into proposing it) by
   comparing the batch's net effect against the current setpoints, not
   just checking each action in isolation.
3. **Explainable audit trail** — the building layer's `diff`/`ChangeRecord`
   history and snapshot list (already built, previously unwired to any UI)
   are exported per run and surfaced in the dashboard's Audit Trail page,
   alongside a disk-based "rollback to a saved cycle's IDF" action (see
   below for why it's disk-based rather than live in-memory restore).
4. **Confidence-tracked reflection** — see Reflection above; trended on the
   dashboard's AI Reasoning page.

## Prompt engineering strategy

System prompts live in `agent/prompts.py`, one per role, each stating its
scope explicitly (Analyst: "do not propose new actions"; Reflection: "the
confidence score is computed deterministically, do not restate or
recompute it"). The Planner's prompt is parameterized with the live safety
bounds (`format_planner_prompt`) so the model is told the exact range its
proposals will be checked against, rather than discovering it only after a
clipped result — this reduces wasted proposals and makes the safety
supervisor's behavior legible in the model's own stated reasoning. Tool
surface is kept intentionally small per agent (see above) since a 3B model
tool-calls more reliably with fewer, narrower options.

## Prompt latency management

- Each cycle makes at most three LLM calls (Planner, Analyst, an optional
  Reflection narrative) — not one per building parameter.
- The Controller and the Safety Supervisor make *zero* LLM calls; they are
  deterministic Python, so the loop's latency scales with simulation time
  and (bounded) LLM calls, not with the number of safety checks or building
  edits.
- Prompts are built from already-aggregated telemetry (see below) — small,
  fixed-size text, not raw simulation output — keeping prompt size and
  latency independent of simulation length or timestep count.
- `agent.llm.LLMClient` is a synchronous, single-call interface by design;
  nothing in this PoC depends on streaming, so latency is a simple sum of
  simulation time + up to three model calls per cycle.

## Handling lengthy simulation logs

EnergyPlus can emit gigabytes of timestep-level output over a long run.
Two choices keep this from ever reaching the LLM or the agents directly:

1. **SQL aggregation at the source.** `telemetry/extractor.py` never reads
   raw `.eso`/`.mtr` text logs — it queries EnergyPlus's SQLite output
   (`eplusout.sql`) with `AVG`/`MAX`/`SUM` aggregates scoped to a specific
   `ReportingFrequency` (e.g. "Run Period" for totals, "Hourly" for peak
   demand and the carbon-weighting breakdown). A multi-year, sub-hourly
   simulation and a one-day one produce the same small, fixed-shape
   `BuildingState` — the aggregation cost is paid once in SQL, not by the
   agent layer re-parsing anything.
2. **Structured dataclasses, not free text.** `telemetry/models.py`'s
   `BuildingState` (and `mcp_server/tools/evaluation.py`'s
   `EvaluationResult`) are the only things that ever reach a prompt
   template (`agent/planner.py`/`analyst.py`'s `_build_prompt`) — a few
   dozen numbers, not a log dump. This is also what keeps prompts small
   under "Prompt latency management" above.

## Testing strategy

The entire suite (`pytest`, 220+ tests) is hermetic: no EnergyPlus install
and no Ollama instance are required to get a green run.

- **eppy needs a real, EnergyPlus-install-only IDD file** to parse any IDF
  at all — there's no way around that for real `BuildingManager.load()`
  calls, so those two tests are `skipif(not ENERGYPLUS_EXE.exists())`.
  Everything else about `BuildingManager` is tested against
  `tests/fixtures/fake_building.py` — a lightweight stand-in for eppy's
  `IDF`/`EpBunch` (plain Python objects backing `idfobjects`/getattr/
  setattr) that the real mixin code runs against unmodified.
- **Telemetry** tests run against `tests/fixtures/synthetic_sql.py` — an
  in-memory-shaped SQLite database matching the real `Simulations`/
  `ReportDataDictionary`/`ReportData`/`Time` schema, used automatically
  when a real `eplusout.sql` isn't present (falls back to a real one if a
  developer has actually run EnergyPlus locally).
- **Agents, orchestrator, and `main.py --dry-run`** use `FakeLLMClient`/
  `FakeToolExecutor` (see "Tool-calling architecture"). The orchestrator
  tests specifically cover: full-state population for one cycle, early
  termination on a passing evaluation, running to `MAX_OPTIMIZATION_CYCLES`
  when never satisfied, and the auto-rollback branch on a detected
  regression.
- **The dashboard** is smoke-tested with `streamlit.testing.v1.AppTest`
  against both the empty state (fresh clone, no run yet) and populated
  logs/reports, for all four pages.

## Running it

Two independent front-ends, same closed-loop core underneath — see the
diagram at the top of this document. Neither is a prerequisite for the
other.

```bash
# --- Option A: CLI, terminal only, no GUI/browser at all ---

# Code-only smoke test -- no EnergyPlus/Ollama required:
python main.py --dry-run --cycles 3

# Live run (needs EnergyPlus + a running Ollama with qwen2.5:3b pulled):
python main.py --cycles 10


# --- Option B: GUI -- the full visual system, this is the only command ---
# --- you need for the dashboard; it can run the closed loop itself.    ---

streamlit run dashboard/app.py
```

`streamlit run dashboard/app.py` opens a local web page with five pages
(Overview, Setup, Simulation Runner, Closed-Loop Runner, Outputs &
Decisions). Its Closed-Loop Runner page runs the entire loop itself —
dry-run or live, toggled in the UI — so it is a complete alternative to
`main.py`, not a viewer that depends on having run the CLI first. Running
`python main.py` separately is only useful if you want the plain-terminal
workflow, or want to seed `logs/`/`reports/` before opening the dashboard's
read-only pages (Overview, Outputs & Decisions read whatever's on disk from
either front-end).
