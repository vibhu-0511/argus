"""Offline test of the T20 runner pieces: a local git repo stands in for GitHub, a stub agent edits the checkout, no model, no network, no Docker."""

from __future__ import annotations

import json
import subprocess

import pytest

from eval import multimodal as mm
from eval import multimodal_run as run
from eval.runner import AgentConfig

GOLD = json.loads((mm.DATA_DIR / "gold_patches.json").read_text(encoding="utf-8"))


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
    (repo / "later.js").write_text("// a later commit\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "later")
    return repo, git(repo, "rev-parse", "HEAD~1")


def task_at(base: str, task_id: str = "markedjs__marked-1435") -> mm.MultimodalTask:
    real = next(t for t in mm.load_subset() if t.id == task_id)
    return real.model_copy(update={"base_commit": base})


def fake_download(url, dest):
    dest.write_bytes(b"\x89PNG fake " + url.encode())


def stub_agent(checkout):
    (checkout / "lib.js").write_text("module.exports = () => 2;\n", encoding="utf-8")
    (checkout / "new.js").write_text("// new file\n", encoding="utf-8")


def test_prepare_checks_out_base_commit_and_keeps_gold_out_of_the_prompt(tmp_path, origin):
    repo, base = origin
    task = task_at(base)
    prompt = run.prepare(task, tmp_path / "run", repo_url=repo.as_uri(), download=fake_download)
    work = tmp_path / "run" / task.id
    assert git(work / "checkout", "rev-parse", "HEAD") == base
    assert not (work / "checkout" / "later.js").exists()
    image = work / "images" / "01.png"
    assert image.exists() and f"Screenshots attached to the issue:\n- {image}" in prompt
    assert (work / "prompt.txt").read_bytes().decode("utf-8") == prompt
    assert task.ticket.text in prompt and base in prompt
    for tid, patch in GOLD.items():
        assert mm.leaks_gold(prompt, patch) is None, tid


def test_stub_agent_patch_is_captured_applies_and_is_not_scored(tmp_path, origin):
    repo, base = origin
    task, root = task_at(base), tmp_path / "run"
    run.prepare(task, root, repo_url=repo.as_uri(), download=fake_download)
    stub_agent(root / task.id / "checkout")
    patch = run.finish(task, root)
    assert "module.exports = () => 2;" in patch and "new.js" in patch
    assert (root / task.id / "model.diff").read_bytes().decode("utf-8") == patch

    fresh = tmp_path / "fresh"
    subprocess.run(["git", "clone", "-q", repo.as_posix(), str(fresh)], check=True)
    git(fresh, "checkout", "-q", base)
    run.apply_patch(fresh, patch)
    assert (fresh / "lib.js").read_text(encoding="utf-8") == "module.exports = () => 2;\n"
    with pytest.raises(run.SetupError, match="does not apply"):
        run.apply_patch(fresh, patch)  # second time: already applied

    rows = run.predictions([task], root, "stub")
    assert rows == [{"instance_id": task.id, "model_name_or_path": "stub", "model_patch": patch}]

    res = run.results([task], root, AgentConfig(name="stub", model="stub", factory="x:y"))
    row = res.tasks[0]
    assert (row.verdict, res.counts.resolved, res.resolve_rate.total) == ("excluded", 0, 0)
    assert row.reason.startswith(run.NOT_SCORED)
    counts_line = run.table(res).splitlines()[-1]
    assert f"{run.NOT_SCORED} 1" in counts_line and "solved" not in counts_line.split(": ")[1]


def test_harness_report_turns_a_patch_into_resolved_or_unresolved(tmp_path, origin):
    repo, base = origin
    ids = ["markedjs__marked-1435", "markedjs__marked-1535"]
    tasks = [task_at(base, i) for i in ids]
    root, reports = tmp_path / "run", tmp_path / "logs"
    for t in tasks:
        run.prepare(t, root, repo_url=repo.as_uri(), download=fake_download)
        stub_agent(root / t.id / "checkout")
        run.finish(t, root)
        d = reports / "stub" / t.id
        d.mkdir(parents=True)
        (d / "report.json").write_text(json.dumps({t.id: {"resolved": t.id == ids[0]}}), encoding="utf-8")
    res = run.results(tasks, root, AgentConfig(name="stub", model="stub", factory="x:y"), reports)
    assert [r.verdict for r in res.tasks] == ["resolved", "unresolved"]
    assert (res.resolve_rate.successes, res.resolve_rate.total) == (1, 2)


def test_every_task_gets_a_row_with_a_reason(tmp_path, origin):
    repo, base = origin
    ok, empty, broken = task_at(base, "markedjs__marked-1435"), task_at(base, "markedjs__marked-1535"), task_at(base, "markedjs__marked-1262")
    root = tmp_path / "run"
    run.prepare(empty, root, repo_url=repo.as_uri(), download=fake_download)
    run.finish(empty, root)  # the agent changed nothing
    with pytest.raises(run.SetupError):
        run.prepare(broken, root, repo_url=(tmp_path / "missing").as_uri(), download=fake_download)
    res = run.results([ok, empty, broken], root, AgentConfig(name="stub", model="stub", factory="x:y"))
    by_id = {r.task_id: r for r in res.tasks}
    assert len(res.tasks) == 3
    assert by_id[ok.id].verdict == "excluded" and "not run" in by_id[ok.id].reason
    assert by_id[empty.id].verdict == "unresolved" and "empty patch" in by_id[empty.id].reason
    assert by_id[broken.id].verdict == "excluded" and by_id[broken.id].reason.startswith("setup failed")
    assert res.counts.model_dump() == {"resolved": 0, "unresolved": 1, "excluded": 2, "error": 0}
