import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from guard import escape
from guard.cli import main as cli_main

NEEDED = {
    "network-tcp", "network-https", "dns-lookup", "host-fs-read", "readonly-mount-write",
    "docker-socket", "metadata-address", "fork-bomb", "symlink-escape",
}


def _table() -> list[escape.Probe]:
    return escape.probes(Path(tempfile.gettempdir()) / "canary" / "canary.txt")


def test_probe_table_has_at_least_eight_with_a_blocked_expectation():
    table = _table()
    ids = [p.id for p in table]
    assert len(table) >= 8 and len(ids) == len(set(ids))
    assert NEEDED <= set(ids)
    assert all(p.expected == "blocked" and p.script for p in table)
    assert escape.CANARY_TOKEN in {p.id: p for p in table}["host-fs-read"].script


def test_host_candidates_for_windows_and_linux_paths():
    class FakeWin:  # str() is all host_candidates uses, so this runs on any OS
        def __str__(self):
            return r"D:\data\t\canary.txt"

    got = escape.host_candidates(FakeWin())  # type: ignore[arg-type]
    assert "/host_mnt/d/data/t/canary.txt" in got and "D:/data/t/canary.txt" in got

    class FakePosix:
        def __str__(self):
            return "/tmp/x"

    assert "/host_mnt/tmp/x" in escape.host_candidates(FakePosix())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "stdout,status",
    [
        ("BLOCKED nothing got out\n", "pass"),
        ("noise\nESCAPED read host file\n", "fail"),
        ("ERROR wget missing\n", "error"),
        ("", "error"),
        ("blocked lower case\n", "error"),  # only the exact verdict word counts
        ("ESCAPED a\nBLOCKED b\n", "fail"),  # first verdict wins
    ],
)
def test_judge(stdout, status):
    assert escape.judge(stdout, 0)[0] == status


def test_format_report_prints_one_line_per_probe():
    report = {
        "tier": "docker", "runtime": "default",
        "probes": [
            {"id": "a", "status": "pass", "detail": "ok"},
            {"id": "b", "status": "fail", "detail": "got out"},
            {"id": "c", "status": "error", "detail": "timeout"},
        ],
        "summary": {"pass": 1, "fail": 1, "error": 1},
    }
    lines = escape.format_report(report).splitlines()
    assert lines[1].startswith("PASS ") and lines[2].startswith("FAIL ") and lines[3].startswith("ERROR")
    assert lines[-1] == "3 probes: 1 pass, 1 fail, 1 error"


def test_docker_argv_keeps_fixloop_flags_and_mounts_only_the_two_dirs(tmp_path):
    argv = escape.docker_argv("n", tmp_path / "w", tmp_path / "c", "true", runtime="runsc")
    joined = " ".join(argv)
    assert "--network none" in joined and "--pids-limit" in joined and "--runtime runsc" in joined
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
    assert len(mounts) == 2 and mounts[1].endswith(":/checks:ro")
    assert "docker.sock" not in joined and "-e" not in argv and "--privileged" not in argv


def test_firecracker_without_launcher_is_not_available_and_never_passes(monkeypatch, capsys):
    monkeypatch.delenv("ARGUS_FIRECRACKER_LAUNCHER", raising=False)
    monkeypatch.setattr(escape, "run_suite", lambda *a, **k: pytest.fail("no probe may run"))
    assert cli_main(["escape", "--tier", "firecracker"]) == escape.EXIT_UNAVAILABLE
    out = capsys.readouterr().out
    assert "tier not available here" in out and "not a pass" in out
    assert "PASS" not in out and "probes:" not in out


def test_gvisor_without_runsc_is_not_available(monkeypatch, capsys):
    monkeypatch.setattr(escape, "_docker_info", lambda fmt: '{"runc":{}}' if "Runtimes" in fmt else "29.0")
    monkeypatch.setattr(escape, "run_suite", lambda *a, **k: pytest.fail("no probe may run"))
    assert escape.main(["--tier", "gvisor"]) == escape.EXIT_UNAVAILABLE
    out = capsys.readouterr().out
    assert "tier not available here" in out and "runsc" in out


def test_gvisor_runtime_setting_is_used(monkeypatch):
    monkeypatch.setattr(escape, "_docker_info", lambda fmt: '{"runc":{},"myrt":{}}' if "Runtimes" in fmt else "29.0")
    assert escape.unavailable("gvisor", "myrt", None) is None
    assert "other" in escape.unavailable("gvisor", "other", None)
    assert escape.unavailable("gvisor", None, None) is not None  # default runtime name is runsc


def test_docker_daemon_down_is_not_available(monkeypatch):
    monkeypatch.setattr(escape, "_docker_info", lambda fmt: None)
    assert "not reachable" in escape.unavailable("docker", None, None)


def test_exit_code_and_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(escape, "unavailable", lambda *a: None)
    report = {"tier": "docker", "runtime": "default", "probes": [{"id": "a", "status": "pass", "detail": "ok"}], "summary": {"pass": 1, "fail": 0, "error": 0}}
    monkeypatch.setattr(escape, "run_suite", lambda *a, **k: report)
    out = tmp_path / "r.json"
    assert escape.main(["--tier", "docker", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["summary"]["pass"] == 1
    assert "PASS" in capsys.readouterr().out
    report["summary"] = {"pass": 0, "fail": 1, "error": 0}
    assert escape.main(["--tier", "docker"]) == 1
    report["summary"] = {"pass": 0, "fail": 0, "error": 1}
    assert escape.main(["--tier", "docker"]) == 1


def test_launcher_that_cannot_start_gives_errors_not_passes():
    report = escape.run_suite("firecracker", None, "no-such-launcher-for-guard-tests", timeout=10)
    assert report["summary"]["pass"] == 0 and report["summary"]["error"] == len(report["probes"])


def test_launcher_protocol_with_a_stub(tmp_path):
    stub = tmp_path / "stub.py"
    stub.write_text("print('BLOCKED stub')\n", encoding="utf-8")
    launcher = f"{shlex.quote(Path(sys.executable).as_posix())} {shlex.quote(stub.as_posix())}"
    report = escape.run_suite("firecracker", None, launcher, timeout=30)
    assert report["summary"]["pass"] == len(report["probes"]) and report["tier"] == "firecracker"


def _docker_up() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.fixture
def dirs(tmp_path):
    if not escape.egress._image_present():
        escape.sandbox.build_image()
    work, checks, canary_dir = tmp_path / "work", tmp_path / "checks", tmp_path / "canary"
    for d in (work, checks, canary_dir):
        d.mkdir()
    (checks / "keep.txt").write_text("same", encoding="utf-8")
    canary = canary_dir / "canary.txt"
    canary.write_text(escape.CANARY_TOKEN, encoding="utf-8")
    return work, checks, canary


@pytest.mark.docker
@pytest.mark.skipif(not _docker_up(), reason="Docker is not running")
def test_docker_tier_blocks_every_probe():
    report = escape.run_suite("docker", None, None)
    bad = [(r["id"], r["status"], r["detail"]) for r in report["probes"] if r["status"] != "pass"]
    assert not bad, bad


@pytest.mark.docker
@pytest.mark.skipif(not _docker_up(), reason="Docker is not running")
def test_probes_can_fail_when_the_sandbox_is_weakened(dirs):
    """Positive controls: each weakening must turn its probe into a fail, otherwise a pass on the real run means nothing."""
    work, checks, canary = dirs
    by_id = {p.id: p for p in escape.probes(canary)}
    mount_at = escape.host_candidates(canary.parent)[1]  # the /host_mnt spelling
    weaker = {
        "host-fs-read": ("-v", f"{canary.parent.resolve()}:{mount_at}:ro"),
        "symlink-escape": ("-v", f"{canary.parent.resolve()}:{mount_at}:ro"),
        "env-no-secrets": ("-e", f"ARGUS_MODEL_API_KEY={escape.FAKE_SECRET}"),
        "fork-bomb": ("--pids-limit", "100000"),
        "host-proc": ("--pid", "host"),
        "mount-syscall": ("--cap-add", "SYS_ADMIN"),
    }
    seen = {}
    for pid, extra in weaker.items():
        seen[pid] = escape.run_probe("docker", by_id[pid], work, checks, None, None, 60, extra)[0]
    assert seen == {pid: "fail" for pid in weaker}, seen
