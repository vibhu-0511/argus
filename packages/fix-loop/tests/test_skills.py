"""P5.5-T02: the skill catalog, `load_skill`, and the format checks. No model, no network."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import Trajectory

from fix_loop.loop import run_fix
from fix_loop.prompt import system_message
from fix_loop.skills import MAX_BODY_CHARS, Reason, loaded_names, load_skills, tool_spec
from fix_loop.turn import PROTOCOL


def _write(root: Path, name: str, *, description: str = "Fix a stale value. Use when a button shows old data.", body: str = "Step one.", front: str | None = None) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    head = front if front is not None else f"name: {name}\ndescription: {json.dumps(description)}"
    (folder / "SKILL.md").write_text(f"---\n{head}\n---\n{body}\n", encoding="utf-8", newline="\n")
    return folder


def _run(tmp_path: Path, label: str, calls: list[dict], skills: Path | None) -> tuple[list[dict], Trajectory]:
    """Run the loop with scripted tool calls; return what the model saw at each call and the stored trajectory."""
    seen: list[list[dict]] = []
    script = iter([*calls, {"tool": "submit", "arguments": {}}])

    def complete(messages):
        seen.append(json.loads(json.dumps(messages)))
        content = json.dumps(next(script))
        return Completion(content, Usage(1, 1, 0), {})

    root = tmp_path / f"work-{label}"
    root.mkdir()
    result = run_fix(
        worktree=root,
        model="fake",
        ledger=Ledger(tmp_path / f"{label}.json", {"fake": ModelQuota(100, 10**9, 100, 10**9, False)}),
        complete=complete,
        out_dir=tmp_path / f"out-{label}",
        step_cap=len(calls) + 1,
        token_cap=10**6,
        run_id="run-1",
        host="test",
        git_commit="abc",
        task_id="t",
        system=PROTOCOL,
        user="Ticket: button is stale",
        skills=skills,
    )
    return seen, Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))


def test_catalog_has_names_and_descriptions_only(tmp_path: Path):
    skills = tmp_path / "skills"
    _write(skills, "stale-closure", description="Fix a stale closure in a hook.", body="SECRET-BODY-ONE")
    _write(skills, "css-clip", description="Fix clipped text.", body="SECRET-BODY-TWO")
    seen, _ = _run(tmp_path, "a", [], skills)
    system = seen[0][0]["content"]
    assert system.startswith(system_message(PROTOCOL))
    catalog = system[len(system_message(PROTOCOL)) :]
    assert "- css-clip: Fix clipped text.\n- stale-closure: Fix a stale closure in a hook." in catalog  # sorted by name
    assert "load_skill" in catalog
    assert "SECRET-BODY" not in system
    assert str(skills) not in system and "SKILL.md" not in system  # no path


def test_load_skill_returns_the_body_and_a_second_call_says_loaded(tmp_path: Path):
    skills = tmp_path / "skills"
    _write(skills, "stale-closure", body="Read the hook deps first.")
    call = {"tool": "load_skill", "arguments": {"name": "stale-closure"}}
    seen, trajectory = _run(tmp_path, "a", [call, call], skills)
    assert seen[1][-1]["content"] == '<skill_content name="stale-closure">\nRead the hook deps first.\n</skill_content>'
    assert "already loaded" in seen[2][-1]["content"] and "Read the hook" not in seen[2][-1]["content"]
    assert loaded_names(trajectory.steps) == ["stale-closure"]  # counted once, from the stored steps
    assert [s.tool_name for s in trajectory.steps] == ["load_skill", "load_skill", "submit"]


def test_unknown_skill_name_is_an_error_and_not_counted(tmp_path: Path):
    skills = tmp_path / "skills"
    _write(skills, "stale-closure")
    seen, trajectory = _run(tmp_path, "a", [{"tool": "load_skill", "arguments": {"name": "nope"}}], skills)
    assert seen[1][-1]["content"].startswith("not-found: nope is not a skill; choose one of: stale-closure")
    assert loaded_names(trajectory.steps) == []


def test_tool_spec_name_is_an_enum_of_loadable_names(tmp_path: Path):
    skills = tmp_path / "skills"
    _write(skills, "b-skill")
    _write(skills, "a-skill")
    _write(skills, "bad", front="name: other\ndescription: x")
    loadable, refused = load_skills(skills)
    spec = tool_spec(loadable)
    assert spec["parameters"]["properties"]["name"]["enum"] == ["a-skill", "b-skill"]
    assert [r.name for r in refused] == ["bad"]
    assert tool_spec([]) is None


def test_twenty_skills_add_fewer_tokens_than_their_bodies(tmp_path: Path):
    skills = tmp_path / "skills"
    for i in range(20):
        description = f"Fix bug type {i:02d} in the Canvas console. Use when a ticket describes the symptom of archetype {i:02d}: wrong value shown, stale state, or a clipped element."
        body = "".join(f"{n}. Open the component for step {n} of skill {i:02d}, read it, and check the props.\n" for n in range(60))
        _write(skills, f"archetype-{i:02d}", description=description, body=body)
    with_skills, _ = _run(tmp_path, "with", [], skills)
    without, _ = _run(tmp_path, "without", [], None)
    loadable, refused = load_skills(skills)
    assert len(loadable) == 20 and not refused
    added = len(with_skills[0][0]["content"]) // 4 - len(without[0][0]["content"]) // 4
    bodies = sum(len(skill.body) // 4 for skill in loadable)
    print(f"catalog adds {added} tokens; the 20 bodies are {bodies} tokens")
    assert (added, bodies) == (880, 23280)  # 20 bodies of 4,659 characters each; the catalog is 3.8% of them
    assert added < bodies


def test_bad_frontmatter(tmp_path: Path):
    skills = tmp_path / "skills"
    cases = {
        "dup-key": "name: dup-key\nname: dup-key\ndescription: x",
        "unknown-key": "name: unknown-key\ndescription: x\nreviewed: true",
        "bad-meta": 'name: bad-meta\ndescription: x\nmetadata:\n  v: 1.0',
        "bool-meta": "name: bool-meta\ndescription: x\nmetadata:\n  reviewed: true",
        "wrong-dir": "name: other-name\ndescription: x",
        "no-desc": "name: no-desc",
        "Bad_Name": "name: Bad_Name\ndescription: x",
        "empty-desc": 'name: empty-desc\ndescription: ""',
        "long-desc": "name: long-desc\ndescription: " + "a" * 1025,
        "not-yaml": "name: [unclosed\ndescription: x",
    }
    for name, front in cases.items():
        _write(skills, name, front=front)
    folder = skills / "no-close"
    folder.mkdir()
    (folder / "SKILL.md").write_text("---\nname: no-close\ndescription: x\nbody without a closing line\n", encoding="utf-8")
    (skills / "empty").mkdir()
    _write(skills, "good", front='name: good\ndescription: ok\nmetadata:\n  argus-status: "unreviewed"\nallowed-tools: read_file edit')
    loadable, refused = load_skills(skills)
    assert [s.name for s in loadable] == ["good"]
    assert {r.name: r.reason for r in refused} == {name: Reason.bad_frontmatter for name in [*cases, "no-close", "empty"]}


def test_refusals_are_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    _write(tmp_path / "skills", "wrong-dir", front="name: other\ndescription: x")
    with caplog.at_level(logging.WARNING, logger="fix_loop.skills"):
        load_skills(tmp_path / "skills")
    assert "skill refused: wrong-dir (bad-frontmatter)" in caplog.text


def test_body_limit_boundary(tmp_path: Path):
    skills = tmp_path / "skills"
    _write(skills, "at-limit", body="x" * MAX_BODY_CHARS)
    _write(skills, "over-limit", body="x" * (MAX_BODY_CHARS + 1))
    loadable, refused = load_skills(skills)
    assert MAX_BODY_CHARS == 8000
    assert [s.name for s in loadable] == ["at-limit"] and len(loadable[0].body) == 8000
    assert [(r.name, r.reason) for r in refused] == [("over-limit", Reason.too_large)]


def test_crlf_file_loads_and_counts_the_same(tmp_path: Path):
    folder = _write(tmp_path / "skills", "crlf", body="a" * MAX_BODY_CHARS)
    folder.joinpath("SKILL.md").write_bytes(folder.joinpath("SKILL.md").read_bytes().replace(b"\n", b"\r\n"))
    loadable, _ = load_skills(tmp_path / "skills")
    assert [s.name for s in loadable] == ["crlf"] and "\r" not in loadable[0].body


def test_no_skills_means_identical_system_bytes_and_tools(tmp_path: Path):
    plain, _ = _run(tmp_path, "plain", [], None)
    empty = tmp_path / "empty-skills"
    empty.mkdir()
    none_loadable, _ = _run(tmp_path, "empty", [], empty)
    only_bad = tmp_path / "bad-skills"
    _write(only_bad, "bad", front="name: other\ndescription: x")
    refused, _ = _run(tmp_path, "bad", [], only_bad)
    for seen in (plain, none_loadable, refused):
        assert seen[0][0]["content"].encode() == system_message(PROTOCOL).encode()
        assert "load_skill" not in seen[0][0]["content"]
    # no skill is loadable, so load_skill is not a tool: the call goes to the normal tools and is refused
    seen, trajectory = _run(tmp_path, "call", [{"tool": "load_skill", "arguments": {"name": "x"}}], empty)
    assert seen[1][-1]["content"] == "not-allowed: load_skill is not a fix-loop tool"
    assert loaded_names(trajectory.steps) == []


def test_same_skill_set_gives_identical_bytes_across_runs(tmp_path: Path):
    skills = tmp_path / "skills"
    for name in ("zeta", "alpha", "mid"):
        _write(skills, name)
    one, _ = _run(tmp_path, "one", [], skills)
    two, _ = _run(tmp_path, "two", [], skills)
    assert one[0][0]["content"].encode() == two[0][0]["content"].encode()
    other = tmp_path / "other"
    for name in ("mid", "alpha", "zeta"):  # created in a different order
        _write(other, name)
    three, _ = _run(tmp_path, "three", [], other)
    assert three[0][0]["content"].encode() == one[0][0]["content"].encode()


def test_missing_directory_is_an_error(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_skills(tmp_path / "nope")
