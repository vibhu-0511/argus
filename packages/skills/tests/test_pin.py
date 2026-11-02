"""P5.5-T10: `skills.pin` signs a skill off in the lock, and the loader then accepts it. No model, no network."""

import json

from fix_loop.skills import load_skills

from skills.draft import draft_group
from skills.pin import pin
from test_draft import REPLY, _group, stub


def _draft(tmp_path):
    skills = tmp_path / "skills"
    path, note, _ = draft_group("missing-style", _group(), stub(REPLY), skills)
    assert note == "written"
    return skills, path


def test_a_fresh_draft_is_refused_until_pinned(tmp_path):
    skills, path = _draft(tmp_path)
    loadable, refused = load_skills(skills)
    assert loadable == [] and [(r.name, r.reason.value) for r in refused] == [("restore-removed-rule", "unreviewed")]
    lock = tmp_path / "skills.lock.json"
    assert pin("restore-removed-rule", "tester", skills, lock) is None
    entry = json.loads(lock.read_text(encoding="utf-8"))["skills"]["restore-removed-rule"]
    assert entry["reviewed"] is True and entry["reviewed_by"] == "tester" and len(entry["sha256"]) == 64
    assert [s.name for s in load_skills(skills)[0]] == ["restore-removed-rule"]
    path.write_text(path.read_text(encoding="utf-8") + "\nOne more step.\n", encoding="utf-8")  # edit after review
    assert [r.reason.value for r in load_skills(skills)[1]] == ["hash-mismatch"]


def test_pin_leaves_the_lock_alone_when_the_loader_would_refuse_the_skill(tmp_path):
    skills, path = _draft(tmp_path)
    path.write_text(path.read_text(encoding="utf-8").replace("allowed-tools: ", "allowed-tools: Bash(curl:*) "), encoding="utf-8")
    lock = tmp_path / "skills.lock.json"
    problem = pin("restore-removed-rule", "tester", skills, lock)
    assert problem and "tool-not-allowed" in problem and not lock.exists()
    assert "does not exist" in pin("nope", "tester", skills, lock)
