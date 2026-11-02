"""P5-T20 with the argus fix loop and Claude sessions as the model: one fresh subagent per model turn.

The pattern of `eval.t14_turn` (and `fix_loop.turn`): no provider call. Each driver call replays `fix_loop.loop.run_fix` for one task from
`answers.jsonl`; the first model call with no stored answer ends the call and prints what that turn's model must see. The loop is the real
one: six typed tools (read_file, list_dir, search, ast_grep, edit, run_cmd, submit), stop reasons, context strategy `cap` at 32,000
estimated tokens, a trajectory JSONL. The task is a SWE-bench Multimodal instance prepared by `eval multimodal prepare` (checkout at
`base_commit`, issue images saved as local files, prompt = `build_prompt`; the gold patch is not in `MultimodalTask`, so it cannot get in).
The prediction is the checkout's diff, captured by `multimodal_run.finish` as `<root>/<id>/model.diff`.

    python -m eval.mm_turn start <instance id>        prepare the task (network: one git fetch, the images) and print the first status line
    python -m eval.mm_turn show <instance id>         print the pending turn (the whole message list, so a fresh worker needs no memory)
    python -m eval.mm_turn answer <instance id> < reply   store one reply (one JSON tool call); prints one status line
    python -m eval.mm_turn status <instance id>       the status line again, or the verdict line
    python -m eval.mm_turn results --out F [--reports DIR] [--only ID ...]   results JSON from the finished runs

Runs live under $MM_RUNS (default packages/eval/runs/mm, not committed). Tokens are chars/4 estimates of the messages, not provider usage.

`run_cmd` here does not use the Docker sandbox of the Canvas runs (the repos' tests cannot run in a bare checkout and Docker is kept for
grading). It runs, without a shell, only read-only `git diff|status|log|show|ls-files|grep` and `node --check <file>` (a syntax check). Anything
else is a `not-allowed` tool error. The SWE-bench harness is what runs the tests.

ponytail: a replay re-runs the tools from a clean checkout every turn, so a turn costs more as the answers pile up (as in the P3/P4 driver).
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import Trajectory

from eval.ablation import _totals
from eval.multimodal import MultimodalTask, load_subset
from eval.multimodal_run import _download, finish, prepare, task_row
from eval.results import TokenCounts
from eval.runner import AgentConfig, _aggregate

HOST = "claude-session"
MODEL = "claude-sonnet-5-5"  # the model named in the trajectory; it has a row in prices.json. The worker model is sonnet (Agent `model` parameter).
WORKER_MODEL = "sonnet"
STRATEGY, BUDGET_TOKENS = "cap", 32_000  # the fix loop's context strategy and budget, the P3/P4 harness defaults
RUNS = Path(os.environ.get("MM_RUNS") or Path(__file__).resolve().parents[2] / "runs" / "mm")
# Self-imposed run budget, NOT a provider limit (docs/quotas.md has no Claude row); a fresh ledger is built on every replay.
BUDGET = {MODEL: ModelQuota(300, 10**7, 300, 10**7, False)}

PROTOCOL = """Reply with exactly one JSON object and nothing else: {"tool": "<name>", "arguments": {...}}.
Tools (paths are relative to the repository checkout):
- read_file {"path"}: read a UTF-8 file.
- list_dir {"path"}: list names in a directory.
- search {"query", "path"}: find an exact string, returns file:line:text.
- ast_grep {"pattern", "path", "lang"}: find code by syntax, returns file:line. Use lang "js" or "ts" or "jsx" or "tsx".
- edit {"path", "old", "new"}: replace one exact occurrence. Whitespace counts. A second match is an error that names the lines.
- run_cmd {"command"}: only read-only git (diff, status, log, show, ls-files, grep) and `node --check <file>` (syntax check). The repository's tests cannot run here.
- submit {}: finish. Call it once the issue is fixed.
The issue text says where its screenshots are; they are local image files. Fix the issue with the smallest change."""

READ_ONLY_GIT = {"diff", "status", "log", "show", "ls-files", "grep"}
GIT_BAD = ("--output", "--open-files-in-pager", "-O", "--ext-diff", "--textconv", "--exec")  # flags that write files or run programs


def _run_cmd(tree: Path, command: str):
    """The whole of run_cmd in this run: no shell, an allowlist, 30 s."""
    from fix_loop.tools import ToolError, ToolResult  # fix_loop is imported lazily, as in eval.ablation

    if any(ch in command for ch in "|;&><`$\n"):
        return ToolError(error="not-allowed", message="no shell syntax: one plain command only")
    try:
        argv = shlex.split(command, posix=True)
    except ValueError:
        return ToolError(error="failed", message="could not parse the command")
    git_ok = len(argv) > 1 and argv[0] == "git" and argv[1] in READ_ONLY_GIT and not any(a.startswith(GIT_BAD) for a in argv[2:])
    node_ok = len(argv) == 3 and argv[:2] == ["node", "--check"] and _inside(tree, argv[2])
    if not (git_ok or node_ok):
        return ToolError(error="not-allowed", message="run_cmd allows only read-only git (diff, status, log, show, ls-files, grep) and node --check <file>")
    try:
        proc = subprocess.run(argv, cwd=tree, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except subprocess.TimeoutExpired:
        return ToolError(error="timeout", message="command timed out after 30s")
    except OSError as exc:
        return ToolError(error="failed", message=str(exc))
    return ToolResult(tool="run_cmd", text=proc.stdout + proc.stderr, returncode=proc.returncode)


def _inside(tree: Path, raw: str) -> bool:
    try:
        (tree / raw).resolve().relative_to(tree.resolve())
    except ValueError:
        return False
    return True


def _execute(tree: Path) -> Callable[[str, dict], object]:
    from fix_loop.tools import ToolError, call

    def execute(name: str, payload: dict):
        if name != "run_cmd":
            return call(name, payload, tree)
        command = payload.get("command")
        if not isinstance(command, str) or not command.strip():
            return ToolError(error="failed", message="missing command")
        return _run_cmd(tree, command)

    return execute


def _reset(tree: Path) -> None:
    for args in (("checkout", "--", "."), ("clean", "-fdq")):
        subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(tree), *args], capture_output=True, check=True)


def _head() -> str:
    repo = Path(__file__).resolve().parents[4]
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"


def _task(task_id: str) -> MultimodalTask:
    found = next((t for t in load_subset() if t.id == task_id), None)
    if found is None:
        raise SystemExit(f"{task_id} is not in the committed multimodal subset")
    return found


def start(task: MultimodalTask, root: Path, repo_url: str | None = None, download: Callable[[str, Path], None] = _download) -> int:
    work = root / task.id
    if (work / "task.json").exists():
        raise SystemExit(f"{task.id} was already started under {root}")
    prepare(task, root, repo_url, download)
    meta = {"task": task.id, "tree": str(work / "checkout"), "strategy": STRATEGY, "budget": BUDGET_TOKENS, "started_at": time.time()}
    (work / "task.json").write_text(json.dumps(meta), encoding="utf-8")
    (work / "answers.jsonl").write_text("", encoding="utf-8")
    return _replay(task, root, quiet=True)


def answer(task: MultimodalTask, root: Path, reply: str) -> int:
    from fix_loop.turn import wrong_kind

    work = root / task.id
    if (work / "verdict.json").exists():
        print((work / "verdict.json").read_text(encoding="utf-8"))
        return 0
    problem = wrong_kind("turn", reply)
    if problem:
        print(f"rejected, nothing recorded: {problem}")
        return 3
    with (work / "answers.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(reply) + "\n")
    return _replay(task, root, quiet=True)


def _replay(task: MultimodalTask, root: Path, quiet: bool = False) -> int:
    from fix_loop.loop import run_fix
    from fix_loop.strategies import cap_strategy
    from fix_loop.turn import STEP_CAP, TOKEN_CAP, NeedTurn, _complete, _print_full

    work = root / task.id
    meta = json.loads((work / "task.json").read_text(encoding="utf-8"))
    tree = Path(meta["tree"])
    answers = [json.loads(line) for line in (work / "answers.jsonl").read_text(encoding="utf-8").splitlines() if line]
    prompt = (work / "prompt.txt").read_bytes().decode("utf-8")
    _reset(tree)
    with tempfile.TemporaryDirectory() as scratch:
        try:
            result = run_fix(
                worktree=tree, model=MODEL, ledger=Ledger(Path(scratch) / "ledger.json", BUDGET), complete=_complete(answers), out_dir=work / "fix",
                step_cap=STEP_CAP, token_cap=TOKEN_CAP, run_id=f"mm-{task.id}", host=HOST, git_commit=_head(), task_id=task.id, system=PROTOCOL,
                user=prompt, execute=_execute(tree), context_budget=BUDGET_TOKENS, strategy=cap_strategy,
            )
        except NeedTurn as need:
            if quiet:
                print(f"recorded {len(answers)} answers; next: worker_model={WORKER_MODEL}")
            else:
                (work / "turn").mkdir(exist_ok=True)  # _print_full may write prompt.txt: keep it away from the task's own prompt.txt
                _print_full(work / "turn", need.messages)
            return 0
    patch = finish(task, root)  # model.diff, and a check that it applies to a clean base
    now = time.time()
    verdict = {
        "task_id": task.id, "stop_reason": result.stop_reason.value, "verdict": "patch-captured" if patch.strip() else "empty-patch",
        "patch_lines": len(patch.splitlines()), "model_turns": len(answers), "model": MODEL, "worker_model": WORKER_MODEL, "token_source": "chars/4 estimate",
        "started_at": meta["started_at"], "finished_at": now, "wall_s": round(now - meta["started_at"], 1),
    }
    (work / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdict))
    return 0


# --- results -----------------------------------------------------------------------------------------------


def results(tasks: list[MultimodalTask], root: Path, reports: Path | None, config: AgentConfig, run_id: str):
    """Rows as in `multimodal_run.results` (a produced patch counts only when the harness graded it), plus steps, stop reason, tokens, wall time."""
    rows, dollars = [], {}
    for t in tasks:
        row = task_row(t, root, reports)
        traj, verdict = root / t.id / "fix" / "trajectory.jsonl", root / t.id / "verdict.json"
        if traj.exists():
            tin, tout, tcached, usd = _totals([traj])
            info = json.loads(verdict.read_text(encoding="utf-8")) if verdict.exists() else {}
            row = row.model_copy(update={
                "stop_reason": info.get("stop_reason"), "steps": len(Trajectory.from_jsonl(traj.read_text(encoding="utf-8")).steps),
                "tokens": TokenCounts(tokens_in=tin, tokens_out=tout, tokens_cached=tcached), "latency_s": info.get("wall_s"), "trajectory": str(traj),
            })
            if usd is not None:
                dollars[t.id] = usd
        rows.append(row)
    return _aggregate(rows, config, run_id, datetime.now(UTC), dollars)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == "start":
        return start(_task(args[1]), RUNS)
    if len(args) == 2 and args[0] in ("show", "status", "answer"):
        task, work = _task(args[1]), RUNS / args[1]
        if args[0] == "answer":
            return answer(task, RUNS, sys.stdin.read().strip())
        if (work / "verdict.json").exists():
            print((work / "verdict.json").read_text(encoding="utf-8"))
            return 0
        if args[0] == "status":
            n = len((work / "answers.jsonl").read_text(encoding="utf-8").splitlines())
            print(f"recorded {n} answers; next: worker_model={WORKER_MODEL}")
            return 0
        return _replay(task, RUNS)
    if args and args[0] == "results":
        parser = argparse.ArgumentParser(prog="eval.mm_turn results")
        parser.add_argument("--out", type=Path, required=True)
        parser.add_argument("--reports", type=Path, help="folder holding only this run's harness report.json files")
        parser.add_argument("--only", nargs="*", default=[])
        ns = parser.parse_args(args[1:])
        tasks = [t for t in load_subset() if not ns.only or t.id in ns.only]
        from fix_loop.turn import STEP_CAP as step_cap, TOKEN_CAP as token_cap

        config = AgentConfig(
            name="argus-fix-loop-claude-session", model=MODEL, host=HOST, factory="eval.mm_turn:results",
            params={"claude_session": True, "worker_model": WORKER_MODEL, "tools": ["read_file", "list_dir", "search", "ast_grep", "edit", "run_cmd", "submit"],
                    "run_cmd": "read-only git and node --check only, no Docker", "fix_context": {"strategy": STRATEGY, "budget": BUDGET_TOKENS},
                    "step_cap": step_cap, "token_cap": token_cap, "token_source": "chars/4 estimate of the messages; excludes subagent harness overhead"},
        )
        res = results(tasks, RUNS, ns.reports, config, "t20-multimodal-argus")
        ns.out.write_text(res.to_json(), encoding="utf-8")
        rate = res.resolve_rate
        print(f"{config.name}: {rate.successes}/{rate.total} resolved over {len(tasks)} tasks, wrote {ns.out}")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
