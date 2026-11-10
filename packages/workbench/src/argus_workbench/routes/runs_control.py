"""POST /api/runs/{id}/start, /stop and /retry: the run controls. All three change something, so the token is required.

    start  body (optional) {"scenario": "<id>", "replay_from": "<run id>"}   -> {"state": <state.json>}
    stop   no body                                                            -> {"state": <state.json>}
    retry  body (optional) {"scenario": "<id>"}                               -> {"state": <state.json of the NEW run>}

The manager is kept on `app.state.run_manager`; a test sets its own (`RunManager(tick_ms=0)`) before the first call.
Errors are typed (manager.py and runner.py: `not_startable`, `scenario_required`, `replay_source_required`,
`not_running`, `not_retryable`, `quota_wait`, `unknown_scenario`, and the store's `unknown_run`).
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from argus_workbench.manager import RunManager

router = APIRouter()
_make = threading.Lock()


class StartBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: str | None = None
    replay_from: str | None = None


class RetryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: str | None = None


def manager(request: Request) -> RunManager:
    app = request.app
    with _make:
        if getattr(app.state, "run_manager", None) is None:
            app.state.run_manager = RunManager()
        return app.state.run_manager


@router.post("/api/runs/{run_id}/start")
def start_run(run_id: str, request: Request, body: StartBody | None = None) -> dict:
    body = body or StartBody()
    state = manager(request).start(run_id, scenario=body.scenario, replay_from=body.replay_from)
    return {"state": state.model_dump(mode="json")}


@router.post("/api/runs/{run_id}/stop")
def stop_run(run_id: str, request: Request) -> dict:
    return {"state": manager(request).stop(run_id).model_dump(mode="json")}


@router.post("/api/runs/{run_id}/retry")
def retry_run(run_id: str, request: Request, body: RetryBody | None = None) -> dict:
    body = body or RetryBody()
    return {"state": manager(request).retry(run_id, scenario=body.scenario).model_dump(mode="json")}
