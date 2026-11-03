"""P7-T10: `guard sandbox-run`. No Docker needed: the launcher calls are replaced."""

import json
import subprocess

import pytest
from fix_loop import sandbox

from guard import egress, sandbox_run
from guard.cli import main as cli_main

GOOD = "fixture-ok\nchecks-keep=same\nchecks-ro=yes\nkernel=Linux 6.1\n"


def _proc(stdout=GOOD, code=0, stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


@pytest.fixture
def fake_docker(monkeypatch):
    """Docker has `have` runtimes; sandbox.run records its arguments and writes the result file the way the fixture would."""
    state = {"have": ["runc", "io.containerd.runc.v2"], "runs": [], "stdout": GOOD, "out": "fixture-ok\n"}
    monkeypatch.setattr(egress, "_docker_version", lambda: "0.0-test")
    monkeypatch.setattr(egress, "_image_present", lambda: True)
    monkeypatch.setattr(sandbox, "docker_runtimes", lambda: state["have"])

    def fake_run(work, checks, command, *, timeout=30, runtime=None):
        state["runs"].append((command, runtime))
        if state["out"] is not None:
            (work / "out.txt").write_text(state["out"], encoding="utf-8")
        return _proc(state["stdout"])

    monkeypatch.setattr(sandbox, "run", fake_run)
    monkeypatch.setattr(sandbox_run, "runsc_version", lambda: None)
    return state


def test_runc_pass_records_command_runtime_and_wall_time(fake_docker, tmp_path):
    out = tmp_path / "r.json"
    assert sandbox_run.main(["--runtime", "runc", "--out", str(out)]) == 0
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["status"] == "pass" and r["runtime"] == "runc" and r["docker_runtimes"] == ["runc", "io.containerd.runc.v2"]
    assert r["command"][:5] == ["docker", "run", "--rm", "--runtime", "runc"] and r["wall_seconds"] >= 0
    assert "--network" in r["command"] and "none" in r["command"]
    assert not any("guard-sandbox-run-" in a and "<tmp>" not in a for a in r["command"])
    assert fake_docker["runs"][0][1] == "runc"


def test_runsc_not_registered_is_unavailable_not_a_pass_and_never_runs(fake_docker, tmp_path, capsys):
    out = tmp_path / "r.json"
    assert sandbox_run.main(["--runtime", "runsc", "--out", str(out)]) == sandbox_run.EXIT_UNAVAILABLE
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["status"] == "unavailable" and "no runtime 'runsc'" in r["detail"] and "did not run" in r["detail"]
    assert "command" not in r and fake_docker["runs"] == []
    assert "not a pass" in capsys.readouterr().err


def test_runsc_registered_runs_with_the_runsc_runtime(fake_docker):
    fake_docker["have"] = ["runc", "runsc"]
    fake_docker["stdout"] = GOOD + "[    0.000000] Starting gVisor...\n"
    r = sandbox_run.run_fixture("runsc")
    assert r["status"] == "pass" and fake_docker["runs"][0][1] == "runsc" and r["gvisor_marker_in_dmesg"] is True


@pytest.mark.parametrize(
    "stdout,out_file",
    [("fixture-ok\nchecks-keep=same\nchecks-ro=no\n", "fixture-ok\n"), (GOOD, None), ("nothing\n", "fixture-ok\n")],
)
def test_broken_fixture_is_a_fail(fake_docker, stdout, out_file):
    fake_docker["stdout"], fake_docker["out"] = stdout, out_file
    assert sandbox_run.run_fixture("runc")["status"] == "fail"


def test_cli_registers_sandbox_run(fake_docker):
    assert cli_main(["sandbox-run", "--runtime", "runsc"]) == sandbox_run.EXIT_UNAVAILABLE
