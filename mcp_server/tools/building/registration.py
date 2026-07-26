from __future__ import annotations

from fastmcp import FastMCP

from mcp_server.dependencies import DependencyProvider


def register_building_tools(
    server: FastMCP,
    dependencies: DependencyProvider,
) -> None:
    """
    Register building manipulation tools.
    """

    @server.tool(
        name="building_summary",
        description="Return a summary of the currently loaded building.",
    )
    def building_summary():
        return dependencies.building.summary()

    @server.tool(
        name="validate_building",
        description="Validate the currently loaded building model.",
    )
    def validate_building():
        return dependencies.building.validate()

    @server.tool(
        name="apply_building_action",
        description="Apply a single modification to the building.",
    )
    def apply_building_action(action):
        return dependencies.building.apply_action(action)

    @server.tool(
        name="apply_building_actions",
        description="Apply multiple building modifications.",
    )
    def apply_building_actions(actions):
        return dependencies.building.apply_actions(actions)

    @server.tool(
        name="create_snapshot",
        description="Create a snapshot of the current building.",
    )
    def create_snapshot(
        name: str,
    ):
        return dependencies.building.create_snapshot(name)

    @server.tool(
        name="restore_snapshot",
        description="Restore a previously created snapshot.",
    )
    def restore_snapshot(
        name: str,
    ):
        return dependencies.building.restore_snapshot(name)

    @server.tool(
        name="list_snapshots",
        description="List all stored building snapshots.",
    )
    def list_snapshots():
        return dependencies.building.list_snapshots()

    @server.tool(
        name="begin_transaction",
        description="Begin a reversible building transaction.",
    )
    def begin_transaction():
        return dependencies.building.begin_transaction()

    @server.tool(
        name="commit_transaction",
        description="Commit the active transaction.",
    )
    def commit_transaction():
        return dependencies.building.commit()

    @server.tool(
        name="rollback_transaction",
        description="Rollback the active transaction.",
    )
    def rollback_transaction():
        return dependencies.building.rollback()

    @server.tool(
        name="building_lifecycle",
        description="Return lifecycle information for the current building.",
    )
    def building_lifecycle():
        return dependencies.building.lifecycle_summary()