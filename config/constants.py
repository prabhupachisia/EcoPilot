"""Cross-cutting literals that aren't environment-driven (see config/settings.py)."""

# Hard bounds the SafetySupervisor clips/rejects LLM-proposed setpoints
# against before they ever reach EnergyPlus (degrees C).
COOLING_SETPOINT_SAFE_RANGE = (22.0, 28.0)
HEATING_SETPOINT_SAFE_RANGE = (18.0, 22.0)

# Fractional drop in an evaluation's overall score (vs. the prior cycle)
# that triggers an automatic snapshot/transaction rollback.
REGRESSION_ROLLBACK_THRESHOLD = 0.10

# Representative commercial electricity rate ($/kWh), for a quick cost
# estimate alongside the energy/carbon numbers -- same "small constant
# instead of a live feed" approach as the carbon-intensity profile.
ELECTRICITY_RATE_PER_KWH = 0.16

# One append-only log file per concern.
SIMULATION_LOG_FILE = "simulation_log.json"
DECISION_LOG_FILE = "decision_log.json"
TOOL_LOG_FILE = "tool_log.json"
MEMORY_LOG_FILE = "memory_log.json"
REFLECTION_LOG_FILE = "reflection_log.json"
