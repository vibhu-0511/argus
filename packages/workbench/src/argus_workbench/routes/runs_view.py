"""GET /api/runs/{id}: everything the live-run screen (screen 2) shows, from the run folder. Read only, no token.

The page POLLS this endpoint while the run is playing (`poll.again`, every `poll.interval_ms`). It is polling, not SSE:
the runner writes the files, this reads them, and a stateless GET needs no stream to keep open. When `poll.again` is
false the page stops asking.

    {run:      state.json (state, display_state, stop_reason, origin, scenario, created_by_retry_of, times),
     origin:   {tag: SIMULATED|REPLAY, note},       the badge on every run; no run here is a model result
     stages:   [{id, label, status: pending|running|done|failed|stopped, steps, tokens}]   Reproduce, Locate, Fix, Verify
     steps:    [{index, stage, tool, text, tokens_in, tokens_out, tokens_cached, stop_reason, tool_error, repeat}]
     totals:   {tokens_in, tokens_out, tokens_cached},
     reason:   null | {kind: quota|stuck|stopped|verifier|failed, label, text}   why the run ended, in different words per kind
     meter:    {rows: [...], note}                   from the ledger (meter.py); rows are empty when there is no data
     actions:  {start|stop|retry: {enabled, why, reset_utc?, reset_text?}}     the same rules the POST routes enforce
     poll:     {again, interval_ms}}

`display_state` is `quota-wait` or `stuck` when the stop reason says so (store.display_state). The reason text for
stuck is the spec's scenario text; for quota it is the ledger's own message from the halting step.

ponytail: state.json and trajectory.jsonl are two reads, so a poll can see a step one tick ahead of the state; the next
poll fixes it. The Retry rule (`retry_action`) repeats the one in `RunManager.retry`; a test calls both and compares.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from argus_core.types import StopReason
from fastapi import APIRouter, Request
from flow.states import State

from argus_workbench import meter, store

from argus_workbench.runner import ACTIVE, OWNER_STOP_TEXT
from argus_workbench.spec import load_spec

router = APIRouter()

SIM_NOTE = "SIMULATED: scripted steps and illustrative token counts from the design spec. Not a measurement, no model was called."
REPLAY_NOTE = "REPLAY: a recorded trajectory played back. Token counts not real for this run: nothing was re-run."
FINISHED_OK = frozenset({State.OPENING_PR, State.AWAITING_QA, State.DONE, State.REJECTED})
_FLOOR = {State.REPRODUCING: 0, State.FIXING: 1, State.VERIFYING: 3}  # a running state is at least this far along the stage bar


def _stage_ids() -> list[str]:
    return [s["id"] for s in load_spec()["stages"]]


def _message(step) -> dict:
    return step.message if isinstance(step.message, dict) else {}


def step_rows(trajectory) -> list[dict]:
    """The steps so far. `repeat` marks identical tool calls in a row (same tool, same text), the stuck signal."""
    rows = []
    for s in trajectory.steps if trajectory else []:
        m = _message(s)
        rows.append({
            "index": s.index, "stage": m.get("stage"), "tool": s.tool_name, "text": m.get("text"),
            "tokens_in": s.tokens_in, "tokens_out": s.tokens_out, "tokens_cached": s.tokens_cached,
            "stop_reason": s.stop_reason.value if s.stop_reason else None, "tool_error": s.tool_error, "repeat": False,
        })
    for a, b in zip(rows, rows[1:]):
        if a["tool"] and (a["tool"], a["text"]) == (b["tool"], b["text"]):
            a["repeat"] = b["repeat"] = True
    return rows


def stage_rows(state: store.RunState, steps: list[dict], verdict: store.Verdict | None) -> list[dict]:
    """The stage bar. Stages before the current one are done; the current one is running, failed or stopped."""
    ids = _stage_ids()
    labels = {s["id"]: s["label"] for s in load_spec()["stages"]}
    seen = [ids.index(s["stage"]) for s in steps if s["stage"] in ids]
    status = ["pending"] * len(ids)
    if state.state in FINISHED_OK or (verdict is not None and verdict.ok):
        status = ["done"] * len(ids)
    elif state.state != State.RECEIVED:
        failed = state.state in (State.FAILED, State.TIMED_OUT)
        if failed and verdict is not None:  # a failed verdict: the verifier is the stage that failed
            cur = ids.index("verify")
        else:
            cur = max(seen[-1] if seen else 0, _FLOOR.get(state.state, 0))
        stopped = bool(steps) and steps[-1]["tool"] == "owner-stop"
        status = ["done"] * cur + ["stopped" if stopped else "failed" if failed else "running"] + ["pending"] * (len(ids) - cur - 1)
    return [
        {"id": i, "label": labels[i], "status": status[n],
         "steps": sum(1 for s in steps if s["stage"] == i), "tokens": sum(s["tokens_in"] + s["tokens_out"] for s in steps if s["stage"] == i)}
        for n, i in enumerate(ids)
    ]


def reason_of(state: store.RunState, steps: list[dict], verdict: store.Verdict | None) -> dict | None:
    """Why the run ended, with a different label and kind for quota, stuck and an owner stop. None while it runs or passed."""
    if state.state not in (State.FAILED, State.TIMED_OUT):
        return None
    last = steps[-1] if steps else None
    if state.stop_reason == StopReason.quota_exceeded:
        text = (last or {}).get("tool_error") or "stop_reason=QuotaExceeded (the ledger message was not recorded)"
        return {"kind": "quota", "label": "Quota used up", "text": text}
    if state.stop_reason == StopReason.stuck:
        repeated = next((s for s in reversed(steps) if s["repeat"]), None)
        text = load_spec()["sim"]["scenario"]["stuck"]["msg"]
        return {"kind": "stuck", "label": "Stuck in a loop", "text": f"{text} (repeated tool: {repeated['tool']})" if repeated else text}
    if state.stop_reason is None and last and last["tool"] == "owner-stop":
        return {"kind": "stopped", "label": "Stopped by owner", "text": OWNER_STOP_TEXT}
    if verdict is not None and not verdict.ok:
        return {"kind": "verifier", "label": "Verifier failed", "text": verdict.first_failure or "a check failed"}
    why = state.stop_reason.value if state.stop_reason else "none"
    return {"kind": "failed", "label": "Run failed", "text": f"The run ended in {state.state.value}; stop_reason={why}."}


def reset_of(state: store.RunState) -> datetime:
    """When a quota stop is lifted: the next 00:00 UTC after it happened (the ledger rolls its day on the UTC date)."""
    return datetime.combine(state.updated_at.astimezone(UTC).date() + timedelta(days=1), time(0, 0), tzinfo=UTC)


def retry_action(state: store.RunState, now: datetime) -> dict:
    """Same rule as RunManager.retry: terminal and not done; a QuotaExceeded stop waits for the UTC date to change."""
    if state.state not in (State.FAILED, State.TIMED_OUT, State.REJECTED):
        return {"enabled": False, "why": "only a finished run that did not pass can be retried"}
    if state.stop_reason == StopReason.quota_exceeded and state.updated_at.astimezone(UTC).date() >= now.astimezone(UTC).date():
        reset = reset_of(state)
        return {"enabled": False, "why": "the quota is used up; retry after the reset", "reset_utc": reset.isoformat(),
                "reset_text": f"resets 00:00 UTC on {reset.date().isoformat()}"}
    return {"enabled": True, "why": "makes a new run; this one is not changed"}


def actions_of(state: store.RunState, now: datetime) -> dict:
    can_start = state.state == State.RECEIVED and state.origin == "SIMULATED" and state.scenario is not None
    start_why = ("starts the scripted scenario" if can_start else
                 "this run is not waiting to start" if state.state != State.RECEIVED else
                 "a REPLAY run needs a recorded run to play" if state.origin == "REPLAY" else "this run has no scenario")
    return {
        "start": {"enabled": can_start, "why": start_why},
        "stop": {"enabled": state.state in ACTIVE, "why": "ends the run where it is" if state.state in ACTIVE else "the run is not running"},
        "retry": retry_action(state, now),
    }


def _optional(run_id: str, name: str, root):
    return store.read_file(run_id, name, root=root) if store.has_file(run_id, name, root=root) else None


@router.get("/api/runs/{run_id}")
def get_run(run_id: str, request: Request) -> dict:
    manager = getattr(request.app.state, "run_manager", None)
    now = (manager.clock if manager else store.utc_now)()
    state = store.get_state(run_id)  # bad_run_id / unknown_run, typed
    trajectory, verdict = _optional(run_id, "trajectory.jsonl", None), _optional(run_id, "verdict.json", None)
    steps = step_rows(trajectory)
    rows, note = [], ""
    stop_row = None
    if state.stop_reason == StopReason.quota_exceeded and steps:
        stop_row = meter.quota_stop_row(steps[-1]["tool_error"])
    if stop_row:
        rows, note = [stop_row], "from the ledger's own QuotaExceeded message; ILLUSTRATIVE, the scripted run charged a throwaway ledger"
    else:
        rows, note = meter.ledger_rows(now)
    playing = state.state in ACTIVE
    return {
        "run": state.model_dump(mode="json"),
        "origin": {"tag": state.origin, "note": SIM_NOTE if state.origin == "SIMULATED" else REPLAY_NOTE},
        "stages": stage_rows(state, steps, verdict),
        "steps": steps,
        "totals": {k: sum(s[k] for s in steps) for k in ("tokens_in", "tokens_out", "tokens_cached")},
        "reason": reason_of(state, steps, verdict),
        "meter": {"rows": rows, "note": note},
        "actions": actions_of(state, now),
        "poll": {"again": playing, "interval_ms": load_spec()["sim"]["tick_ms"]},
    }
