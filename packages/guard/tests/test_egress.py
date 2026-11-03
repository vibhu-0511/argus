import subprocess

import pytest

from guard import egress


def test_check_script_covers_every_check_and_tool_guard():
    script = egress.check_script()
    for name, (tool, _) in egress.CHECKS.items():
        assert f"echo {name}=reached" in script
        assert f"echo {name}=connect-failed" in script
        assert f"command -v {tool}" in script and f"echo {name}=tool-missing" in script


def test_parse_marks_missing_output():
    got = egress.parse("tcp=connect-failed\nhttps=reached\nnoise\n")
    assert got == {"tcp": "connect-failed", "https": "reached", "dns": "no-output"}


def test_main_exit_code_follows_the_policy(monkeypatch, tmp_path):
    monkeypatch.setattr(egress, "_image_present", lambda: True)
    monkeypatch.setattr(egress, "_docker_version", lambda: "test")
    held = {"tcp": "connect-failed", "https": "connect-failed", "dns": "connect-failed"}
    monkeypatch.setattr(egress, "run_sandboxed", lambda: (held, ""))
    out = tmp_path / "r.json"
    assert egress.main(["--out", str(out)]) == 0
    assert '"no_egress_held": true' in out.read_text(encoding="utf-8")
    monkeypatch.setattr(egress, "run_sandboxed", lambda: (dict(held, dns="reached"), ""))
    assert egress.main([]) == 1
    # a check that did not run (tool missing) is not a pass
    monkeypatch.setattr(egress, "run_sandboxed", lambda: (dict(held, tcp="tool-missing"), ""))
    assert egress.main([]) == 1


def _docker_up() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.mark.docker
@pytest.mark.skipif(not _docker_up(), reason="Docker is not running")
def test_sandbox_has_no_egress_for_real():
    if not egress._image_present():
        egress.sandbox.build_image()
    results, _ = egress.run_sandboxed()
    assert results == {"tcp": "connect-failed", "https": "connect-failed", "dns": "connect-failed"}
