"""P5-T26 break-it: a timestamp at the top of the system prompt breaks the byte-stable prefix.

The shipped prompt is not touched. The test wraps `fix_loop.loop.system_message` so the current time comes first, then
shows two things: the byte comparison from `test_cache_prefix` no longer holds, and a stub provider that reports cached
tokens only when the system bytes match an earlier request reports zero cached tokens per call.

ponytail: the stub is the only cache here. Groq's usage object had no cached-token field in the 2026-10-29 probe
(`docs/quotas.md`), so the effect on a real provider is unmeasured.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota

from fix_loop import loop
from fix_loop.loop import run_fix
from fix_loop.prompt import system_message, user_message
from fix_loop.turn import PROTOCOL
from test_cache_prefix import _first_request

CALLS = 3
START = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)


def _stamp_at_top(monkeypatch: pytest.MonkeyPatch) -> None:
    """Put the current time, one second later on every call, before the shipped system message."""
    ticks = iter(START + timedelta(seconds=n) for n in range(1000))
    monkeypatch.setattr(
        loop, "system_message", lambda instruction: f"Current time: {next(ticks).isoformat()}\n" + system_message(instruction)
    )


class PrefixCacheStub:
    """Reports the system message's tokens as cached when the same system bytes came in on an earlier request."""

    def __init__(self) -> None:
        self.seen: set[bytes] = set()

    def complete(self, messages: list[dict]) -> Completion:
        prefix = messages[0]["content"].encode()
        system_tokens = len(prefix) // 4
        cached = system_tokens if prefix in self.seen else 0
        self.seen.add(prefix)
        tokens_in = system_tokens + len(messages[1]["content"]) // 4
        return Completion(json.dumps({"tool": "submit", "arguments": {}}), Usage(tokens_in, 1, cached), {})


def _cached_per_call(tmp_path: Path, name: str) -> tuple[list[int], dict]:
    """Run the fix loop CALLS times against one stub and one ledger; return cached tokens per call and the ledger bucket."""
    provider = PrefixCacheStub()
    ledger = Ledger(tmp_path / f"{name}.json", {"fake": ModelQuota(100, 10**9, 100, 10**9, False)})
    per_call: list[int] = []
    before = 0
    for n in range(CALLS):
        task = {"ticket": f"Button is clipped ({n})", "repro": "r", "locate": {"file": "a.tsx", "line": 1}}
        run_fix(
            worktree=tmp_path / f"{name}-{n}",
            model="fake",
            ledger=ledger,
            complete=provider.complete,
            out_dir=tmp_path / f"out-{name}-{n}",
            step_cap=1,
            token_cap=10**6,
            run_id=f"run-{n}",
            host="test",
            git_commit="abc",
            task_id=f"{name}-{n}",
            system=PROTOCOL,
            user=user_message(task),
        )
        total = json.loads(ledger.path.read_text(encoding="utf-8"))["models"]["fake"]["cached"]
        per_call.append(total - before)
        before = total
    return per_call, json.loads(ledger.path.read_text(encoding="utf-8"))["models"]["fake"]


def test_timestamp_at_top_breaks_the_prefix_comparison(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _stamp_at_top(monkeypatch)
    one = _first_request(tmp_path, "one", ticket="Button is clipped", run_id="run-1", stamp="2026-11-01T10:00:00Z")
    two = _first_request(tmp_path, "two", ticket="Menu overlaps title", run_id="run-2", stamp="2027-02-03T22:30:00Z")

    # the comparison test_cache_prefix asserts to be equal now comes out unequal
    shipped = system_message(PROTOCOL).encode()
    assert one[0]["content"].encode() != two[0]["content"].encode()
    assert one[0]["content"].encode() != shipped
    assert json.dumps(one[:1], sort_keys=True) != json.dumps(two[:1], sort_keys=True)
    assert "2026-11-01" in one[0]["content"]  # the "no run-specific text in the prefix" check fails too
    assert one[0]["content"].endswith(system_message(PROTOCOL))  # only the head changed, the rest is the shipped text


def test_cached_tokens_fall_to_zero_with_the_timestamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    stable, stable_bucket = _cached_per_call(tmp_path, "stable")
    with monkeypatch.context() as patch:
        _stamp_at_top(patch)
        busted, busted_bucket = _cached_per_call(tmp_path, "busted")

    # first call is cold in both; after that the stable prefix is cached and the stamped one never is
    assert stable[0] == busted[0] == 0
    assert all(tokens > 0 for tokens in stable[1:])
    assert busted[1:] == [0] * (CALLS - 1)

    # same totals through the ledger, and the cached tokens turn into fresh ones
    assert stable_bucket["cached"] == sum(stable) > 0
    assert busted_bucket["cached"] == 0
    assert busted_bucket["fresh"] >= stable_bucket["fresh"] + stable_bucket["cached"]
