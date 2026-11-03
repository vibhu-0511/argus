"""P7-T21: DNS exfiltration from the sandbox. The lookup fails and the attempt (with the names asked for) is in the audit log.

Names are reserved test names (.invalid, RFC 2606). The fake canary and fake secret are obviously fake. Docker tests skip when the daemon is down.
"""

import json
import shlex
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from guard import escape
from guard.auditlog import verify
from guard.cli import main

CANARY_NAME = "CANARY-NOT-A-SECRET.exfil.invalid"


def _docker_up() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _probe(pid: str):
    return {p.id: p for p in escape.probes(Path("/nonexistent/canary.txt"))}[pid]


def test_the_probe_asks_for_reserved_names_that_carry_a_fake_canary_and_a_fake_secret():
    names = _probe("dns-exfil").queries
    assert CANARY_NAME in names
    assert all(n.endswith("exfil.invalid") for n in names)  # .invalid never resolves anywhere
    assert any(n.startswith(escape.FAKE_SECRET.encode().hex()) for n in names)  # the secret, hex-encoded in a label
    assert all(len(label) <= 63 for n in names for label in n.split("."))  # a legal DNS name, so a refusal is not a syntax error
    script = _probe("dns-exfil").script
    assert all(n in script for n in names) and "ESCAPED" in script and "BLOCKED" in script


def test_the_attempt_and_the_names_queried_are_in_the_audit_log(tmp_path, capsys):
    stub = tmp_path / "stub.py"
    stub.write_text("print('BLOCKED stub')\n", encoding="utf-8")
    log = tmp_path / "audit.jsonl"
    launcher = f"{shlex.quote(Path(sys.executable).as_posix())} {shlex.quote(stub.as_posix())}"
    assert main(["escape", "--tier", "firecracker", "--launcher", launcher, "--audit-log", str(log)]) == 0
    rec = next(r for r in map(json.loads, log.read_text(encoding="ascii").splitlines()) if r["payload"]["probe"] == "dns-exfil")
    assert rec["kind"] == "policy_event" and CANARY_NAME in rec["payload"]["queries"]
    assert main(["verify-log", str(log)]) == 0


@pytest.mark.docker
@pytest.mark.skipif(not _docker_up(), reason="Docker is not running")
def test_in_the_real_sandbox_the_lookup_fails_and_is_recorded(tmp_path):
    log = tmp_path / "audit.jsonl"
    assert main(["escape", "--tier", "docker", "--audit-log", str(log)]) == 0
    recs = {r["payload"]["probe"]: r["payload"] for r in map(json.loads, log.read_text(encoding="ascii").splitlines())}
    assert recs["dns-exfil"]["status"] == "pass" and CANARY_NAME in recs["dns-exfil"]["queries"]
    assert recs["no-net-route"]["status"] == "pass"
    assert verify(log).bad_line is None


@pytest.mark.docker
@pytest.mark.skipif(not _docker_up(), reason="Docker is not running")
@pytest.mark.parametrize("pid", ["dns-exfil", "no-net-route"])
def test_positive_control_the_probe_fails_when_the_container_has_a_network(pid):
    """Same script, same image, Docker's default bridge instead of `--network none`. Without this a pass proves nothing."""
    if not escape.egress._image_present():
        escape.sandbox.build_image()
    name = f"guard-t21-ctl-{uuid.uuid4().hex[:8]}"
    try:
        proc = subprocess.run(["docker", "run", "--rm", "--name", name, escape.sandbox.IMAGE, "sh", "-c", _probe(pid).script],
                              capture_output=True, text=True, timeout=90)
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    status, detail = escape.judge(proc.stdout, proc.returncode)
    if pid == "dns-exfil" and status == "pass":
        pytest.skip(f"this machine's resolver is unreachable even with a network, so the control cannot see an answer: {detail}")
    assert status == "fail", (status, detail)
