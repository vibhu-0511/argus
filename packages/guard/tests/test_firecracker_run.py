"""P7-T11: `guard firecracker-run`. No KVM, no Firecracker and no Docker needed: the config, the init script, the judge and the
'tier not available' path are tested; the boot itself is not (it needs a KVM host, see docs/notes/p7-t11.md)."""

import json

from guard import firecracker_run as fc
from guard.cli import main as cli_main
from guard.sandbox_run import FIXTURE

GOOD = "boot noise\r\n" + fc.BEGIN + "\r\nfixture-ok\r\nchecks-keep=same\r\nchecks-ro=yes\r\nkernel=Linux 6.18\r\nwork-out=fixture-ok\r\n" + fc.END + "\r\n"


def test_config_has_boot_source_two_drives_and_no_network():
    cfg = fc.build_config("vmlinux", "root.ext4", "checks.ext4")
    assert cfg["boot-source"] == {"kernel_image_path": "vmlinux", "boot_args": "console=ttyS0 reboot=k panic=1 init=/fixture-init"}
    root, checks = cfg["drives"]
    assert (root["drive_id"], root["is_root_device"], root["is_read_only"]) == ("rootfs", True, False)
    assert (checks["drive_id"], checks["is_root_device"], checks["is_read_only"]) == ("checks", False, True)
    assert cfg["machine-config"] == {"vcpu_count": 1, "mem_size_mib": 512}
    assert "network-interfaces" not in cfg
    json.dumps(cfg)


def test_init_script_runs_the_same_fixture_between_markers():
    s = fc.init_script()
    assert s.startswith("#!/bin/sh\n") and FIXTURE in s
    assert s.index(fc.BEGIN) < s.index(FIXTURE) < s.index(fc.END)
    assert "mount -t ext4 -o ro /dev/vdb /checks" in s and "reboot -f" in s


def test_judge_pass_and_each_failure():
    assert fc.judge(GOOD)[0] == "pass"
    assert fc.judge("kernel panic")[0] == "fail"
    assert fc.judge(GOOD.replace("checks-ro=yes", "checks-ro=no"))[0] == "fail"
    assert "checks-ro=yes" in fc.judge(GOOD.replace("checks-ro=yes", "checks-ro=no"))[1]
    assert "no end marker" in fc.judge(GOOD.replace(fc.END, ""))[1]


def test_unavailable_without_kvm_or_binary(monkeypatch):
    monkeypatch.setattr(fc.os.path, "exists", lambda p: False)
    assert "does not exist" in fc.unavailable("firecracker")
    monkeypatch.setattr(fc.os.path, "exists", lambda p: True)
    monkeypatch.setattr(fc.os, "access", lambda p, m: True)
    monkeypatch.setattr(fc.shutil, "which", lambda b: None)
    assert "binary was not found" in fc.unavailable("no-such-firecracker")
    monkeypatch.setattr(fc.shutil, "which", lambda b: "/usr/bin/firecracker")
    assert fc.unavailable("firecracker") is None


def test_cli_without_kvm_is_exit_3_and_never_boots(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(fc.os.path, "exists", lambda p: False)
    monkeypatch.setattr(fc, "run_microvm", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not boot")))
    out = tmp_path / "r.json"
    assert cli_main(["firecracker-run", "--out", str(out)]) == 3
    assert "tier not available" in capsys.readouterr().out
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "unavailable" and report["kvm_present"] is False


def test_print_init_needs_no_kvm(capsys):
    assert cli_main(["firecracker-run", "--print-init"]) == 0
    assert capsys.readouterr().out == fc.init_script()
