"""Hard-stop quota ledger. The check runs before the HTTP call. State is a JSON file so a restart keeps the day's count.

ponytail: one process owns the file. Two writers on the same path can drop a record. Upgrade path is an OS lock around load and save.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


class QuotaExceeded(RuntimeError):
    def __init__(self, model: str, limit: str, used: int, cap: int):
        self.model = model
        self.limit = limit
        self.used = used
        self.cap = cap
        super().__init__(f"{model} would exceed {limit}: {used} of {cap}")


@dataclass(frozen=True)
class ModelQuota:
    requests_per_day: int
    tokens_per_day: int
    requests_per_minute: int
    tokens_per_minute: int
    cached_counts: bool


@dataclass(frozen=True)
class Usage:
    tokens_in: int
    tokens_out: int
    tokens_cached: int = 0


def load_quotas(path: Path) -> dict[str, ModelQuota]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```yaml\n(.*?)```", text, flags=re.DOTALL)
    if match is None:
        raise ValueError(f"no yaml quota block in {path}")
    block = yaml.safe_load(match.group(1))
    quotas: dict[str, ModelQuota] = {}
    for model, raw in (block.get("models") or {}).items():
        quotas[model] = ModelQuota(
            requests_per_day=int(raw["requests_per_day"]),
            tokens_per_day=int(raw["tokens_per_day"]),
            requests_per_minute=int(raw["requests_per_minute"]),
            tokens_per_minute=int(raw["tokens_per_minute"]),
            cached_counts=bool(raw["cached_counts"]),
        )
    return quotas


class Ledger:
    def __init__(
        self,
        path: Path,
        quotas: dict[str, ModelQuota],
        *,
        now: Callable[[], datetime] | None = None,
    ):
        self.path = path
        self.quotas = quotas
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._state = self._load()

    def call(self, model: str, send: Callable[[], Usage], *, token_estimate: int = 0) -> Usage:
        self._check(model, token_estimate)
        usage = send()
        self._record(model, usage)
        return usage

    def _check(self, model: str, token_estimate: int) -> None:
        quota = self.quotas.get(model)
        if quota is None:
            raise QuotaExceeded(model, "unknown-model", 0, 0)
        self._roll_day()
        bucket = self._bucket(model)
        now = self._now()
        recent = _within_minute(bucket["events"], now)
        if bucket["requests"] + 1 > quota.requests_per_day:
            raise QuotaExceeded(model, "requests_per_day", bucket["requests"] + 1, quota.requests_per_day)
        if len(recent) + 1 > quota.requests_per_minute:
            raise QuotaExceeded(model, "requests_per_minute", len(recent) + 1, quota.requests_per_minute)
        day_tokens = bucket["tokens"] + token_estimate
        if bucket["tokens"] >= quota.tokens_per_day or day_tokens > quota.tokens_per_day:
            raise QuotaExceeded(model, "tokens_per_day", day_tokens, quota.tokens_per_day)
        minute_tokens = sum(item["tokens"] for item in recent) + token_estimate
        if minute_tokens > quota.tokens_per_minute:
            raise QuotaExceeded(model, "tokens_per_minute", minute_tokens, quota.tokens_per_minute)

    def _record(self, model: str, usage: Usage) -> None:
        quota = self.quotas[model]
        charged = usage.tokens_in + usage.tokens_out
        if not quota.cached_counts:
            charged -= usage.tokens_cached
        charged = max(charged, 0)
        bucket = self._bucket(model)
        bucket["requests"] += 1
        bucket["tokens"] += charged
        bucket["cached"] += usage.tokens_cached
        bucket["events"].append({"t": self._now().isoformat(), "tokens": charged})
        self._save()

    def _bucket(self, model: str) -> dict:
        return self._state["models"].setdefault(
            model, {"requests": 0, "tokens": 0, "cached": 0, "events": []}
        )

    def _roll_day(self) -> None:
        day = self._now().date().isoformat()
        if self._state["day"] != day:
            self._state = {"day": day, "models": {}}

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"day": self._now().date().isoformat(), "models": {}}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._state), encoding="utf-8")


def _within_minute(events: list[dict], now: datetime) -> list[dict]:
    cutoff = now - timedelta(seconds=60)
    kept = []
    for item in events:
        stamp = datetime.fromisoformat(item["t"])
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        if stamp > cutoff:
            kept.append(item)
    return kept
