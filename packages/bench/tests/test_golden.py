from argus_bench.cli import main
from argus_bench.golden import platform_repo, task_dirs


def test_golden_requires_all():
    assert main(["golden"]) == 2


def test_platform_repo_and_seeded_tasks():
    assert platform_repo().name == "dcortex-platform"
    assert len(task_dirs()) == 30
