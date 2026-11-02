"""Offline test of the T20 argus fix-loop adapter: a local git repo stands in for GitHub, scripted replies stand in for the Claude workers. No model, no network, no Docker."""

from __future__ import annotations

import json
import subprocess

import pytest

from eval import mm_turn as mm
from eval import multimodal as mmod
from eval.multimodal_run import NOT_SCORED
from eval.runner import AgentConfig


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


@pytest.fixture
def origin(tmp_path):
    repo = tmp_path / "origin"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "lib.js").write_text("module.exports = () => 1;\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
    return repo, git(repo, "rev-parse", "HEAD")


def task_at(base: str):
    return next(t for t in mmod.load_subset() if t.id == "markedjs__marked-1435").model_copy(update={"base_commit": base})


def call(tool, **arguments):
    return json.dumps({"tool": tool, "arguments": arguments})


def test_the_loop_runs_from_replies_and_captures_the_diff(tmp_path, origin, capsys):
    repo, base = origin
    task, root = task_at(base), tmp_path / "run"
    assert mm.start(task, root, repo.as_uri(), lambda url, dest: dest.write_bytes(b"png")) == 0
    assert "recorded 0 answers" in capsys.readouterr().out

    assert mm.answer(task, root, "I will just fix it") == 3  # plain text is not a tool call: nothing recorded
    assert "rejected" in capsys.readouterr().out
    assert (root / task.id / "answers.jsonl").read_text(encoding="utf-8") == ""

    for reply in (call("read_file", path="lib.js"), call("run_cmd", command="rm -rf ."), call("edit", path="lib.js", old="=> 1", new="=> 2"), call("submit")):
        assert mm.answer(task, root, reply) == 0
    out = capsys.readouterr().out
    verdict = json.loads(out.strip().splitlines()[-1])
    assert (verdict["stop_reason"], verdict["verdict"], verdict["model_turns"]) == ("submit", "patch-captured", 4)
    patch = (root / task.id / "model.diff").read_bytes().decode("utf-8")
    assert "-module.exports = () => 1;" in patch and "+module.exports = () => 2;" in patch
    steps = [json.loads(line) for line in (root / task.id / "fix" / "trajectory.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(s.get("tool_error") == "not-allowed" for s in steps)  # rm was refused, the loop went on

    res = mm.results([task], root, None, AgentConfig(name="argus-test", model=mm.MODEL, host=mm.HOST, factory="x:y"), "t")
    row = res.tasks[0]
    assert row.verdict == "excluded" and row.reason.startswith(NOT_SCORED)  # produced, never graded: not solved
    assert (row.stop_reason, row.steps) == ("submit", 4) and row.tokens.tokens_in > 0 and res.resolve_rate.total == 0


def test_run_cmd_is_read_only_and_has_no_shell(tmp_path, origin):
    repo, base = origin
    ok = mm._run_cmd(repo, "git status")
    assert ok.returncode == 0
    for bad in ("git diff > out.txt", "git diff --output=out.txt", "git commit -m x", "git -c core.pager=x diff", "node -e 1", "node --check ../x.js", "sh -c ls", "rm -rf ."):
        result = mm._run_cmd(repo, bad)
        assert result.ok is False and result.error in ("not-allowed", "failed"), bad
    assert not (repo / "out.txt").exists()


def test_prompt_has_local_images_and_no_gold_patch(tmp_path, origin):
    repo, base = origin
    task, root = task_at(base), tmp_path / "run"
    mm.start(task, root, repo.as_uri(), lambda url, dest: dest.write_bytes(b"png"))
    prompt = (root / task.id / "prompt.txt").read_bytes().decode("utf-8")
    assert str(root / task.id / "images" / "01.png") in prompt
    gold = json.loads((mmod.DATA_DIR / "gold_patches.json").read_text(encoding="utf-8"))
    assert all(mmod.leaks_gold(prompt, patch) is None for patch in gold.values())
