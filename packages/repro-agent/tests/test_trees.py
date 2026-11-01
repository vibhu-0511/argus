"""Live tree runner: the CSS of the two trees, the cache and the verdict mapping. The sandbox run is stubbed; the one test
that really runs it needs ARGUS_PLATFORM_REPO and the rig (`python -m repro_agent.trees up`) and is marked docker."""

import os
import subprocess
from pathlib import Path

import pytest

from repro_agent import trees
from repro_agent.browser import ToolUnavailable

BUG = "diff --git a/s.css b/s.css\n--- a/s.css\n+++ b/s.css\n@@ -1,3 +1,3 @@\n a {\n-  size: 20px;\n+  size: 8px;\n }\n"
GOLDEN = "diff --git a/s.css b/s.css\n--- a/s.css\n+++ b/s.css\n@@ -1,3 +1,3 @@\n a {\n-  size: 8px;\n+  size: 20px;\n }\n"


def _repo_and_task(tmp_path: Path, crlf: bool = False) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)  # noqa: E731
    git("init", "-q")
    (repo / "s.css").write_bytes(b"a {\n  size: 20px;\n}\n")
    git("add", "s.css")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x")
    task = tmp_path / "task"
    task.mkdir()
    for name, text in (("bug.patch", BUG), ("golden.patch", GOLDEN)):
        (task / name).write_bytes((text.replace("\n", "\r\n") if crlf else text).encode())
    return repo, task


@pytest.mark.parametrize("crlf", [False, True])  # the checked-out patch files have CRLF on Windows
def test_the_two_trees_differ_by_the_patches(tmp_path: Path, crlf: bool):
    repo, task = _repo_and_task(tmp_path, crlf)
    found = trees.css_trees(task, repo)
    assert found["buggy"] == {"s.css": b"a {\n  size: 8px;\n}\n"}
    assert found["golden"] == {"s.css": b"a {\n  size: 20px;\n}\n"}


def _stub(monkeypatch, buggy: str, golden: str, calls: list):
    monkeypatch.setattr(trees, "status", lambda: {"canvas": True, "proxy": True})
    monkeypatch.setattr(trees, "_proxy_up", lambda: True)

    def run_both(script, task_dir):
        calls.append(script)
        return {"buggy": {"result": buggy, "detail": ""}, "golden": {"result": golden, "detail": ""}}

    monkeypatch.setattr(trees, "run_both", run_both)


@pytest.mark.parametrize(
    "buggy,golden,want",
    [("fail", "pass", (True, True)), ("pass", "pass", (False, True)), ("fail", "fail", (True, False)), ("error", "pass", (False, True)), ("fail", "error", (True, False))],
)
def test_verdict_mapping(tmp_path: Path, monkeypatch, buggy, golden, want):
    _stub(monkeypatch, buggy, golden, [])
    run = trees.trees_for(tmp_path / "seed-x")("await expect(a).toBeVisible();")
    assert (run.failed_on_buggy, run.passed_on_golden) == want


def test_a_skipped_test_is_never_a_reproduction(tmp_path: Path, monkeypatch):
    _stub(monkeypatch, "fail", "pass", [])
    run = trees.trees_for(tmp_path / "seed-x")("test.skip(true); await expect(a).toBeVisible();")
    assert (run.failed_on_buggy, run.passed_on_golden) == (False, False)


def test_the_cache_runs_a_script_once_per_task(tmp_path: Path, monkeypatch):
    calls: list = []
    _stub(monkeypatch, "fail", "pass", calls)
    cache = tmp_path / "cache"
    for _ in range(2):
        trees.trees_for(tmp_path / "seed-x", cache)("s")
    trees.trees_for(tmp_path / "seed-y", cache)("s")
    assert len(calls) == 2 and len(list(cache.glob("*.json"))) == 2


def test_without_the_rig_the_runner_refuses_before_any_script(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(trees, "status", lambda: {"canvas": False, "proxy": False})
    with pytest.raises(ToolUnavailable, match="rig is not up"):
        trees.trees_for(tmp_path)


@pytest.mark.docker
def test_a_real_script_is_valid_on_seed_e01():
    if not os.environ.get("ARGUS_PLATFORM_REPO") or not all(trees.status().values()):
        pytest.skip("needs ARGUS_PLATFORM_REPO and the rig: python -m repro_agent.trees up")
    task = Path(__file__).resolve().parents[2] / "bench" / "tasks" / "seeded" / "seed-e01"
    script = "await expect(page.locator('.landing-brand').first()).toHaveCSS('font-size', '20px');"
    run = trees.trees_for(task)(script)
    assert (run.failed_on_buggy, run.passed_on_golden) == (True, True)
