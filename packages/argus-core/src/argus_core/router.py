"""Route a stage to a cheap or strong tier by a written policy, and record which tier and host served each call.

The policy lives in `routing.yaml`. This module only reads it and applies it. A call goes through the quota
ledger like any other. On a quota refusal (the ledger's `QuotaExceeded`, or an HTTP 429 from the host) the
tier's fallback route on the other host is tried once; if that is refused too, the error reaches the caller.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from argus_core.client import Completion, ModelClient
from argus_core.ledger import Ledger, QuotaExceeded, Usage

ROUTING_PATH = Path(__file__).with_name("routing.yaml")


class UnknownStage(KeyError):
    """The stage has no entry in the policy. There is no default tier."""


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Route(_Frozen):
    host: str
    model: str


class TierRoutes(_Frozen):
    primary: Route
    fallback: Route | None = None


class Policy(_Frozen):
    stages: dict[str, str]
    tiers: dict[str, TierRoutes]
    fallback_on: list[Literal["quota_exceeded", "http_429"]] = ["quota_exceeded", "http_429"]

    @model_validator(mode="after")
    def stages_name_a_tier(self) -> Policy:
        for stage, tier in self.stages.items():
            if tier not in self.tiers:
                raise ValueError(f"stage {stage!r} names tier {tier!r}, which is not in tiers")
        return self


def load_policy(path: Path = ROUTING_PATH) -> Policy:
    return Policy.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class Routed:
    """A completion plus who served it. `trace()` is what a TrajectoryStep stores."""

    completion: Completion
    stage: str
    tier: str
    host: str
    model: str
    fell_back: bool

    def trace(self) -> dict[str, str]:
        return {"tier": self.tier, "host": self.host, "model": self.model}


class Router:
    def __init__(self, policy: Policy, ledger: Ledger, clients: Mapping[str, ModelClient]):
        self.policy = policy
        self.ledger = ledger
        self.clients = clients

    def complete(self, stage: str, messages: list[dict], *, token_estimate: int = 0) -> Routed:
        tier = self.policy.stages.get(stage)
        if tier is None:
            raise UnknownStage(f"no tier for stage {stage!r} in the routing policy")
        routes = self.policy.tiers[tier]
        try:
            return self._call(stage, tier, routes.primary, messages, token_estimate, fell_back=False)
        except Exception as exc:
            if routes.fallback is None or not self._is_refusal(exc):
                raise
        return self._call(stage, tier, routes.fallback, messages, token_estimate, fell_back=True)

    def _call(self, stage, tier, route: Route, messages, token_estimate, *, fell_back: bool) -> Routed:
        client = self.clients.get(route.host)
        if client is None:
            raise KeyError(f"no client for host {route.host!r} (tier {tier!r})")
        held: dict[str, Completion] = {}

        def send() -> Usage:
            done = client.complete(route.model, messages)
            held["completion"] = done
            return Usage(done.usage.tokens_in, done.usage.tokens_out, done.usage.tokens_cached)

        self.ledger.call(route.model, send, token_estimate=token_estimate)
        return Routed(held["completion"], stage, tier, route.host, route.model, fell_back)

    def _is_refusal(self, exc: Exception) -> bool:
        on = self.policy.fallback_on
        if isinstance(exc, QuotaExceeded):
            return "quota_exceeded" in on
        if isinstance(exc, httpx.HTTPStatusError):
            return "http_429" in on and exc.response.status_code == 429
        return False
