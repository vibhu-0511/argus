"""Read-only GitHub REST reader for the reconciliation poller (P6-T07).

`HttpGitHubReader` implements `flow.reconcile.GitHubReader` with GET requests only: it cannot write.
The token comes from the environment variable `GITHUB_TOKEN` (see `from_env`), goes only into the
`Authorization` header, and is never in a repr, a log line or an error message. The httpx transport is
injectable, so tests serve recorded JSON and touch no network.

A ticket id is `owner/repo#number` (what `flow.webhook.ticket_id_of` builds). Per ticket the reader
makes five reads: the issue, the PRs with the stable branch as head, the branch ref, the
`workflow_dispatch` runs and the issue comments.

ponytail: runs, comments and PRs are read from the first page only (100 runs, 100 comments, 2 PRs).
A run older than the newest 100 dispatch runs of the repo, or a marker past the first 100 comments,
is not seen. For one repo with a few tickets that holds; page through them when it does not.
"""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

from flow.reconcile import GitHubReadError, GitHubState, NotATicket, PrView, RunView
from flow.states import DISPATCH_STEPS, State, branch_name, comment_marker, effect_key

TOKEN_ENV = "GITHUB_TOKEN"
API_URL = "https://api.github.com"
_TICKET = re.compile(r"^([^/#\s]+)/([^/#\s]+)#(\d+)$")
_MARKED_STATES = (State.AWAITING_QA, State.DONE, State.FAILED, State.REJECTED, State.TIMED_OUT)  # states.py _COMMENT_STATES


class HttpGitHubReader:
    def __init__(self, token: str, *, transport: httpx.BaseTransport | None = None, base_url: str = API_URL, timeout: float = 10.0) -> None:
        if not token:
            raise ValueError("a GitHub token is required")
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def __repr__(self) -> str:  # the client holds the token
        return "HttpGitHubReader(token=<set>)"

    @classmethod
    def from_env(cls, **kwargs: Any) -> HttpGitHubReader:
        token = os.environ.get(TOKEN_ENV, "")
        if not token:
            raise RuntimeError(f"{TOKEN_ENV} is not set")
        return cls(token, **kwargs)

    def _get(self, path: str, params: dict[str, Any] | None = None, *, missing_ok: bool = False) -> Any:
        try:
            response = self._client.get(path, params=params)
        except httpx.HTTPError as e:
            raise GitHubReadError(f"GET {path} failed: {type(e).__name__}") from None
        if missing_ok and response.status_code == 404:
            return None
        if response.status_code != 200:
            raise GitHubReadError(f"GET {path} -> {response.status_code}")
        return response.json()

    def read_github_state(self, ticket_id: str) -> GitHubState:
        match = _TICKET.match(ticket_id)
        if match is None:
            raise ValueError(f"ticket id {ticket_id!r} is not owner/repo#number")
        owner, repo, number = match.groups()
        base = f"/repos/{owner}/{repo}"
        branch = branch_name(ticket_id)

        issue = self._get(f"{base}/issues/{number}")
        if "pull_request" in issue:
            raise NotATicket(f"{ticket_id} is a pull request, not an issue")
        pulls = self._get(f"{base}/pulls", {"head": f"{owner}:{branch}", "state": "all", "per_page": 2})
        ref = self._get(f"{base}/git/ref/heads/{branch}", missing_ok=True)
        runs = self._get(f"{base}/actions/runs", {"event": "workflow_dispatch", "per_page": 100})
        comments = self._get(f"{base}/issues/{number}/comments", {"per_page": 100})

        bodies = "\n".join(c.get("body") or "" for c in comments)
        return GitHubState(
            ticket_id=ticket_id,
            issue_open=issue["state"] == "open",
            labels=frozenset(label["name"] for label in issue.get("labels", [])),
            branch_exists=ref is not None,
            pr=_pr_of(pulls, branch),
            runs=_latest_runs(runs["workflow_runs"], ticket_id),
            markers=frozenset(s.value for s in _MARKED_STATES if comment_marker(effect_key(ticket_id, f"comment-{s.value}")) in bodies),
        )

    def list_open_tickets(self, repo: str, label: str | None, page_size: int, max_pages: int) -> list[str]:
        tickets: list[str] = []
        for page in range(1, max_pages + 1):
            params: dict[str, Any] = {"state": "open", "per_page": page_size, "page": page, "sort": "updated", "direction": "desc"}
            if label:
                params["labels"] = label
            items = self._get(f"/repos/{repo}/issues", params)
            tickets += [f"{repo}#{i['number']}" for i in items if "pull_request" not in i]  # the issues API lists PRs too
            if len(items) < page_size:
                break
        return tickets


def _pr_of(pulls: list[dict[str, Any]], branch: str) -> PrView | None:
    """The PR whose head is the stable branch. The `head` filter already narrows it; this is a guard."""
    for p in pulls:
        if p["head"]["ref"] == branch:
            return PrView(p["number"], p["state"], bool(p.get("draft")), p.get("merged_at") is not None)
    return None


def _latest_runs(runs: list[dict[str, Any]], ticket_id: str) -> dict[str, RunView]:
    """Per step, the newest run whose title is the step's run key (the run-name T04 sets)."""
    latest: dict[str, dict[str, Any]] = {}
    for step in DISPATCH_STEPS:
        key = effect_key(ticket_id, f"dispatch-{step}")
        found = [r for r in runs if r.get("display_title") == key]
        if found:
            latest[step] = max(found, key=lambda r: (r["created_at"], r["id"]))
    return {step: RunView(r["status"], r.get("conclusion")) for step, r in latest.items()}
