"""P5-T13: the system message (AGENTS.md map plus the tool list) is a byte-stable prefix; run-specific text comes after it."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota

from fix_loop.loop import run_fix
from fix_loop.prompt import system_message, user_message
from fix_loop.turn import PROTOCOL


def _first_request(tmp_path: Path, name: str, *, ticket: str, run_id: str, stamp: str) -> list[dict]:
    seen: list[list[dict]] = []

    def complete(messages):
        seen.append(json.loads(json.dumps(messages)))
        return Completion(json.dumps({"tool": "submit", "arguments": {}}), Usage(1, 1, 0), {})

    task = {"ticket": ticket, "repro": f"valid at {stamp}", "locate": {"file": "a.tsx", "line": 1}}
    run_fix(
        worktree=tmp_path / name,
        model="fake",
        ledger=Ledger(tmp_path / f"{name}.json", {"fake": ModelQuota(100, 10**9, 100, 10**9, False)}),
        complete=complete,
        out_dir=tmp_path / f"out-{name}",
        step_cap=1,
        token_cap=1000,
        run_id=run_id,
        host="test",
        git_commit="abc",
        task_id=name,
        system=PROTOCOL,
        user=f"[{stamp}] run {run_id}\n" + user_message(task),
    )
    return seen[0]


def test_prefix_bytes_do_not_change_with_ticket_time_or_run_id(tmp_path: Path):
    one = _first_request(tmp_path, "one", ticket="Button is clipped", run_id="run-1", stamp="2026-11-01T10:00:00Z")
    two = _first_request(tmp_path, "two", ticket="Menu overlaps title", run_id="run-2", stamp="2027-02-03T22:30:00Z")

    prefix_one = system_message(PROTOCOL).encode()
    assert one[0]["role"] == two[0]["role"] == "system"
    assert one[0]["content"].encode() == two[0]["content"].encode() == prefix_one
    assert "Tools:" in one[0]["content"]  # the tool list is inside the prefix

    dynamic = ["Button is clipped", "Menu overlaps title", "run-1", "run-2", "2026-11-01", "2027-02-03"]
    assert not any(text in prefix_one.decode() for text in dynamic)

    # on the wire, everything up to the user turn is the same bytes for both runs
    wire = [json.dumps(m[:1], sort_keys=True) for m in (one, two)]
    assert wire[0] == wire[1]
    assert one[1]["content"] != two[1]["content"]
