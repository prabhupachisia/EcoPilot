# EcoPilot

A closed-loop building-HVAC optimizer built for Honeywell's "Eco-Loop
BuildingAgents" hackathon. A local, open-source LLM (Ollama, `qwen2.5:3b`)
reasons over live EnergyPlus telemetry through MCP tool-calling, proposes
HVAC setpoint changes, and those changes feed back into EnergyPlus for the
next simulation cycle — a genuine closed loop, not a one-shot
recommendation.

Four agents (Planner, Analyst, Controller, Reflection), orchestrated as a
LangGraph state machine, cooperate under a deterministic (non-LLM) safety
supervisor and a FAISS case-memory of past optimization cycles. See
[architecture.md](architecture.md) for the full system design, tool-calling
architecture, prompt engineering strategy, and testing approach.

## Quickstart

```bash
pip install -r requirements.txt

# Code-only smoke test -- no EnergyPlus/Ollama required:
python main.py --dry-run --cycles 3

# Live run (needs EnergyPlus installed + `ollama pull qwen2.5:3b` running locally):
python main.py --cycles 10

# Dashboard (reads whatever the last run wrote to logs/ and reports/):
streamlit run dashboard/app.py
```

Copy `.env.example` to `.env` and fill in `ENERGYPLUS_HOME`/`ENERGYPLUS_EXE`
for a live run; `--dry-run` needs no configuration at all.

## Tests

```bash
pytest
```

The entire suite is hermetic — no EnergyPlus install and no Ollama instance
are required for a green run (see architecture.md's "Testing strategy").

## Project layout

- `agent/` — the multi-agent brain: `planner.py`/`analyst.py`/
  `controller.py`/`reflection.py`, `orchestrator.py` (LangGraph),
  `safety.py` (deterministic guardrail), `memory.py` (FAISS case memory),
  `llm.py`/`tools.py` (LLM and MCP tool-calling interfaces + fakes for
  testing), `prompts.py`, `dry_run.py` (synthetic `--dry-run` environment).
- `mcp_server/` — the MCP tool server: building manipulation (`tools/
  building/`, eppy-backed), simulation, telemetry, evaluation, case
  memory, knowledge base (document RAG), reports, carbon intensity.
- `energyplus/` — the baseline IDF/weather file and the `EnergyPlusRunner`
  subprocess wrapper.
- `telemetry/` — SQLite extraction from EnergyPlus's `eplusout.sql` into
  structured `BuildingState` dataclasses.
- `dashboard/` — the Streamlit dashboard (`app.py`) and its data-loading
  layer (`data.py`), read persisted JSON logs/reports.
- `config/` — environment-driven settings (`settings.py`) and static
  constants (`constants.py`, e.g. safety ranges).
- `main.py` — the CLI entrypoint tying everything together.
- `tests/` — hermetic test suite, including `tests/fixtures/` (fake IDF,
  synthetic SQL) that make the above testable without EnergyPlus/Ollama.
