"""P3-T13: AGENTS.md is in the system message the model sees."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota

from fix_loop.loop import run_fix

_AGENTS = Path(__file__).resolve().parents[1] / "AGENTS.md"


def test_agents_md_is_in_the_system_message(tmp_path: Path):
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
        system="fix the ticket",
        user="ticket",
    )
    system = seen[0][0]["content"]
    text = _AGENTS.read_text(encoding="utf-8")
    assert text in system
    assert "fix the ticket" in system
    for phrase in (
        "apps/canvas",
        "pnpm",
        "npm run typecheck",
        "copa-local",
        "localhost:19080",
        "5433",
        "stratum.entities",
    ):
        assert phrase in system
