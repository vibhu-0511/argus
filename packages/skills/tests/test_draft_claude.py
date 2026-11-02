"""P5.5-T05: the Claude-subagent driver. Replies are written by hand; no model, no network."""

import json
from pathlib import Path

from skills.draft_claude import finish, prepare

RUNS = Path(__file__).parent / "fixtures" / "runs"
REPLY = {"name": "restore-removed-rule", "description": "Fix a missing style: a rule was removed.", "body": "1. Search the class.\n2. Edit.\n3. Submit."}


def test_prepare_then_finish_writes_one_draft_per_replied_group(tmp_path):
    keys = prepare(RUNS, tmp_path)
    assert keys == ["g01", "g02"]  # font-size (mut-0190), missing-style (mut-0001, mut-0002)
    saved = json.loads((tmp_path / "g02.prompt.json").read_text(encoding="utf-8"))
    assert saved["runs"] == ["mut-0001", "mut-0002"] and "seed-" not in json.dumps(saved)
    (tmp_path / "g02.reply.txt").write_text(json.dumps(REPLY), encoding="utf-8")
    out = tmp_path / "skills"
    ledger = finish(RUNS, tmp_path, out)
    assert [r["result"] for r in ledger["groups"]] == ["no reply", "written"]
    assert (out / "restore-removed-rule" / "SKILL.md").is_file() and ledger["totals"]["written"] == 1
