"""Shared helpers for the reconcile tests: GitHub's recorded JSON served through an httpx MockTransport.

A fixture file under `fixtures/reconcile/` holds the JSON bodies of the five GitHub reads the reader
makes (issue, pulls, branch ref, runs, comments) plus the state it must derive. `load(name, ticket)`
can move a fixture to another ticket id (the ticket id, the stable branch and so the run titles are
swapped in the text), so tests that share one Postgres never meet on a workflow id.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from flow.github_read import HttpGitHubReader
from flow.states import branch_name

FIXTURES = Path(__file__).parent / "fixtures" / "reconcile"
FIXTURE_TICKET = "acme/shop#12"
NAMES = sorted(p.stem for p in FIXTURES.glob("*.json"))


def load(name: str, ticket: str = FIXTURE_TICKET) -> dict:
    text = (FIXTURES / f"{name}.json").read_text(encoding="utf-8")
    text = text.replace(branch_name(FIXTURE_TICKET), branch_name(ticket)).replace(FIXTURE_TICKET, ticket)
    return json.loads(text)


def transport(fx: dict, *, requests: list[httpx.Request] | None = None, fail: dict[str, int] | None = None) -> httpx.MockTransport:
    """Serve `fx` for the reader's reads. `fail` maps a path suffix to a status code to answer instead."""
    owner, rest = fx["ticket"].split("/")
    repo, number = rest.split("#")
    base = f"/repos/{owner}/{repo}"

    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        path = request.url.path
        for suffix, status in (fail or {}).items():
            if path.endswith(suffix):
                return httpx.Response(status, json={"message": "boom"})
        if path == f"{base}/issues/{number}":
            return httpx.Response(200, json=fx["issue"])
        if path == f"{base}/pulls":
            head = request.url.params["head"]
            assert head.startswith(f"{owner}:argus/") and request.url.params["state"] == "all"
            return httpx.Response(200, json=[p for p in fx["pulls"] if head == f"{owner}:{p['head']['ref']}"])
        if path.startswith(f"{base}/git/ref/heads/argus/"):
            return httpx.Response(404, json={"message": "Not Found"}) if fx["ref"] is None else httpx.Response(200, json=fx["ref"])
        if path == f"{base}/actions/runs":
            assert request.url.params["event"] == "workflow_dispatch"
            return httpx.Response(200, json=fx["runs"])
        if path == f"{base}/issues/{number}/comments":
            return httpx.Response(200, json=fx["comments"])
        return httpx.Response(500, json={"message": f"unexpected read {request.method} {path}"})

    return httpx.MockTransport(handler)


def reader_for(fx: dict, **kwargs) -> HttpGitHubReader:
    return HttpGitHubReader("test-token", transport=transport(fx, **kwargs))
