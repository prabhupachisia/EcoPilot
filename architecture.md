# EcoPilot Architecture

```text
                              EcoPilot
                                 │
 ┌──────────────────────────────────────────────────────────┐
 │                 Streamlit Dashboard                      │
 └──────────────────────────────────────────────────────────┘
                                 ▲
                                 │
                          Reports & Metrics
                                 ▲
                                 │
─────────────────────────────────────────────────────────────

                         Agent Orchestrator
                                 │
       ┌──────────────┬──────────────┬──────────────┬──────────────┐
       │              │              │              │
 Planner Agent   Analyst Agent  Controller Agent Reflection Agent
       │              │              │              │
       └──────────────┴──────────────┴──────────────┴──────────────┘
                          │
                    Shared FAISS Memory
                          │
                    Knowledge Retrieval
                          │
                    MCP Tool Interface
                          │
      ┌──────────────┬───────────────┬──────────────┐
      │              │               │
 Read Metrics   Modify Building   Run Simulation
      │              │               │
      └──────────────┴───────────────┴──────────────┘
                          │
                     EnergyPlus API
                          │
                    Building Simulation
                          │
                 CSV / SQL / ESO Outputs
                          │
                  Telemetry Processing
                          │
                  Structured Building State
```