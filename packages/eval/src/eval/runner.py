"""Eval runner. A task list and an agent config go in; one results JSON (eval.results) comes out.

The agent is a callable `Task -> Outcome`. It owns setup, the run and scoring; the runner owns timing,
counting and the interval. Tasks run one after another.
"""

from __future__ import annotations

import importlib
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from argus_core.prices import dollar_equivalent
from argus_core.types import Task
from pydantic import BaseModel, ConfigDict, Field

from eval.metrics import load_trajectory, run_metrics, summarize
from eval.results import AgentInfo, Counts, Latency, ResolveRate, Results, TaskRow, TokenCounts, TokenMeans, Tokens, Verdict
from eval.stats import percentile, wilson


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    host: str = "local"
    factory: str = Field(description="`module:function`. The function takes this config and returns the agent callable.")
    params: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class Outcome:
    verdict: Verdict
    reason: str | None = None
    stop_reason: str | None = None
    steps: int | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cached: int = 0
    latency_s: float | None = None  # replaces the measured wall time (a replay has none worth keeping)
    trajectory: str | None = None


Agent = Callable[[Task], Outcome]


def load_agent(config: AgentConfig) -> Agent:
    module, _, attr = config.factory.partition(":")
    return getattr(importlib.import_module(module), attr)(config)


def load_tasks(path: Path) -> list[Task]:
    return [Task.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def run_eval(
    tasks: Sequence[Task],
    agent: Agent,
    config: AgentConfig,
    *,
    run_id: str | None = None,
    now: datetime | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Results:
    rows: list[TaskRow] = []
    for task in tasks:
        start = clock()
        try:
            outcome = agent(task)
        except Exception as exc:  # a crashed agent is a result, not a crashed eval
            outcome = Outcome("error", reason=f"{type(exc).__name__}: {exc}")
        latency = outcome.latency_s if outcome.latency_s is not None else clock() - start
        rows.append(
            TaskRow(
                task_id=task.id,
                tier=task.meta.tier.value,
                verdict=outcome.verdict,
                reason=outcome.reason,
                stop_reason=outcome.stop_reason,
                steps=outcome.steps,
                tokens=TokenCounts(
                    tokens_in=outcome.tokens_in, tokens_out=outcome.tokens_out, tokens_cached=outcome.tokens_cached
                ),
                latency_s=None if outcome.verdict == "excluded" else round(latency, 3),
                trajectory=outcome.trajectory,
            )
        )
    return _aggregate(rows, config, run_id or config.name, now or datetime.now(UTC))


def _aggregate(rows: list[TaskRow], config: AgentConfig, run_id: str, now: datetime) -> Results:
    count = {v: sum(r.verdict == v for r in rows) for v in ("resolved", "unresolved", "excluded", "error")}
    scored = [r for r in rows if r.verdict != "excluded"]
    total = len(scored)
    low, high = wilson(count["resolved"], total) if total else (None, None)
    token_sum = {
        field: sum(getattr(r.tokens, field) for r in scored) for field in ("tokens_in", "tokens_out", "tokens_cached")
    }
    # no tokens, no price needed; tokens on an unpriced model raise UnknownModelPrice (never a silent 0)
    dollars = dollar_equivalent(config.model, **token_sum) if token_sum["tokens_in"] or token_sum["tokens_out"] else None
    latencies = [r.latency_s for r in scored if r.latency_s is not None]
    p50, p95 = percentile(latencies, 50), percentile(latencies, 95)
    runs = [run_metrics(load_trajectory(Path(r.trajectory))) for r in rows if r.trajectory]
    return Results(
        run_id=run_id,
        created_at=now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        agent=AgentInfo(name=config.name, model=config.model, host=config.host, params=config.params),
        counts=Counts(**count),
        resolve_rate=ResolveRate(
            successes=count["resolved"],
            total=total,
            rate=round(count["resolved"] / total, 6) if total else None,
            ci_low=None if low is None else round(low, 6),
            ci_high=None if high is None else round(high, 6),
        ),
        tokens=Tokens(
            total=TokenCounts(**token_sum),
            per_task=TokenMeans(**{k: round(v / total, 3) for k, v in token_sum.items()}) if total else None,
        ),
        latency_s=Latency(
            p50=None if p50 is None else round(p50, 3),
            p95=None if p95 is None else round(p95, 3),
            n=len(latencies),
        ),
        trajectory_metrics=summarize(runs) if runs else None,
        dollar_equivalent=None if dollars is None else round(dollars, 6),
        tasks=rows,
    )
