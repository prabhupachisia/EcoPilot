from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent.llm import FakeLLMClient, LLMResponse, OllamaLLMClient, ToolCall


def test_fake_llm_client_returns_queued_responses_in_order() -> None:
    first = LLMResponse(content="first")
    second = LLMResponse(content="second")

    client = FakeLLMClient(responses=[first])
    client.queue(second)

    assert client.complete("system", "user") is first
    assert client.complete("system", "user") is second


def test_fake_llm_client_records_calls() -> None:
    client = FakeLLMClient(responses=[LLMResponse(content="ok")])

    client.complete("system prompt", "user prompt", tools=[{"name": "foo"}])

    assert client.calls == [
        {
            "system_prompt": "system prompt",
            "user_prompt": "user prompt",
            "tools": [{"name": "foo"}],
        }
    ]


def test_fake_llm_client_raises_when_out_of_responses() -> None:
    client = FakeLLMClient()

    with pytest.raises(AssertionError):
        client.complete("system", "user")


def _fake_ollama_response(content: str, tool_calls: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=tool_calls)
    )


def test_ollama_llm_client_wraps_chat_response() -> None:
    fake_tool_call = SimpleNamespace(
        function=SimpleNamespace(name="set_hvac_setpoints", arguments={"cooling_c": 25.0})
    )
    ollama_client = Mock()
    ollama_client.chat.return_value = _fake_ollama_response(
        "Raising the cooling setpoint.", [fake_tool_call]
    )

    client = OllamaLLMClient(model="qwen2.5:3b", client=ollama_client)

    response = client.complete("system prompt", "user prompt", tools=[{"name": "foo"}])

    ollama_client.chat.assert_called_once_with(
        model="qwen2.5:3b",
        messages=[
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ],
        tools=[{"name": "foo"}],
    )

    assert response.content == "Raising the cooling setpoint."
    assert response.tool_calls == [
        ToolCall(name="set_hvac_setpoints", arguments={"cooling_c": 25.0})
    ]


def test_ollama_llm_client_handles_no_tool_calls() -> None:
    ollama_client = Mock()
    ollama_client.chat.return_value = _fake_ollama_response("No action needed.", None)

    client = OllamaLLMClient(client=ollama_client)

    response = client.complete("system", "user")

    assert response.content == "No action needed."
    assert response.tool_calls == []
