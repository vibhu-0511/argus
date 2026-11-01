"""QA approval through a plain GitHub review comment, no MCP needed (P6-T10).

A reviewer writes `/argus approve` or `/argus reject` on a line of its own in a PR review or an
inline review comment. GitHub sends `pull_request_review` / `pull_request_review_comment` to the
webhook (`flow.webhook`), which calls `parse_review_event` here and, on a hit, sends the QA signal
(`flow.qa.send_qa_signal`) in the background. It is the same signal the MRTR tool (T09) sends, with
source `review-comment`, so the workflow cannot tell the two paths apart.

`parse_review_event` is pure: payload in, `ReviewSignal` or None out, no I/O. It returns None unless
all of these hold, and a None is a quiet no-op, never an error:
- the action is a new comment (`submitted` / `created`), not an edit or a delete;
- the commenter's login is in `ARGUS_FLOW_QA_REVIEWERS` (comma separated, case-insensitive; unset or
  empty allows nobody, so the path fails closed);
- the PR is an Argus PR: its title is `Argus fix for <ticket_id>` and its head branch is
  `branch_name(<ticket_id>)`, so the ticket id comes from the PR and is checked against the branch;
- exactly one of the two commands appears at the start of a line (quoted lines starting with `>` do
  not count, and both commands together are ambiguous, so neither counts).

The idempotency key is `qa_signal_key(ticket, "review-comment", "<kind>-<github id>")`: the same
comment delivered twice, or edited back and forth, is the same key and changes nothing.

ponytail: `issue_comment` (a comment in the PR conversation tab) is not handled; its payload has no
head branch to check against the title. Add it, with the title check alone, if reviewers write there.
"""

from __future__ import annotations

import os
from typing import Any, NamedTuple

from flow.states import branch_name

REVIEWERS_ENV = "ARGUS_FLOW_QA_REVIEWERS"
COMMANDS = {("/argus", "approve"): "approve", ("/argus", "reject"): "reject"}
TITLE_PREFIX = "Argus fix for "  # flow.workflow.find_or_create_pr writes `Argus fix for <ticket_id>`

# event -> (payload key of the comment, action that means "new", prefix of the source id)
EVENTS = {
    "pull_request_review": ("review", "submitted", "review"),
    "pull_request_review_comment": ("comment", "created", "comment"),
}


class ReviewSignal(NamedTuple):
    ticket_id: str
    decision: str  # "approve" or "reject"
    source_id: str  # `review-<id>` or `comment-<id>`, the second part of the idempotency key
    by: str  # commenter's login


def send_review_signal(signal: ReviewSignal) -> None:
    """Send the signal to the ticket's workflow. The webhook runs this after it has answered 202."""
    from flow.qa import send_qa_signal  # late: parsing and the webhook need no DBOS

    send_qa_signal(signal.ticket_id, signal.decision, "review-comment", signal.source_id, by=signal.by)


def reviewers_from_env() -> frozenset[str]:
    return frozenset(n.strip().lower() for n in os.environ.get(REVIEWERS_ENV, "").split(",") if n.strip())


def parse_decision(body: str | None) -> str | None:
    """`approve`, `reject` or None, from the commands at the start of the body's lines."""
    found = {COMMANDS.get(tuple(line.lower().split()[:2])) for line in (body or "").splitlines()} - {None}
    return found.pop() if len(found) == 1 else None


def ticket_of_pr(pr: dict[str, Any]) -> str | None:
    """The ticket id of an Argus PR, only when its title and its head branch agree."""
    title = pr.get("title") or ""
    ticket = title[len(TITLE_PREFIX):].strip() if title.startswith(TITLE_PREFIX) else ""
    if ticket and (pr.get("head") or {}).get("ref") == branch_name(ticket):
        return ticket
    return None


def parse_review_event(event: str, payload: Any, reviewers: frozenset[str] | None = None) -> ReviewSignal | None:
    if event not in EVENTS or not isinstance(payload, dict):
        return None
    key, new_action, kind = EVENTS[event]
    comment = payload.get(key)
    if payload.get("action") != new_action or not isinstance(comment, dict) or not comment.get("id"):
        return None
    login = ((comment.get("user") or {}).get("login") or "").lower()
    if not login or login not in (reviewers if reviewers is not None else reviewers_from_env()):
        return None
    decision = parse_decision(comment.get("body"))
    ticket = ticket_of_pr(payload.get("pull_request") or {})
    if decision is None or ticket is None:
        return None
    return ReviewSignal(ticket, decision, f"{kind}-{comment['id']}", login)
