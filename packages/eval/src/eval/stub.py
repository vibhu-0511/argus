"""Stub agent for the CLI and for tests. No model call. Resolves the task ids listed in `params.resolve`."""

from __future__ import annotations

from argus_core.types import Task

from eval.runner import AgentConfig, Outcome


def make(config: AgentConfig):
    resolve = set(config.params.get("resolve", []))

    def agent(task: Task) -> Outcome:
        return Outcome(
            "resolved" if task.id in resolve else "unresolved",
            stop_reason="submit",
            steps=3,
            tokens_in=1000,
            tokens_out=50,
            tokens_cached=200,
            latency_s=float(config.params.get("latency_s", 1.0)),
        )

    return agent
