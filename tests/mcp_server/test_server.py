import asyncio

import mcp_server.server as server_module


def test_server_module_builds_a_fastmcp_instance() -> None:
    assert server_module.mcp.name == "EcoPilot"


def test_server_registers_the_expected_tools() -> None:
    tools = asyncio.run(server_module.mcp.get_tools())

    expected = {
        "run_simulation_tool",
        "read_building_state_tool",
        "building_summary",
        "validate_building",
        "apply_building_action",
        "apply_building_actions",
        "set_hvac_setpoints",
        "get_hvac_setpoints",
        "create_snapshot",
        "restore_snapshot",
        "list_snapshots",
        "begin_transaction",
        "commit_transaction",
        "rollback_transaction",
        "building_lifecycle",
        "evaluate_snapshot",
        "generate_evaluation_score",
        "summarize_evaluation",
        "store_experience",
        "retrieve_similar_cases",
        "get_decision_history",
        "get_confidence_trend",
        "load_knowledge_document",
        "build_knowledge_index",
        "rebuild_knowledge_index",
        "search_knowledge",
        "retrieve_context",
        "knowledge_statistics",
        "clear_knowledge_base",
        "generate_report",
        "list_reports",
        "get_carbon_intensity",
        "get_carbon_intensity_profile",
        "get_low_carbon_hours",
        "get_high_carbon_hours",
        "compute_carbon_emissions",
    }

    assert expected <= set(tools.keys())
