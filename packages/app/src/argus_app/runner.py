"""Target-agnostic runner (P8-T06): `python -m argus_app.runner`, the entry point of `.github/workflows/argus-reusable.yml`.

`flow.agent_job` stays the one harness (job read from the environment, `result.json` written last, failure reasons
scrubbed, exit 0 or 1). Its default steps are bound to one target: the dcortex checkout (`ARGUS_PLATFORM_REPO`), a seeded
task on disk, the Vite rig and the bench scorer. These steps replace them and take everything about the target from the
repo's own `.argus.yml` (`argus_app.config`): how to start the app, which routes must answer, how to run the tests, and
how much one issue may spend. No path, port, command or route of any repo is written in this file; a test checks that.

    repro    start the app, check the routes, run the tests on the untouched tree: a baseline report
    fix      the fix loop (`fix_loop.loop.run_fix`) on a worktree, with the ticket from the event payload; makes patch.diff
    verify   a fresh worktree, the patch applied, then the same start, routes and tests; ok only if all three hold

Environment: `ARGUS_TARGET_REPO` (checkout of the repo to work on, default `target`), `ARGUS_OUT`, `ARGUS_STEP`,
`ARGUS_TICKET_ID`, `ARGUS_RUN_KEY`; the ticket is read from `GITHUB_EVENT_PATH` (an `issues` event) or `ARGUS_TICKET_FILE`, so
no GitHub token is needed. `ARGUS_START_TIMEOUT` (seconds, default 120) is how long the app may take to answer.
Each step works in `$ARGUS_OUT/<step>/` and takes the step before it as upstream: the baseline report for fix, the patch for verify.

`.argus.yml` is read once, from the tree as checked out, before any patch exists. A patch that edits `.argus.yml`
cannot change the commands verify runs.

ponytail: the repro step is a baseline, not a model-written reproduction script: that needs a tree without the bug to compare
with, which a live issue does not have (the same gap `flow.agent_job` reports as "not a seeded task"). The default fix agent
is wired from the P3 loop and has not run on a runner. The start command is stopped by killing its process tree; a command
that starts containers (`docker compose up`) leaves them running. The tests never call a model.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path

from argus_core.redact import SECRET_NAME
from flow import agent_job
from flow.agent_job import Job, Step, StepResult, StepUnavailable

from argus_app.config import TenantConfig, load_config

START_TIMEOUT = 120.0
TEST_TIMEOUT = 600
TAIL = 1500  # characters of command output kept in a report

FixAgent = Callable[[Path, Job, TenantConfig, str], tuple[str, str]]  # (tree, job, config, ticket) -> (stop reason, trajectory text)


class TargetError(RuntimeError):
    """The app did not come up or a route did not answer. The message says which and ends with the app's last output."""


# --- the target, from the config ----------------------------------------------------------------------------------


def target_repo(env: Mapping[str, str]) -> Path:
    path = Path(env.get("ARGUS_TARGET_REPO") or "target")
    if not path.is_dir():
        raise StepUnavailable(f"ARGUS_TARGET_REPO {str(path)!r} is not a directory")
    return path.resolve()


def urls(config: TenantConfig) -> list[str]:
    return [config.base_url + route for route in config.routes]


def plan(config: TenantConfig) -> list[str]:
    """What a run would do with this config, as lines of text. Nothing is started."""
    return [f"start: {config.start}", f"test:  {config.test}", *(f"route: {u}" for u in urls(config)),
            f"budget: {config.budget.max_tokens} tokens, {config.budget.max_steps} steps"]


def _clean_env(env: Mapping[str, str]) -> dict[str, str]:
    """The environment of the tenant's own commands: no variable named like a secret (the model key never reaches them)."""
    return {k: v for k, v in env.items() if not SECRET_NAME.search(k)}


def _git(tree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return agent_job._git(tree, *args)


def _diff(tree: Path) -> str:
    """The patch, byte for byte: text mode would turn the CRLF of a file with Windows line ends into LF and the patch would not apply."""
    _git(tree, "add", "-N", ".")  # a new file is part of the patch too
    done = subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(tree), "diff"], capture_output=True)
    return done.stdout.decode("utf-8")


def _toplevel(repo: Path) -> tuple[Path, Path]:
    """(git root, path of `repo` inside it). The target may be a folder of a bigger repository."""
    top = _git(repo, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise StepUnavailable(f"{repo} is not inside a git checkout")
    root = Path(top.stdout.strip()).resolve()
    return root, repo.resolve().relative_to(root)


# --- start, routes, tests -----------------------------------------------------------------------------------------


def _kill(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGTERM)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=10)


def _tail(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")[-TAIL:] if path.is_file() else ""


def _answers(url: str) -> str:
    """'' when the URL answers with a status below 400, else the reason it does not."""
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return "" if r.status < 400 else f"status {r.status}"
    except urllib.error.HTTPError as e:
        return f"status {e.code}"
    except OSError as e:
        return type(e).__name__


@contextlib.contextmanager
def running_app(config: TenantConfig, cwd: Path, log: Path, env: Mapping[str, str], timeout: float = START_TIMEOUT) -> Iterator[None]:
    """Run `config.start` in `cwd` until the block ends; leave the block only after every route has answered."""
    log.parent.mkdir(parents=True, exist_ok=True)
    group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with log.open("wb") as out:
        proc = subprocess.Popen(config.start, shell=True, cwd=cwd, env=_clean_env(env), stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **group)
        try:
            deadline = time.monotonic() + timeout
            while True:
                if proc.poll() is not None:
                    raise TargetError(f"the start command exited with code {proc.returncode} before the app answered. Output:\n{_tail(log)}")
                bad = {u: why for u in urls(config) if (why := _answers(u))}
                if not bad:
                    break
                if time.monotonic() > deadline:
                    raise TargetError(f"after {timeout:.0f} s these routes did not answer: {bad}. Output:\n{_tail(log)}")
                time.sleep(0.5)
            yield
        finally:
            _kill(proc)


def run_tests(config: TenantConfig, cwd: Path, env: Mapping[str, str], timeout: int = TEST_TIMEOUT) -> tuple[int, str]:
    try:
        done = subprocess.run(config.test, shell=True, cwd=cwd, env=_clean_env(env), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"the test command ran over {timeout} s and was stopped"
    return done.returncode, (done.stdout + done.stderr)[-TAIL:]


def check(config: TenantConfig, cwd: Path, log: Path, env: Mapping[str, str]) -> tuple[bool, str]:
    """Start, routes, tests in `cwd`. (every part held, report). A start or route failure is a failed check, not a crash."""
    try:
        with running_app(config, cwd, log, env, float(env.get("ARGUS_START_TIMEOUT") or START_TIMEOUT)):
            routes = "routes answered: " + ", ".join(config.routes)
            code, output = run_tests(config, cwd, env)
    except TargetError as e:
        return False, str(e)
    return code == 0, f"{routes}\ntest command `{config.test}` exited {code}\n{output}".rstrip()


# --- the steps ----------------------------------------------------------------------------------------------------


def read_ticket(env: Mapping[str, str]) -> str:
    path = env.get("ARGUS_TICKET_FILE") or env.get("GITHUB_EVENT_PATH")
    if not path or not Path(path).is_file():
        raise StepUnavailable("no ticket: GITHUB_EVENT_PATH (an issues event) and ARGUS_TICKET_FILE are not set")
    issue = json.loads(Path(path).read_text(encoding="utf-8")).get("issue")
    if not isinstance(issue, dict) or not issue.get("title"):
        raise StepUnavailable("the event has no issue with a title; run it from an `issues` event")
    return f"{issue['title']}\n\n{issue.get('body') or ''}"


def _label(ticket_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", ticket_id)


def _fix_agent(tree: Path, job: Job, config: TenantConfig, ticket: str) -> tuple[str, str]:
    """The P3 fix loop on `tree`, routed to the tenant's own model key. The commands run in the no-network sandbox, which has
    no toolchain: the test command is for the verify step, and the prompt says so."""
    from fix_loop.loop import run_fix
    from fix_loop.strategies import cap_strategy
    from fix_loop.turn import PROTOCOL, _execute

    policy, router = agent_job._router(job)
    checks = job.out / "checks"
    checks.mkdir(parents=True, exist_ok=True)
    result = run_fix(
        worktree=tree, model=policy.tiers[policy.stages["fix"]].primary.model, host="groq", router=router, stage="fix",
        out_dir=job.out / "fix", step_cap=config.budget.max_steps, token_cap=config.budget.max_tokens, run_id=job.run_key,
        git_commit=agent_job._head(), task_id=_label(job.ticket_id), system=PROTOCOL, execute=_execute(tree, checks),
        context_budget=32_000, strategy=cap_strategy,
        user=f"Ticket:\n{ticket}\n\nBaseline: {job.upstream or 'not-run'}\n"
             f"The repo's tests run after you finish with `{config.test}`; they cannot run in your sandbox.\n",
    )
    return result.stop_reason.value, agent_job._read(result.trajectory_path)


def build_steps(env: Mapping[str, str], fix_agent: FixAgent = _fix_agent) -> dict[str, Step]:
    def setup(job: Job) -> tuple[Path, TenantConfig]:
        repo = target_repo(env)
        return repo, load_config(repo)  # read once, before any patch

    def repro(job: Job) -> StepResult:
        repo, config = setup(job)
        ok, report = check(config, repo, job.out / "app.log", env)
        # a baseline succeeds when the app starts and every route answers, whatever the tests say: a test that already
        # fails is part of the evidence the fix step gets
        return StepResult(report.startswith("routes answered"), report)

    def fix(job: Job) -> StepResult:
        from fix_loop import worktree

        repo, config = setup(job)
        ticket = read_ticket(env)
        root, prefix = _toplevel(repo)
        tree = worktree.create(root, _label(job.ticket_id), "HEAD", root=job.out / "trees")
        try:
            reason, trajectory = fix_agent(tree / prefix, job, config, ticket)
            patch = _diff(tree)
        finally:
            worktree.destroy(root, tree)
        if not patch.strip():
            return StepResult(False, f"the fix loop made no change: {reason}", trajectory=trajectory)
        return StepResult(True, patch, patch=patch, trajectory=trajectory)

    def verify(job: Job) -> StepResult:
        from fix_loop import worktree

        repo, config = setup(job)
        root, prefix = _toplevel(repo)
        tree = worktree.create(root, _label(job.ticket_id), "HEAD", root=job.out / "trees")
        try:
            handed = job.out / "upstream.txt"  # read as bytes: `job.upstream` has had its CRLF turned into LF
            upstream = handed.read_bytes() if handed.is_file() else job.upstream.encode("utf-8")
            if upstream.strip():  # empty means "verify the checkout as it is" (the self-test run has no fix before it)
                patch = job.out / "upstream.patch"
                patch.write_bytes(upstream)
                applied = _git(tree, "apply", str(patch))
                if applied.returncode != 0:
                    return StepResult(False, f"the patch does not apply: {applied.stderr.strip()[:300]}")
            ok, report = check(config, tree / prefix, job.out / "app.log", env)
        finally:
            worktree.destroy(root, tree)
        return StepResult(ok, report)

    return {"repro": repro, "fix": fix, "verify": verify}


# --- entry ----------------------------------------------------------------------------------------------------------


UPSTREAM = {"fix": ("repro", "result.json"), "verify": ("fix", "patch.diff")}


def _hand_over(root: Path, step: str, out: Path) -> None:
    """Write `out/upstream.txt` from the step before: its `result.json` output (repro), or its `patch.diff` (fix)."""
    before = UPSTREAM.get(step)
    if before is None:
        return
    src = root / before[0] / before[1]
    if src.is_file():
        data = src.read_bytes()
        out.mkdir(parents=True, exist_ok=True)
        (out / "upstream.txt").write_bytes(json.loads(data)["output"].encode("utf-8") if src.suffix == ".json" else data)


def run(env: Mapping[str, str] | None = None, steps: Mapping[str, Step] | None = None) -> int:
    env = dict(os.environ if env is None else env)
    root = Path(env.get("ARGUS_OUT") or "argus-out")
    out = root / env.get("ARGUS_STEP", "")
    _hand_over(root, env.get("ARGUS_STEP", ""), out)
    return agent_job.main({**env, "ARGUS_OUT": str(out)}, steps or build_steps(env))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["plan"] and len(args) == 2:  # `plan <repo folder or .argus.yml>`: print what a run would do, start nothing
        print("\n".join(plan(load_config(args[1]))))
        return 0
    if args:
        print("usage: python -m argus_app.runner [plan <repo folder or .argus.yml>]", file=sys.stderr)
        return 2
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
