from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from argus_bench.golden import golden_all

_REPO = Path(__file__).resolve().parents[3]
_BUG = """\
diff --git a/missing.txt b/missing.txt
--- a/missing.txt
+++ b/missing.txt
@@ -1 +1 @@
-old
+new
"""
_STALE = """\
diff --git a/app.txt b/app.txt
--- a/app.txt
+++ b/app.txt
@@ -1 +1 @@
-goodbye
+fixed
"""


def _git(repo: Path, *args: str, identity: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = ["git", "-c", "core.autocrlf=false"]
    if identity:
        cmd += ["-c", "user.email=dev@example.com", "-c", "user.name=dev"]
    cmd += ["-C", str(repo), *args]
    return subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")


def test_stale_golden_fails_until_regenerated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / "app.txt").write_text("hello\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "app.txt")
    _git(repo, "commit", "-m", "init", identity=True)

    task = tmp_path / "stale-probe"
    task.mkdir()
    (task / "bug.patch").write_text(_BUG, encoding="utf-8", newline="\n")
    (task / "golden.patch").write_text(_STALE, encoding="utf-8", newline="\n")

    calls: list[str] = []

    def stub(task_path: str, tree: Path) -> int:
        calls.append(task_path)
        return 0

    monkeypatch.setattr("argus_bench.golden.score_task", stub)

    code = golden_all(tree=repo, tasks=[task])
    stale_out = capsys.readouterr().out
    assert code != 0
    assert "fail stale-probe" in stale_out
    assert calls == []

    app = repo / "app.txt"
    original = app.read_bytes()
    app.write_bytes(b"hello fixed\n")
    diff = _git(repo, "diff", "--", "app.txt")
    app.write_bytes(original)
    (task / "golden.patch").write_text(diff.stdout, encoding="utf-8", newline="\n")

    code = golden_all(tree=repo, tasks=[task])
    fixed_out = capsys.readouterr().out
    assert code == 0
    assert "pass stale-probe" in fixed_out
    assert len(calls) == 1

    workflow = (_REPO / ".github" / "workflows" / "golden.yml").read_text(encoding="utf-8")
    assert "uv run bench golden --all" in workflow
    assert "continue-on-error" not in workflow
