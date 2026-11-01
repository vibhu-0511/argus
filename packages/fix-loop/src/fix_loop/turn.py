"""Claude-as-model turns for the fix loop. No provider call.

Each call replays `run_fix` from `answers.jsonl` in a clean worktree. The first model call with no stored
answer ends the call and prints what the model must see. `answer` appends one reply and replays again.
Token counts are chars/4 estimates of the messages, not provider usage.

    python -m fix_loop.turn start <task dir> <run id> [none|cap|offload|summary [budget]]
    python -m fix_loop.turn answer <run id> < reply.json     (reply is one JSON tool call)
    python -m fix_loop.turn show <run id>                    (strategy runs only: print the pending turn again)

With a strategy the call is stateless: every turn prints the whole message list the loop would send, so a fresh
model sees exactly what the strategy left it. `answer` then prints one status
line, not the next turn, so the model that answers a turn never sees the next one. The summary strategy asks for one plain-text reply (not JSON).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota

from fix_loop import sandbox, worktree
from fix_loop.loop import run_fix
from fix_loop.strategies import cap_strategy, offload, summary_strategy
from fix_loop.tools import RunCmdArgs, ToolError, ToolResult, _interactive, call

MODEL = "claude-session"
HOST = "claude-session"
RUNS = Path(__file__).resolve().parents[2] / "runs"
REPO = Path(__file__).resolve().parents[4]
STEP_CAP = 20
TOKEN_CAP = 400_000  # v1 pilot used 150_000 and every run hit it; raised before the v2 pilot
# Self-imposed run budget. docs/quotas.md has no Claude row and none was added; this is not a provider limit.
BUDGET = {MODEL: ModelQuota(300, 10**7, 300, 10**7, False)}

PROTOCOL = """Reply with exactly one JSON object and nothing else: {"tool": "<name>", "arguments": {...}}.
Tools:
- read_file {"path"}: read a UTF-8 file in the worktree.
- list_dir {"path"}: list names in a directory.
- search {"query", "path"}: find an exact string, returns file:line:text.
- edit {"path", "old", "new"}: replace one exact occurrence. Whitespace counts. A second match is an error that names the lines.
- run_cmd {"command"}: run a sh command in the worktree. No network.
- submit {}: finish. Call it once the ticket is fixed.
Fix the ticket with the smallest change."""


class NeedTurn(Exception):
    def __init__(self, messages: list[dict]):
        self.messages = messages


DISPLAY = 20_000  # the Bash tool cuts long output without saying so; the driver cuts at 20k and says so


def _show(text: str) -> str:
    if len(text) <= DISPLAY:
        return text
    return f"{text[:DISPLAY]}\n[driver display cut: the loop sent {len(text)} characters, {DISPLAY} shown]"


def _est(text: str) -> int:
    return max(1, len(text) // 4)


def _complete(answers: list[str]):
    seen = {"n": 0}

    def complete(messages: list[dict]) -> Completion:
        if seen["n"] >= len(answers):
            raise NeedTurn(messages)
        content = answers[seen["n"]]
        seen["n"] += 1
        return Completion(content, Usage(_est(json.dumps(messages)), _est(content), 0), {})

    return complete


def _execute(tree: Path, checks: Path):
    def execute(name: str, payload: dict) -> ToolResult | ToolError:
        if name != "run_cmd":
            return call(name, payload, tree)
        try:
            args = RunCmdArgs.model_validate(payload)
        except Exception as exc:
            return ToolError(error="failed", message=str(exc).splitlines()[0])
        if _interactive(args.command):
            return ToolError(error="not-allowed", message="interactive command rejected")
        try:
            proc = sandbox.run(tree, checks, ["sh", "-c", args.command], timeout=30)
        except subprocess.TimeoutExpired:
            return ToolError(error="timeout", message="command timed out after 30s")
        return ToolResult(tool="run_cmd", text=proc.stdout + proc.stderr, returncode=proc.returncode)

    return execute


def _git(tree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-C", str(tree), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def _reset(tree: Path, bug: str) -> None:
    _git(tree, "checkout", "--", ".")
    _git(tree, "clean", "-fdq")
    patch = tree.parent / "bug.patch"
    patch.write_bytes(bug.encode("utf-8"))  # bytes: text mode would turn LF into CRLF on Windows
    applied = _git(tree, "apply", str(patch))
    if applied.returncode != 0:
        raise RuntimeError(applied.stderr.strip())


def _platform() -> Path:
    from argus_bench.golden import platform_repo

    return platform_repo()


STRATEGIES = ("none", "cap", "offload", "summary")
BUDGET_DEFAULT = 32_000  # estimated tokens; a strategy runs at 80% of it (loop semantics). A choice, not a measurement.
SUMMARY_PROMPT = "Summarize the earlier turns."


def _strategy(name: str, tree: Path, complete, ledger: Ledger):
    if name == "cap":
        return cap_strategy
    if name == "summary":
        summarize = summary_strategy(complete, ledger, MODEL)

        def strategy(messages: list[dict], used: int, budget: int) -> list[dict]:
            # the summarizer sees each earlier turn cut at DISPLAY, like every other prompt; a raw 1 MB tool output is unreadable
            cut = [{**m, "content": _show(str(m.get("content") or ""))} for m in messages]
            return summarize(cut, used, budget)

        return strategy
    if name == "offload":
        def strategy(messages: list[dict], used: int, budget: int) -> list[dict]:
            del used, budget
            last = messages[-1]
            body = offload(str(last.get("content") or ""), tree, f"obs-{len(messages)}.txt")
            return [*messages[:-1], {**last, "content": body}]

        return strategy
    return None


def wrong_kind(kind: str, reply: str) -> str | None:
    """A summary request takes plain text, a turn takes one JSON tool call. A reply of the other kind would shift every later reply by one."""
    try:
        body = json.loads(reply)
    except json.JSONDecodeError:
        body = None
    is_call = isinstance(body, dict) and "tool" in body
    if kind == "summary" and is_call:
        return "this turn is a summary request: reply with plain text, not a tool call"
    if kind == "turn" and not is_call:
        return "this turn needs one JSON tool call, not plain text"
    return None


def _print_full(out: Path, messages: list[dict]) -> None:
    summary = messages[0].get("content") == SUMMARY_PROMPT
    # variant A in the stateful runs also showed each message cut at DISPLAY; keep that so the rows compare
    body = (lambda c: c) if summary else _show
    text = "\n\n".join(f"[{m['role']}]\n{body(str(m['content']))}" for m in messages)
    if summary:
        text = "[THIS TURN IS A SUMMARY REQUEST. REPLY WITH PLAIN TEXT ONLY, NOT JSON.]" + chr(10) + chr(10) + text
        text += "\n\n[REPLY WITH THE PLAIN-TEXT SUMMARY ONLY, NOT JSON. It must be shorter than the turns above.]"
    if len(text) <= DISPLAY:
        print(text)
        return
    dest = out / "prompt.txt"
    dest.write_text(text, encoding="utf-8", newline="\n")
    print(f"[prompt too long to print: {len(text)} characters in {dest}. Read the whole file with the Read tool, in pieces if needed, then answer.]")


def start(task: Path, run_id: str, strategy: str = "", budget: int = BUDGET_DEFAULT) -> int:
    out = RUNS / run_id
    out.mkdir(parents=True, exist_ok=False)
    checks = out / "checks"
    checks.mkdir()
    shutil.copy(task / "checks.json", checks / "checks.json")  # golden.patch stays out of the mount
    tree = worktree.create(_platform(), task.name, "HEAD", root=out)
    (out / "task.json").write_text(json.dumps({"task": str(task), "tree": str(tree), "strategy": strategy, "budget": budget}), encoding="utf-8")
    (out / "answers.jsonl").write_text("", encoding="utf-8")
    return _replay(out)


def answer(run_id: str, reply: str) -> int:
    out = RUNS / run_id
    pending = out / "pending.json"
    if json.loads((out / "task.json").read_text(encoding="utf-8")).get("strategy") and pending.exists():
        problem = wrong_kind(json.loads(pending.read_text(encoding="utf-8"))["kind"], reply)
        if problem:
            print(f"rejected, nothing recorded: {problem}")
            return 3
    with (out / "answers.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(reply) + "\n")
    return _replay(out, quiet=bool(json.loads((out / "task.json").read_text(encoding="utf-8")).get("strategy")))


def _replay(out: Path, quiet: bool = False) -> int:
    meta = json.loads((out / "task.json").read_text(encoding="utf-8"))
    task, tree = Path(meta["task"]), Path(meta["tree"])
    ticket = json.loads((task / "ticket.json").read_text(encoding="utf-8"))
    answers = [json.loads(line) for line in (out / "answers.jsonl").read_text(encoding="utf-8").splitlines() if line]
    _reset(tree, (task / "bug.patch").read_text(encoding="utf-8"))
    name = meta.get("strategy", "")
    with tempfile.TemporaryDirectory() as scratch:
        ledger = Ledger(Path(scratch) / "ledger.json", BUDGET)
        complete = _complete(answers)
        try:
            result = run_fix(
                worktree=tree, model=MODEL, ledger=ledger, complete=complete, out_dir=out,
                step_cap=STEP_CAP, token_cap=TOKEN_CAP, run_id=out.name, host=HOST, git_commit=_head(),
                task_id=ticket["id"], system=PROTOCOL,
                user=f"Ticket:\n{ticket['text']}\n\nRepro: not-run\nLocate: none\n",
                execute=_execute(tree, out / "checks"),
                context_budget=int(meta.get("budget", BUDGET_DEFAULT)) if name else None,
                strategy=_strategy(name, tree, complete, ledger) if name else None,
            )
        except NeedTurn as need:
            last = need.messages[-1]
            kind = "summary" if need.messages[0].get("content") == SUMMARY_PROMPT else "turn"
            (out / "pending.json").write_text(json.dumps({"kind": kind}), encoding="utf-8")
            if quiet:
                print(f"recorded {len(answers)} answers; the next turn is pending")
            elif name:
                _print_full(out, need.messages)
            elif len(need.messages) == 2:
                for item in need.messages:
                    print(f"[{item['role']}]\n{_show(item['content'])}\n")
            else:
                print(f"[observation after step {len(answers)}]\n{_show(last['content'])}")
            return 0
        code = subprocess.run(
            [str(Path(sys.executable).parent / "bench"), "score", str(task), "--tree", str(tree)],
            cwd=REPO, capture_output=True, text=True, encoding="utf-8",
        ).returncode
        verdict = {"task_id": ticket["id"], "stop_reason": result.stop_reason.value, "score_exit": code,
                   "verdict": "excluded" if code == 2 else "resolved" if code == 0 else "unresolved",
                   "model": MODEL, "model_turns": len(answers), "token_source": "chars/4 estimate"}
        (out / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
        (out / "diff.patch").write_text(_git(tree, "diff").stdout, encoding="utf-8", newline="\n")
        worktree.destroy(_platform(), tree)
        print(json.dumps(verdict))
        return 0


def _head() -> str:
    return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows stdout is cp1252 and crashed on '→'
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) in (3, 4, 5) and args[0] == "start":
        if len(args) > 3 and args[3] not in STRATEGIES:
            print(f"strategy must be one of {STRATEGIES}", file=sys.stderr)
            return 2
        return start(Path(args[1]).resolve(), args[2], *(args[3:4]), *(int(a) for a in args[4:5]))
    if len(args) == 2 and args[0] == "show":
        return _replay(RUNS / args[1])
    if len(args) == 2 and args[0] == "answer":
        return answer(args[1], sys.stdin.read().strip())
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
