from __future__ import annotations

import asyncio
from typing import Any, Protocol

from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError


class ToolExecutor(Protocol):
    """The narrow interface agents use to invoke MCP tools.

    Agents never talk to ``fastmcp`` directly -- they go through this
    interface, so control-flow (Planner/Controller/orchestrator) is
    testable against a ``FakeToolExecutor`` with no MCP server or
    EnergyPlus/Ollama involved.
    """

    def call(self, name: str, **kwargs: Any) -> Any: ...


class FastMCPToolExecutor:
    """Calls tools on a real ``FastMCP`` server via fastmcp's in-memory transport.

    Using the in-memory transport (``Client(server)`` against a live
    ``FastMCP`` instance, no subprocess/socket) keeps this genuine MCP
    tool-calling -- the same protocol a network-connected client would use
    -- without the overhead of a separate process for a single-machine
    hackathon PoC.
    """

    def __init__(self, server: FastMCP) -> None:
        self._server = server

    def call(self, name: str, **kwargs: Any) -> Any:
        return asyncio.run(self._call_async(name, kwargs))

    async def _call_async(self, name: str, arguments: dict[str, Any]) -> Any:
        async with Client(self._server) as client:
            try:
                result = await client.call_tool(name, arguments)
            except ToolError as error:
                raise RuntimeError(f"MCP tool '{name}' failed: {error}") from error

            return result.data


class FakeToolExecutor:
    """Scripted ``ToolExecutor`` for tests.

    ``queue(name, result)`` registers what a call to ``name`` should
    return; ``result`` may be a plain value or a callable taking the same
    kwargs the tool was called with (for scripting responses that depend on
    input). Every call is recorded in ``.calls`` for assertions.
    """

    def __init__(self) -> None:
        self._responses: dict[str, Any] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def queue(self, name: str, result: Any) -> None:
        self._responses[name] = result

    def call(self, name: str, **kwargs: Any) -> Any:
        self.calls.append((name, kwargs))

        if name not in self._responses:
            raise AssertionError(
                f"FakeToolExecutor has no scripted response for '{name}'."
            )

        result = self._responses[name]

        if callable(result):
            return result(**kwargs)

        return result


__all__ = [
    "ToolExecutor",
    "FastMCPToolExecutor",
    "FakeToolExecutor",
]
