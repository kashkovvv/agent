"""Cache model responses in JSON files, one file per request."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from agent.types import LLMClient, LLMResponse, Message, Usage

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "cache"


class CachedLLM:
    def __init__(
        self,
        client: LLMClient,
        model: str,
        cache_dir: str | Path = DEFAULT_CACHE_DIR,
        enabled: bool = True,
    ):
        self.client = client
        self.model = model
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled

    def complete(
        self,
        messages: list[Message],
        json_schema: dict | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        if not self.enabled:
            return self.client.complete(messages, json_schema=json_schema, temperature=temperature)

        request = {
            "model": self.model,
            "messages": messages,
            "json_schema": json_schema,
            "temperature": float(temperature),
        }
        request_json = json.dumps(request, sort_keys=True, ensure_ascii=False)
        key = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
        path = self.cache_dir / f"{key}.json"

        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return LLMResponse(
                text=data["text"],
                usage=Usage(),  # No model call, so no tokens spent on this request.
                tool_calls=data["tool_calls"],
            )

        response = self.client.complete(messages, json_schema=json_schema, temperature=temperature)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(response), ensure_ascii=False), encoding="utf-8")
        return response
