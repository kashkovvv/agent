"""Cache tests with a fake client, without network requests."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from agent.types import LLMResponse, Usage
from evals.cache import CachedLLM

MESSAGES = [
    {"role": "system", "content": "Отвечай кратко."},
    {"role": "user", "content": "Привет!"},
]


class FakeLLM:
    def __init__(self):
        self.calls = []

    def complete(self, messages, json_schema=None, temperature=0.0):
        self.calls.append((messages, json_schema, temperature))
        return LLMResponse(
            text=f"Ответ {len(self.calls)}",
            usage=Usage(input_tokens=10, output_tokens=5),
            tool_calls=[{"name": "example", "arguments": {"text": "Привет!"}}],
        )


def test_repeated_request_uses_cache(tmp_path: Path) -> None:
    client = FakeLLM()
    cache = CachedLLM(client, "model", tmp_path)
    first = cache.complete(MESSAGES)
    second = cache.complete(MESSAGES)

    assert len(client.calls) == 1
    assert second.text == first.text
    assert second.tool_calls == first.tool_calls
    assert first.usage == Usage(10, 5)
    assert second.usage == Usage()
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text(encoding="utf-8")) == asdict(first)


@pytest.mark.parametrize(
    "model, messages, schema, temperature",
    [
        ("other-model", MESSAGES, None, 0),
        ("model", [{"role": "user", "content": "Другой запрос"}], None, 0),
        ("model", list(reversed(MESSAGES)), None, 0),
        ("model", MESSAGES, {"type": "object"}, 0),
        ("model", MESSAGES, None, 0.5),
    ],
    ids=["model", "messages", "message_order", "schema", "temperature"],
)
def test_different_requests_have_separate_entries(
    tmp_path: Path,
    model: str,
    messages: list[dict],
    schema: dict | None,
    temperature: float,
) -> None:
    client = FakeLLM()
    CachedLLM(client, "model", tmp_path).complete(MESSAGES)
    CachedLLM(client, model, tmp_path).complete(
        messages, json_schema=schema, temperature=temperature
    )

    assert len(client.calls) == 2
    assert client.calls[1] == (messages, schema, temperature)
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_new_instance_reads_saved_response(tmp_path: Path) -> None:
    first = CachedLLM(FakeLLM(), "model", tmp_path).complete(MESSAGES)
    client = FakeLLM()
    second = CachedLLM(client, "model", tmp_path).complete(MESSAGES)

    assert client.calls == []
    assert second.text == first.text
    assert second.tool_calls == first.tool_calls
    assert second.usage == Usage()


def test_dictionary_key_order_does_not_change_request(tmp_path: Path) -> None:
    client = FakeLLM()
    cache = CachedLLM(client, "model", tmp_path)
    cache.complete(MESSAGES, json_schema={"type": "object", "properties": {}}, temperature=0)
    reordered = [{"content": item["content"], "role": item["role"]} for item in MESSAGES]
    cache.complete(reordered, json_schema={"properties": {}, "type": "object"}, temperature=0.0)

    assert len(client.calls) == 1


def test_disabled_cache_does_not_read_or_overwrite_entries(tmp_path: Path) -> None:
    client = FakeLLM()
    CachedLLM(client, "model", tmp_path).complete(MESSAGES)
    saved_file = next(tmp_path.glob("*.json"))
    saved_text = saved_file.read_text(encoding="utf-8")
    cache = CachedLLM(client, "model", tmp_path, enabled=False)
    second = cache.complete(MESSAGES)
    third = cache.complete(MESSAGES)

    assert len(client.calls) == 3
    assert second.text != third.text
    assert second.usage == third.usage == Usage(10, 5)
    assert saved_file.read_text(encoding="utf-8") == saved_text


def test_disabled_cache_does_not_create_files(tmp_path: Path) -> None:
    cache_dir = tmp_path / "disabled"
    CachedLLM(FakeLLM(), "model", cache_dir, enabled=False).complete(MESSAGES)
    assert not cache_dir.exists()
