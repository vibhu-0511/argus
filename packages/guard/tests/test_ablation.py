"""P7-T13: `guard ablation`. No Docker needed: the launcher and the escape suite are replaced; the timing code is run on a real
(non-docker) child process."""

import json
from pathlib import Path
import subprocess
import sys

import pytest
from fix_loop import sandbox

from guard import ablation, egress, escape
from guard.cli import main as cli_main

GOOD = "fixture-ok\nchecks-keep=same\nchecks-ro=yes\nkernel=Linux 6.1\n"


def test_percentile_is_nearest_rank():
    v = list(range(1, 31))  # 1..30
    assert ablation.percentile(v, 50) == 15
    assert ablation.percentile(v, 95) == 29
    assert ablation.percentile([7.0], 95) == 7.0
    assert ablation.percentile([3, 1, 2], 50) == 2  # unsorted input


def test_stats_in_ms_and_empty():
    s = ablation.stats([0.1, 0.2, 0.3, 0.4])
    assert s == {"n": 4, "p50": 200.0, "p95": 400.0, "min": 100.0, "max": 400.0}
    assert ablation.stats([]) is None


def test_start_once_times_first_line_before_exit():
    code = "import time; print('fixture-ok', flush=True); time.sleep(0.3)"
    r = ablation.start_once([sys.executable, "-c", code], None, 30)
    assert r["stdout"].startswith("fixture-ok") and r["returncode"] == 0
    assert r["run_s"] >= 0.25 and r["cold_s"] < r["total_s"] - 0.25


def test_start_once_silent_child_is_killed_by_the_timeout():
    r = ablation.start_once([sys.executable, "-c", "import time; time.sleep(30)"], None, 1)
    assert r["cold_s"] is None and r["total_s"] < 10


@pytest.fixture
def fake(monkeypatch):
    """Docker is there; every start prints the good fixture output and writes /work/out.txt; the escape suite is canned."""
    state = {"argv": [], "escape_fail": 0}
    monkeypatch.setattr(escape, "unavailable", lambda tier, runtime, launcher: None)
    monkeypatch.setattr(egress, "_image_present", lambda: True)
    monkeypatch.setattr(egress, "_docker_version", lambda: "0.0-test")
    monkeypatch.setattr(ablation, "leftover_containers", lambda tier: [])

    def fake_start(argv, name, timeout):
        state["argv"].append((argv, name))
        work = next(a for a in argv if a.endswith(":/work")).rsplit(":/work", 1)[0]
        open(work + "/out.txt", "w", encoding="utf-8").write("fixture-ok\n")
        return {"cold_s": 0.5 + 0.01 * len(state["argv"]), "run_s": 0.1, "total_s": 0.7, "returncode": 0, "stdout": GOOD, "stderr": ""}

    monkeypatch.setattr(ablation, "start_once", fake_start)
    monkeypatch.setattr(
        escape, "run_suite",
        lambda tier, runtime, launcher, timeout=60: {
            "probes": [{"id": f"p{i}", "status": "pass" if i >= state["escape_fail"] else "fail"} for i in range(12)],
            "summary": {"pass": 12 - state["escape_fail"], "fail": state["escape_fail"], "error": 0},
        },
    )
    return state


def test_docker_tier_records_n_starts_stats_and_escape(fake, tmp_path):
    out = tmp_path / "a.json"
    assert ablation.main(["--tier", "docker", "--n", "5", "--out", str(out)]) == 0
    r = json.loads(out.read_text(encoding="utf-8"))
    assert (r["tier"], r["variant"], r["status"], r["starts_ok"]) == ("docker", "A", "done", 5)
    assert r["cold_start_ms"]["n"] == 5 and len(r["cold_start_samples_ms"]) == 5
    assert r["escape"]["probes_passed"] == 12 and r["escape"]["probes_total"] == 12
    # own throwaway names, the fix-loop flags, no runtime flag on the docker tier
    assert len({name for _, name in fake["argv"]}) == 5 and all(n.startswith("guard-abl-docker-") for _, n in fake["argv"])
    argv = fake["argv"][0][0]
    assert argv[:5] == ["docker", "run", "--rm", "--name", fake["argv"][0][1]] and "--runtime" not in argv
    assert argv[argv.index("--network") + 1] == "none"


def test_an_escaped_probe_makes_the_run_not_done(fake, tmp_path):
    fake["escape_fail"] = 1
    out = tmp_path / "a.json"
    assert ablation.main(["--tier", "docker", "--n", "2", "--out", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "done_with_problems"


def test_gvisor_tier_passes_the_runtime(fake, tmp_path):
    assert ablation.main(["--tier", "gvisor", "--n", "1", "--out", str(tmp_path / "b.json")]) == 0
    argv = fake["argv"][0][0]
    assert argv[argv.index("--runtime") + 1] == "runsc"


def test_gvisor_without_runtime_is_not_run_and_starts_nothing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(escape, "unavailable", lambda tier, runtime, launcher: "Docker has no runtime 'runsc' registered")
    monkeypatch.setattr(ablation, "start_once", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not start")))
    out = tmp_path / "b.json"
    assert cli_main(["ablation", "--tier", "gvisor", "--out", str(out)]) == 3
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["status"] == "not_run" and r["detail"].startswith("not run: ") and "cold_start_ms" not in r
    assert "not a pass" in capsys.readouterr().out


def test_firecracker_tier_is_not_run_without_kvm(monkeypatch, tmp_path):
    monkeypatch.setattr(ablation.firecracker_run, "unavailable", lambda fc: "/dev/kvm does not exist (no KVM on this host)")
    out = tmp_path / "c.json"
    assert ablation.main(["--tier", "firecracker", "--out", str(out)]) == 3
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["status"] == "not_run" and "/dev/kvm" in r["detail"] and r["variant"] == "C"


def test_failed_start_is_listed_and_not_counted(fake, monkeypatch, tmp_path):
    real = ablation.start_once

    def flaky(argv, name, timeout):
        r = real(argv, name, timeout)
        if len(fake["argv"]) == 2:
            r["returncode"], r["stdout"] = 1, "boom"
        return r

    monkeypatch.setattr(ablation, "start_once", flaky)
    out = tmp_path / "a.json"
    assert ablation.main(["--tier", "docker", "--n", "3", "--out", str(out)]) == 1
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["starts_ok"] == 2 and r["starts_failed"][0]["start"] == 2


def test_microvm_tier_measures_launch_to_exit_and_does_not_claim_probes(monkeypatch, tmp_path):
    monkeypatch.setattr(ablation.firecracker_run, "unavailable", lambda fc: None)
    walls = iter([1.0, 1.2, 1.4])
    monkeypatch.setattr(ablation.firecracker_run, "run_microvm",
                        lambda *a, **k: {"status": "pass", "wall_seconds": next(walls)})
    (tmp_path / "r").write_bytes(b"rootfs")
    fc = {"firecracker": "fc", "kernel": "k", "rootfs": str(tmp_path / "r"), "checks": "c"}
    r = ablation.run_ablation("firecracker", 3, fc)
    assert r["status"] == "done" and r["starts_ok"] == 3 and r["total_ms"]["p50"] == 1200.0
    assert r["cold_start_ms"] is None and "not_run" in r["escape"]


def test_microvm_tier_without_images_is_not_run(monkeypatch):
    monkeypatch.setattr(ablation.firecracker_run, "unavailable", lambda fc: None)
    r = ablation.run_ablation("firecracker", 3, {"firecracker": "fc"})
    assert r["status"] == "not_run" and "--kernel" in r["detail"]


def test_each_microvm_boot_gets_its_own_copy_of_the_rootfs(monkeypatch, tmp_path):
    base = tmp_path / "rootfs.ext4"
    base.write_bytes(b"pristine")
    seen = []

    def fake_boot(fcbin, kernel, rootfs, checks, workdir, timeout):
        seen.append(rootfs)
        assert Path(rootfs).read_bytes() == b"pristine"
        Path(rootfs).write_bytes(b"dirty")  # the guest writes to its root drive
        return {"status": "pass", "wall_seconds": 1.0}

    monkeypatch.setattr(ablation.firecracker_run, "run_microvm", fake_boot)
    r = ablation.measure_microvm(3, {"firecracker": "fc", "kernel": "k", "rootfs": str(base), "checks": "c"})
    assert r["starts_ok"] == 3 and len(set(seen)) == 3 and base.read_bytes() == b"pristine"

