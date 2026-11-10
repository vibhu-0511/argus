"""Screen 4 (PR raised): the PR card of an approved run, built on the mock GitHub. No real PR exists.

    GET  /api/runs/{id}/pr                 state (no-pr or draft), reason, the stored pr.json, the mock note, the Mark-ready gate
    POST /api/runs/{id}/pr                 (re)build the PR of an approved run: finds the PR of the branch and updates it
    GET  /api/runs/{id}/trajectory.jsonl   the run's trajectory file as text: the target of the PR body's trajectory link

Importing this module registers `pull_request.on_approve` on `decisions.ON_APPROVE`, so approving a run raises its PR
without an edit of the review files. `register()` does the same again after something cleared the list. The rules are in `argus_workbench.pull_request`.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from argus_workbench import decisions, pull_request, store

router = APIRouter()


def register() -> None:
    """Put the PR hook on `decisions.ON_APPROVE` once. A test that clears that list (test_review does) calls this again."""
    if pull_request.on_approve not in decisions.ON_APPROVE:
        decisions.ON_APPROVE.append(pull_request.on_approve)


register()


@router.get("/api/runs/{run_id}/pr")
def get_pr(run_id: str) -> dict:
    return pull_request.pr_view(run_id)


@router.post("/api/runs/{run_id}/pr")
def post_pr(run_id: str) -> dict:
    pull_request.raise_pr(run_id)
    return pull_request.pr_view(run_id)


@router.get("/api/runs/{run_id}/trajectory.jsonl")
def get_trajectory(run_id: str) -> PlainTextResponse:
    trajectory = store.read_file(run_id, "trajectory.jsonl")  # validated; missing: typed 404
    return PlainTextResponse(trajectory.to_jsonl(), media_type="text/plain; charset=utf-8")
