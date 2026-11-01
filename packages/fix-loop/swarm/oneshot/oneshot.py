"""P0-T28 one-shot baseline redone with the session model (claude-session): one call, ticket plus current text of the files
named in bug.patch, no tools. Same prompt builder as `bench baseline`; the reply is a unified diff, applied and scored like a run.

    oneshot.py prep <seeded task suffix> [run id]   create runs/p0c-oneshot-<suffix> (worktree with bug.patch applied, prompt.txt)
    oneshot.py show <run id>                  print the prompt
    oneshot.py answer <run id> < reply        apply the diff, score, write verdict.json, print the verdict line

Deviations from the gpt-oss-20b run in P0-T29, all mine: the model is the session model; the worker is told to reply with a
unified diff only (the P0 prompt had no such line); code fences around the diff are stripped; `git apply --recount --unidiff-zero` is used because
models miscount hunk headers and may leave out context lines (e02's first reply did; the strict run was re-scored with the same reply); a diff that does not apply is `unresolved` with the apply error recorded (set ONESHOT_LENIENT=1 to retry
with GNU `patch -l --fuzz=3` on the same saved reply: used only to re-score). All 29 runnable seeded
tasks instead of 10. Tokens are chars/4 estimates; the ledger is the self-imposed 300-call budget of turn.py, not a provider limit.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from argus_bench.baseline import _prompt
from argus_core.ledger import Ledger, Usage
from fix_loop import turn, worktree

RUNS, REPO = turn.RUNS, turn.REPO
BENCH = REPO / "packages" / "bench" / "tasks" / "seeded"
DISPLAY = 20_000
HEADER = "Reply with the unified diff (git format, paths a/... and b/..., hunk context copied exactly from the file text below) that fixes the ticket, and nothing else.\n\n"


def est(text: str) -> int:
    return max(1, len(text) // 4)


def prep(suffix: str, run: str = "") -> int:
    task = BENCH / f"seed-{suffix}"
    out = RUNS / (run or f"p0c-oneshot-{suffix}")
    out.mkdir(parents=True, exist_ok=False)
    checks = out / "checks"
    checks.mkdir()
    shutil.copy(task / "checks.json", checks / "checks.json")
    tree = worktree.create(turn._platform(), task.name, "HEAD", root=out)
    bug = (task / "bug.patch").read_text(encoding="utf-8")
    turn._reset(tree, bug)
    ticket = json.loads((task / "ticket.json").read_text(encoding="utf-8"))
    prompt = _prompt(ticket["text"], bug, tree)
    (out / "prompt.txt").write_text(prompt, encoding="utf-8", newline="\n")
    (out / "task.json").write_text(json.dumps({"task": str(task), "tree": str(tree), "tokens_in": est(prompt)}), encoding="utf-8")
    print(f"prepared {out.name}: prompt {len(prompt)} characters")
    return 0


def show(run: str) -> int:
    prompt = (RUNS / run / "prompt.txt").read_text(encoding="utf-8")
    if len(prompt) <= DISPLAY:
        print(HEADER + prompt)
    else:
        print(f"[{HEADER.strip()}]\n[prompt too long to print: {len(prompt)} characters in {RUNS / run / 'prompt.txt'}. Read the whole file with the Read tool, in pieces if needed, then answer.]")
    return 0


def extract(reply: str) -> str:
    lines = [ln for ln in reply.replace("\r\n", "\n").split("\n") if not ln.startswith("```")]
    start = next((i for i, ln in enumerate(lines) if ln.startswith(("diff --git", "--- "))), None)
    return "" if start is None else "\n".join(lines[start:]).rstrip("\n") + "\n"


def answer(run: str, reply: str) -> int:
    out = RUNS / run
    if (out / "verdict.json").exists():
        print("rejected: this run already has a verdict")
        return 3
    meta = json.loads((out / "task.json").read_text(encoding="utf-8"))
    task, tree = Path(meta["task"]), Path(meta["tree"])
    patch = extract(reply)
    (out / "reply.txt").write_text(reply, encoding="utf-8", newline="\n")
    (out / "reply.patch").write_bytes(patch.encode("utf-8"))
    Ledger(out / "ledger.json", turn.BUDGET).call(turn.MODEL, lambda: Usage(meta["tokens_in"], est(reply), 0), token_estimate=meta["tokens_in"])
    error, code, mode = "", None, "git"
    if not patch:
        error = "no diff found in the reply"
    else:
        applied = turn._git(tree, "apply", "--recount", "--unidiff-zero", "--whitespace=nowarn", str(out / "reply.patch"))
        if applied.returncode != 0:
            error = applied.stderr.strip()[:300]
            if os.environ.get("ONESHOT_LENIENT"):  # re-score only: GNU patch tolerates offsets, fuzz and blank context lines without the leading space
                fallback = subprocess.run(["patch", "-p1", "-l", "--fuzz=3", "--no-backup-if-mismatch", "-s", "-i", str(out / "reply.patch")],
                                          cwd=tree, capture_output=True, text=True, encoding="utf-8")
                if fallback.returncode == 0:
                    error, mode = "", "patch"
    if not error:
        code = subprocess.run([sys.executable, "-m", "argus_bench.cli", "score", str(task), "--tree", str(tree)],
                              cwd=REPO, capture_output=True, text=True, encoding="utf-8").returncode
    ticket = json.loads((task / "ticket.json").read_text(encoding="utf-8"))
    verdict = {"task_id": ticket["id"], "applied": not error, "apply_mode": mode, "apply_error": error, "score_exit": code,
               "verdict": "excluded" if code == 2 else "resolved" if code == 0 else "unresolved", "model": turn.MODEL,
               "tokens_in": meta["tokens_in"], "tokens_out": est(reply), "token_source": "chars/4 estimate", "variant": "P0 one-shot, claude-session"}
    (out / "diff.patch").write_text(turn._git(tree, "diff").stdout, encoding="utf-8", newline="\n")
    worktree.destroy(turn._platform(), tree)
    (out / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdict))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prep":
        raise SystemExit(prep(*sys.argv[2:4]))
    if cmd == "show":
        raise SystemExit(show(sys.argv[2]))
    raise SystemExit(answer(sys.argv[2], sys.stdin.read()))
