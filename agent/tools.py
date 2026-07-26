from __future__ import annotations

import asyncio
from typing import Any, Protocol

from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError


class ToolExecutor(Protocol):
    """Narrow interface agents use to invoke MCP tools.

    Agents don't talk to fastmcp directly - they go through this instead,
    so the control flow (Planner/Controller/orchestrator) can be tested
    against a FakeToolExecutor with no MCP server, EnergyPlus, or Ollama
    anywhere in sight.
    """

    def call(self, tool_name: str, **kwargs: Any) -> Any: ...


class FastMCPToolExecutor:
    """Calls tools on a real FastMCP server over fastmcp's in-memory transport.

    `Client(server)` talks to a live FastMCP instance directly, no
    subprocess or socket involved, but it's still the real MCP call_tool
    RPC under the hood - just skipping the network hop since everything's
    running on one machine anyway.
    """

    def __init__(self, server: FastMCP) -> None:
        self._server = server

    def call(self, tool_name: str, **kwargs: Any) -> Any:
        return asyncio.run(self._call_async(tool_name, kwargs))

    async def _call_async(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        async with Client(self._server) as client:
            try:
                result = await client.call_tool(tool_name, arguments)
            except ToolError as error:
                raise RuntimeError(f"MCP tool '{tool_name}' failed: {error}") from error

            return result.data


class FakeToolExecutor:
    """Scripted ToolExecutor for tests.

    queue(name, result) registers what calling `name` should return.
    `result` can be a plain value, or a callable that takes the same
    kwargs the tool was called with if the response needs to depend on
    input. Every call gets recorded in `.calls` for assertions.
    """

    def __init__(self) -> None:
        self._responses: dict[str, Any] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def queue(self, name: str, result: Any) -> None:
        self._responses[name] = result

    def call(self, tool_name: str, **kwargs: Any) -> Any:
        self.calls.append((tool_name, kwargs))

        if tool_name not in self._responses:
            raise AssertionError(
                f"FakeToolExecutor has no scripted response for '{tool_name}'."
            )

        result = self._responses[tool_name]

        if callable(result):
            return result(**kwargs)

        return result


__all__ = [
    "ToolExecutor",
    "FastMCPToolExecutor",
    "FakeToolExecutor",
]
