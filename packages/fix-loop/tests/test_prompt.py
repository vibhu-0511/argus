"""P3-T16: the first user message carries the repro result and the locate hint."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota

from fix_loop.loop import run_fix
from fix_loop.prompt import user_message

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bug-17.json"


def test_fixture_task_is_the_first_user_message(tmp_path: Path):
    task = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    text = user_message(task)
    seen: list[list[dict]] = []

    def complete(messages):
        seen.append(messages)
        return Completion(json.dumps({"tool": "submit", "arguments": {}}), Usage(1, 1, 0), {})

    run_fix(
        worktree=tmp_path / "work",
        model="fake",
        ledger=Ledger(tmp_path / "ledger.json", {"fake": ModelQuota(100, 10**9, 100, 10**9, False)}),
        complete=complete,
        out_dir=tmp_path / "out",
        step_cap=2,
        token_cap=1000,
        run_id="run-1",
        host="test",
        git_commit="abc",
        task_id="bug-17",
        system="system",
        user=text,
    )
    user = seen[0][1]["content"]
    assert "Repro: valid" in user
    assert "apps/canvas/src/screens/Landing.tsx:40" in user
    assert task["ticket"] in user
