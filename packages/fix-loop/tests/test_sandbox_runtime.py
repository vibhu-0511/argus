"""P7-T10: the sandbox runtime setting. No Docker needed: the docker calls are replaced."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fix_loop import sandbox

PREFIX = ["docker", "run", "--rm"]


def _tail(work: Path, checks: Path) -> list[str]:
    return [
        "--network", "none", "--cpus", "1", "--memory", "512m",
        "-v", f"{work}:/work", "-v", f"{checks}:/checks:ro", "-w", "/work",
        "argus-fix-sandbox:p3", "echo", "hi",
    ]


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    work, checks = tmp_path / "work", tmp_path / "checks"
    work.mkdir()
    checks.mkdir()
    return work.resolve(), checks.resolve()


@pytest.fixture
def calls(monkeypatch) -> list[list[str]]:
    seen: list[list[str]] = []

    def fake(cmd, *a, **k):
        seen.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(sandbox.subprocess, "run", fake)
    monkeypatch.delenv(sandbox.RUNTIME_ENV, raising=False)
    return seen


def test_argv_default_has_no_runtime_flag(dirs):
    work, checks = dirs
    assert sandbox.docker_argv(work, checks, ["echo", "hi"]) == PREFIX + _tail(work, checks)


@pytest.mark.parametrize("rt", ["runsc", "runc"])
def test_argv_with_runtime_adds_exactly_one_flag_pair(dirs, rt):
    work, checks = dirs
    assert sandbox.docker_argv(work, checks, ["echo", "hi"], rt) == PREFIX + ["--runtime", rt] + _tail(work, checks)


def test_run_without_setting_is_one_docker_call_and_no_runtime(dirs, calls):
    work, checks = dirs
    sandbox.run(work, checks, ["echo", "hi"])
    assert calls == [PREFIX + _tail(work, checks)]  # no `docker info` either


def test_run_reads_the_environment_setting(dirs, calls, monkeypatch):
    work, checks = dirs
    monkeypatch.setattr(sandbox, "docker_runtimes", lambda: ["runc", "runsc"])
    monkeypatch.setenv(sandbox.RUNTIME_ENV, "runsc")
    sandbox.run(work, checks, ["echo", "hi"])
    assert calls == [PREFIX + ["--runtime", "runsc"] + _tail(work, checks)]


def test_run_parameter_wins_over_environment(dirs, calls, monkeypatch):
    work, checks = dirs
    monkeypatch.setattr(sandbox, "docker_runtimes", lambda: ["runc", "runsc"])
    monkeypatch.setenv(sandbox.RUNTIME_ENV, "runsc")
    sandbox.run(work, checks, ["echo", "hi"], runtime="runc")
    assert calls == [PREFIX + ["--runtime", "runc"] + _tail(work, checks)]


def test_blank_setting_means_default(monkeypatch):
    monkeypatch.setenv(sandbox.RUNTIME_ENV, "  ")
    assert sandbox.configured_runtime() is None


def test_missing_runtime_is_an_error_and_nothing_runs(dirs, calls, monkeypatch):
    work, checks = dirs
    monkeypatch.setattr(sandbox, "docker_runtimes", lambda: ["runc", "io.containerd.runc.v2"])
    monkeypatch.setenv(sandbox.RUNTIME_ENV, "runsc")
    with pytest.raises(sandbox.RuntimeUnavailable, match="no runtime 'runsc'.*Not falling back"):
        sandbox.run(work, checks, ["echo", "hi"])
    assert calls == []  # no `docker run` on runc behind the caller's back


def test_docker_runtimes_parses_the_info_json(monkeypatch):
    monkeypatch.setattr(sandbox.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, '{"runc":{},"runsc":{}}\n', ""))
    assert sandbox.docker_runtimes() == ["runc", "runsc"]


def test_daemon_down_is_runtime_unavailable(monkeypatch):
    monkeypatch.setattr(sandbox.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "cannot connect"))
    with pytest.raises(sandbox.RuntimeUnavailable, match="not reachable"):
        sandbox.check_runtime("runsc")
