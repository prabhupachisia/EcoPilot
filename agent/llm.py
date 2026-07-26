from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import ollama

from config.settings import OLLAMA_BASE_URL, OLLAMA_MODEL


@dataclass(slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None


class LLMClient(Protocol):
    """The narrow interface every agent role depends on.

    One method, on purpose - a real OllamaLLMClient and a scripted
    FakeLLMClient stay interchangeable that way, so agent tests never need
    a live Ollama instance.
    """

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse: ...


class OllamaLLMClient:
    """Wraps a local Ollama model (default: qwen2.5:3b) with tool-calling."""

    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        client: ollama.Client | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self._client = client or ollama.Client(host=base_url)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = self._client.chat(
            model=self.model,
            messages=messages,
            tools=tools,
        )

        message = response.message

        tool_calls = [
            ToolCall(
                name=call.function.name,
                arguments=dict(call.function.arguments or {}),
            )
            for call in (message.tool_calls or [])
        ]

        return LLMResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            raw=response,
        )


class FakeLLMClient:
    """Scripted ``LLMClient`` for tests: returns queued responses in order.

    Also records every call so tests can assert on the prompts/tools an
    agent actually sent.
    """

    def __init__(self, responses: list[LLMResponse] | None = None) -> None:
        self._responses: list[LLMResponse] = list(responses or [])
        self.calls: list[dict[str, Any]] = []

    def queue(self, response: LLMResponse) -> None:
        self._responses.append(response)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "tools": tools,
            }
        )

        if not self._responses:
            raise AssertionError("FakeLLMClient has no queued responses left.")

        return self._responses.pop(0)


__all__ = [
    "ToolCall",
    "LLMResponse",
    "LLMClient",
    "OllamaLLMClient",
    "FakeLLMClient",
]
