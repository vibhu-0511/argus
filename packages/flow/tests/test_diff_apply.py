"""The in-memory unified-diff applier behind the GitHub write client. No network.

The round trip test makes real `git diff` output from a throwaway repo (in `tmp_path`) and checks the
applier produces the files git left on disk; it is skipped when `git` is not installed.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from flow.diff_apply import FileChange, PatchError, apply_unified


def files(**tree: str):
    return tree.get


def test_a_modification_a_creation_and_a_deletion():
    patch = (
        "diff --git a/a.txt b/a.txt\nindex 1..2 100755\n--- a/a.txt\n+++ b/a.txt\n@@ -1,3 +1,3 @@\n one\n-two\n+TWO\n three\n"
        "diff --git a/new.txt b/new.txt\nnew file mode 100644\nindex 0..3\n--- /dev/null\n+++ b/new.txt\n@@ -0,0 +1 @@\n+hi\n"
        "diff --git a/old.txt b/old.txt\ndeleted file mode 100644\nindex 4..0\n--- a/old.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-bye\n"
    )
    got = apply_unified(patch, files(**{"a.txt": "one\ntwo\nthree\n", "old.txt": "bye\n"}))
    assert got == [FileChange("a.txt", "100755", "one\nTWO\nthree\n"), FileChange("new.txt", "100644", "hi\n"), FileChange("old.txt", "100644", None)]


def test_a_context_that_does_not_match_changes_nothing():
    patch = "--- a/a.txt\n+++ b/a.txt\n@@ -1,2 +1,2 @@\n one\n-two\n+TWO\n"
    with pytest.raises(PatchError, match="does not match"):
        apply_unified(patch, files(**{"a.txt": "one\nSOMETHING ELSE\n"}))


@pytest.mark.parametrize(
    ("patch", "word"),
    [
        ("diff --git a/x b/x\nGIT binary patch\nliteral 3\n", "binary"),
        ("diff --git a/x b/y\nsimilarity index 100%\nrename from x\nrename to y\n", "renames"),
        ("--- x\n+++ y\n@@ -1 +1 @@\n-a\n+b\n", "unsupported path"),
        ("not a diff at all\n", "no file changes"),
        ("--- a/x\n+++ b/x\n", "no hunks"),
        ("--- a/x\n+++ b/x\n@@ -1,3 +1,3 @@\n a\n", "shorter"),
    ],
)
def test_unsupported_or_broken_patches_are_refused_with_a_reason(patch, word):
    with pytest.raises(PatchError, match=word):
        apply_unified(patch, files(x="a\n"))


def test_creating_a_file_that_exists_and_changing_one_that_does_not_are_refused():
    create = "--- /dev/null\n+++ b/x\n@@ -0,0 +1 @@\n+a\n"
    change = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
    with pytest.raises(PatchError, match="already exists"):
        apply_unified(create, files(x="a\n"))
    with pytest.raises(PatchError, match="does not exist"):
        apply_unified(change, files())


def test_the_no_newline_marker_is_followed():
    removed_newline = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+a\n\\ No newline at end of file\n"
    added_newline = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n\\ No newline at end of file\n+a\n"
    assert apply_unified(removed_newline, files(x="a\n"))[0].content == "a"
    assert apply_unified(added_newline, files(x="a"))[0].content == "a\n"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_it_matches_what_git_produces(tmp_path):
    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True, text=True).stdout

    git("init", "-q")
    body = "".join(f"line {i}\n" for i in range(1, 41))
    (tmp_path / "a.txt").write_text(body, newline="\n")
    (tmp_path / "gone.txt").write_text("gone\n", newline="\n")
    (tmp_path / "tail.txt").write_text("no newline", newline="\n")
    git("add", "-A"), git("commit", "-q", "-m", "base")
    (tmp_path / "a.txt").write_text(body.replace("line 3\n", "line 3 changed\n").replace("line 30\n", "line 30\nextra\n").replace("line 38\n", ""), newline="\n")
    (tmp_path / "gone.txt").unlink()
    (tmp_path / "tail.txt").write_text("no newline either", newline="\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "new.txt").write_text("fresh\n", newline="\n")
    git("add", "-A")
    patch = git("diff", "--cached")
    expected = {"a.txt": (tmp_path / "a.txt").read_text(), "tail.txt": "no newline either", "sub/new.txt": "fresh\n", "gone.txt": None}
    base = {"a.txt": body, "gone.txt": "gone\n", "tail.txt": "no newline"}
    got = {c.path: c.content for c in apply_unified(patch, base.get)}
    assert got == expected
