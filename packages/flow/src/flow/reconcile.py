"""Reconciliation poller: rebuild a ticket's state from GitHub, never from a webhook (P6-T07).

GitHub is the source of truth. A webhook is only a hint (`flow.webhook`), and a hint can be lost
(Render asleep, GitHub's 10 s timeout, a redeploy). The poller reads what GitHub shows for a
ticket, maps it onto a `flow.states.State` with the pure `derive_state`, and starts the ticket
workflow through the same `Enqueuer` the webhook uses, so both paths meet on `SetWorkflowID(ticket_id)`.

`Reconciler.reconcile(ticket_id)`:
1. reads GitHub (`GitHubReader`, read-only); a lookup error raises and nothing else happened;
2. derives the state from the "GitHub shows" column of `flow.states.STATES`;
3. asks `WorkflowLookup` whether the workflow exists. None and the state is not terminal: enqueue it.
   The workflow then re-walks its keyed steps, each of which finds the run, branch and PR GitHub
   already shows (`flow.workflow`), so it lands at the derived state and opens no second PR. A
   workflow that exists is never enqueued again; the result reports the state to resume at. A
   terminal state with no workflow is only reported: there is nothing left to run.

The poller never creates a PR, a branch, a label or a comment itself, and it never writes to GitHub.

`Reconciler.poll_once()` lists open tickets and reconciles each; `poll_forever` is the loop the
service will run later (not deployed here). Poll defaults are a choice for ADR-021/022 to confirm:
see `PollConfig`. No cost is claimed for them; T14 measures Neon.

ponytail: the poller starts a workflow only when none exists. A workflow stuck in ERROR or CANCELLED
keeps its id, so it is reported (`workflow_status`), not restarted. Resuming it is DBOS recovery (T19).
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Mapping, NamedTuple, Protocol

from flow.enqueue import Enqueuer
from flow.states import TERMINAL, State, workflow_id

log = logging.getLogger("flow.reconcile")

REPO_ENV = "ARGUS_FLOW_REPO"
LABEL_ENV = "ARGUS_FLOW_TICKET_LABEL"
PAGE_SIZE_ENV = "ARGUS_FLOW_POLL_PAGE_SIZE"
MAX_PAGES_ENV = "ARGUS_FLOW_POLL_MAX_PAGES"
INTERVAL_ENV = "ARGUS_FLOW_POLL_INTERVAL_S"


class NotATicket(ValueError):
    """The number names a pull request, not an issue. Nothing is started for it."""


class GitHubReadError(RuntimeError):
    """A GitHub read failed. The message has the method, path and status, never a header or token."""


@dataclass(frozen=True)
class PrView:
    number: int
    state: str  # "open" or "closed"
    draft: bool
    merged: bool


@dataclass(frozen=True)
class RunView:
    status: str  # queued, in_progress, completed
    conclusion: str | None  # success, failure, cancelled, ... once completed


@dataclass(frozen=True)
class GitHubState:
    """Only what GitHub shows for one ticket. No workflow state in here."""

    ticket_id: str
    issue_open: bool
    labels: frozenset[str]  # issue label names
    branch_exists: bool  # the stable branch `flow.states.branch_name`
    pr: PrView | None  # the PR whose head is the stable branch, in any state
    runs: Mapping[str, RunView] = field(default_factory=dict)  # step ("repro", "fix", "verify") -> latest run
    markers: frozenset[str] = frozenset()  # states whose comment marker (`comment_marker`) is on the issue


class GitHubReader(Protocol):
    """Read-only. Every method raises on an error: an error is never "nothing there"."""

    def read_github_state(self, ticket_id: str) -> GitHubState: ...

    def list_open_tickets(self, repo: str, label: str | None, page_size: int, max_pages: int) -> list[str]: ...


class WorkflowView(NamedTuple):
    status: str  # DBOS status: ENQUEUED, PENDING, SUCCESS, ERROR, CANCELLED, ...
    state: str | None  # the final state in the workflow's output, once it has finished


class WorkflowLookup(Protocol):
    def get(self, ticket_id: str) -> WorkflowView | None: ...


class DbosLookup:
    """Reads the workflow with id `workflow_id(ticket_id)` from the DBOS system database."""

    def get(self, ticket_id: str) -> WorkflowView | None:
        from dbos import DBOS

        status = DBOS.get_workflow_status(workflow_id(ticket_id))
        if status is None:
            return None
        output = status.output if isinstance(status.output, dict) else {}
        return WorkflowView(status.status, output.get("state"))


# More than one terminal sign at once means a label lagged behind; the first listed wins.
_TERMINAL_ORDER = (State.DONE, State.REJECTED, State.TIMED_OUT, State.FAILED)


def derive_state(g: GitHubState) -> State:
    """Map what GitHub shows onto a state. Pure: same input, same answer, no I/O.

    Follows the "GitHub shows" column of `flow.states.STATES`. Order matters, strongest evidence first:
    the PR (merged, closed, ready for review), then terminal labels and comment markers, then a failed
    run, then a closed issue, then an open draft PR or branch, then the furthest concluded run.

    ponytail: any concluded run that is not `success` counts as failed (failure, cancelled, timed_out,
    startup_failure, skipped, ...). Only attempt 1 of a step is read (`effect_key` default). A ready
    (non-draft) open PR is `done`, as the table says, even if a human marked it ready.
    """
    pr = g.pr
    if pr is not None:
        if pr.merged:
            return State.DONE
        if pr.state == "closed":
            return State.REJECTED
        if not pr.draft:
            return State.DONE
    signs = g.labels | {f"argus:{s}" for s in g.markers}
    for state in _TERMINAL_ORDER:
        if f"argus:{state.value}" in signs:
            return state
    if any(r.status == "completed" and r.conclusion != "success" for r in g.runs.values()):
        return State.FAILED
    if not g.issue_open:
        return State.REJECTED  # someone closed the ticket before a PR existed: stop
    if pr is not None and f"argus:{State.AWAITING_QA.value}" in g.labels:
        return State.AWAITING_QA
    if pr is not None or g.branch_exists:
        return State.OPENING_PR
    done = {step for step, r in g.runs.items() if r.conclusion == "success"}
    if "verify" in done:
        return State.OPENING_PR
    if "fix" in done:
        return State.VERIFYING
    if "repro" in done:
        return State.FIXING
    return State.REPRODUCING if g.runs else State.RECEIVED


@dataclass(frozen=True)
class Reconciled:
    ticket_id: str
    state: State  # what GitHub shows: the state to resume at
    action: str  # "started" (enqueued now), "exists" (workflow already there), "settled" (terminal, no workflow)
    workflow_status: str | None = None
    workflow_state: str | None = None

    @property
    def diverged(self) -> bool:
        """The finished workflow ended in a different state than GitHub shows now."""
        return self.workflow_state is not None and self.workflow_state != self.state.value


@dataclass(frozen=True)
class PollConfig:
    """What `poll_once` and `poll_forever` read. Defaults are a choice, not a measurement.

    ponytail: 30 tickets a page, 3 pages, every 300 s. The bounds keep one poll to at most
    `page_size * max_pages` tickets at about five GitHub reads each; the interval is the longest a
    lost hint can wait. ADR-021/022 confirm or change these against the GitHub rate limit, the free
    Render sleep and Neon's scale-to-zero (T13, T14). Beyond `page_size * max_pages` open tickets
    the least recently updated are not polled. An in-process loop runs only while the service is
    awake, so it cannot wake a sleeping Render service.
    """

    repo: str = ""  # "owner/name"
    label: str | None = None  # only issues with this label; None = every open issue, like the webhook
    page_size: int = 30
    max_pages: int = 3
    interval_s: float = 300.0

    @classmethod
    def from_env(cls) -> PollConfig:
        repo = os.environ.get(REPO_ENV, "")
        if repo.count("/") != 1 or not all(repo.split("/")):
            raise RuntimeError(f"{REPO_ENV} must be set to owner/name")
        cfg = cls(
            repo=repo,
            label=os.environ.get(LABEL_ENV) or None,
            page_size=int(os.environ.get(PAGE_SIZE_ENV, cls.page_size)),
            max_pages=int(os.environ.get(MAX_PAGES_ENV, cls.max_pages)),
            interval_s=float(os.environ.get(INTERVAL_ENV, cls.interval_s)),
        )
        if not 1 <= cfg.page_size <= 100:  # GitHub's per_page maximum
            raise RuntimeError(f"{PAGE_SIZE_ENV} must be 1 to 100")
        if cfg.max_pages < 1:
            raise RuntimeError(f"{MAX_PAGES_ENV} must be at least 1")
        if cfg.interval_s < 60:  # ponytail: floor of 60 s so a typo cannot hammer the GitHub API
            raise RuntimeError(f"{INTERVAL_ENV} must be at least 60")
        return cfg


@dataclass(frozen=True)
class PollResult:
    reconciled: list[Reconciled]
    errors: dict[str, str]  # ticket id -> reason; those tickets were left untouched


class Reconciler:
    def __init__(self, reader: GitHubReader, workflows: WorkflowLookup, enqueuer: Enqueuer, config: PollConfig | None = None) -> None:
        self.reader, self.workflows, self.enqueuer = reader, workflows, enqueuer
        self.config = config or PollConfig()

    def reconcile(self, ticket_id: str) -> Reconciled:
        """Read, derive, compare, then maybe start. Any error before the enqueue leaves everything untouched."""
        state = derive_state(self.reader.read_github_state(ticket_id))
        existing = self.workflows.get(ticket_id)
        if existing is not None:
            return Reconciled(ticket_id, state, "exists", existing.status, existing.state)
        if state in TERMINAL:
            return Reconciled(ticket_id, state, "settled")
        self.enqueuer.enqueue_reconcile(ticket_id)  # same workflow id as the webhook: a race is absorbed
        return Reconciled(ticket_id, state, "started")

    def poll_once(self) -> PollResult:
        """Reconcile every listed open ticket. A failed listing raises; a failed ticket is reported and skipped."""
        cfg = self.config
        tickets = self.reader.list_open_tickets(cfg.repo, cfg.label, cfg.page_size, cfg.max_pages)
        reconciled: list[Reconciled] = []
        errors: dict[str, str] = {}
        for ticket_id in tickets:
            try:
                reconciled.append(self.reconcile(ticket_id))
            except Exception as e:  # one ticket's error must not stop the others
                errors[ticket_id] = str(e) if isinstance(e, (GitHubReadError, NotATicket)) else type(e).__name__
                log.warning("reconcile of %s failed: %s", ticket_id, errors[ticket_id])
        return PollResult(reconciled, errors)


async def poll_forever(poller: Reconciler, stop: asyncio.Event) -> None:
    """Run `poll_once` every `config.interval_s` until `stop` is set. The service starts it later:

        stop = asyncio.Event()
        task = asyncio.create_task(poll_forever(poller, stop))   # in the app's lifespan
        ...
        stop.set(); await task                                   # on shutdown

    `poll_once` is blocking (httpx, DBOS), so it runs in a thread. A failed poll is logged and the
    loop goes on; the next tick tries again.
    """
    while not stop.is_set():
        try:
            await asyncio.to_thread(poller.poll_once)
        except Exception:
            log.exception("poll failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=poller.config.interval_s)
        except asyncio.TimeoutError:
            pass
