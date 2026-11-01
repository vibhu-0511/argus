"""One model call. Ticket text and the current text of files named in bug.patch."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from argus_bench.task_dir import load_task_dir
from argus_core.ledger import Ledger, ModelQuota, Usage, load_quotas
from argus_core.profile import client_from_profile, load_profiles

_BENCH = Path(__file__).resolve().parents[2]
_REPO = _BENCH.parents[1]


def baseline_task(
    task: str,
    tree: Path,
    *,
    model: str = "openai/gpt-oss-20b",
    ledger_path: Path | None = None,
) -> int:
    try:
        directory = _task_dir(task)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2
    active, profiles = load_profiles(_REPO / "config" / "profiles.md")
    profile = profiles[active]
    key_env = str(profile.get("key_env") or "")
    if not key_env or not os.environ.get(key_env):
        print("skipping live call: key unset")
        return 2
    loaded = load_task_dir(directory)
    prompt = _prompt(loaded.ticket.text, loaded.bug_patch, tree)
    client = client_from_profile(profile)
    ledger = Ledger(
        ledger_path or (_REPO / ".local" / "quota-ledger.json"),
        load_quotas(_REPO / "docs" / "quotas.md"),
    )
    content: list[str] = []

    def send() -> Usage:
        done = client.complete(model, [{"role": "user", "content": prompt}])
        content.append(done.content)
        return Usage(
            tokens_in=done.usage.tokens_in,
            tokens_out=done.usage.tokens_out,
            tokens_cached=done.usage.tokens_cached,
        )

    ledger.call(model, send, token_estimate=len(prompt) // 4)
    print(content[0], end="")
    return 0


def baseline_many(
    tasks: list[str],
    *,
    ledger_path: Path,
    partial_path: Path,
    quotas: dict[str, ModelQuota],
    complete: Callable[[str], str],
    model: str = "openai/gpt-oss-20b",
    now: Callable[[], datetime] | None = None,
) -> int:
    finished: dict[str, str] = {}
    if partial_path.is_file():
        finished = json.loads(partial_path.read_text(encoding="utf-8"))
    if now is None:
        ledger = Ledger(ledger_path, quotas)
    else:
        ledger = Ledger(ledger_path, quotas, now=now)
    for task_id in tasks:
        if task_id in finished:
            continue
        held: list[str] = []

        def send(current: str = task_id) -> Usage:
            held.append(complete(current))
            return Usage(tokens_in=1, tokens_out=1, tokens_cached=0)

        ledger.call(model, send, token_estimate=1)
        finished[task_id] = held[0]
        partial_path.parent.mkdir(parents=True, exist_ok=True)
        partial_path.write_text(json.dumps(finished), encoding="utf-8")
    return 0


def _task_dir(arg: str) -> Path:
    direct = Path(arg)
    if direct.is_dir():
        return direct
    for candidate in (_BENCH / "tasks" / "seeded" / arg, _BENCH / "tasks" / "mutated" / arg):
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"missing task: {arg}")


def _prompt(ticket: str, patch: str, tree: Path) -> str:
    parts = [ticket]
    for rel in _paths(patch):
        parts.append(f"{rel}\n{(tree / rel).read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def _paths(patch: str) -> list[str]:
    found: list[str] = []
    for line in patch.splitlines():
        if line.startswith("--- a/"):
            path = line[6:].strip()
        elif line.startswith("+++ b/"):
            path = line[6:].strip()
        else:
            continue
        if not path or path == "/dev/null" or path in found:
            continue
        found.append(path)
    return found
