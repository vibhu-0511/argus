"""The ticket-to-fix workflow as a DBOS workflow with durable steps (P6-T03).

One workflow per ticket, id = the ticket id (see `flow.dbos_runtime`). Its body only decides the
order: each pipeline state runs one DBOS step, and the next state comes from `flow.states.next_state`
and nowhere else, so an illegal move raises `IllegalTransition` instead of happening. Step results
are stored by DBOS in its system database.

DBOS runs a step at least once and never again after its result is stored. A crash between a
side effect and that store re-runs the step, so every effect is keyed (`flow.states.effect_key`,
`branch_name`) and the runner or GitHub client finds the effect it already made before acting.
The runners and the GitHub client are injected (`Deps`); the real Actions dispatch is T04.

The workflow stops at `awaiting-qa` and waits for the QA signal with `DBOS.recv` (P6-T08, signal
side in `flow.qa`). Approve ends in `done` and marks the PR ready for review, reject ends in
`rejected` and closes the PR, and no signal within the configured timeout ends in `timed-out` with
the PR left open and draft. The deadline is stored by DBOS, so a restart continues the same wait
instead of starting a new one.

ponytail: the injected `Deps` is process-global because a DBOS workflow is a module-level function
registered once, and one process runs one DBOS. Fine for one executor on Render; a second
application in the same process would need the deps passed through the workflow input.
"""

from __future__ import annotations

from typing import Any, NamedTuple, Protocol

from dbos import DBOS
from dbos._error import DBOSMaxStepRetriesExceeded  # not exported by dbos/__init__ in 3.4.0

from flow.config import DEFAULT_QA_TIMEOUT_SECONDS
from flow.qa import QA_TOPIC
from flow.states import (
    TERMINAL,
    Event,
    State,
    branch_name,
    effect_key,
    next_state,
    START,
)


class Outcome(NamedTuple):
    ok: bool
    output: str = ""  # repro script, patch or verdict text; the next step's upstream input


class PullRequest(NamedTuple):
    number: int
    url: str
    draft: bool


class Runner(Protocol):
    """Runs one dispatch step (repro, fix or verify). T04 backs it with GitHub Actions."""

    def run(self, ticket_id: str, run_key: str, upstream: str) -> Outcome:
        """Find the run for `run_key` and wait for it, else start it. Never starts a second one."""


class GitHubClient(Protocol):
    def push_branch(self, branch: str, patch: str, key: str) -> None:
        """Make `branch` carry the patch commit of `key`; a repeat of the same key changes nothing."""

    def find_pr(self, branch: str) -> PullRequest | None:
        """The PR with head `branch`, in any state, or None. A lookup error must raise."""

    def create_draft_pr(self, branch: str, title: str, body: str) -> PullRequest: ...

    def ready_pr(self, branch: str) -> None:
        """Mark the PR of `branch` ready for review; skip when it is not a draft (`ready-pr`)."""

    def close_pr(self, branch: str) -> None:
        """Close the PR of `branch` unmerged; skip when it is already closed (`close-pr`)."""

    def post_comment(self, ticket_id: str, key: str, body: str) -> None:
        """Skip when a comment with `key`'s marker exists (`flow.states.comment_marker`)."""

    def set_label(self, ticket_id: str, state: str) -> None:
        """Label the issue `argus:<state>` and drop its other `argus:*` labels."""


class Deps(NamedTuple):
    repro: Runner
    fix: Runner
    verify: Runner
    github: GitHubClient
    qa_timeout_seconds: float | None = None  # None: the default in flow.config; `launch` fills it from settings


_deps: Deps | None = None


def set_deps(deps: Deps) -> None:
    global _deps
    _deps = deps


def _need() -> Deps:
    if _deps is None:
        raise RuntimeError("flow.workflow.set_deps() was not called")
    return _deps


def find_or_create_pr(github: GitHubClient, ticket_id: str) -> PullRequest:
    """One stable branch per ticket, found before created, draft until QA, no `closes #N`.

    A lookup that raises propagates: an error is not "no PR", so nothing is created.
    """
    branch = branch_name(ticket_id)
    found = github.find_pr(branch)
    if found is not None:
        return found
    return github.create_draft_pr(branch, f"Argus fix for {ticket_id}", f"Draft fix for {ticket_id}, awaiting QA.")


# ponytail: three attempts, 0.5 s then 1 s apart. Enough for a blip; GitHub secondary rate limits
# want a longer interval, tune it with the real client in T04.
_RETRY = {"retries_allowed": True, "max_attempts": 3, "interval_seconds": 0.5, "backoff_rate": 2.0}


def _result(outcome: Outcome, **extra: Any) -> dict[str, Any]:
    return {"ok": outcome.ok, "output": outcome.output, **extra}


@DBOS.step(**_RETRY)
def repro_step(ticket_id: str, upstream: str) -> dict[str, Any]:
    return _result(_need().repro.run(ticket_id, effect_key(ticket_id, "dispatch-repro"), upstream))


@DBOS.step(**_RETRY)
def fix_step(ticket_id: str, repro_script: str) -> dict[str, Any]:
    return _result(_need().fix.run(ticket_id, effect_key(ticket_id, "dispatch-fix"), repro_script))


@DBOS.step(**_RETRY)
def verify_step(ticket_id: str, patch: str) -> dict[str, Any]:
    return _result(_need().verify.run(ticket_id, effect_key(ticket_id, "dispatch-verify"), patch))


@DBOS.step(**_RETRY)
def open_pr_step(ticket_id: str, patch: str) -> dict[str, Any]:
    github = _need().github
    github.push_branch(branch_name(ticket_id), patch, effect_key(ticket_id, "push-branch"))
    pr = find_or_create_pr(github, ticket_id)
    github.post_comment(ticket_id, effect_key(ticket_id, "comment-awaiting-qa"), f"Draft PR: {pr.url}. Awaiting QA.")
    github.set_label(ticket_id, State.AWAITING_QA.value)
    return _result(Outcome(True, pr.url), number=pr.number, draft=pr.draft)


@DBOS.step(**_RETRY)
def finish_step(ticket_id: str, state: str, reason: str) -> dict[str, Any]:
    """The effects of the terminal state, in the order of `states.STATES`: PR, comment, label.

    `done` marks the PR ready for review and `rejected` closes it; `failed` and `timed-out` leave
    it as it is. Both PR effects are keyed by the stable branch and skip when already done.
    """
    github = _need().github
    if state == State.DONE.value:
        github.ready_pr(branch_name(ticket_id))
    elif state == State.REJECTED.value:
        github.close_pr(branch_name(ticket_id))
    github.post_comment(ticket_id, effect_key(ticket_id, f"comment-{state}"), f"Argus: {state}. {reason}".strip())
    github.set_label(ticket_id, state)
    return _result(Outcome(True, state))


# state -> (step, state whose output it takes, event on success, event on failure)
_PIPELINE = {
    State.REPRODUCING: (repro_step, None, Event.REPRO_OK, Event.REPRO_FAILED),
    State.FIXING: (fix_step, State.REPRODUCING, Event.FIX_OK, Event.FIX_FAILED),
    State.VERIFYING: (verify_step, State.FIXING, Event.VERIFY_OK, Event.VERIFY_FAILED),
    State.OPENING_PR: (open_pr_step, State.FIXING, Event.PR_OPENED, Event.PR_FAILED),
}


def _run(step: Any, ticket_id: str, upstream: str) -> dict[str, Any]:
    try:
        return step(ticket_id, upstream)
    except DBOSMaxStepRetriesExceeded as e:  # the step raised on every attempt
        return {"ok": False, "output": f"{step.__name__} failed after {e.max_retries} attempts"}


_DECISION_EVENT = {"approve": Event.QA_APPROVED, "reject": Event.QA_REJECTED}


def await_qa(ticket_id: str) -> tuple[State, str]:
    """Wait for the QA signal (`flow.qa`) and return the state it leads to and the reason.

    The first message decides. A message is validated before it is sent, so an unknown decision
    here means a writer bypassed `send_qa_signal`; it raises KeyError and the workflow ends in ERROR.
    ponytail: one `recv`, so the timeout is for the whole wait. Fine while there is one signal path
    per ticket; a second reviewer step would need its own wait.
    """
    deps = _need()
    timeout = deps.qa_timeout_seconds if deps.qa_timeout_seconds is not None else DEFAULT_QA_TIMEOUT_SECONDS
    msg = DBOS.recv(QA_TOPIC, timeout_seconds=timeout)
    if msg is None:
        return next_state(State.AWAITING_QA, Event.QA_TIMEOUT), f"no QA signal within {timeout:g} s"
    by = f" by {msg['by']}" if msg.get("by") else ""
    return next_state(State.AWAITING_QA, _DECISION_EVENT[msg["decision"]]), f"{msg['decision']} via {msg['source']}{by}"


@DBOS.workflow()
def ticket_workflow(ticket_id: str) -> dict[str, Any]:
    state = next_state(START, Event.START)
    trail = [START.value, state.value]
    outputs: dict[State, str] = {}
    reason = ""
    while state in _PIPELINE:
        step, source, ok_event, failed_event = _PIPELINE[state]
        result = _run(step, ticket_id, outputs.get(source, ""))
        outputs[state] = result["output"]
        if not result["ok"]:
            reason = f"{state.value}: {result['output']}"
        state = next_state(state, ok_event if result["ok"] else failed_event)
        trail.append(state.value)
    if state is State.AWAITING_QA:
        state, reason = await_qa(ticket_id)
        trail.append(state.value)
    assert state in TERMINAL
    finish_step(ticket_id, state.value, reason)
    return {"ticket_id": ticket_id, "state": state.value, "trail": trail, "reason": reason}
