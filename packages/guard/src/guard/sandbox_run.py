"""P7-T10: `guard sandbox-run --runtime runsc|runc`. Runs one small fixture task in the fix-loop sandbox under a Docker runtime and
records what ran: the docker command, the runtime, the runtimes Docker has, `runsc --version`, and the wall time.

It starts the container through `fix_loop.sandbox.run`, the same launcher fix-loop uses, so the flags are the real ones.
State is `pass`, `fail` or `unavailable`. `unavailable` (the runtime is not registered in Docker) is not a pass and the
container is never started on another runtime. Exit code: 0 pass, 1 fail, 3 unavailable.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from fix_loop import sandbox

from guard import egress

EXIT_UNAVAILABLE = 3
# The fixture task: read a check, write a result into /work, prove /checks is read-only, then print what kernel the task saw.
# `dmesg` is evidence only: under gVisor it prints gVisor's own boot lines, under runc it is refused or shows the VM kernel's.
FIXTURE = (
    "echo fixture-ok; echo fixture-ok > /work/out.txt; "
    "echo checks-keep=$(cat /checks/keep.txt); "
    "if echo x > /checks/keep.txt 2>/dev/null; then echo checks-ro=no; else echo checks-ro=yes; fi; "
    "echo kernel=$(uname -sr); dmesg 2>&1 | head -n 3"
)


def runsc_version() -> str | None:
    """`runsc --version` of the binary on this host's PATH, or None. On Docker Desktop the binary lives in its VM, not here."""
    exe = shutil.which("runsc")
    if not exe:
        return None
    try:
        proc = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (proc.stdout or proc.stderr).strip() or None


def judge(proc: subprocess.CompletedProcess[str], host_out: str | None) -> tuple[str, str]:
    if proc.returncode != 0:
        return "fail", f"exit {proc.returncode}: {(proc.stderr or '').strip()[:200]}"
    if "fixture-ok" not in proc.stdout.splitlines():
        return "fail", "the fixture did not print fixture-ok"
    if (host_out or "").strip() != "fixture-ok":
        return "fail", "the result file written in /work did not reach the host folder"
    if "checks-ro=yes" not in proc.stdout.splitlines() or "checks-keep=same" not in proc.stdout.splitlines():
        return "fail", "/checks was not read-only and unchanged"
    return "pass", "fixture ran, result file written, /checks read-only"


def run_fixture(runtime: str) -> dict:
    report: dict = {
        "task": "sandbox-run",
        "runtime": runtime,
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": platform.platform(),
        "docker_server": egress._docker_version(),
        "image": sandbox.IMAGE,
        "runsc_version": runsc_version(),
    }
    try:
        report["docker_runtimes"] = sandbox.docker_runtimes()
        sandbox.check_runtime(runtime)
    except sandbox.RuntimeUnavailable as exc:
        report.update(status="unavailable", detail=f"{exc} The fixture did not run.")
        return report
    if not egress._image_present():
        sandbox.build_image()
    with tempfile.TemporaryDirectory(prefix="guard-sandbox-run-", ignore_cleanup_errors=True) as tmp:
        work, checks = Path(tmp) / "work", Path(tmp) / "checks"
        work.mkdir()
        checks.mkdir()
        (checks / "keep.txt").write_text("same", encoding="utf-8")
        command = ["sh", "-c", FIXTURE]
        # the same function builds the argv that sandbox.run executes; the temp folder is shown as <tmp>
        argv = sandbox.docker_argv(work.resolve(), checks.resolve(), command, runtime)
        report["command"] = [a.replace(str(Path(tmp).resolve()), "<tmp>") for a in argv]
        start = time.perf_counter()
        try:
            proc = sandbox.run(work, checks, command, timeout=120, runtime=runtime)
        except subprocess.TimeoutExpired:
            report.update(status="fail", detail="hard timeout after 120s", wall_seconds=round(time.perf_counter() - start, 3))
            return report
        report["wall_seconds"] = round(time.perf_counter() - start, 3)  # one run, includes container start; T13 repeats it for p50/p95
        out = work / "out.txt"
        status, detail = judge(proc, out.read_text(encoding="utf-8") if out.exists() else None)
    report.update(status=status, detail=detail, stdout=proc.stdout.strip()[:600])
    if runtime == "runsc":
        report["gvisor_marker_in_dmesg"] = "gvisor" in proc.stdout.lower()  # evidence only, not part of the verdict
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="guard sandbox-run", description=__doc__)
    ap.add_argument("--runtime", choices=("runsc", "runc"), required=True)
    ap.add_argument("--out", help="write the result JSON here (for example packages/guard/results/sandbox-run-runsc.json)")
    args = ap.parse_args(argv)

    report = run_fixture(args.runtime)
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    if report["status"] == "unavailable":
        print(f"sandbox-run: runtime {args.runtime} not available here. This is not a pass.", file=sys.stderr)
        return EXIT_UNAVAILABLE
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
