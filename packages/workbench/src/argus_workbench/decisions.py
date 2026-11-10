"""The reviewer's decision (screen 3): approve, request changes or reject. Every rule is enforced here, on the server.

    decide(run_id, DecisionRequest(...))        # -> DecisionResult; the route /api/runs/{id}/decision calls this

Rules (P10-T07):
- Approve is refused (`verifier_failed`) when the verifier failed. When the judge says fail while the checks pass, it
  needs a written reason (`reason_required`). The judge never changes the verdict; it is advisory (ADR-013).
- Request changes needs a note. It creates a NEW run folder in state `received` (created_by_retry_of = this run,
  same ticket, scenario and origin) with the note in its intake.json, and does not start it; the page calls start.
- Reject needs a reason from the spec's `targets.reasons.reject`; "Other (say what)" also needs text in `note`.
- decision.json is written once. The same idempotency key again returns the stored decision unchanged; a different key
  after a decision exists is a typed 409 `already_decided`.
- Approve and reject move a run that is in `awaiting-qa` to `done` / `rejected` (flow's QA_APPROVED / QA_REJECTED).
  A run in `failed` (verifier failed) keeps its state. Request changes never changes the old run's state.

Hook for the PR screen (T08), no edit of this file needed:

    from argus_workbench import decisions
    decisions.ON_APPROVE.append(my_callback)     # my_callback(run_id: str, decision: store.Decision) -> None

Callbacks run once, after an approve was stored and the state moved (state is then `done`), in list order, never on an
idempotent replay. A callback may raise `WorkbenchError`; the decision stays stored and the error is returned in
`hook_errors`. Any other exception is a bug and propagates.

ponytail: one process-wide lock around decide; two server processes on one store would need a file lock.
ponytail: no timed-out ("Re-request review") and no check/judge `error` state: the verdict file has only pass/fail.
"""

from __future__ import annotations

import shutil
import threading
from collections.abc import Callable
from typing import Literal

from argus_core.types import Screenshot, Ticket
from flow.states import Event, State
from pydantic import BaseModel, ConfigDict, Field

from argus_workbench import store
from argus_workbench.errors import WorkbenchError
from argus_workbench.spec import load_spec

ON_APPROVE: list[Callable[[str, store.Decision], None]] = []
_LOCK = threading.Lock()
_REVIEWABLE = (State.AWAITING_QA, State.FAILED)
MAX_TEXT = 2000
Action = Literal["approve", "request-changes", "reject"]


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    reason: str | None = Field(default=None, max_length=MAX_TEXT)
    note: str | None = Field(default=None, max_length=MAX_TEXT)
    idempotency_key: str = Field(min_length=1, max_length=128)


class DecisionResult(BaseModel):
    decision: store.Decision
    replayed: bool = False
    new_run_id: str | None = None
    hook_errors: list[dict] = []


def reject_reasons() -> list[str]:
    return list(load_spec()["targets"]["reasons"]["reject"])


def change_reasons() -> list[str]:
    return list(load_spec()["targets"]["reasons"]["changes"])


def approve_gate(verdict: store.Verdict, state: store.RunState) -> dict:
    """What Approve needs for this run: {enabled, needs_reason, disabled_reason}. The page shows it; `decide` enforces it."""
    if not verdict.ok:
        return {"enabled": False, "needs_reason": False, "disabled_reason": f"the verifier failed: {verdict.first_failure}"}
    if state.state != State.AWAITING_QA:
        return {"enabled": False, "needs_reason": False, "disabled_reason": f"the run is {state.display_state}, not awaiting review"}
    return {"enabled": True, "needs_reason": verdict.judge_label == "fail", "disabled_reason": None}


def stored_decision(run_id: str, *, root=None) -> store.Decision | None:
    return store.read_file(run_id, "decision.json", root=root) if store.has_file(run_id, "decision.json", root=root) else None


def follow_up_run_id(run_id: str, *, root=None) -> str | None:
    """The run that "Request changes" created from `run_id`, if any (newest first)."""
    return next((s.run_id for s in store.list_runs(root=root) if s.created_by_retry_of == run_id), None)


def _text(value: str | None) -> str:
    return (value or "").strip()


def _clean(req: DecisionRequest, verdict: store.Verdict, state: store.RunState) -> tuple[Action, str | None]:
    """Check the rules for this action; return (action, the reason to store)."""
    if req.action not in ("approve", "request-changes", "reject"):
        raise WorkbenchError("invalid_action", "action must be approve, request-changes or reject", field="action")
    action: Action = req.action  # type: ignore[assignment]
    reason, note = _text(req.reason), _text(req.note)
    if state.state not in _REVIEWABLE:
        raise WorkbenchError("not_reviewable", f"a run that is {state.display_state} cannot be decided", field="action", status=409)
    if action == "approve":
        gate = approve_gate(verdict, state)
        if not gate["enabled"]:
            code = "verifier_failed" if not verdict.ok else "not_reviewable"
            raise WorkbenchError(code, f"Approve is refused: {gate['disabled_reason']}", field="action", status=409)
        if gate["needs_reason"] and not reason:
            raise WorkbenchError("reason_required", "the judge says fail: Approve needs a written reason", field="reason")
        return action, reason or note or None
    if action == "request-changes":
        if not note:
            raise WorkbenchError("note_required", "Request changes needs a note for the next run", field="note")
        if reason and reason not in change_reasons():
            raise WorkbenchError("unknown_reason", "reason is not in the list of change reasons", field="reason")
        return action, note
    if not reason:
        raise WorkbenchError("reason_required", "Reject needs a reason", field="reason")
    if reason not in reject_reasons():
        raise WorkbenchError("unknown_reason", "reason is not in the list of reject reasons", field="reason")
    if reason.startswith("Other"):
        if not note:
            raise WorkbenchError("note_required", "Other needs text saying what", field="note")
        return action, f"Other: {note}"
    return action, reason


def _copy_ticket(ticket: Ticket, old_id: str, new_id: str, root) -> Ticket:
    """The ticket for the new run. A screenshot file is copied along; if it is gone the new ticket drops it."""
    shot: Screenshot | None = ticket.screenshot
    if shot is not None:
        src = store.run_dir(old_id, root) / shot.path
        if src.is_file() and src.resolve().is_relative_to(store.run_dir(old_id, root)):
            dest = store.run_dir(new_id, root) / shot.path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
        else:
            ticket = ticket.model_copy(update={"screenshot": None})
    return ticket


def _open_follow_up(run_id: str, state: store.RunState, note: str, reason: str | None, clock, root) -> str:
    """Create the next run (received, not started) with the reviewer's note in its intake.json."""
    intake = store.read_file(run_id, "intake.json", root=root).model_dump()
    new_id = store.new_run_id()
    ticket = store.read_file(run_id, "ticket.json", root=root)
    store.create_run(ticket, scenario=state.scenario, origin=state.origin, run_id=new_id, retry_of=run_id, clock=clock, root=root)
    try:
        if ticket.screenshot is not None:
            ticket = _copy_ticket(ticket, run_id, new_id, root)
            store.write_file(new_id, "ticket.json", ticket, root=root)
        store.write_file(new_id, "intake.json", {**intake, "reviewer_note": note, "change_reason": reason}, root=root)
    except BaseException:
        shutil.rmtree(store.run_dir(new_id, root), ignore_errors=True)
        raise
    return new_id


def decide(run_id: str, req: DecisionRequest, *, clock=store.utc_now, root=None) -> DecisionResult:
    with _LOCK:
        state = store.get_state(run_id, root=root)  # unknown run: typed 404
        existing = stored_decision(run_id, root=root)
        if existing is not None:
            if existing.idempotency_key == req.idempotency_key:
                return DecisionResult(decision=existing, replayed=True, new_run_id=follow_up_run_id(run_id, root=root))
            raise WorkbenchError("already_decided", f"this run was already decided: {existing.decision}", field="idempotency_key", status=409)
        if not store.has_file(run_id, "verdict.json", root=root):
            raise WorkbenchError("no_verdict", "this run has no verdict to review", field="run_id", status=409)
        verdict = store.read_file(run_id, "verdict.json", root=root)
        action, reason = _clean(req, verdict, state)
        new_id = _open_follow_up(run_id, state, _text(req.note), _text(req.reason) or None, clock, root) if action == "request-changes" else None
        decision = store.Decision(decision=action, reason=reason, idempotency_key=req.idempotency_key, decided_at=clock())
        try:
            store.write_file(run_id, "decision.json", decision, overwrite=False, root=root)
        except BaseException:
            if new_id:
                shutil.rmtree(store.run_dir(new_id, root), ignore_errors=True)
            raise
        if state.state == State.AWAITING_QA and action != "request-changes":
            store.advance(run_id, Event.QA_APPROVED if action == "approve" else Event.QA_REJECTED, stop_reason=state.stop_reason, clock=clock, root=root)
        errors = []
        if action == "approve":
            for hook in list(ON_APPROVE):
                try:
                    hook(run_id, decision)
                except WorkbenchError as exc:
                    errors.append(exc.body()["error"])
        return DecisionResult(decision=decision, new_run_id=new_id, hook_errors=errors)
