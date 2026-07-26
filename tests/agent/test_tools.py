import pytest
from fastmcp import FastMCP

from agent.tools import FakeToolExecutor, FastMCPToolExecutor


def test_fake_tool_executor_returns_queued_plain_value() -> None:
    executor = FakeToolExecutor()
    executor.queue("get_carbon_intensity", 0.4)

    result = executor.call("get_carbon_intensity", hour=12)

    assert result == 0.4
    assert executor.calls == [("get_carbon_intensity", {"hour": 12})]


def test_fake_tool_executor_supports_callable_response() -> None:
    executor = FakeToolExecutor()
    executor.queue("set_hvac_setpoints", lambda cooling_c=None, **_: {"applied": cooling_c})

    result = executor.call("set_hvac_setpoints", cooling_c=25.0)

    assert result == {"applied": 25.0}


def test_fake_tool_executor_raises_for_unscripted_tool() -> None:
    executor = FakeToolExecutor()

    with pytest.raises(AssertionError):
        executor.call("unregistered_tool")


def test_fastmcp_tool_executor_calls_a_real_registered_tool() -> None:
    server = FastMCP("test-server")

    @server.tool
    def add(a: int, b: int) -> int:
        return a + b

    executor = FastMCPToolExecutor(server)

    assert executor.call("add", a=2, b=3) == 5


def test_fastmcp_tool_executor_raises_on_tool_error() -> None:
    server = FastMCP("test-server")

    @server.tool
    def fail() -> None:
        raise ValueError("boom")

    executor = FastMCPToolExecutor(server)

    with pytest.raises(RuntimeError):
        executor.call("fail")
