"""Screen 4, the PR (P10-T08): build the draft PR of an approved run through `argus_app.pr` and the MOCK GitHub.

    raise_pr(run_id)        # -> store.PrFile, also written to pr.json; the approve hook and POST /api/runs/{id}/pr call it
    pr_view(run_id)         # -> the dict GET /api/runs/{id}/pr returns

What is reused, nothing copied: `argus_app.pr.open_or_update_pr` (no patch -> no call; find the PR of the branch first;
push; create a draft or update title and body), `argus_app.pr.pr_title` / `pr_body`, `flow.states.branch_name` (one stable
branch per ticket) and `flow.github_write.HttpGitHubClient` with an httpx MockTransport (`mock_github`). The workbench adds
only what the task row asks for on top of that body: the before/after report link, the CI state, the backport follow-up.

Rules (each has a test in tests/test_pr.py):
- Title and body are JSON fields of the API call. No shell runs: a ticket whose id or text contains `$(...)` is stored and
  shown as text.
- An empty (or missing) patch gives no PR, no GitHub call, no pr.json and a typed `no_patch` error.
- One branch per ticket id, so a second approval (another run of the same ticket, or a repeat of this call) finds the PR and
  updates it. `action` in pr.json says "created" or "updated"; there is never a second PR for the branch.
- The PR is a draft. Marking it ready needs a real QA signal; there is none here, so the step is disabled and says why.
- The trajectory link is a relative path to a file this workbench serves; no URL is made up. The mock PR URL ends in
  `.invalid` and the page shows it as text.
- CI is "not run": nothing in P10 runs or reads a CI check, so no other state can be stored.
- pr.json is tagged SIMULATED, whatever the origin of the run (the run's own origin is in `run_origin`).

Registered as an approve hook in routes/pr.py. The hook and the route share one lock, so two calls never race the
find-before-act of the same branch.

`argus_app.pr` and `flow.github_write` are imported inside the functions that use them: they reach `flow.workflow`, which
imports dbos and psycopg. A machine that blocks that DLL (Application Control does here, now and then) then still starts
the server and every other screen; only raising a PR fails, with the typed error `pr_unavailable`.

ponytail: one process-wide lock; two server processes on one store would need a file lock.
ponytail: the body is `pr_body` cut at its screenshot table (the workbench stores no screenshots) plus the extra sections;
if `pr_body` changes its layout, `_body` raises and the tests fail.
"""

from __future__ import annotations

import threading
from pathlib import Path

from flow.states import branch_name

from argus_workbench import decisions, store
from argus_workbench.errors import WorkbenchError
from argus_workbench.mock_github import MOCK_REPO, mock_for
from argus_workbench.spec import load_spec

_LOCK = threading.Lock()
MOCK_TOKEN = "mock-token-not-real"  # never leaves the process: the transport is in memory
MOCK_NOTE = "Mock transport, no real PR. This PR exists only inside this workbench; nothing was sent to GitHub."
CI_NOT_RUN = "not run"
READY_REASON = "Marking a PR ready needs a real QA signal on a real PR. This build has no QA signal and no real PR, so the step is disabled."
_CUT = "| Before | After |"


def trajectory_link(run_id: str) -> str:
    return f"/api/runs/{run_id}/trajectory.jsonl"


def report_link(run_id: str) -> str:
    return f"/api/runs/{run_id}/report"


def _ci() -> dict:
    ci = load_spec()["sim"]["ci"]
    return {"state": CI_NOT_RUN, "checks": ci["checks"], "note": "No CI result is stored for this run; the checks below are the ones a tenant repo would show."}


def _backport() -> dict:
    b = load_spec()["sim"]["backport"]
    return {"target_branch": b["targetBranch"], "target_note": b["targetNote"], "conflict_note": b["conflictNote"], "status": "not run"}


def _body(run_id: str, ticket, evidence, has_report: bool) -> str:
    """`pr_body` up to its screenshot table, then the report link, CI state and backport follow-up. Plain text, Markdown-safe."""
    from argus_app.pr import pr_body

    base = pr_body(ticket.id, ticket.text.strip().splitlines()[0] if ticket.text.strip() else "", evidence)
    if _CUT not in base:
        raise WorkbenchError("pr_body_changed", "argus_app.pr.pr_body no longer has the screenshot table this wrapper cuts", status=500)
    ci, backport = _ci(), _backport()
    report = f"[report]({report_link(run_id)}) (the workbench shows it in a sandboxed frame)" if has_report else "not available"
    return "\n".join([
        base.split(_CUT)[0].rstrip(),
        "",
        f"Before and after: {report}. No screenshots are stored in a workbench run.",
        "",
        f"CI: {ci['state']}. {ci['note']}",
        f"Checks: {', '.join(ci['checks'])}.",
        "",
        f"Backport follow-up: after the owner merges, Argus can open a backport PR to `{backport['target_branch']}`. "
        f"{backport['target_note']} {backport['conflict_note']} Status: {backport['status']}, nothing is merged here.",
        "",
        f"Run {run_id} is SIMULATED data from the workbench. {MOCK_NOTE}",
        "",
    ])


class _Body:
    """A PrClient that sends our body where `open_or_update_pr` would send its own. Everything else is passed on unchanged."""

    def __init__(self, inner, body: str) -> None:
        self._inner, self._body = inner, body

    def push_branch(self, branch, patch, key):
        return self._inner.push_branch(branch, patch, key)

    def find_pr(self, branch):
        return self._inner.find_pr(branch)

    def create_draft_pr(self, branch, title, body):
        return self._inner.create_draft_pr(branch, title, self._body)

    def update_pr(self, branch, title, body):
        return self._inner.update_pr(branch, title, self._body)


def raise_pr(run_id: str, *, root: Path | str | None = None) -> store.PrFile:
    """Create or update the mock draft PR of an approved run and write pr.json. Typed errors: not_approved, no_patch, verifier_failed, pr_failed."""
    with _LOCK:
        store.get_state(run_id, root=root)  # unknown run: typed 404
        decision = decisions.stored_decision(run_id, root=root)
        if decision is None or decision.decision != "approve":
            raise WorkbenchError("not_approved", "No PR: this run was not approved.", field="run_id", status=409)
        patch = store.read_file(run_id, "patch.diff", root=root) if store.has_file(run_id, "patch.diff", root=root) else ""
        if not patch.strip():
            raise WorkbenchError("no_patch", "The patch is empty, so no PR was raised and nothing was sent.", field="patch", status=409)
        verdict = store.read_file(run_id, "verdict.json", root=root)
        if not verdict.ok:
            raise WorkbenchError("verifier_failed", f"No PR: the verifier failed: {verdict.first_failure}", field="run_id", status=409)
        try:
            from argus_app.pr import Evidence, EvidenceError, open_or_update_pr, pr_title
            from flow.github_write import GitHubWriteError, HttpGitHubClient
        except ImportError as exc:
            raise WorkbenchError("pr_unavailable", f"The PR code could not be loaded: {type(exc).__name__}", status=503) from None
        state = store.get_state(run_id, root=root)
        ticket = store.read_file(run_id, "ticket.json", root=root)
        has_traj = store.has_file(run_id, "trajectory.jsonl", root=root)
        has_report = store.has_file(run_id, "report.html", root=root)
        evidence = Evidence(True, "", verdict.judge_label, trajectory_link(run_id) if has_traj else None, None, None)
        body = _body(run_id, ticket, evidence, has_report)
        branch, title = branch_name(ticket.id), pr_title(ticket.id)
        mock = mock_for(root)
        mock.seed_from_patch(patch)
        before = mock.count("POST", "/pulls")
        client = _Body(HttpGitHubClient(MOCK_TOKEN, MOCK_REPO, transport=mock.transport()), body)
        try:
            pr = open_or_update_pr(client, ticket.id, patch, evidence, issue_title=ticket.text)
        except (GitHubWriteError, EvidenceError, ValueError) as exc:
            raise WorkbenchError("pr_failed", f"The mock GitHub refused the PR: {exc}", status=502) from None
        if pr is None:  # unreachable: the empty patch was refused above; kept so a change in argus_app.pr cannot pass silently
            raise WorkbenchError("no_patch", "The patch is empty, so no PR was raised.", field="patch", status=409)
        previous = store.read_file(run_id, "pr.json", root=root) if store.has_file(run_id, "pr.json", root=root) else None
        return store.write_file(run_id, "pr.json", {
            "number": pr.number, "url": pr.url, "draft": pr.draft, "origin": "SIMULATED", "transport": "mock", "run_origin": state.origin,
            "action": "created" if mock.count("POST", "/pulls") > before else "updated",
            "updates": (previous.model_extra.get("updates", 0) + 1) if previous else 0,
            "title": title, "branch": branch, "body": body, "ci": _ci(), "backport": _backport(),
            "links": {"trajectory": trajectory_link(run_id) if has_traj else None, "report": report_link(run_id) if has_report else None},
            "judge_label": verdict.judge_label, "verdict_ok": verdict.ok,
            "mark_ready": {"enabled": False, "reason": READY_REASON},
        }, root=root)


def _no_pr_reason(run_id: str, root) -> tuple[str, bool]:
    """Why a run has no PR, and whether `raise_pr` could be tried now."""
    decision = decisions.stored_decision(run_id, root=root)
    if decision is None:
        return "No PR: the run has not been approved yet.", False
    if decision.decision != "approve":
        return f"No PR: the run was {'rejected' if decision.decision == 'reject' else 'sent back for changes'}, not approved.", False
    patch = store.read_file(run_id, "patch.diff", root=root) if store.has_file(run_id, "patch.diff", root=root) else ""
    if not patch.strip():
        return "No PR: the patch is empty, so nothing was raised and nothing was sent.", False
    return "Approved, but the PR was not raised yet.", True


def pr_view(run_id: str, *, root: Path | str | None = None) -> dict:
    state = store.get_state(run_id, root=root)
    states = [{"id": s["id"], "text": s["text"], "reachable": s["id"] in ("no-pr", "draft")} for s in load_spec()["screens"][3]["states"]]
    view = {"run_id": run_id, "origin": state.origin, "mock_note": MOCK_NOTE, "mark_ready": {"enabled": False, "reason": READY_REASON}, "states": states}
    if store.has_file(run_id, "pr.json", root=root):
        pr = store.read_file(run_id, "pr.json", root=root)
        return {**view, "state": "draft" if pr.draft else "ready", "reason": None, "can_raise": False, "pr": pr.model_dump(mode="json")}
    reason, can = _no_pr_reason(run_id, root)
    return {**view, "state": "no-pr", "reason": reason, "can_raise": can, "pr": None}


def on_approve(run_id: str, decision: store.Decision) -> None:
    """The T07 approve hook: raise the PR of the run that was just approved."""
    raise_pr(run_id)
