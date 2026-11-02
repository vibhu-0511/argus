"""The results JSON. One file per eval run. Later tasks (report, gate, dashboard) read this and nothing else.

Change it only by bumping `schema_version`. The JSON Schema is generated from these models:
`python -m eval schema > packages/eval/schemas/results.schema.json`. Field notes: packages/eval/README.md.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from eval.metrics import MetricsSummary

Verdict = Literal["resolved", "unresolved", "excluded", "error"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AgentInfo(_Model):
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    host: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict, description="The agent config's free-form params, copied as given.")


class Counts(_Model):
    resolved: int = Field(ge=0)
    unresolved: int = Field(ge=0)
    excluded: int = Field(ge=0, description="Could not be set up or scored. Listed with a reason, left out of the resolve-rate denominator.")
    error: int = Field(ge=0, description="The agent raised. Counted as unresolved in the denominator.")


class ResolveRate(_Model):
    successes: int = Field(ge=0, description="resolved")
    total: int = Field(ge=0, description="resolved + unresolved + error")
    rate: float | None = Field(description="successes / total, 6 decimals. null when total is 0.")
    ci_low: float | None = Field(description="Lower bound of the interval. null when total is 0.")
    ci_high: float | None = Field(description="Upper bound of the interval. null when total is 0.")
    interval: Literal["wilson95"] = Field(default="wilson95", description="Wilson score interval, 95%, z = 1.96.")


class TokenCounts(_Model):
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    tokens_cached: int = Field(ge=0)


class TokenMeans(_Model):
    tokens_in: float
    tokens_out: float
    tokens_cached: float


class Tokens(_Model):
    total: TokenCounts = Field(description="Summed over scored tasks (every task except excluded ones).")
    per_task: TokenMeans | None = Field(description="total / resolve_rate.total. null when total is 0.")


class Latency(_Model):
    p50: float | None = Field(description="Seconds, linear interpolation between closest ranks. null when n is 0.")
    p95: float | None = Field(description="Seconds, same method. null when n is 0.")
    n: int = Field(ge=0, description="Scored tasks that have a latency.")


class TaskRow(_Model):
    task_id: str = Field(min_length=1)
    tier: str | None = Field(description="easy, medium or hard, from the task's meta.")
    verdict: Verdict
    reason: str | None = Field(description="Why a task is excluded or errored. null otherwise.")
    stop_reason: str | None = Field(description="The run's stop reason, for example submit or step-cap.")
    steps: int | None = Field(ge=0)
    tokens: TokenCounts
    latency_s: float | None = Field(description="Seconds. The agent's own figure if it gave one, else wall time around the agent call.")
    trajectory: str | None = Field(description="Path to the run's trajectory.jsonl, as the agent gave it.")


class Results(_Model):
    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    created_at: str = Field(description="UTC, ISO 8601, seconds.")
    agent: AgentInfo
    counts: Counts
    resolve_rate: ResolveRate
    tokens: Tokens
    latency_s: Latency
    trajectory_metrics: MetricsSummary | None = Field(
        description="docs/metrics.md over the tasks that gave a trajectory. null when none did."
    )
    dollar_equivalent: float | None = Field(
        default=None,
        alias="$_equivalent",
        description="List-price dollar equivalent of the scored tokens (argus_core.prices). null when there are no tokens.",
    )
    tasks: list[TaskRow]

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True, indent=2) + "\n"


def schema_json() -> str:
    schema = Results.model_json_schema()
    schema["$id"] = "https://argus.local/schemas/results.schema.json"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"
