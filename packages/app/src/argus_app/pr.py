"""Open or update the pull request of a fix, with its evidence in the body (P8-T09).

    evidence = load_evidence(verify_dir, trajectory_url=..., before_url=..., after_url=...)
    pr = open_or_update_pr(creator_client(scoped_token), "acme/shop#7", patch, evidence, issue_title="Button is cut off")

What the body holds: the verifier verdict (`verdict.json` of the verify step), the judge label (`judge.json`, or
"not run"), a link to the trajectory and the before and after screenshots. The links are given by the caller, who
knows where the artifacts were stored; nothing here makes a URL up. A link that is missing is written as "not
available" and the body then shows no image for it. Only `https://` URLs without spaces, quotes, brackets or angle
brackets are accepted, so a value cannot break out of the Markdown or inject HTML.

Rules, each with a test in `tests/test_pr.py`:

- No patch (empty or only whitespace): no PR and no GitHub call at all.
- Title and body are fields of the JSON body of the API call (`flow.github_write` posts `json=`). No shell, no
  `subprocess`, no string template runs anywhere: a title like `$(touch x)` is text in a JSON string.
- One stable branch per ticket (`flow.states.branch_name`) and one PR for it: found first (`state=all`), then created
  as a draft, never marked ready here (QA does that, `flow.workflow.finish_step`). A re-run finds the PR and updates
  its title and body. A closed or merged PR is not touched.
- The lookup comes before the push: if it fails, the error propagates and nothing was pushed, created or edited.
- One creator, and it is not the agent: every call is made by `creator_client`, which holds the App installation
  token of the one repo (ADR-026 `write` profile). The fix loop has no GitHub write code and no token (a test scans
  its source), so the agent cannot open, edit or ready a PR; the PR is opened by the service after verify.
- The title stays `Argus fix for <ticket>` because `flow.review_comment.ticket_of_pr` reads the ticket back from it.

ponytail: a re-run with a different patch for the same ticket updates the body but not the branch (the push is keyed
by the ticket and attempt 1, `flow.github_write.push_branch`); a deliberate re-run with attempt > 1 does not exist yet.
Screenshots must already be somewhere reachable by URL; this module neither uploads nor embeds binary files.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from argus_core.redact import redact
from flow.github_write import HttpGitHubClient
from flow.installations import ScopedToken
from flow.review_comment import TITLE_PREFIX
from flow.states import branch_name, effect_key
from flow.workflow import PullRequest

JUDGE_LABELS = ("pass", "fail", "collateral", "error")
NOT_RUN = "not run"
_URL = re.compile(r"https://[^\s\"'<>()\[\]`]+")
_TEXT_LIMIT = 300


class EvidenceError(ValueError):
    """An evidence file or link is not usable. The message names the file or the field."""


class PrClient(Protocol):
    def push_branch(self, branch: str, patch: str, key: str) -> None: ...
    def find_pr(self, branch: str) -> PullRequest | None: ...
    def create_draft_pr(self, branch: str, title: str, body: str) -> PullRequest: ...
    def update_pr(self, branch: str, title: str, body: str) -> PullRequest: ...


@dataclass(frozen=True)
class Evidence:
    verdict_ok: bool
    verdict_reason: str  # why the verifier said no, "" when it said yes
    judge_label: str  # one of JUDGE_LABELS or NOT_RUN
    trajectory_url: str | None
    before_url: str | None
    after_url: str | None


def _url(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if not _URL.fullmatch(value):
        raise EvidenceError(f"{field} is not a plain https URL")
    return value


def load_evidence(
    directory: str | Path, *, trajectory_url: str | None = None, before_url: str | None = None, after_url: str | None = None
) -> Evidence:
    """Read the verify step's folder: `verdict.json` ({"ok": bool, "first_failure"?, "failed_check"?}), optional `judge.json` ({"label"}).

    A screenshot link counts only when the folder has the matching PNG (`before.png`, `after.png`), so a link cannot
    point at an artifact that was never made.
    """
    folder = Path(directory)
    try:
        verdict = json.loads((folder / "verdict.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise EvidenceError("verdict.json is missing or is not JSON") from None
    if not isinstance(verdict, dict) or not isinstance(verdict.get("ok"), bool):
        raise EvidenceError('verdict.json has no boolean "ok"')
    label = NOT_RUN
    if (folder / "judge.json").is_file():
        try:
            label = str(json.loads((folder / "judge.json").read_text(encoding="utf-8")).get("label"))
        except (OSError, ValueError, AttributeError):
            raise EvidenceError("judge.json is not JSON with a label") from None
        if label not in JUDGE_LABELS:
            raise EvidenceError(f"judge.json label {label!r} is not one of {JUDGE_LABELS}")
    reason = "" if verdict["ok"] else ": ".join(str(verdict[k]) for k in ("failed_check", "first_failure") if verdict.get(k))
    return Evidence(
        verdict["ok"],
        reason,
        label,
        _url(trajectory_url, "trajectory_url"),
        _url(before_url, "before_url") if (folder / "before.png").is_file() else None,
        _url(after_url, "after_url") if (folder / "after.png").is_file() else None,
    )


def _plain(text: str) -> str:
    """One line, no backticks, no secret, cut: safe inside a Markdown code span."""
    return " ".join(redact(text).replace("`", "'").split())[:_TEXT_LIMIT]


def pr_title(ticket_id: str) -> str:
    return TITLE_PREFIX + ticket_id


def pr_body(ticket_id: str, issue_title: str, evidence: Evidence) -> str:
    """The body as text. No closing keyword (`closes #n`) anywhere: QA, not a merge, ends the ticket."""
    verdict = "ok" if evidence.verdict_ok else "rejected" + (f" ({_plain(evidence.verdict_reason)})" if evidence.verdict_reason else "")

    def image(name: str, url: str | None) -> str:
        return f"![{name}]({url})" if url else f"{name} screenshot: not available"

    trajectory = f"[trajectory]({evidence.trajectory_url})" if evidence.trajectory_url else "not available"
    lines = [
        f"Draft fix for {ticket_id}, opened by Argus. Awaiting QA.",
        "",
        f"Issue: `{_plain(issue_title) or 'no title'}`",
        "",
        "| Evidence | Result |",
        "|---|---|",
        f"| Verifier verdict | {verdict} |",
        f"| Judge label (advisory) | {evidence.judge_label} |",
        f"| Trajectory | {trajectory} |",
        "",
        "| Before | After |",
        "|---|---|",
        f"| {image('before', evidence.before_url)} | {image('after', evidence.after_url)} |",
    ]
    return "\n".join(lines) + "\n"


def creator_client(scoped: ScopedToken, **kwargs) -> HttpGitHubClient:
    """The one PR creator: the App installation token of one repo, from `flow.installations.mint_for_repo(..., "write")`."""
    return HttpGitHubClient(scoped.token.token, scoped.repo, **kwargs)


def open_or_update_pr(github: PrClient, ticket_id: str, patch: str, evidence: Evidence, issue_title: str = "") -> PullRequest | None:
    """None when there is no patch. Otherwise the draft PR of the ticket's branch, created or (on a re-run) updated."""
    if not patch.strip():
        return None
    branch = branch_name(ticket_id)
    title, body = pr_title(ticket_id), pr_body(ticket_id, issue_title, evidence)
    found = github.find_pr(branch)  # a lookup error raises here: nothing has been pushed, created or edited
    github.push_branch(branch, patch, effect_key(ticket_id, "push-branch"))
    if found is None:
        return github.create_draft_pr(branch, title, body)
    return github.update_pr(branch, title, body)
