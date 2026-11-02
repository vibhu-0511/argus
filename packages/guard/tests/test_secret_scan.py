"""P7-T03: the CI secret scan fails on a planted token and on a token in a git remote URL, and the repository itself is clean."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "check_no_secrets.py"
spec = importlib.util.spec_from_file_location("check_no_secrets", SCRIPT)
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

# Built at run time and without the word FAKE, so the scan sees a real-looking value in the temporary repo only.
PLANTED = "ghp_" + "B" * 36


def _repo(tmp_path: Path, remote: str | None = None) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", remote], check=True)
    return tmp_path


def test_a_token_in_a_remote_url_is_flagged(tmp_path):
    repo = _repo(tmp_path, "https://x-access-token:" + PLANTED + "@github.com/vibhu-0511/argus.git")
    assert scan.remote_leaks(repo) == ["remote.origin.url"]


def test_a_user_only_remote_url_is_flagged(tmp_path):
    assert scan.remote_leaks(_repo(tmp_path, "https://" + PLANTED + "@github.com/vibhu-0511/argus.git")) == ["remote.origin.url"]


def test_a_plain_remote_and_no_remote_pass(tmp_path):
    assert scan.remote_leaks(_repo(tmp_path / "a", "https://github.com/vibhu-0511/argus.git")) == []
    assert scan.remote_leaks(_repo(tmp_path / "b", "git@github.com:vibhu-0511/argus.git")) == []
    assert scan.remote_leaks(_repo(tmp_path / "c")) == []


def test_a_planted_token_in_a_tracked_file_is_flagged_without_printing_it(tmp_path):
    repo = _repo(tmp_path)
    (repo / "notes.md").write_text(f"token: {PLANTED}\n", encoding="utf-8")
    (repo / "ok.md").write_text(f"token: {PLANTED} FAKE\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    hits = scan.tracked_leaks(repo)
    assert hits == ["notes.md:1: ghp_..."]
    assert PLANTED not in " ".join(hits)


def test_this_repository_is_clean():
    assert scan.remote_leaks() == []
    assert scan.tracked_leaks() == []
    assert scan.main() == 0
