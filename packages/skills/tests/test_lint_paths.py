"""P5.5-T16: the lint's path check. A path a skill names that is not in the repo fails; a path that is there passes. No model, no network."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fix_loop.skills import load_skills
from skills.lint import LOCK, SKILLS, lint, referenced_paths
from skills.pin import pin

STALE = Path(__file__).parent / "fixtures" / "stale-skills"
REAL_CSS = "apps/canvas/src/insights/desk/desk.css"
DEAD_CSS = "apps/canvas/src/insights/desk.css"  # where the fixture skills say it is: moved into desk/ since


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "repo" / "apps/canvas/src/insights/desk").mkdir(parents=True)
    (tmp_path / "repo" / REAL_CSS).write_text(".x{}", encoding="utf-8")
    return tmp_path / "repo"


def pinned(tmp_path, variant):
    """The fixture skill copied next to a throwaway lock: the real lock is never touched."""
    skills = tmp_path / "skills"
    shutil.copytree(STALE / variant, skills)
    lock = tmp_path / "skills.lock.json"
    for folder in skills.iterdir():
        assert pin(folder.name, "test", skills, lock) is None
    return skills, lock


def test_what_counts_as_a_path():
    text = (
        "read `apps/canvas/a.css` and `apps/canvas/b/`, then `apps/canvas/c.tsx:22`. "
        "Not these: `desk.css` `/work/AGENTS.md` `../checks/checks.json` `./x/y.css` `src/*.css` `src/<name>.css` "
        "`https://x.io/a.css` `a b/c.css` `apps/canvas` `read/write` `.tsx` `platform/`. Twice: `apps/canvas/a.css`"
    )
    assert referenced_paths(text) == ["apps/canvas/a.css", "apps/canvas/b/", "apps/canvas/c.tsx"]


@pytest.mark.parametrize("variant", ["natural", "insistent"])
def test_stale_path_fails(tmp_path, repo, variant):
    skills, lock = pinned(tmp_path, variant)
    assert lint(skills, lock) == []  # trusted and well formed: only the path check can see it
    assert [r.reason.value for r in load_skills(skills, lock)[1]] == []  # and the loader loads it
    [line] = lint(skills, lock, repo)
    assert line.startswith(f"css-token-base-rule-desk: stale-path: `{DEAD_CSS}` is not in repo")


def test_valid_path_passes(tmp_path, repo):
    skills, lock = pinned(tmp_path, "natural")
    file = skills / "css-token-base-rule-desk" / "SKILL.md"
    file.write_text(file.read_text(encoding="utf-8").replace(DEAD_CSS, REAL_CSS), encoding="utf-8")
    assert pin("css-token-base-rule-desk", "test", skills, lock) is None
    assert lint(skills, lock, repo) == []


def test_real_skills_still_pass(repo):
    assert lint(SKILLS, LOCK, repo) == []
    assert lint(SKILLS, LOCK) == []
    assert all(referenced_paths(f.read_text(encoding="utf-8")) == [] for f in SKILLS.glob("*/SKILL.md"))  # they name no repo path


@pytest.mark.skipif(not os.environ.get("ARGUS_PLATFORM_REPO"), reason="needs the platform checkout")
def test_real_skills_pass_against_the_platform_repo():
    assert lint(SKILLS, LOCK, Path(os.environ["ARGUS_PLATFORM_REPO"])) == []


def test_command_line(tmp_path, repo):
    skills, lock = pinned(tmp_path, "insistent")
    args = [sys.executable, "-m", "skills.lint", "--skills", str(skills), "--lock", str(lock)]
    bad = subprocess.run([*args, "--repo", str(repo)], capture_output=True, text=True)
    assert bad.returncode == 1 and "stale-path" in bad.stderr
    env = {k: v for k, v in os.environ.items() if k != "ARGUS_PLATFORM_REPO"}
    no_repo = subprocess.run(args, capture_output=True, text=True, env=env)
    assert no_repo.returncode == 0 and "paths not checked" in no_repo.stderr
