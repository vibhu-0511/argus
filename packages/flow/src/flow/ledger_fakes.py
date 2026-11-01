"""Fake runners and GitHub client whose world is an append-only file, so effects outlive a killed process (P6-T19, P6-T21).

`flow.fakes` keeps its state in memory: a process that is killed takes the "GitHub" with it, and a
crash experiment would see nothing. Here every call appends one row to a JSON-lines `Ledger`, and the
fakes read the ledger to find what already happened. The ledger is the world: a restarted process,
plain Python or DBOS, sees the same runs, branch, PR, comments and label.

One row per call: `seq` (global counter), `op`, `key`, `n` (this is the n-th call with this op and
key), `made` (the call made a new effect; False when it found the effect or only read) and the draft
flag of a created PR. Find-before-act is the same for both variants of the experiment: an effect is
made only when no row with `made` and the same op and key exists, which is the rule `flow.fakes`
and the real runners keep. `duplicates` counts effects made more than once; `repeated_calls`
counts calls beyond the first for an op and key (an expected at-least-once repeat is not a duplicate).

`Hook` is the kill switch: the fakes call `hit("<point>")` at the points of `KILL_POINTS`. Armed for
one point, the process prints `AT <point>` and waits; the harness then kills it from outside. That is
a hard kill at an exact moment, not an exception.

ponytail: the ledger is read whole on every call (O(rows)); a run has about 30 rows. A file appended
by one process at a time; two writers at once would interleave lines.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

from flow.workflow import Outcome, PullRequest

# In pipeline order. `<step>:before` is also "the step before it finished and stored its result";
# `<step>:effect` and the `open-pr` / `finish` points inside a step are before that step's result is stored.
KILL_POINTS = (
    "repro:before",
    "repro:effect",
    "fix:before",
    "fix:effect",
    "verify:before",
    "verify:effect",
    "open-pr:before",
    "open-pr:pushed",
    "open-pr:pr-created",
    "open-pr:effects-done",
    "qa:before-wait",
    "qa:waiting",
    "finish:before",
    "finish:ready",
    "finish:effects-done",
)
# Points where the step's side effect exists and DBOS has not stored its result yet.
BEFORE_STORED = frozenset(
    {"repro:effect", "fix:effect", "verify:effect", "open-pr:pushed", "open-pr:pr-created", "open-pr:effects-done"}
    | {"finish:ready", "finish:effects-done"}
)


class Ledger:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def made(self, op: str, key: str) -> bool:
        return any(r["op"] == op and r["key"] == key and r["made"] for r in self.rows())

    def add(self, op: str, key: str, made: bool, **extra: Any) -> None:
        rows = self.rows()
        row = {"seq": len(rows) + 1, "op": op, "key": key, "n": 1 + sum(r["op"] == op and r["key"] == key for r in rows), "made": made, **extra}
        with self.path.open("a", encoding="utf-8") as f:  # closed (flushed to the OS) before the call returns
            f.write(json.dumps(row) + "\n")

    def act(self, op: str, key: str, **extra: Any) -> bool:
        """Find-before-act: record the call, made only if the effect was not there. Returns whether it was made."""
        made = not self.made(op, key)
        self.add(op, key, made, **extra)
        return made


def duplicates(rows: list[dict[str, Any]]) -> int:
    """Effects made more than once: rows with `made` beyond one per (op, key)."""
    return sum(c - 1 for c in Counter((r["op"], r["key"]) for r in rows if r["made"]).values())


def repeated_calls(rows: list[dict[str, Any]]) -> list[str]:
    """`op key` of every call that is not the first with that op and key."""
    return [f"{r['op']} {r['key']}" for r in rows if r["n"] > 1]


class Hook:
    def __init__(self, kill_at: str | None) -> None:
        if kill_at is not None and kill_at not in KILL_POINTS:
            raise ValueError(f"unknown kill point {kill_at!r}")
        self.kill_at = kill_at

    def hit(self, point: str) -> None:
        if point == self.kill_at:
            print(f"AT {point}", flush=True)
            time.sleep(600)  # the harness kills the process from outside; this is only a stop for a lost harness
            os._exit(3)


class LedgerRunner:
    """Repro, fix or verify runner: one run per run key, found if it was already started."""

    def __init__(self, step: str, ledger: Ledger, hook: Hook, outcome: Outcome) -> None:
        self.step, self.ledger, self.hook, self.outcome = step, ledger, hook, outcome

    def run(self, ticket_id: str, run_key: str, upstream: str) -> Outcome:
        self.hook.hit(f"{self.step}:before")
        self.ledger.act(f"dispatch-{self.step}", run_key)
        self.hook.hit(f"{self.step}:effect")
        return self.outcome


class LedgerGitHub:
    def __init__(self, ledger: Ledger, hook: Hook) -> None:
        self.ledger, self.hook = ledger, hook
        self.lookup_error: Exception | None = None

    def push_branch(self, branch: str, patch: str, key: str) -> None:
        self.hook.hit("open-pr:before")
        self.ledger.act("push-branch", key, branch=branch)
        self.hook.hit("open-pr:pushed")

    def find_pr(self, branch: str) -> PullRequest | None:
        self.ledger.add("find-pr", branch, made=False)
        if self.lookup_error is not None:
            raise self.lookup_error
        if not self.ledger.made("create-pr", branch):
            return None
        return PullRequest(1, f"https://example.test/pr/{branch}", draft=not self.ledger.made("ready-pr", branch))

    def create_draft_pr(self, branch: str, title: str, body: str) -> PullRequest:
        if self.ledger.made("create-pr", branch):
            self.ledger.add("create-pr", branch, made=False)
            raise RuntimeError("a PR for this head already exists")  # GitHub answers 422
        self.ledger.add("create-pr", branch, made=True, draft=True)
        self.hook.hit("open-pr:pr-created")
        return PullRequest(1, f"https://example.test/pr/{branch}", draft=True)

    def ready_pr(self, branch: str) -> None:
        self.hook.hit("finish:before")
        if not self.ledger.made("create-pr", branch):
            raise KeyError(branch)  # no PR to mark, as on GitHub
        self.ledger.act("ready-pr", branch)  # already ready: found, not made
        self.hook.hit("finish:ready")

    def close_pr(self, branch: str) -> None:
        self.ledger.act("close-pr", branch)

    def post_comment(self, ticket_id: str, key: str, body: str) -> None:
        self.ledger.act("comment", key)

    def set_label(self, ticket_id: str, state: str) -> None:
        labels = [r for r in self.ledger.rows() if r["op"] == "label" and r["made"]]
        made = not (labels and labels[-1]["key"] == f"{ticket_id}:{state}")  # the label is already the current one
        self.ledger.add("label", f"{ticket_id}:{state}", made)
        self.hook.hit({"awaiting-qa": "open-pr:effects-done", "done": "finish:effects-done"}.get(state, ""))
