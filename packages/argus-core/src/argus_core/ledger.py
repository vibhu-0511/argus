"""Hard-stop quota ledger. The check runs before the HTTP call. State is a JSON file so a restart keeps the day's count.

Tenants (P8-T07). Every call belongs to a tenant; callers that pass none are the `default` tenant, so P0-P7 code and
tests are unchanged. The model quotas (docs/quotas.md) are the host's limits and are shared: they are always checked
against the total over all tenants. On top of that, when the ledger is given `budgets`, each tenant has its own
fair-share limits (see `TenantBudget`). A tenant that hits its own limit gets `TenantQuotaExceeded`, which names it;
a second tenant under its limit goes on. Fair-share rule: a tenant may use its own daily budget over all models, and
at most `provider_share` of any one model's limits (day and minute), so one tenant cannot take the whole shared
free-tier limit. Order of checks: tenant budget, tenant share of the model, then the shared limit.

ponytail: budgets are an argument, not read from a file yet (ADR-028 decides). A share is a fixed fraction; unused capacity is not lent to other tenants. One process owns the file. Two writers on the same path can drop a record. Upgrade path is an OS lock around load and save.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


DEFAULT_TENANT = "default"


class QuotaExceeded(RuntimeError):
    def __init__(self, model: str, limit: str, used: int, cap: int):
        self.model = model
        self.limit = limit
        self.used = used
        self.cap = cap
        super().__init__(f"{model} would exceed {limit}: {used} of {cap}")


class TenantQuotaExceeded(QuotaExceeded):
    """A tenant used up its own budget or its share of a model. The message names the tenant."""

    def __init__(self, tenant: str, model: str, limit: str, used: int, cap: int):
        super().__init__(model, limit, used, cap)
        self.tenant = tenant
        self.args = (f"tenant {tenant}: {model} would exceed {limit}: {used} of {cap}",)


@dataclass(frozen=True)
class TenantBudget:
    """One tenant's daily limits. `requests_per_day` and `tokens_per_day` count over all models.

    `provider_share` (0 to 1] is the part of any single model's day and minute limits this tenant may use.
    Pick it as 1 divided by the number of tenants that share the host's free tier.
    """

    requests_per_day: int
    tokens_per_day: int
    provider_share: float = 0.5

    def __post_init__(self) -> None:
        if not 0 < self.provider_share <= 1:
            raise ValueError("provider_share must be above 0 and at most 1")


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
        budgets: dict[str, TenantBudget] | None = None,
    ):
        self.path = path
        self.quotas = quotas
        self.budgets = budgets  # None: no per-tenant limits, only the shared model limits
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._state = self._load()

    def call(self, model: str, send: Callable[[], Usage], *, token_estimate: int = 0, tenant: str = DEFAULT_TENANT) -> Usage:
        self._check(model, token_estimate, tenant)
        usage = send()
        self._record(model, usage, tenant)
        return usage

    def for_tenant(self, tenant: str) -> TenantLedger:
        """A view with the same `call` as this ledger, bound to `tenant`. Router and the agent loops take it unchanged."""
        return TenantLedger(self, tenant)

    def _check(self, model: str, token_estimate: int, tenant: str = DEFAULT_TENANT) -> None:
        quota = self.quotas.get(model)
        if quota is None:
            raise QuotaExceeded(model, "unknown-model", 0, 0)
        if not tenant:
            raise ValueError("tenant must not be empty")
        self._roll_day()
        now = self._now()
        self._check_tenant(model, quota, token_estimate, tenant, now)
        everyone = [b for models in self._all_tenants() if (b := models.get(model)) is not None]
        _enforce(everyone, quota, token_estimate, now, lambda limit, used, cap: QuotaExceeded(model, limit, used, cap))

    def _check_tenant(self, model: str, quota: ModelQuota, token_estimate: int, tenant: str, now: datetime) -> None:
        if self.budgets is None:
            return
        budget = self.budgets.get(tenant)
        if budget is None:
            if tenant == DEFAULT_TENANT:
                return  # P0-P7 callers; list "default" in budgets to limit it too
            raise TenantQuotaExceeded(tenant, model, "unknown-tenant", 0, 0)
        mine = self._models_of(tenant)
        requests = sum(b["requests"] for b in mine.values()) + 1
        if requests > budget.requests_per_day:
            raise TenantQuotaExceeded(tenant, model, "tenant_requests_per_day", requests, budget.requests_per_day)
        tokens = sum(b["tokens"] for b in mine.values()) + token_estimate
        if tokens > budget.tokens_per_day:
            raise TenantQuotaExceeded(tenant, model, "tenant_tokens_per_day", tokens, budget.tokens_per_day)
        share = ModelQuota(
            requests_per_day=_part(quota.requests_per_day, budget.provider_share),
            tokens_per_day=_part(quota.tokens_per_day, budget.provider_share),
            requests_per_minute=_part(quota.requests_per_minute, budget.provider_share),
            tokens_per_minute=_part(quota.tokens_per_minute, budget.provider_share),
            cached_counts=quota.cached_counts,
        )
        _enforce(
            [self._bucket(model, tenant)], share, token_estimate, now,
            lambda limit, used, cap: TenantQuotaExceeded(tenant, model, f"provider_share.{limit}", used, cap),
        )

    def _record(self, model: str, usage: Usage, tenant: str = DEFAULT_TENANT) -> None:
        # `tokens` is what counts against the cap; `cached` and `fresh` (prompt tokens that missed the cache) are kept apart.
        quota = self.quotas[model]
        charged = usage.tokens_in + usage.tokens_out
        if not quota.cached_counts:
            charged -= usage.tokens_cached
        charged = max(charged, 0)
        bucket = self._bucket(model, tenant)
        bucket["requests"] += 1
        bucket["tokens"] += charged
        bucket["cached"] += usage.tokens_cached
        bucket["fresh"] = bucket.get("fresh", 0) + max(usage.tokens_in - usage.tokens_cached, 0)
        bucket["events"].append({"t": self._now().isoformat(), "tokens": charged})
        self._save()

    def _models_of(self, tenant: str) -> dict[str, dict]:
        # the default tenant keeps its buckets under "models" (the P0 layout); the others sit under "tenants"
        if tenant == DEFAULT_TENANT:
            return self._state["models"]
        return self._state["tenants"].setdefault(tenant, {})

    def _all_tenants(self) -> list[dict[str, dict]]:
        return [self._state["models"], *self._state["tenants"].values()]

    def _bucket(self, model: str, tenant: str = DEFAULT_TENANT) -> dict:
        return self._models_of(tenant).setdefault(
            model, {"requests": 0, "tokens": 0, "cached": 0, "fresh": 0, "events": []}
        )

    def _roll_day(self) -> None:
        day = self._now().date().isoformat()
        if self._state["day"] != day:
            self._state = {"day": day, "models": {}, "tenants": {}}

    def _load(self) -> dict:
        if self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            state.setdefault("tenants", {})  # files written before P8-T07 have none
            return state
        return {"day": self._now().date().isoformat(), "models": {}, "tenants": {}}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._state), encoding="utf-8")


class TenantLedger:
    """`Ledger.call` bound to one tenant. Anything that takes a ledger (Router, run_fix, run_planned) takes this."""

    def __init__(self, ledger: Ledger, tenant: str):
        if not tenant:
            raise ValueError("tenant must not be empty")
        self.ledger = ledger
        self.tenant = tenant

    def call(self, model: str, send: Callable[[], Usage], *, token_estimate: int = 0) -> Usage:
        return self.ledger.call(model, send, token_estimate=token_estimate, tenant=self.tenant)


def _part(cap: int, share: float) -> int:
    return max(1, int(cap * share))


def _enforce(
    buckets: list[dict],
    quota: ModelQuota,
    token_estimate: int,
    now: datetime,
    fail: Callable[[str, int, int], QuotaExceeded],
) -> None:
    """Raise `fail(limit, used, cap)` if one more call on top of `buckets` (all of one model) would pass `quota`."""
    recent = [item for b in buckets for item in _within_minute(b["events"], now)]
    requests = sum(b["requests"] for b in buckets)
    tokens = sum(b["tokens"] for b in buckets)
    if requests + 1 > quota.requests_per_day:
        raise fail("requests_per_day", requests + 1, quota.requests_per_day)
    if len(recent) + 1 > quota.requests_per_minute:
        raise fail("requests_per_minute", len(recent) + 1, quota.requests_per_minute)
    day_tokens = tokens + token_estimate
    if tokens >= quota.tokens_per_day or day_tokens > quota.tokens_per_day:
        raise fail("tokens_per_day", day_tokens, quota.tokens_per_day)
    minute_tokens = sum(item["tokens"] for item in recent) + token_estimate
    if minute_tokens > quota.tokens_per_minute:
        raise fail("tokens_per_minute", minute_tokens, quota.tokens_per_minute)


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
