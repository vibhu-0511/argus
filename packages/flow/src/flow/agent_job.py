"""Entry point of `.github/workflows/agent-job.yml`: `uv run --package flow python -m flow.agent_job` (P6-T04).

Runs exactly one pipeline step (`repro`, `fix` or `verify`) and writes what `flow.actions.ActionsRunner` reads back
from the artifact `argus-result`, into the folder `ARGUS_OUT`:

    result.json        {"ok": bool, "output": str}   always written, also when the step crashes
    patch.diff         the patch, when the step made one
    trajectory.jsonl   the step's trajectory, when it made one

Input comes from the environment the workflow sets: `ARGUS_TICKET_ID`, `ARGUS_STEP`, `ARGUS_RUN_KEY`,
`ARGUS_OUT`, and the upstream output (repro script for `fix`, patch for `verify`) from the file
`$ARGUS_OUT/upstream.txt` (the workflow writes it), else from `ARGUS_UPSTREAM`. The model key
`ARGUS_MODEL_API_KEY` is read only by the default steps.

The three steps are injectable callables (`Step`: `Job -> StepResult`); tests pass fakes. The defaults call the
real packages: `repro_agent.loop.run_repro`, `fix_loop.loop.run_fix` and, for verify, the bench scorer
`argus_bench.score.score_task` on the patched tree. Their inputs exist only for a seeded task, so the defaults take
`ARGUS_TICKET_ID` as a seeded task id (`packages/bench/tasks/seeded/<id>`) and need `ARGUS_PLATFORM_REPO`, the
repro rig and Docker. Any other ticket id (`owner/repo#number`) ends as a failure result that says so.

A failure result never carries a secret: the reason is the exception class name and its message with the value of
every environment variable named like a secret, and anything shaped like a GitHub, Groq or `sk-` token or a bearer
header, replaced by `***`. The exit code is 0 when the step succeeded and 1 when it did not, either way after
`result.json` is written.

ponytail: the defaults are wired from the code and have not run on a runner. They need the platform checkout and the
Docker rig, which `agent-job.yml` sets up but nobody has seen run (see docs/notes/p6-t04.md). Verify uses the bench scorer
(deterministic checks of the seeded task), not `verify.pipeline.run`, which needs screenshots and DOM reports that
nothing produces for a ticket yet.
ponytail: a success `output` is written as the step made it (a patch must stay byte-exact); only failure reasons are scrubbed.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from argus_core.redact import redact

from flow.actions import MAX_MEMBER
from flow.states import DISPATCH_STEPS

REPO = Path(__file__).resolve().parents[4]
SEEDED = REPO / "packages" / "bench" / "tasks" / "seeded"
REASON_LIMIT = 2000  # characters of a failure reason
_SECRET_SHAPE = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gsk_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|Bearer\s+\S+")


class StepUnavailable(RuntimeError):
    """The step cannot run with what this job was given (not a bug in the step). The message is the reason."""


@dataclass(frozen=True)
class Job:
    ticket_id: str
    step: str
    run_key: str
    upstream: str
    out: Path


@dataclass(frozen=True)
class StepResult:
    ok: bool
    output: str  # repro script, patch or verdict text: what the next step takes as upstream
    patch: str = ""
    trajectory: str = ""


Step = Callable[[Job], StepResult]


# --- result file ---------------------------------------------------------------------------------------------


def scrub(text: str, env: Mapping[str, str]) -> str:
    """Replace every secret-named env value and every token-shaped string in `text` with `***`."""
    # argus_core.redact knows the `ghs_<APPID>_<JWT>` installation token (P7-T03/T04); _SECRET_SHAPE keeps the looser Bearer rule
    return _SECRET_SHAPE.sub("***", redact(text, env))


def _failure(reason: str, env: Mapping[str, str]) -> StepResult:
    return StepResult(False, scrub(reason, env)[:REASON_LIMIT])


def _write(out: Path, result: StepResult, env: Mapping[str, str]) -> StepResult:
    """Patch and trajectory first, `result.json` last and atomically, so a half-written job leaves no result.

    Returns what was written: a file over the artifact limit turns the result into a failure."""
    for name, text in (("result.json", result.output), ("patch.diff", result.patch), ("trajectory.jsonl", result.trajectory)):
        if len(text.encode("utf-8")) > MAX_MEMBER:  # the runner refuses the whole artifact over this size
            size = len(text.encode("utf-8"))
            result = _failure(f"{name} is {size} bytes, over the artifact limit {MAX_MEMBER}", env)
            break
    out.mkdir(parents=True, exist_ok=True)
    for name, text in (("patch.diff", result.patch), ("trajectory.jsonl", result.trajectory)):
        if text:
            (out / name).write_text(text, encoding="utf-8", newline="\n")
    tmp = out / "result.json.tmp"
    tmp.write_text(json.dumps({"ok": result.ok, "output": result.output}), encoding="utf-8", newline="\n")
    tmp.replace(out / "result.json")
    return result


def _read_job(env: Mapping[str, str]) -> Job:
    ticket_id, step, run_key = (env.get(k, "") for k in ("ARGUS_TICKET_ID", "ARGUS_STEP", "ARGUS_RUN_KEY"))
    if not ticket_id or not run_key:
        raise StepUnavailable("ARGUS_TICKET_ID and ARGUS_RUN_KEY must be set")
    if step not in DISPATCH_STEPS:
        raise StepUnavailable(f"ARGUS_STEP {step!r} is not one of {DISPATCH_STEPS}")
    out = Path(env.get("ARGUS_OUT") or "argus-out")
    file = out / "upstream.txt"
    upstream = file.read_text(encoding="utf-8") if file.is_file() else env.get("ARGUS_UPSTREAM", "")
    return Job(ticket_id, step, run_key, upstream, out)


def main(env: Mapping[str, str] | None = None, steps: Mapping[str, Step] | None = None) -> int:
    env = os.environ if env is None else env
    steps = steps or DEFAULT_STEPS
    out = Path(env.get("ARGUS_OUT") or "argus-out")
    try:
        job = _read_job(env)
        result = steps[job.step](job)
    except Exception as e:  # every crash still leaves a readable result; the reason is scrubbed, not the traceback
        result = _failure(f"{type(e).__name__}: {e}", env)
    if not result.ok:  # a failure reason is text a person reads; it must not carry a secret
        result = replace(result, output=_failure(result.output, env).output)
    result = _write(out, result, env)
    print(f"agent_job {env.get('ARGUS_STEP', '?')}: ok={result.ok}", file=sys.stderr)
    return 0 if result.ok else 1


# --- default steps: the real packages, on a seeded task -------------------------------------------------------


def _task_dir(job: Job) -> Path:
    directory = SEEDED / job.ticket_id
    if "/" in job.ticket_id or not (directory / "ticket.json").is_file():
        raise StepUnavailable(
            f"ticket {job.ticket_id!r} is not a seeded task: no adapter turns a live issue into the task directory "
            "(ticket, bug.patch, checks) the repro, fix and verify packages work on"
        )
    return directory


def _router(job: Job):
    """The routing policy and a router over it. Groq is the only host with a key in this job."""
    from argus_core.client import ModelClient
    from argus_core.ledger import Ledger, load_quotas
    from argus_core.router import Router, load_policy

    key = os.environ.get("ARGUS_MODEL_API_KEY", "")
    if not key:
        raise StepUnavailable("ARGUS_MODEL_API_KEY is not set")
    ledger = Ledger(job.out / "ledger.json", load_quotas(REPO / "docs" / "quotas.md"))
    policy = load_policy()
    return policy, Router(policy, ledger, {"groq": ModelClient("https://api.groq.com/openai/v1", key)})


def _head() -> str:
    done = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def _git(tree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(tree), *args], capture_output=True, text=True, encoding="utf-8")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def repro_step(job: Job) -> StepResult:
    from argus_core.types import Ticket
    from repro_agent.loop import run_repro
    from repro_agent.trees import trees_for

    task = _task_dir(job)
    policy, router = _router(job)
    ticket = Ticket.model_validate_json((task / "ticket.json").read_text(encoding="utf-8"))
    result = run_repro(
        ticket=ticket, task_dir=task, model=policy.tiers[policy.stages["repro"]].primary.model, run_trees=trees_for(task),
        out_dir=job.out / "repro", cap=3, run_id=job.run_key, host="groq", git_commit=_head(), router=router, stage="repro",
    )
    trajectory = _read(result.trajectory_path)
    if result.script is None:
        return StepResult(False, f"no valid reproduction: {result.stop_reason.value}", trajectory=trajectory)
    return StepResult(True, result.script, trajectory=trajectory)


def fix_step(job: Job) -> StepResult:
    from argus_bench.golden import platform_repo
    from argus_core.types import Ticket
    from fix_loop import worktree
    from fix_loop.loop import run_fix
    from fix_loop.strategies import cap_strategy
    from fix_loop.turn import PROTOCOL, STEP_CAP, TOKEN_CAP, _execute, _reset

    task = _task_dir(job)
    policy, router = _router(job)
    ticket = Ticket.model_validate_json((task / "ticket.json").read_text(encoding="utf-8"))
    checks = job.out / "checks"
    checks.mkdir(parents=True, exist_ok=True)
    (checks / "checks.json").write_bytes((task / "checks.json").read_bytes())  # golden.patch stays out of the mount
    repo = platform_repo()
    tree = worktree.create(repo, job.ticket_id, "HEAD", root=job.out / "trees")
    try:
        _reset(tree, (task / "bug.patch").read_text(encoding="utf-8"))
        result = run_fix(
            worktree=tree, model=policy.tiers[policy.stages["fix"]].primary.model, host="groq", router=router, stage="fix",
            out_dir=job.out / "fix", step_cap=STEP_CAP, token_cap=TOKEN_CAP, run_id=job.run_key, git_commit=_head(), task_id=ticket.id,
            system=PROTOCOL, execute=_execute(tree, checks), context_budget=32_000, strategy=cap_strategy,
            user=f"Ticket:\n{ticket.text}\n\nRepro: {job.upstream or 'not-run'}\nLocate: none\n",
        )
        patch = _git(tree, "diff").stdout
    finally:
        worktree.destroy(repo, tree)
    trajectory = _read(result.trajectory_path)
    if not patch.strip():
        return StepResult(False, f"the fix loop made no change: {result.stop_reason.value}", trajectory=trajectory)
    return StepResult(True, patch, patch=patch, trajectory=trajectory)


def verify_step(job: Job) -> StepResult:
    from argus_bench.golden import platform_repo
    from argus_bench.score import score_task
    from fix_loop import worktree
    from fix_loop.turn import _reset

    task = _task_dir(job)
    if not job.upstream.strip():
        raise StepUnavailable("verify needs the patch from the fix step as upstream, got none")
    repo = platform_repo()
    tree = worktree.create(repo, job.ticket_id, "HEAD", root=job.out / "trees")
    try:
        _reset(tree, (task / "bug.patch").read_text(encoding="utf-8"))
        patch = job.out / "upstream.patch"
        patch.write_bytes(job.upstream.encode("utf-8"))
        applied = _git(tree, "apply", str(patch))
        if applied.returncode != 0:
            return StepResult(False, f"the patch does not apply: {applied.stderr.strip()[:300]}")
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = score_task(job.ticket_id, tree)
    finally:
        worktree.destroy(repo, tree)
    verdict = captured.getvalue().strip()
    return StepResult(code == 0, verdict or f"scorer exit {code}")  # scorer exit 0 resolved, 1 unresolved, 2 excluded


DEFAULT_STEPS: dict[str, Step] = {"repro": repro_step, "fix": fix_step, "verify": verify_step}

if __name__ == "__main__":
    raise SystemExit(main())
