"""Workflow state machine for one ticket: states, legal transitions, idempotency keys.

Pure Python. No DBOS, no network, no clock, no randomness. The DBOS workflow (P6-T03) calls
`next_state` to decide where it goes, the reconciliation poller (P6-T07) reads `STATES` to map
GitHub objects back to a state, and the keys name every side effect so a retry can find it.
`markdown_tables()` renders the tables in docs/notes/p6-state-machine.md; a test keeps them equal.

ponytail: one state per pipeline step, no retry loop back from `verifying` to `fixing`. The fix
loop already retries its own verify (fix_loop VERIFY_RETRIES); a second loop here would need an
attempt guard in `next_state`. Add it when the P5 results show verify-then-refix pays.
"""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import NamedTuple


class State(StrEnum):
    RECEIVED = "received"
    REPRODUCING = "reproducing"
    FIXING = "fixing"
    VERIFYING = "verifying"
    OPENING_PR = "opening-pr"
    AWAITING_QA = "awaiting-qa"
    DONE = "done"
    FAILED = "failed"
    REJECTED = "rejected"
    TIMED_OUT = "timed-out"


class Event(StrEnum):
    START = "start"
    REPRO_OK = "repro_ok"
    REPRO_FAILED = "repro_failed"
    FIX_OK = "fix_ok"
    FIX_FAILED = "fix_failed"
    VERIFY_OK = "verify_ok"
    VERIFY_FAILED = "verify_failed"
    PR_OPENED = "pr_opened"
    PR_FAILED = "pr_failed"
    QA_APPROVED = "qa_approved"
    QA_REJECTED = "qa_rejected"
    QA_TIMEOUT = "qa_timeout"


START = State.RECEIVED
TERMINAL = frozenset({State.DONE, State.FAILED, State.REJECTED, State.TIMED_OUT})


class IllegalTransition(ValueError):
    """`event` is not allowed in `state`. The caller drops or reports it; the state does not move."""


# (from, event, to, what fires the event). One row per legal transition; anything else is illegal.
# A step event fires when the step's last effect is done and its result is stored.
TRANSITIONS: tuple[tuple[State, Event, State, str], ...] = (
    (State.RECEIVED, Event.START, State.REPRODUCING, "workflow body begins for a new ticket"),
    (State.REPRODUCING, Event.REPRO_OK, State.FIXING, "repro run concluded success and returned a script"),
    (State.REPRODUCING, Event.REPRO_FAILED, State.FAILED, "repro run failed, was cancelled, or did not reproduce"),
    (State.FIXING, Event.FIX_OK, State.VERIFYING, "fix run concluded success and returned a patch"),
    (State.FIXING, Event.FIX_FAILED, State.FAILED, "fix run failed, was cancelled, or hit its budget"),
    (State.VERIFYING, Event.VERIFY_OK, State.OPENING_PR, "verify run concluded success and the verdict is ok"),
    (State.VERIFYING, Event.VERIFY_FAILED, State.FAILED, "verify run failed or the verdict is not ok"),
    (State.OPENING_PR, Event.PR_OPENED, State.AWAITING_QA, "draft PR exists on the stable branch"),
    (State.OPENING_PR, Event.PR_FAILED, State.FAILED, "GitHub refused the branch or PR after the step retries"),
    (State.AWAITING_QA, Event.QA_APPROVED, State.DONE, "first approve signal (review comment or MRTR answer)"),
    (State.AWAITING_QA, Event.QA_REJECTED, State.REJECTED, "first reject signal"),
    (State.AWAITING_QA, Event.QA_TIMEOUT, State.TIMED_OUT, "the durable QA deadline passed with no signal"),
)

_NEXT = {(frm, ev): to for frm, ev, to, _ in TRANSITIONS}
assert len(_NEXT) == len(TRANSITIONS), "duplicate (state, event) row"


def next_state(state: State, event: Event) -> State:
    """The state after `event`, or IllegalTransition. Duplicate signals are deduped by key before this."""
    try:
        return _NEXT[State(state), Event(event)]
    except KeyError:
        raise IllegalTransition(f"event {Event(event).value!r} is not legal in state {State(state).value!r}") from None


class StateInfo(NamedTuple):
    github_object: str
    evidence: str  # what GitHub shows while this state is current; the poller (T07) reads this
    effects: tuple[str, ...]  # effect names (see EFFECTS) the step runs before it fires its event


STATES: dict[State, StateInfo] = {
    State.RECEIVED: StateInfo("issue", "issue open; no `argus:*` run, no branch, no PR", ("start-workflow",)),
    State.REPRODUCING: StateInfo(
        "Actions run", "a `dispatch-repro` run is queued or in progress, none concluded", ("dispatch",)
    ),
    State.FIXING: StateInfo(
        "Actions run", "`dispatch-repro` concluded success; no `dispatch-fix` run concluded", ("dispatch",)
    ),
    State.VERIFYING: StateInfo(
        "Actions run", "`dispatch-fix` concluded success; no `dispatch-verify` run concluded", ("dispatch",)
    ),
    State.OPENING_PR: StateInfo(
        "branch, PR",
        "`dispatch-verify` concluded success; PR missing, or present without label `argus:awaiting-qa`",
        ("push-branch", "open-pr", "post-comment", "set-label"),
    ),
    State.AWAITING_QA: StateInfo(
        "PR", "draft PR on the stable branch, open, issue labelled `argus:awaiting-qa`", ("record-qa-signal",)
    ),
    State.DONE: StateInfo(
        "PR", "PR ready for review or merged; issue labelled `argus:done`", ("ready-pr", "post-comment", "set-label")
    ),
    State.FAILED: StateInfo(
        "issue", "any step run concluded failure or cancelled; issue labelled `argus:failed`", ("post-comment", "set-label")
    ),
    State.REJECTED: StateInfo(
        "PR", "PR closed unmerged; issue labelled `argus:rejected`", ("close-pr", "post-comment", "set-label")
    ),
    State.TIMED_OUT: StateInfo(
        "PR", "PR still open and draft; issue labelled `argus:timed-out`", ("post-comment", "set-label")
    ),
}


class Effect(NamedTuple):
    github_object: str
    key: str  # what makes it the same effect on a retry
    find: str  # how a retry finds the existing effect before acting


EFFECTS: dict[str, Effect] = {
    "start-workflow": Effect(
        "issue",
        "workflow id = `<ticket_id>`",
        "enqueue with the same workflow id; DBOS returns the existing workflow, so a second enqueue is a no-op",
    ),
    "dispatch": Effect(
        "Actions run",
        "`argus:<ticket_id>:dispatch-<step>:<attempt>`, sent as input `run_key` and used as the run's `run-name`",
        "list `workflow_dispatch` runs of the workflow and match the run title to the key; found: wait for it, "
        "do not dispatch. A concurrency group on the key allows one running and one pending run",
    ),
    "push-branch": Effect(
        "branch",
        "branch `argus/<slug>-<hash8>` (no attempt in it) and commit trailer `Argus-Key: argus:<ticket_id>:push-branch:<attempt>`",
        "GET the branch ref; its head commit carries the trailer: done. Ref missing: create it. Ref exists without "
        "the trailer: add the patch commit on top. Never force-push",
    ),
    "open-pr": Effect(
        "PR",
        "the head branch (one stable branch per ticket); opened as draft",
        "list PRs with `head=<owner>:<branch>` and `state=all`; found: reuse it, any state. None: create a draft. "
        "A lookup error raises and creates nothing. No `closes #N` or commit-message search",
    ),
    "post-comment": Effect(
        "issue comment",
        "`argus:<ticket_id>:comment-<state>:<attempt>`, written into the body as `<!-- argus-key: <key> -->`",
        "list the issue comments and look for the marker; found: skip, do not edit",
    ),
    "set-label": Effect(
        "issue label",
        "label `argus:<state>`; adding a label that is present changes nothing",
        "read the issue labels; add `argus:<state>`, then remove other `argus:*` labels, ignoring 404",
    ),
    "ready-pr": Effect(
        "PR",
        "the PR of the stable branch",
        "read `isDraft`; already false: skip. Otherwise mark ready for review",
    ),
    "close-pr": Effect(
        "PR",
        "the PR of the stable branch",
        "read `state`; already closed: skip. Otherwise close it (reopenable)",
    ),
    "record-qa-signal": Effect(
        "none (workflow store)",
        "`argus:<ticket_id>:qa:<source>:<source_id>`, source is `review-comment` or `mrtr`",
        "the first signal moves the state; a repeat of the same key is dropped; a different key after the state "
        "left `awaiting-qa` hits IllegalTransition and is dropped",
    ),
}

DISPATCH_STEPS = ("repro", "fix", "verify")
_COMMENT_STATES = (State.AWAITING_QA, State.DONE, State.FAILED, State.REJECTED, State.TIMED_OUT)
_EFFECT_NAMES = frozenset(
    {f"dispatch-{s}" for s in DISPATCH_STEPS} | {"push-branch"} | {f"comment-{s.value}" for s in _COMMENT_STATES}
)
QA_SOURCES = frozenset({"review-comment", "mrtr"})


def _need(ticket_id: str, attempt: int = 1) -> None:
    if not ticket_id:
        raise ValueError("ticket_id must not be empty")
    if attempt < 1:
        raise ValueError("attempt starts at 1")


def workflow_id(ticket_id: str) -> str:
    """The webhook and the poller both enqueue with this id, so one ticket is one workflow."""
    _need(ticket_id)
    return ticket_id


def branch_name(ticket_id: str) -> str:
    """One stable branch per ticket. The hash keeps `a/b#1` and `a-b-1` apart; the slug is for humans."""
    _need(ticket_id)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ticket_id).strip("-").lower()[:40].strip("-") or "ticket"
    return f"argus/{slug}-{hashlib.sha1(ticket_id.encode()).hexdigest()[:8]}"


def effect_key(ticket_id: str, effect: str, attempt: int = 1) -> str:
    """Key of a step effect: `dispatch-<step>`, `push-branch` or `comment-<state>`.

    `attempt` is 1 until a deliberate re-run of a ticket exists; a retry of the same step after a
    crash keeps the same attempt, which is what lets it find the effect it already made.
    """
    _need(ticket_id, attempt)
    if effect not in _EFFECT_NAMES:
        raise ValueError(f"unknown effect {effect!r}")
    return f"argus:{ticket_id}:{effect}:{attempt}"


def qa_signal_key(ticket_id: str, source: str, source_id: str) -> str:
    """Key of one QA signal, from where it came from: a review comment id or an MRTR request id."""
    _need(ticket_id)
    if source not in QA_SOURCES:
        raise ValueError(f"unknown QA source {source!r}")
    if not source_id:
        raise ValueError("source_id must not be empty")
    return f"argus:{ticket_id}:qa:{source}:{source_id}"


def comment_marker(key: str) -> str:
    """Hidden line written into a comment body so a retry can find the comment by its key."""
    return f"<!-- argus-key: {key} -->"


def markdown_tables() -> str:
    """The three tables in docs/notes/p6-state-machine.md, generated so they cannot drift from the code."""
    def code(text: str) -> str:
        return f"`{text}`"

    kind = lambda s: "start" if s == START else "terminal" if s in TERMINAL else "active"  # noqa: E731
    out = ["### States", "", "| State | Kind | GitHub object | GitHub shows | Effects |", "|---|---|---|---|---|"]
    for s, i in STATES.items():
        out.append(f"| {code(s.value)} | {kind(s)} | {i.github_object} | {i.evidence} | {', '.join(map(code, i.effects))} |")
    out += ["", "### Transitions", "", "| From | Event | To | Fires when |", "|---|---|---|---|"]
    for frm, ev, to, why in TRANSITIONS:
        out.append(f"| {code(frm.value)} | {code(ev.value)} | {code(to.value)} | {why} |")
    out += ["", "### Side effects", "", "| Effect | GitHub object | Idempotency key | A retry finds it by |", "|---|---|---|---|"]
    for name, e in EFFECTS.items():
        out.append(f"| {code(name)} | {e.github_object} | {e.key} | {e.find} |")
    return "\n".join(out)
