"""P5.5-T05 driver: Claude subagents as the cheap-tier draft model (no provider key, no network).

    python -m skills.draft_claude prepare --runs packages/skills/trajectories --work packages/skills/draft-runs/p55-t05
    ... one fresh Haiku subagent per group reads <work>/gNN.prompt.json and writes its reply to <work>/gNN.reply.txt ...
    python -m skills.draft_claude finish  --runs packages/skills/trajectories --work packages/skills/draft-runs/p55-t05

`prepare` uses `skills.draft.groups` and `render_run`, so the same runs, the same train-only rule and the same prompt
reach the model as with `skills.draft`. `finish` feeds each stored reply to `skills.draft.draft_group` (the same format
check, the same refusals, the same frontmatter written by the script) and writes `<work>/ledger.json`.

ponytail: tokens are chars/4 estimates of the prompt and reply files. A subagent's own harness overhead is not visible.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from argus_core.client import Completion, Usage

from skills.draft import PER_SKILL, SKILLS_DIR, draft_group, groups, prompt, render_run, successes
from skills.split import SPLIT


def _plan(runs: Path, per_skill: int):
    train = set(json.loads(SPLIT.read_text(encoding="utf-8"))["train"])
    return groups(successes(runs, train), per_skill)


def prepare(runs: Path, work: Path, per_skill: int = PER_SKILL) -> list[str]:
    work.mkdir(parents=True, exist_ok=True)
    made = []
    for n, (archetype, paths) in enumerate(_plan(runs, per_skill), 1):
        texts = {task: render_run(task, path) for task, path in paths.items()}
        messages = prompt(archetype, texts)
        (work / f"g{n:02d}.prompt.json").write_text(json.dumps({"archetype": archetype, "runs": list(paths), "messages": messages}, indent=2) + "\n", encoding="utf-8", newline="\n")
        made.append(f"g{n:02d}")
    return made


def finish(runs: Path, work: Path, out: Path = SKILLS_DIR, per_skill: int = PER_SKILL) -> dict:
    rows = []
    for n, (archetype, paths) in enumerate(_plan(runs, per_skill), 1):
        key = f"g{n:02d}"
        reply_file = work / f"{key}.reply.txt"
        saved = json.loads((work / f"{key}.prompt.json").read_text(encoding="utf-8"))
        assert saved["runs"] == list(paths), f"{key}: prompt was made for other runs; run prepare again"
        row = {"group": key, "archetype": archetype, "sources": list(paths), "tokens_in": sum(len(m["content"]) for m in saved["messages"]) // 4}
        if not reply_file.is_file():
            rows.append({**row, "result": "no reply", "path": None, "tokens_out": 0})
            continue
        reply = reply_file.read_text(encoding="utf-8")
        done = Completion(reply, Usage(row["tokens_in"], len(reply) // 4, 0), {})
        path, note, _ = draft_group(archetype, {t: render_run(t, p) for t, p in paths.items()}, lambda _messages: done, out)
        rows.append({**row, "result": note, "path": path and path.parent.name, "tokens_out": done.usage.tokens_out})
    ledger = {
        "token_source": "chars/4 of the prompt and reply files; excludes each subagent's harness overhead; no provider usage exists for Claude sessions",
        "model": "claude-haiku-5-5 (subagent model haiku), one fresh subagent per group (retries are new subagents)",
        "groups": rows,
        "totals": {"groups": len(rows), "written": sum(r["result"] == "written" for r in rows), "tokens_in": sum(r["tokens_in"] for r in rows), "tokens_out": sum(r["tokens_out"] for r in rows)},
    }
    (work / "ledger.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8", newline="\n")
    return ledger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skills.draft_claude")
    parser.add_argument("step", choices=["prepare", "finish"])
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--per-skill", type=int, default=PER_SKILL)
    ns = parser.parse_args(argv)
    if ns.step == "prepare":
        print(" ".join(prepare(ns.runs, ns.work, ns.per_skill)))
    else:
        ledger = finish(ns.runs, ns.work, per_skill=ns.per_skill)
        for row in ledger["groups"]:
            print(f"{row['group']} {row['archetype']}: {row['path'] or 'nothing'} ({row['result']})")
        print(json.dumps(ledger["totals"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
