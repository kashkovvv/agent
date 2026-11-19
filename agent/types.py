"""Shared types for calling language models."""

from dataclasses import dataclass, field
from typing import Protocol

Message = dict  # {"role": "system" | "user" | "assistant", "content": str}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMResponse:
    text: str
    usage: Usage
    tool_calls: list[dict] = field(default_factory=list)


class LLMClient(Protocol):
    def complete(
        self,
        messages: list[Message],
        json_schema: dict | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse: ...
