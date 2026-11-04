"""Ticket intake: a labelled issue starts a workflow (P8-T08).

A tenant puts the intake label (default `argus`, env `ARGUS_INTAKE_LABEL`) on an issue. GitHub sends `issues` /
`labeled` to the webhook. `flow.webhook` verifies the HMAC, answers 202 and hands the payload to `Intake.handle`
after the response (ADR-021: the webhook is a hint, it makes no GitHub call before it answers). `handle` then:

1. drops everything that is not the intake label being added to an issue (another label, another action);
2. asks GitHub whether the person who added the label has write access to the repo
   (`GET /repos/{repo}/collaborators/{login}/permission`, with an installation token that only reads, ADR-026);
3. on `admin`, `maintain` or `write`: `enqueue_reconcile(ticket_id)`, the same call the poller makes;
4. on anything else, or when the check itself fails: does nothing and says so. The ignore goes to the structured
   log (`intake_ignored {json}`) and, when an audit sink is given, to it as kind `intake_ignored`
   (`guard.auditlog.AuditLog.append` fits). A failed check refuses, it never lets the label through.

Exactly one workflow per issue: the ticket id `owner/repo#number` is the only workflow key (`flow.enqueue`), so the
same delivery twice (GitHub's redelivery), a label removed and added again (a new delivery id), or a second person
adding it all end on the one workflow. `HintDedup` on the delivery id only saves the permission call.

The tokens come from `token_for(repo)`; the service passes `flow.installations.mint_for_repo(..., "read")`. A repo
the App is not installed on is refused before any HTTP call.

ponytail: an issue that was created with the label already on it is covered by GitHub's own `labeled` event for it;
an `opened` event is not looked at. A finished workflow is not started again by a new label (same workflow id)
until a deliberate re-run with `attempt` > 1 exists. The permission is read per event, not cached.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from typing import NamedTuple

import httpx

from flow.enqueue import Enqueuer, HintDedup

LABEL_ENV = "ARGUS_INTAKE_LABEL"
DEFAULT_LABEL = "argus"
EVENTS = frozenset({"issues"})
WRITE_ROLES = frozenset({"admin", "maintain", "write"})
API_URL = "https://api.github.com"

log = logging.getLogger("flow.intake")


class Decision(NamedTuple):
    outcome: str  # "started", "ignored" or "error"
    reason: str
    ticket_id: str | None = None


def label_from_env() -> str:
    return os.environ.get(LABEL_ENV, "").strip() or DEFAULT_LABEL


class Intake:
    def __init__(
        self,
        enqueuer: Enqueuer,
        token_for: Callable[[str], str],
        *,
        label: str | None = None,
        audit: Callable[[str, dict], object] | None = None,
        dedup: HintDedup | None = None,
        transport: httpx.BaseTransport | None = None,
        base_url: str = API_URL,
    ) -> None:
        self._enqueuer, self._token_for, self._audit = enqueuer, token_for, audit
        self.label = (label or label_from_env()).casefold()
        self._dedup = dedup if dedup is not None else HintDedup()
        self._transport, self._base = transport, base_url

    def __repr__(self) -> str:
        return f"Intake(label={self.label!r})"

    def handle(self, payload: dict, delivery_id: str | None = None) -> Decision:
        """One `issues` event. Never raises: the answer was sent already, the outcome is in the log."""
        who = _who(payload, self.label)
        if who is None:
            return Decision("ignored", "not the intake label being added")
        repo, number, actor = who
        ticket_id = f"{repo}#{number}"
        if delivery_id and not self._dedup.first_time(delivery_id):
            return Decision("ignored", "repeat delivery", ticket_id)
        try:
            allowed, reason = self._may_start(repo, actor)
        except Exception as e:  # the type only: a driver or HTTP message can carry a host or a header
            allowed, reason = False, f"permission check failed ({type(e).__name__})"
        if not allowed:
            if delivery_id and "failed" in reason:
                self._dedup.forget(delivery_id)  # a manual redelivery after the outage gets through
            self._ignored(ticket_id, actor, reason)
            return Decision("ignored", reason, ticket_id)
        try:
            self._enqueuer.enqueue_reconcile(ticket_id)
        except Exception as e:
            if delivery_id:
                self._dedup.forget(delivery_id)
            log.error("intake enqueue failed for %s (%s)", ticket_id, type(e).__name__)
            return Decision("error", f"enqueue failed ({type(e).__name__})", ticket_id)
        log.info("intake_started %s", json.dumps({"ticket": ticket_id, "actor": actor}, sort_keys=True))
        return Decision("started", "label added by a user with write access", ticket_id)

    def _may_start(self, repo: str, actor: str) -> tuple[bool, str]:
        token = self._token_for(repo)  # RepoNotInstalled lands in handle()'s except: the repo is refused
        with httpx.Client(base_url=self._base, transport=self._transport, timeout=10.0) as client:
            response = client.get(
                f"/repos/{repo}/collaborators/{actor}/permission",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
            )
        if response.status_code == 404:
            return False, "actor has no access to the repo"
        if response.status_code != 200:
            return False, f"permission check failed (HTTP {response.status_code})"
        data = response.json()
        # `role_name` knows maintain and triage; the older `permission` only admin, write, read, none.
        role = str(data.get("role_name") or data.get("permission") or "none").lower()
        return (True, role) if role in WRITE_ROLES else (False, f"actor has {role} access, write is needed")

    def _ignored(self, ticket_id: str, actor: str, reason: str) -> None:
        record = {"ticket": ticket_id, "actor": actor, "label": self.label, "reason": reason}
        log.warning("intake_ignored %s", json.dumps(record, sort_keys=True))
        if self._audit:
            self._audit("intake_ignored", record)


def _who(payload: dict, label: str) -> tuple[str, int, str] | None:
    """(repo, issue number, login of the person who added the label), only for the intake label being added to an issue."""
    added = (payload.get("label") or {}).get("name")
    repo = (payload.get("repository") or {}).get("full_name")
    number = (payload.get("issue") or {}).get("number")
    actor = (payload.get("sender") or {}).get("login")
    if payload.get("action") != "labeled" or not isinstance(added, str) or added.casefold() != label:
        return None
    if not (repo and isinstance(number, int) and actor) or "pull_request" in payload["issue"]:
        return None
    return repo, number, actor
