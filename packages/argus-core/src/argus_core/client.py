"""One OpenAI-compatible chat client. The host is `base_url` and the key. Nothing else changes."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class Usage:
    tokens_in: int
    tokens_out: int
    tokens_cached: int


@dataclass(frozen=True)
class Completion:
    content: str
    usage: Usage
    raw: dict


class ModelClient:
    def __init__(self, base_url: str, api_key: str = "", *, timeout: float = 60.0):
        if not base_url:
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def complete(self, model: str, messages: list[dict]) -> Completion:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        with httpx.Client(timeout=self.timeout) as http:
            response = http.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages},
            )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage") or {}
        details = usage.get("prompt_tokens_details") or {}
        message = data["choices"][0]["message"]
        return Completion(
            content=message.get("content") or "",
            usage=Usage(
                tokens_in=int(usage.get("prompt_tokens") or 0),
                tokens_out=int(usage.get("completion_tokens") or 0),
                tokens_cached=int(details.get("cached_tokens") or 0),
            ),
            raw=data,
        )
