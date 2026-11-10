"""Screen 3 (Review and decision): the review view, the inert report, and the decision.

    GET  /api/runs/{id}/review     four checks in order, first failure, judge card, patch summary, approve gate, decision
    GET  /api/runs/{id}/report     report.html with a CSP that makes it inert even when opened directly
    POST /api/runs/{id}/decision   {action, reason, note, idempotency_key}; rules in argus_workbench.decisions

Everything shown comes from the run folder through `store` (validated on read) and from the packaged spec. The
judge card text (family, model, alpha, notes) is the spec's `sim.judgeCard` as written: it is design text, no judge
runs here, and alpha stays a dash until a calibration run exists.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from verify.pipeline import ORDER

from argus_workbench import decisions, store
from argus_workbench.errors import WorkbenchError
from argus_workbench.spec import load_spec

router = APIRouter()
# Even a direct visit is inert: sandboxed (no script, no same origin), nothing loaded but data: images.
REPORT_CSP = "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"


def patch_summary(diff: str | None) -> dict:
    """Files and line counts of a unified diff. An empty or missing patch means no PR."""
    text = diff or ""
    files = [line[6:] if line.startswith("+++ b/") else line[4:] for line in text.splitlines() if line.startswith("+++ ")]
    added = sum(1 for line in text.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in text.splitlines() if line.startswith("-") and not line.startswith("---"))
    return {"empty": not text.strip(), "files": files, "added": added, "removed": removed, "bytes": len(text.encode("utf-8"))}


def _checks(verdict: store.Verdict) -> list[dict]:
    """All four checks in verify's order. One that did not run (short-circuit) is listed as "not run", never as pass."""
    ran = {c.name: c for c in verdict.checks}
    return [
        {"name": n, "status": "not run", "reason": "short-circuited after the first hard failure", "route": None} if n not in ran
        else {"name": n, "status": "pass" if ran[n].ok else "fail", "reason": ran[n].reason, "route": ran[n].route}
        for n in ORDER
    ]


def _verdict(run_id: str) -> store.Verdict:
    if not store.has_file(run_id, "verdict.json"):
        store.get_state(run_id)  # unknown run: typed 404 first
        raise WorkbenchError("no_verdict", "this run has no verdict to review", field="run_id", status=404)
    return store.read_file(run_id, "verdict.json")


@router.get("/api/runs/{run_id}/review")
def get_review(run_id: str) -> dict:
    state = store.get_state(run_id)
    verdict = _verdict(run_id)
    card = load_spec()["sim"]["judgeCard"]
    checks = _checks(verdict)
    skipped = [c["name"] for c in checks if c["status"] == "not run"]
    note = f"Checks that did not run: {', '.join(skipped)}. The pipeline stops at the first hard failure." if skipped else None
    decision = decisions.stored_decision(run_id)
    patch = store.read_file(run_id, "patch.diff") if store.has_file(run_id, "patch.diff") else None
    return {
        "run_id": run_id,
        "state": state.state.value,
        "display_state": state.display_state,
        "origin": state.origin,
        "verdict_ok": verdict.ok,
        "checks": checks,
        "first_failure": verdict.first_failure,
        "failed_check": verdict.failed_check,
        "short_circuit_note": note,
        "judge": {
            "label": verdict.judge_label,
            "note": verdict.judge_note,
            "advisory": verdict.judge_advisory,
            "advisory_note": "Advisory only: alpha is uncalibrated (ADR-013). The judge never changes the checks.",
            "alpha": card["alpha"],
            "alpha_note": card["alphaNote"],
            "order_disagreement": card["orderDisagreement"],
            "family": card["family"],
            "model": card["model"],
        },
        "patch": patch_summary(patch),
        "report_url": f"/api/runs/{run_id}/report" if store.has_file(run_id, "report.html") else None,
        "approve": decisions.approve_gate(verdict, state),
        "reject_reasons": decisions.reject_reasons(),
        "change_reasons": decisions.change_reasons(),
        "decision": decision.model_dump(mode="json") if decision else None,
        "follow_up_run_id": decisions.follow_up_run_id(run_id) if decision else None,
    }


@router.get("/api/runs/{run_id}/report")
def get_report(run_id: str) -> HTMLResponse:
    html = store.read_file(run_id, "report.html")  # missing: typed 404
    return HTMLResponse(html, headers={"Content-Security-Policy": REPORT_CSP})


@router.post("/api/runs/{run_id}/decision")
def post_decision(run_id: str, body: decisions.DecisionRequest) -> dict:
    result = decisions.decide(run_id, body)
    return result.model_dump(mode="json")
