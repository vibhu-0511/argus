"""P5.5-T05: the draft script on small stored-trajectory fixtures. The model is a stub; no network."""

import json
from pathlib import Path

from argus_core.client import Completion, Usage

from skills.draft import draft_group, groups, parse_reply, prompt, render_run, successes
from skills.split import SPLIT, TASKS

RUNS = Path(__file__).parent / "fixtures" / "runs"
TRAIN = set(json.loads(SPLIT.read_text(encoding="utf-8"))["train"])
REPLY = {
    "name": "restore-removed-rule",
    "description": "Fix a missing style: a rule was removed. Use when a ticket says a property on a class changed from a value.",
    "body": "1. Search the class name.\n2. Read the stylesheet around it.\n3. Add the rule back with edit.\n4. Submit.",
}


def stub(reply):
    seen = []

    def complete(messages):
        seen.append(messages)
        content = reply if isinstance(reply, str) else "```json\n" + json.dumps(reply) + "\n```"
        return Completion(content, Usage(5, 5, 0), {})

    complete.seen = seen
    return complete


def _group():
    found = successes(RUNS, TRAIN)
    return {t: render_run(t, p) for t, p in found.items() if t.startswith("mut-000")}


def test_only_resolved_train_runs_count():
    found = successes(RUNS, TRAIN)
    assert sorted(found) == ["mut-0001", "mut-0002", "mut-0190"]  # mut-0003 unresolved, seed-e01 held-out
    assert [(a, list(g)) for a, g in groups(found, 3)] == [
        ("font-size", ["mut-0190"]),
        ("missing-style", ["mut-0001", "mut-0002"]),
    ]
    assert [list(g) for _, g in groups(found, 1)] == [["mut-0190"], ["mut-0001"], ["mut-0002"]]


def test_prompt_has_ticket_and_steps_and_no_held_out_text():
    text = render_run("mut-0001", successes(RUNS, TRAIN)["mut-0001"])
    assert text.startswith("Ticket: transform-box on .busy-orbit changed from fill-box.")
    assert '"tool": "edit"' in text and "submitted" in text
    assert "seed-" not in json.dumps(prompt("missing-style", _group()))


def test_draft_is_written_unreviewed_and_loader_format_accepts_it(tmp_path):
    from fix_loop.skills import _parse

    path, note, done = draft_group("missing-style", _group(), stub(REPLY), tmp_path)
    assert note == "written" and path == tmp_path / "restore-removed-rule" / "SKILL.md"
    raw = path.read_bytes()
    fields, body = _parse("restore-removed-rule", raw)  # the description holds ": " and is quoted
    assert fields["description"] == REPLY["description"]
    assert fields["metadata"] == {
        "argus-status": "unreviewed",
        "argus-archetype": "missing-style",
        "argus-sources": "mut-0001,mut-0002",
    }
    assert "run_cmd" not in fields["allowed-tools"].split()
    assert body.startswith("1. Search the class name.")
    assert b"\r" not in raw and done.usage.tokens_in == 5


def test_bad_replies_write_nothing(tmp_path):
    (tmp_path / "taken").mkdir()
    cases = {
        "not json": "sorry, no",
        "missing key": json.dumps({"name": "a-b", "description": "d"}),
        "bad name": json.dumps({**REPLY, "name": "Bad Name"}),
        "name exists": json.dumps({**REPLY, "name": "taken"}),
        "empty description": json.dumps({**REPLY, "description": "  "}),
        "body too large": json.dumps({**REPLY, "body": "x" * 8001}),
    }
    for label, reply in cases.items():
        path, note, _ = draft_group("missing-style", _group(), stub(reply), tmp_path)
        assert path is None, (label, note)
    assert [p.name for p in tmp_path.iterdir()] == ["taken"]
    assert parse_reply("noise {\"name\": \"a\", \"description\": \"b\", \"body\": \"c\"} noise")["body"] == "c"

