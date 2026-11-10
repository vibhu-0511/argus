"""Screen 5 (P10-T09): GET /api/history lists runs, GET /api/history/metrics gives the four metrics.

The list shows every run with its origin badge (SIMULATED or REPLAY). The metrics never read the run store: they come
from real result files (history_metrics) or are dashes. `excluded` says how many runs the list holds that no number uses.
"""

from __future__ import annotations

from fastapi import APIRouter

from argus_workbench import store
from argus_workbench.errors import WorkbenchError
from argus_workbench.history_metrics import history_metrics

router = APIRouter()
ORIGINS = ("SIMULATED", "REPLAY")
EMPTY = {"code": "no_runs", "message": "No runs yet. Start one from the Issue tab."}


def _optional(run_id: str, name: str):
    """The validated file, None if the run has none, 'unreadable' if it exists but no longer validates."""
    try:
        return store.read_file(run_id, name) if store.has_file(run_id, name) else None
    except WorkbenchError:
        return "unreadable"


def _row(s: store.RunState) -> dict:
    decision = _optional(s.run_id, "decision.json")
    return {
        "run_id": s.run_id,
        "created_at": s.created_at.isoformat(),
        "state": s.state.value,
        "display_state": s.display_state,
        "stop_reason": s.stop_reason.value if s.stop_reason else None,
        "scenario": s.scenario,
        "origin": s.origin,
        "decision": decision if isinstance(decision, str) or decision is None else decision.decision,
        "pr": _optional(s.run_id, "pr.json") is not None,
        "retry_of": s.created_by_retry_of,
    }


@router.get("/api/history")
def list_history(origin: str | None = None) -> dict:
    if origin is not None and origin not in ORIGINS:
        raise WorkbenchError("bad_origin", f"origin is one of {', '.join(ORIGINS)}", field="origin")
    runs = [_row(s) for s in store.list_runs() if origin is None or s.origin == origin]
    return {"runs": runs, "count": len(runs), "empty": None if runs else EMPTY}


@router.get("/api/history/metrics")
def get_metrics() -> dict:
    # Every run in the store is SIMULATED or REPLAY, so none of them is an input here.
    origins = [s.origin for s in store.list_runs()]
    return {**history_metrics(), "excluded": {o: origins.count(o) for o in ORIGINS}}
