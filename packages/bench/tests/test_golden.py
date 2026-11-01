from collections import Counter

import pytest

from argus_bench.cli import main
from argus_bench.golden import platform_repo, task_dirs


def test_golden_requires_all():
    assert main(["golden"]) == 2


def test_platform_repo_comes_from_the_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ARGUS_PLATFORM_REPO", str(tmp_path))
    assert platform_repo() == tmp_path
    monkeypatch.delenv("ARGUS_PLATFORM_REPO")
    with pytest.raises(FileNotFoundError, match="ARGUS_PLATFORM_REPO"):
        platform_repo()


def test_seeded_and_mutated_tasks_are_counted_separately():
    kinds = Counter(path.parent.name for path in task_dirs())
    assert kinds == {"seeded": 30, "mutated": 300}
