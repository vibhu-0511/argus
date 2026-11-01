"""P3-T10, T11, T12: caps, offload, and a summary that has to shrink."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota

from argus_core.types import StopReason

from fix_loop.loop import run_fix
from fix_loop.strategies import (
    HEAD,
    OUTPUT_CAP,
    SummaryDidNotShrink,
    cap_text,
    offload,
    rolling_summary,
    summary_strategy,
)
from fix_loop.tools import ToolResult
from fix_loop.tools import call


def test_50k_output_is_cut_to_the_cap_and_drops_the_tail():
    body = ("a" * (50_000 - 1)) + "Z"
    capped = cap_text(body)
    assert len(body) == 50_000
    assert len(capped) == OUTPUT_CAP
    assert capped.endswith("[truncated]")
    assert "Z" not in capped
    assert capped.startswith("a")
    assert cap_text("short") == "short"


def test_offload_leaves_a_path_and_read_file_returns_the_body(tmp_path: Path):
    body = ("H" * HEAD) + ("Z" * (OUTPUT_CAP + 1))
    shown = offload(body, tmp_path, "obs-1.txt")
    assert shown.startswith("H" * HEAD)
    assert "[offloaded .argus/obs-1.txt]" in shown
    assert "Z" * 50 not in shown
    got = call("read_file", {"path": ".argus/obs-1.txt"}, tmp_path)
    assert got.ok is True
    assert got.text == body


def test_summary_keeps_the_system_prompt_and_the_first_user_message(tmp_path: Path):
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "FIRST"},
        {"role": "assistant", "content": "a" * 400},
        {"role": "user", "content": "b" * 400},
    ]
    ledger = Ledger(tmp_path / "ledger.json", {"cheap": ModelQuota(10, 10**6, 10, 10**6, False)})
    summarized = rolling_summary(
        messages,
        complete=lambda _messages: Completion("short", Usage(2, 3, 1), {}),
        ledger=ledger,
        model="cheap",
    )
    assert summarized[0]["content"] == "SYS"
    assert summarized[1]["content"] == "FIRST"
    assert len(summarized) == 3
    assert summarized[2]["content"] == "Summary:\nshort"
    assert "omitted" not in summarized[2]["content"]
    stored = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert stored["models"]["cheap"]["tokens"] == 4


def test_summary_that_does_not_shrink_is_a_stop(tmp_path: Path):
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "FIRST"},
        {"role": "user", "content": "x"},
    ]
    ledger = Ledger(tmp_path / "ledger.json", {"cheap": ModelQuota(10, 10**6, 10, 10**6, False)})
    try:
        rolling_summary(
            messages,
            complete=lambda _messages: Completion("y" * 500, Usage(1, 1, 0), {}),
            ledger=ledger,
            model="cheap",
        )
    except SummaryDidNotShrink:
        return
    raise AssertionError("summary grew the window")


def test_loop_stops_when_the_summary_does_not_shrink(tmp_path: Path):
    ledger = Ledger(
        tmp_path / "ledger.json",
        {
            "fake": ModelQuota(10, 10**6, 10, 10**6, False),
            "cheap": ModelQuota(10, 10**6, 10, 10**6, False),
        },
    )
    result = run_fix(
        worktree=tmp_path / "work",
        model="fake",
        ledger=ledger,
        complete=lambda _messages: Completion(
            json.dumps({"tool": "read_file", "arguments": {"path": "a.txt"}}),
            Usage(8, 2, 0),
            {},
        ),
        out_dir=tmp_path / "out",
        step_cap=3,
        token_cap=1000,
        run_id="run-1",
        host="test",
        git_commit="abc",
        task_id="bug-17",
        system="system",
        user="fix it",
        execute=lambda name, _payload: ToolResult(tool=name, text="ok"),
        context_budget=10,
        strategy=summary_strategy(
            complete=lambda _messages: Completion("y" * 100_000, Usage(1, 1, 0), {}),
            ledger=ledger,
            model="cheap",
        ),
    )
    assert result.stop_reason is StopReason.summary
    stored = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert stored["models"]["cheap"]["tokens"] == 2
