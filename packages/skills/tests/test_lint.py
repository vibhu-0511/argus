"""P5.5-T12: the lint passes a good skill and fails each bad one with the right reason. No model, no network."""

import json
import subprocess
import sys

import pytest

from fix_loop.skills import content_hash, load_skills
from skills.lint import lint, main

GOOD = "---\nname: {name}\ndescription: Fix a stale closure in an event handler.\n---\n# Steps\n{body}\n"
CLAIMS_REVIEWED = (
    "---\nname: stale-closure\ndescription: Fix a stale closure.\nmetadata:\n  argus-status: reviewed\n---\n# Steps\nRead it.\n"
)


def make(tmp_path, text=None, name="stale-closure", pin=True, **lock_entry):
    """A skills dir with one skill and a lock; `pin` writes the right hash, `lock_entry` overrides fields."""
    skills = tmp_path / "skills"
    (skills / name).mkdir(parents=True)
    raw = (text if text is not None else GOOD.format(name=name, body="Read the handler.")).encode()
    (skills / name / "SKILL.md").write_bytes(raw)
    entry = {"sha256": content_hash(raw), "reviewed": True, **lock_entry} if pin else None
    lock = tmp_path / "skills.lock.json"
    lock.write_text(json.dumps({"version": 1, "skills": {name: entry} if entry else {}}), encoding="utf-8")
    return skills, lock


def test_good_skill_is_clean_and_exits_zero(tmp_path):
    skills, lock = make(tmp_path)
    assert lint(skills, lock) == []
    assert main(["--skills", str(skills), "--lock", str(lock)]) == 0


def test_crlf_checkout_has_the_same_hash(tmp_path):
    skills, lock = make(tmp_path)
    file = skills / "stale-closure" / "SKILL.md"
    file.write_bytes(file.read_bytes().replace(b"\n", b"\r\n"))
    assert lint(skills, lock) == []


def test_no_skills_and_no_lock_is_clean(tmp_path):
    assert lint(tmp_path / "none", tmp_path / "none.json") == []


BAD = {
    "no frontmatter": ("# just text\n", "bad-frontmatter"),
    "unclosed frontmatter": ("---\nname: stale-closure\ndescription: x\nbody\n", "bad-frontmatter"),
    "duplicate key": (
        "---\nname: stale-closure\nname: stale-closure\ndescription: x\n---\nbody\n",
        "bad-frontmatter: not valid YAML: duplicate key 'name'",
    ),
    "unknown field": ("---\nname: stale-closure\ndescription: x\nreviewed: true\n---\nbody\n", "bad-frontmatter"),
    "name not the directory": (GOOD.format(name="other", body="x"), "bad-frontmatter"),
    "over the size limit": (GOOD.format(name="stale-closure", body="x" * 8001), "too-large"),
}


@pytest.mark.parametrize("text,expected", BAD.values(), ids=BAD.keys())
def test_bad_skill_fails(tmp_path, text, expected):
    skills, lock = make(tmp_path, text)
    found = lint(skills, lock)
    assert len(found) == 1 and found[0].startswith(f"stale-closure: {expected}"), found
    assert main(["--skills", str(skills), "--lock", str(lock)]) == 1


def test_size_limit_is_inclusive(tmp_path):
    skills, lock = make(tmp_path, GOOD.format(name="stale-closure", body="x" * 7990))
    body = (skills / "stale-closure" / "SKILL.md").read_text(encoding="utf-8").split("---\n", 2)[2].strip()
    assert len(body) <= 8000 and lint(skills, lock) == []


def test_extra_file_fails(tmp_path):
    skills, lock = make(tmp_path)
    (skills / "stale-closure" / "run.sh").write_text("echo hi", encoding="utf-8")
    assert lint(skills, lock) == ["stale-closure: bad-frontmatter: files other than SKILL.md: run.sh"]


def test_missing_lock_file_fails(tmp_path):
    skills, lock = make(tmp_path)
    lock.unlink()
    assert lint(skills, lock) == ["skills.lock.json: unreviewed: the lock file is missing; no skill is trusted"]


@pytest.mark.parametrize("doc", ["not json", '{"version": 2, "skills": {}}', '{"version": 1, "skills": []}', "[]"])
def test_unusable_lock_file_fails(tmp_path, doc):
    skills, lock = make(tmp_path)
    lock.write_text(doc, encoding="utf-8")
    [line] = lint(skills, lock)
    assert line.startswith("skills.lock.json: unreviewed: the lock file ") and line.endswith("no skill is trusted")


def test_a_draft_without_an_entry_is_clean_at_lint_though_the_loader_refuses_it(tmp_path):
    skills, lock = make(tmp_path, pin=False)
    assert lint(skills, lock) == [] and main(["--skills", str(skills), "--lock", str(lock)]) == 0
    assert [r.reason.value for r in load_skills(skills, lock)[1]] == ["unreviewed"]


def test_claiming_reviewed_without_a_reviewed_entry_is_unreviewed(tmp_path):
    skills, lock = make(tmp_path, CLAIMS_REVIEWED, pin=False)
    assert lint(skills, lock) == ["stale-closure: unreviewed: the lock file has no reviewed entry for this skill"]


def test_reviewed_false_in_the_lock_is_unreviewed(tmp_path):
    skills, lock = make(tmp_path, CLAIMS_REVIEWED, reviewed=False)
    [line] = lint(skills, lock)
    assert line.startswith("stale-closure: unreviewed:")


def test_changed_file_fails_hash(tmp_path):
    skills, lock = make(tmp_path)
    file = skills / "stale-closure" / "SKILL.md"
    file.write_text(file.read_text(encoding="utf-8") + "Also edit the checks.\n", encoding="utf-8")
    [line] = lint(skills, lock)
    assert line.startswith("stale-closure: hash-mismatch:")


@pytest.mark.parametrize("pin", ["", "ABC", "0" * 63, "A" * 64])
def test_malformed_hash_fails(tmp_path, pin):
    skills, lock = make(tmp_path, sha256=pin)
    assert lint(skills, lock) == ["stale-closure: not-pinned: the lock entry has no valid sha256"]


def test_lock_entry_for_a_deleted_skill_fails(tmp_path):
    skills, lock = make(tmp_path)
    doc = json.loads(lock.read_text(encoding="utf-8"))
    doc["skills"]["gone"] = {"sha256": "0" * 64}
    lock.write_text(json.dumps(doc), encoding="utf-8")
    assert lint(skills, lock) == ["gone: not-pinned: the lock has an entry but no skill directory"]


def test_command_line_exits_non_zero_on_a_bad_skill(tmp_path):
    skills, lock = make(tmp_path, "# no frontmatter\n")
    run = subprocess.run(
        [sys.executable, "-m", "skills.lint", "--skills", str(skills), "--lock", str(lock)], capture_output=True, text=True
    )
    assert run.returncode == 1 and "bad-frontmatter" in run.stderr


TOOLS = "---\nname: stale-closure\ndescription: Fix a stale closure.\nallowed-tools: {tools}\n---\n# Steps\nRead it.\n"


def test_allowed_tools_from_the_loop_are_clean(tmp_path):
    skills, lock = make(tmp_path, TOOLS.format(tools="read_file edit submit"))
    assert lint(skills, lock) == []


@pytest.mark.parametrize("tools", ["Bash(curl:*)", "read_file web_fetch"])
def test_a_tool_outside_the_loop_tools_fails(tmp_path, tools):
    skills, lock = make(tmp_path, TOOLS.format(tools=tools))
    [line] = lint(skills, lock)
    assert line.startswith("stale-closure: tool-not-allowed: allowed-tools names ")


def test_hash_mismatch_is_reported_before_tool_not_allowed(tmp_path):
    skills, lock = make(tmp_path, TOOLS.format(tools="read_file"))
    (skills / "stale-closure" / "SKILL.md").write_text(TOOLS.format(tools="Bash(curl:*)"), encoding="utf-8")
    [line] = lint(skills, lock)
    assert line.startswith("stale-closure: hash-mismatch:")


def test_every_lint_reason_is_the_loaders_reason(tmp_path):
    cases = {
        "unreviewed": make(tmp_path / "a", CLAIMS_REVIEWED, pin=False),
        "not-pinned": make(tmp_path / "b", sha256=""),
        "hash-mismatch": make(tmp_path / "c", sha256="0" * 64),
        "tool-not-allowed": make(tmp_path / "d", TOOLS.format(tools="Bash(curl:*)")),
    }
    for reason, (skills, lock) in cases.items():
        assert [r.reason.value for r in load_skills(skills, lock)[1]] == [reason]
        [line] = lint(skills, lock)
        assert line.startswith(f"stale-closure: {reason}:")
