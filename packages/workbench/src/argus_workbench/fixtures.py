"""Example run folders for every scenario, so other groups can build screens and tests against real files.

EVERYTHING HERE IS SIMULATED DATA (or REPLAY when asked). The steps and token counts come from the ILLUSTRATIVE
`sim` block of the spec, not from a measurement; the patch and report are made-up text. No model was called.
These folders are written with the same store functions a runner uses, so they validate like any run.

    write_fixture_run("normal", root=tmp_path)      # one folder, run id "fixture-normal"
    write_all_fixtures(root=tmp_path)               # one folder per scenario

Stage to flow state: reproduce -> reproducing, locate and fix -> fixing, verify -> verifying (flow.states has no
locating state). A scenario ends where the spec says: normal and judge in awaiting-qa; quota (QuotaExceeded),
stuck and verifier in failed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from argus_core.types import StopReason, Ticket, Trajectory, TrajectoryMeta, TrajectoryStep
from flow.states import Event

from argus_workbench import store
from argus_workbench.spec import load_spec, scenario_ids

PATCH = (
    "# SIMULATED fixture patch, not a model result\n"
    "--- a/src/radar/header.css\n+++ b/src/radar/header.css\n"
    "@@ -1,3 +1,3 @@\n .radar-header {\n-  min-width: 420px;\n+  min-width: 0;\n }\n"
)
REPORT = (
    "<!doctype html><html><head><meta charset=\"utf-8\"><title>SIMULATED report</title></head><body>"
    "<h1>SIMULATED before/after report</h1><p>Made-up fixture. No model produced this.</p>"
    "<p>Before: header cut off at 375 px. After: header fits.</p></body></html>\n"
)
_STAGE_STATE = {"reproduce": "reproducing", "locate": "fixing", "fix": "fixing", "verify": "verifying"}


def fixed_clock(start: datetime = datetime(2026, 1, 1, tzinfo=UTC), step_s: int = 1):
    """A clock that returns `start`, then one second later, and so on. For tests; the server uses utc_now."""
    ticks = iter(range(10**9))
    return lambda: start + timedelta(seconds=next(ticks) * step_s)


def _steps(scenario: str) -> list[TrajectoryStep]:
    """The scripted steps of a scenario from spec `sim`, cut where the scenario halts."""
    sim = load_spec()["sim"]
    rule = sim["scenario"][scenario]
    out: list[TrajectoryStep] = []

    def add(stage: str, ev: dict, stop: StopReason | None = None, error: str | None = None) -> None:
        out.append(TrajectoryStep(
            index=len(out), tokens_in=ev["in"], tokens_out=ev["out"], tokens_cached=ev["cached"], stop_reason=stop,
            message={"stage": stage, "text": ev["msg"], "origin": "SIMULATED"}, tool_name=ev["tool"], tool_error=error,
        ))

    for stage in sim["stages"]:
        events = stage["events"]
        if stage["id"] == "verify":
            events = [e for e in events if e["tool"] == "judge"] if scenario in ("normal", "judge") else []
        if rule.get("haltStage") == stage["id"]:
            for ev in events[: rule["afterEvent"]]:
                add(stage["id"], ev)
            if scenario == "stuck":
                for _ in range(rule["repeat"]["times"]):
                    add(stage["id"], {"tool": rule["repeat"]["tool"], "msg": rule["repeat"]["msg"], "in": 300, "out": 20, "cached": 0})
                out[-1] = out[-1].model_copy(update={"stop_reason": StopReason.stuck})
            else:
                add(stage["id"], {"tool": "model-call", "msg": rule["msg"], "in": 0, "out": 0, "cached": 0},
                    StopReason.quota_exceeded, rule["msg"])
            return out
        for ev in events:
            add(stage["id"], ev)
    out[-1] = out[-1].model_copy(update={"stop_reason": StopReason.submit})
    return out


def _verdict(scenario: str, origin: str) -> store.Verdict:
    block = load_spec()["sim"]["scenario"][scenario] if scenario in ("verifier", "judge") else load_spec()["sim"]["normalVerdict"]
    checks = []
    for c in block["checks"]:
        if c["status"] == "skipped" or (checks and not checks[-1].ok):
            break  # verify.pipeline.run stops at the first hard failure; later checks are absent
        checks.append(store.Check(name=c["name"], ok=c["status"] == "pass", reason=c["detail"], route=c["route"]))
    failed = next((c for c in checks if not c.ok), None)
    return store.Verdict(
        ok=failed is None, checks=checks, first_failure=block["firstFailure"], failed_check=failed.name if failed else None,
        judge_label=block["judge"]["label"], judge_note=block["judge"]["note"], origin=origin,
    )


def write_fixture_run(
    scenario: str, *, run_id: str | None = None, origin: str = "SIMULATED", root: Path | str | None = None, clock=None
) -> store.RunState:
    """Write one complete example folder for `scenario`. With origin REPLAY the state carries no scenario."""
    if scenario not in scenario_ids():
        raise ValueError(f"scenario must be one of {', '.join(scenario_ids())}")
    run_id = run_id or f"fixture-{scenario}"
    clock = clock or fixed_clock()
    ticket = Ticket(id="FIXTURE-1", text="SIMULATED fixture ticket: the Radar header is cut off at 375 px.")
    store.create_run(ticket, scenario=scenario if origin == "SIMULATED" else None, origin=origin, run_id=run_id, clock=clock, root=root)
    store.write_file(run_id, "intake.json", {"repo": "dcortex", "route": "/ops/radar", "ack_public_or_synthetic": True}, root=root)
    steps = _steps(scenario)
    meta = TrajectoryMeta(run_id=run_id, task_id="FIXTURE-1", model="scripted", host="simulated", prompt_hash="none", git_commit="none")
    store.write_file(run_id, "trajectory.jsonl", Trajectory(meta=meta, steps=steps), root=root)

    def go(event: Event, stop: StopReason | None = None) -> store.RunState:
        return store.advance(run_id, event, stop_reason=stop, clock=clock, root=root)

    go(Event.START)
    if scenario == "stuck":
        go(Event.REPRO_OK)
        return go(Event.FIX_FAILED, StopReason.stuck)
    if scenario == "quota":
        go(Event.REPRO_OK)
        return go(Event.FIX_FAILED, StopReason.quota_exceeded)
    go(Event.REPRO_OK)
    go(Event.FIX_OK)
    store.write_file(run_id, "patch.diff", PATCH, root=root)
    store.write_file(run_id, "report.html", REPORT, root=root)
    verdict = _verdict(scenario, origin)
    store.write_file(run_id, "verdict.json", verdict, root=root)
    if not verdict.ok:
        return go(Event.VERIFY_FAILED, StopReason.submit)
    go(Event.VERIFY_OK)
    return go(Event.PR_OPENED, StopReason.submit)


def write_all_fixtures(*, root: Path | str | None = None, origin: str = "SIMULATED") -> dict[str, store.RunState]:
    """One folder per scenario, run ids `fixture-<scenario>` (`fixture-<scenario>-replay` for origin REPLAY)."""
    suffix = "" if origin == "SIMULATED" else "-replay"
    return {s: write_fixture_run(s, run_id=f"fixture-{s}{suffix}", origin=origin, root=root) for s in scenario_ids()}
