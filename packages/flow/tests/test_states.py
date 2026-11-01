"""State machine: every (state, event) pair, reachability, the markdown table, deterministic keys."""

from __future__ import annotations

import itertools
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flow.states import (
    EFFECTS,
    START,
    STATES,
    TERMINAL,
    TRANSITIONS,
    Event,
    IllegalTransition,
    State,
    branch_name,
    comment_marker,
    effect_key,
    markdown_tables,
    next_state,
    qa_signal_key,
    workflow_id,
)

NOTE = Path(__file__).resolve().parents[3] / "docs" / "notes" / "p6-state-machine.md"
LEGAL = {(frm, ev): to for frm, ev, to, _ in TRANSITIONS}


@pytest.mark.parametrize("state,event", list(itertools.product(State, Event)))
def test_every_pair_is_in_the_table_or_rejected(state, event):
    if (state, event) in LEGAL:
        assert next_state(state, event) is LEGAL[(state, event)]
    else:
        with pytest.raises(IllegalTransition, match=event.value):
            next_state(state, event)


def test_the_table_has_no_duplicate_rows_and_every_state_has_info():
    assert len(LEGAL) == len(TRANSITIONS)
    assert set(STATES) == set(State)


def test_terminal_states_have_no_exit():
    assert not [t for t in TRANSITIONS if t[0] in TERMINAL]


def test_every_state_is_reachable_and_every_active_state_can_finish():
    seen, todo = {START}, [START]
    while todo:
        s = todo.pop()
        for (frm, _), to in LEGAL.items():
            if frm == s and to not in seen:
                seen.add(to)
                todo.append(to)
    assert seen == set(State)
    # backwards from the terminals: every state that can finish
    done, todo = set(TERMINAL), list(TERMINAL)
    while todo:
        s = todo.pop()
        for (frm, _), to in LEGAL.items():
            if to == s and frm not in done:
                done.add(frm)
                todo.append(frm)
    assert done == set(State)


def test_unknown_names_are_rejected():
    with pytest.raises(ValueError):
        next_state("nope", Event.START)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        next_state(State.RECEIVED, "nope")  # type: ignore[arg-type]


def test_every_state_effect_is_described():
    assert {e for i in STATES.values() for e in i.effects} <= set(EFFECTS)


def test_markdown_table_equals_the_code():
    text = NOTE.read_text(encoding="utf-8")
    m = re.search(r"<!-- generated:begin -->\n(.*?)\n<!-- generated:end -->", text, re.S)
    assert m, "markers missing in docs/notes/p6-state-machine.md"
    assert m.group(1) == markdown_tables(), (
        "table and code differ; regenerate with: "
        'uv run python -c "from flow.states import markdown_tables; print(markdown_tables())"'
    )
    # the transition rows, read back from the file rather than from the generator
    rows = re.findall(r"^\| `([\w-]+)` \| `(\w+)` \| `([\w-]+)` \|", m.group(1), re.M)
    assert {(State(a), Event(b), State(c)) for a, b, c in rows} == {(f, e, t) for f, e, t, _ in TRANSITIONS}


def test_keys_are_stable_and_distinct():
    t = "acme/app#17"
    assert workflow_id(t) == t
    assert branch_name(t) == branch_name(t) == "argus/acme-app-17-" + branch_name(t)[-8:]
    assert branch_name(t) != branch_name("acme-app-17")
    assert effect_key(t, "dispatch-fix") == effect_key(t, "dispatch-fix") == "argus:acme/app#17:dispatch-fix:1"
    keys = {effect_key(t, e, a) for e in ("dispatch-repro", "dispatch-fix", "push-branch", "comment-done") for a in (1, 2)}
    assert len(keys) == 8
    assert qa_signal_key(t, "mrtr", "req-9") == qa_signal_key(t, "mrtr", "req-9") != qa_signal_key(t, "review-comment", "req-9")
    assert comment_marker(effect_key(t, "comment-done")) == "<!-- argus-key: argus:acme/app#17:comment-done:1 -->"


def test_keys_do_not_depend_on_a_clock_or_randomness():
    import flow.states as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+(time|datetime|random|uuid|secrets)\b", src, re.M)


def test_branch_is_a_valid_ref_for_odd_ticket_ids():
    for t in ("a/b#1", "###", "x" * 200, "ünï/cödé..lock", "a b\tc"):
        b = branch_name(t)
        assert re.fullmatch(r"argus/[a-z0-9-]+-[0-9a-f]{8}", b) and len(b) < 70, b


@pytest.mark.parametrize(
    "call",
    [
        lambda: workflow_id(""),
        lambda: effect_key("t", "dispatch-fix", 0),
        lambda: effect_key("t", "delete-everything"),
        lambda: qa_signal_key("t", "slack", "1"),
        lambda: qa_signal_key("t", "mrtr", ""),
    ],
)
def test_bad_key_inputs_raise(call):
    with pytest.raises(ValueError):
        call()
