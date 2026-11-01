"""Claude-as-model turns: stored answers are replayed in order, and the first missing one asks for a turn."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fix_loop.turn import NeedTurn, _complete


def test_stored_answers_replay_then_ask_for_a_turn():
    complete = _complete(['{"tool": "submit", "arguments": {}}'])
    first = complete([{"role": "user", "content": "abcdefgh"}])
    assert first.content == '{"tool": "submit", "arguments": {}}'
    assert first.usage.tokens_in > 0 and first.usage.tokens_cached == 0
    pending = [{"role": "user", "content": "next"}]
    with pytest.raises(NeedTurn) as need:
        complete(pending)
    assert need.value.messages == pending


def test_strategies_shape_the_message_list(tmp_path):
    from fix_loop.turn import _strategy

    assert _strategy("none", tmp_path, None, None) is None
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "x" * 20_000}]
    capped = _strategy("cap", tmp_path, None, None)(msgs, 0, 1)
    assert len(capped[-1]["content"]) <= 8_000 and capped[0] == msgs[0]
    moved = _strategy("offload", tmp_path, None, None)(msgs, 0, 1)
    assert "[offloaded .argus/obs-2.txt]" in moved[-1]["content"]
    assert (tmp_path / ".argus" / "obs-2.txt").read_text(encoding="utf-8") == "x" * 20_000


def test_summary_strategy_cuts_each_turn_before_summarizing(tmp_path):
    from argus_core.client import Completion, Usage
    from fix_loop.turn import DISPLAY, _strategy

    seen = {}

    def complete(messages):
        seen["older"] = messages[1]["content"]
        return Completion("short", Usage(1, 1, 0), {})

    class Ledger:
        def call(self, model, send):
            send()

    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}, {"role": "user", "content": "x" * 2_000_000}]
    out = _strategy("summary", tmp_path, complete, Ledger())(msgs, 0, 1)
    assert len(seen["older"]) < DISPLAY + 200 and out[-1]["content"] == "Summary:" + chr(10) + "short"


def test_a_reply_of_the_wrong_kind_is_rejected():
    from fix_loop.turn import wrong_kind

    call = json.dumps({'tool': 'submit', 'arguments': {}})
    assert wrong_kind('summary', call) is not None
    assert wrong_kind('summary', 'Summary of earlier turns: ...') is None
    assert wrong_kind('turn', 'I would look at the css') is not None
    assert wrong_kind('turn', call) is None
