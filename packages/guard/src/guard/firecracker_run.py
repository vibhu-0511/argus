"""P7-T11: `guard firecracker-run`. Boots the fixture task in a Firecracker microVM and records what the guest printed.

The config and the guest init script are built by pure functions (tested without KVM). The boot itself needs `/dev/kvm` and the
`firecracker` binary; when either is missing the command prints "tier not available" and exits 3. That is never a pass.
The guest has no network device at all (the microVM equivalent of `--network none`), 1 vCPU and 512 MiB (the fix-loop sandbox
limits). The fixture command is the one `guard sandbox-run` uses, so the two tiers run the same task.

Flow (the workflow `.github/workflows/firecracker.yml` does the host steps): the init script from `--print-init` is put into the
guest rootfs as `/fixture-init`; the kernel boots with `init=/fixture-init`; the script mounts the read-only checks drive on
/checks, runs the fixture, prints it between two marker lines on the serial console, and powers the guest off. Firecracker's
stdout is that console. Exit code: 0 pass, 1 fail, 3 tier not available.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from guard.sandbox_run import FIXTURE

EXIT_UNAVAILABLE = 3
KVM = "/dev/kvm"
BEGIN, END = "GUARD-FIRECRACKER-BEGIN", "GUARD-FIRECRACKER-END"
# boot args from the Firecracker quickstart (docs/getting-started.md); `init=` makes the kernel run the fixture script as pid 1
BOOT_ARGS = "console=ttyS0 reboot=k panic=1 init=/fixture-init"
VCPUS, MEM_MIB = 1, 512  # same as fix_loop.sandbox CPUS and MEMORY


def init_script(fixture: str = FIXTURE) -> str:
    """Shell script the guest kernel runs as pid 1. The checks drive is the second block device (/dev/vdb), mounted read-only."""
    return (
        "#!/bin/sh\n"
        "mount -t proc proc /proc; mount -t sysfs sys /sys; mount -t devtmpfs dev /dev 2>/dev/null\n"
        "mkdir -p /work /checks; mount -t ext4 -o ro /dev/vdb /checks\n"
        f"cd /work; echo {BEGIN}\n"
        f"{fixture}\n"
        "echo work-out=$(cat /work/out.txt)\n"
        f"echo {END}\n"
        "sync; reboot -f; echo b > /proc/sysrq-trigger\n"
    )


def build_config(kernel: str, rootfs: str, checks: str) -> dict:
    """The `--config-file` JSON (field names as in Firecracker's tests/framework/vm_config.json). No network interface."""
    return {
        "boot-source": {"kernel_image_path": kernel, "boot_args": BOOT_ARGS},
        "drives": [
            {"drive_id": "rootfs", "path_on_host": rootfs, "is_root_device": True, "is_read_only": False},
            {"drive_id": "checks", "path_on_host": checks, "is_root_device": False, "is_read_only": True},
        ],
        "machine-config": {"vcpu_count": VCPUS, "mem_size_mib": MEM_MIB},
    }


def unavailable(firecracker: str | None) -> str | None:
    """None when a microVM can start here, else the reason."""
    if not os.path.exists(KVM):
        return f"{KVM} does not exist (no KVM on this host)"
    if not (os.access(KVM, os.R_OK) and os.access(KVM, os.W_OK)):
        return f"{KVM} exists but this user cannot read and write it"
    if not firecracker or not (shutil.which(firecracker) or os.path.isfile(firecracker)):
        return "the firecracker binary was not found (--firecracker or PATH)"
    return None


def guest_lines(console: str) -> tuple[list[str], bool]:
    """(the fixture's lines, whether the end marker was seen): what the guest printed between the two markers."""
    lines = [ln.strip() for ln in console.replace("\r", "").splitlines()]
    if BEGIN not in lines:
        return [], False
    inner = lines[lines.index(BEGIN) + 1:]
    return (inner[:inner.index(END)], True) if END in inner else (inner, False)


def judge(console: str) -> tuple[str, str]:
    lines, finished = guest_lines(console)
    if not lines:
        return "fail", "no fixture output between the markers (the guest did not reach the fixture)"
    if not finished:
        return "fail", "the fixture did not finish (no end marker)"
    need = ("fixture-ok", "checks-keep=same", "checks-ro=yes", "work-out=fixture-ok")
    missing = [n for n in need if n not in lines]
    return ("fail", "missing in the guest output: " + ", ".join(missing)) if missing else ("pass", "fixture ran in the microVM, /checks read-only")


def firecracker_version(firecracker: str) -> str | None:
    try:
        proc = subprocess.run([firecracker, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (proc.stdout or proc.stderr).strip().splitlines()[0] if (proc.stdout or proc.stderr).strip() else None


def run_microvm(firecracker: str, kernel: str, rootfs: str, checks: str, workdir: Path, timeout: int) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    cfg = workdir / "vm-config.json"
    cfg.write_text(json.dumps(build_config(kernel, rootfs, checks), indent=2) + "\n", encoding="utf-8")
    cmd = [firecracker, "--api-sock", str(workdir / "firecracker.socket"), "--config-file", str(cfg)]
    report: dict = {"command": cmd, "config": build_config(kernel, rootfs, checks), "firecracker_version": firecracker_version(firecracker)}
    start = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        report.update(status="fail", detail=f"hard timeout after {timeout}s", console=out[-2000:])
        return report
    report["wall_seconds"] = round(time.perf_counter() - start, 3)  # one boot plus the fixture, not a p50
    status, detail = judge(proc.stdout)
    report.update(status=status, detail=detail, exit_code=proc.returncode, console=proc.stdout[-2000:], stderr=proc.stderr.strip()[-400:])
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="guard firecracker-run", description=__doc__)
    ap.add_argument("--print-init", action="store_true", help="print the guest init script and exit (the workflow writes it into the rootfs)")
    ap.add_argument("--kernel", help="uncompressed guest kernel (vmlinux)")
    ap.add_argument("--rootfs", help="ext4 rootfs that holds /fixture-init")
    ap.add_argument("--checks", help="ext4 image with keep.txt containing 'same'; attached read-only")
    ap.add_argument("--firecracker", default="firecracker", help="firecracker binary (default: from PATH)")
    ap.add_argument("--workdir", default="firecracker-run", help="folder for the config file and the API socket")
    ap.add_argument("--timeout", type=int, default=120, help="hard timeout for the boot plus fixture, seconds")
    ap.add_argument("--out", help="write the result JSON here")
    args = ap.parse_args(argv)

    if args.print_init:
        sys.stdout.write(init_script())
        return 0
    report: dict = {
        "task": "firecracker-run", "tier": "firecracker", "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": platform.platform(), "kvm_present": os.path.exists(KVM),
    }
    why = unavailable(args.firecracker)
    if why:
        report.update(status="unavailable", detail=f"{why}. The microVM did not boot.")
        print(f"firecracker-run: tier not available here: {why}\nNo microVM booted. This is not a pass.")
    elif not (args.kernel and args.rootfs and args.checks):
        ap.error("--kernel, --rootfs and --checks are required to boot")
    else:
        report.update(run_microvm(args.firecracker, args.kernel, args.rootfs, args.checks, Path(args.workdir), args.timeout))
        print(json.dumps(report, indent=2))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return EXIT_UNAVAILABLE if report["status"] == "unavailable" else 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
