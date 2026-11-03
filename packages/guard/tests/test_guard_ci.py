"""P7-T17: the three ways the `guard` workflow must go red, shown without Docker and without a model.

1. a probe that escapes -> `guard escape` exits 1 (a stub launcher plays the sandbox and prints ESCAPED),
2. a planted secret -> the secret scan exits 1 (fake token built at run time in a temporary repository),
3. an edited line in the audit log -> `guard verify-log` exits 1 and names the line.
Also: every probe outcome is a record, the committed sample log verifies, and the workflow file parses and uses no secret.
"""

import json
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

from guard import egress, escape
from guard.auditlog import verify
from guard.cli import main

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "guard.yml"
SCAN = ROOT / ".github" / "workflows" / "check_no_secrets.py"
SAMPLE = Path(__file__).parent / "fixtures" / "audit-sample.jsonl"
PLANTED = "ghp_" + "C" * 36  # obviously fake, built at run time so no file of this repo holds a token shape


def _launcher(tmp_path: Path, verdict: str) -> str:
    """A 'sandbox' that prints one verdict line for every probe. Same protocol the Firecracker tier uses."""
    stub = tmp_path / "stub.py"
    stub.write_text(f"print({verdict!r})\n", encoding="utf-8")
    return f"{shlex.quote(Path(sys.executable).as_posix())} {shlex.quote(stub.as_posix())}"


def _suite(tmp_path: Path, verdict: str) -> tuple[int, Path]:
    log = tmp_path / "escape-audit.jsonl"
    code = main(["escape", "--tier", "firecracker", "--launcher", _launcher(tmp_path, verdict), "--audit-log", str(log)])
    return code, log


def test_blocked_probes_exit_0_and_every_probe_is_a_record(tmp_path):
    code, log = _suite(tmp_path, "BLOCKED stub")
    recs = [json.loads(line) for line in log.read_text(encoding="ascii").splitlines()]
    assert code == 0
    assert [r["payload"]["probe"] for r in recs] == [p.id for p in escape.probes(tmp_path / "c.txt")]
    assert {r["kind"] for r in recs} == {"policy_event"} and {r["payload"]["status"] for r in recs} == {"pass"}
    assert verify(log).bad_line is None


def test_a_probe_that_escapes_fails_the_suite_and_the_record_says_so(tmp_path, capsys):
    code, log = _suite(tmp_path, "ESCAPED forced by the test")
    assert code == 1
    assert "FAIL" in capsys.readouterr().out
    recs = [json.loads(line) for line in log.read_text(encoding="ascii").splitlines()]
    assert recs and all(r["payload"]["status"] == "fail" and "forced" in r["payload"]["detail"] for r in recs)
    assert verify(log).bad_line is None  # the log itself is intact; the job still goes red on the suite step


def test_one_probe_escaping_among_blocked_ones_still_fails(tmp_path, monkeypatch):
    real = escape.run_probe
    monkeypatch.setattr(escape, "run_probe", lambda tier, probe, *a, **k: ("fail", "forced") if probe.id == "docker-socket" else real(tier, probe, *a, **k))
    code, log = _suite(tmp_path, "BLOCKED stub")
    assert code == 1
    statuses = {json.loads(line)["payload"]["probe"]: json.loads(line)["payload"]["status"] for line in log.read_text(encoding="ascii").splitlines()}
    assert statuses.pop("docker-socket") == "fail" and set(statuses.values()) == {"pass"}


def test_an_edited_log_fails_verify_log_and_names_the_line(tmp_path, capsys):
    _, log = _suite(tmp_path, "BLOCKED stub")
    assert main(["verify-log", str(log)]) == 0
    lines = log.read_bytes().split(b"\n")
    lines[3] = lines[3].replace(b'"pass"', b'"fail"')  # flip one outcome in the middle
    log.write_bytes(b"\n".join(lines))
    capsys.readouterr()
    assert main(["verify-log", str(log)]) == 1
    assert "BAD line 4" in capsys.readouterr().err


def test_a_planted_secret_fails_the_scan_in_process_and_as_a_command(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_no_secrets", SCAN)
    scan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scan)

    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "notes.md").write_text("nothing here\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    assert scan.main(repo) == 0  # clean temp repo
    assert subprocess.run([sys.executable, str(SCAN), str(repo)], capture_output=True).returncode == 0

    (repo / "notes.md").write_text(f"token: {PLANTED}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    assert scan.main(repo) == 1
    proc = subprocess.run([sys.executable, str(SCAN), str(repo)], capture_output=True, text=True)
    assert proc.returncode == 1
    assert "notes.md:1: ghp_..." in proc.stderr and PLANTED not in proc.stderr + proc.stdout  # the value is never printed


def test_a_workflow_that_names_a_model_secret_fails_the_scan(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "x.yml").write_text("env:\n  K: ${{ secrets.OPENAI_API_KEY }}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    proc = subprocess.run([sys.executable, str(SCAN), str(repo)], capture_output=True, text=True)
    assert proc.returncode == 1 and "x.yml" in proc.stderr


def test_the_committed_sample_log_verifies_even_with_windows_line_endings(tmp_path):
    v = verify(SAMPLE)
    assert (v.bad_line, v.count) == (None, 6)
    crlf = tmp_path / "sample-crlf.jsonl"  # a Windows checkout with autocrlf
    crlf.write_bytes(SAMPLE.read_bytes().replace(b"\n", b"\r\n"))
    assert verify(crlf).bad_line is None
    assert main(["verify-log", str(SAMPLE), "--head", v.head]) == 0
    assert main(["verify-log", str(SAMPLE), "--head", "0" * 64]) == 1


def test_egress_probe_writes_a_record_per_check(tmp_path, monkeypatch):
    monkeypatch.setattr(egress, "_image_present", lambda: True)
    monkeypatch.setattr(egress, "_docker_version", lambda: "test")
    held = {"tcp": "connect-failed", "https": "connect-failed", "dns": "connect-failed"}
    monkeypatch.setattr(egress, "run_sandboxed", lambda: (held, ""))
    log = tmp_path / "egress-audit.jsonl"
    assert egress.main(["--audit-log", str(log)]) == 0
    recs = [json.loads(line)["payload"] for line in log.read_text(encoding="ascii").splitlines()]
    assert [(r["check"], r["held"]) for r in recs] == [("tcp", True), ("https", True), ("dns", True)]
    assert verify(log).bad_line is None


def test_workflow_parses_runs_on_push_pr_and_dispatch_and_uses_no_secret():
    text = WORKFLOW.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    triggers = doc.get("on", doc.get(True))  # YAML 1.1 reads a bare `on` as the boolean True
    assert {"push", "pull_request", "workflow_dispatch"} <= set(triggers)
    assert doc["permissions"] == {"contents": "read"}
    job = doc["jobs"]["guard"]
    assert job["runs-on"] == "ubuntu-latest"
    runs = " ".join(step.get("run", "") for step in job["steps"])
    for needle in ("uv sync --all-packages --locked", "guard escape --tier docker", "--audit-log", "check_no_secrets.py", "verify-log"):
        assert needle in runs, needle
    assert "secrets." not in text.replace("check_no_secrets", "") and "API_KEY" not in text and "OPENAI" not in text  # no secret at all, not even the default token by name
    assert "GITHUB_STEP_SUMMARY" in text and "upload-artifact" in text
    assert verify(SAMPLE).head in text  # the pinned head in the workflow is the sample's real head
    assert "if: always()" in text  # later steps still run when the suite step is red, so the log is kept
