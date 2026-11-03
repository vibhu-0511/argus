"""P7-T13: `guard ablation --tier docker|gvisor|firecracker`. Measures one sandbox tier and writes
`packages/guard/results/ablation-<tier>.json`.

For the tier it (1) starts the fixture container N times and records each cold start, (2) runs the escape suite and records the
probes passed, (3) records how long the fixture takes after it has started. Every container has its own throwaway name
(`guard-abl-<tier>-...`) and is removed; no other container is touched.

Definitions, so the numbers are not misread:
- cold start = time from the moment `docker run` is launched until the first line the fixture prints (`fixture-ok`). It includes
  the Docker CLI, the daemon, the bind mounts and, on Docker Desktop, the VM boundary.
- fixture run = time from that first line until the container has exited and been removed (`--rm`).
- p50 and p95 use the nearest-rank method over the N samples. N is small: the p95 of 30 samples is the 29th value.
A tier that cannot run here is written as `status: not_run` with the reason and exit code 3. It is never a pass and has no numbers.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fix_loop import sandbox

from guard import egress, escape, firecracker_run
from guard.sandbox_run import FIXTURE, judge

EXIT_NOT_RUN = 3
VARIANT = {"docker": "A", "gvisor": "B", "firecracker": "C"}
RUNTIME = {"docker": None, "gvisor": "runsc"}


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile (p in 0..100) of a non-empty list."""
    ordered = sorted(values)
    return ordered[max(math.ceil(p / 100 * len(ordered)), 1) - 1]


def stats(values_s: list[float]) -> dict | None:
    """n, p50, p95, min and max in milliseconds, or None when there are no samples."""
    if not values_s:
        return None
    ms = [v * 1000 for v in values_s]
    return {"n": len(ms), "p50": round(percentile(ms, 50), 1), "p95": round(percentile(ms, 95), 1), "min": round(min(ms), 1), "max": round(max(ms), 1)}


def start_once(argv: list[str], name: str | None, timeout: int) -> dict:
    """Launch argv, time it to the first stdout line and to exit. `name` is a docker container to force-remove afterwards."""
    t0 = time.perf_counter()
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    timer = threading.Timer(timeout, proc.kill)  # a container that never prints must not block the run
    timer.start()
    try:
        first = proc.stdout.readline()
        t1 = time.perf_counter()
        rest, err = proc.communicate()
        t2 = time.perf_counter()
    finally:
        timer.cancel()
        if name:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    return {
        "cold_s": (t1 - t0) if first else None, "run_s": (t2 - t1) if first else None, "total_s": t2 - t0,
        "returncode": proc.returncode, "stdout": first + rest, "stderr": err,
    }


def measure_starts(tier: str, n: int, timeout: int = 120) -> dict:
    """N fresh containers with the fix-loop sandbox flags, each judged by the same check as `guard sandbox-run`."""
    runtime = RUNTIME[tier]
    cold, run, total, failures = [], [], [], []
    with tempfile.TemporaryDirectory(prefix="guard-ablation-", ignore_cleanup_errors=True) as tmp:
        for i in range(n):
            work, checks = Path(tmp) / f"work{i}", Path(tmp) / f"checks{i}"
            work.mkdir()
            checks.mkdir()
            (checks / "keep.txt").write_text("same", encoding="utf-8")
            name = f"guard-abl-{tier}-{uuid.uuid4().hex[:8]}"
            argv = sandbox.docker_argv(work.resolve(), checks.resolve(), ["sh", "-c", FIXTURE], runtime)
            argv = [*argv[:3], "--name", name, *argv[3:]]  # after `docker run --rm`
            r = start_once(argv, name, timeout)
            out = work / "out.txt"
            status, detail = judge(subprocess.CompletedProcess(argv, r["returncode"], r["stdout"], r["stderr"]),
                                   out.read_text(encoding="utf-8") if out.exists() else None)
            if status == "pass" and r["cold_s"] is not None:
                cold.append(r["cold_s"])
                run.append(r["run_s"])
                total.append(r["total_s"])
            else:
                failures.append({"start": i + 1, "detail": detail})
    return {
        "starts_requested": n, "starts_ok": len(cold), "starts_failed": failures,
        "cold_start_ms": stats(cold), "fixture_run_ms": stats(run), "total_ms": stats(total),
        "cold_start_samples_ms": [round(c * 1000, 1) for c in cold],
    }


def leftover_containers(tier: str) -> list[str]:
    proc = subprocess.run(["docker", "ps", "-a", "--filter", f"name=guard-abl-{tier}-", "--format", "{{.Names}}"], capture_output=True, text=True)
    return proc.stdout.split()


def not_run_reason(tier: str) -> str | None:
    """None when this tier can be measured here, else the reason."""
    if tier == "firecracker":
        why = firecracker_run.unavailable("firecracker")
        return (why or "no cold-start harness for the microVM tier exists; it has to be written and run on a KVM host") + \
               ". The microVM tier is built in P7-T11 and has never booted"
    return escape.unavailable(tier, RUNTIME[tier], None)


def run_ablation(tier: str, n: int) -> dict:
    report: dict = {
        "suite": "ablation", "tier": tier, "variant": VARIANT[tier], "runtime": RUNTIME.get(tier) or ("microVM" if tier == "firecracker" else "default"),
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "host": platform.platform(),
        "image": sandbox.IMAGE, "n_requested": n,
    }
    why = not_run_reason(tier)
    if why:
        report.update(status="not_run", detail=f"not run: {why}")
        return report
    if not egress._image_present():
        sandbox.build_image()
    report["docker_server"] = egress._docker_version()
    report["flags"] = {"network": "none", "cpus": sandbox.CPUS, "memory": sandbox.MEMORY, "checks": "ro", "fixture": "guard.sandbox_run.FIXTURE"}
    report["definitions"] = {
        "cold_start": "docker run launched -> first line printed by the fixture",
        "fixture_run": "first line printed -> container exited and removed (--rm)",
        "percentile": "nearest-rank over the samples",
    }
    report.update(measure_starts(tier, n))
    suite = escape.run_suite(tier, RUNTIME[tier], None)
    report["escape"] = {
        "probes_passed": suite["summary"]["pass"], "probes_total": len(suite["probes"]), "summary": suite["summary"],
        "probes": [{"id": p["id"], "status": p["status"]} for p in suite["probes"]],
    }
    report["leftover_containers"] = leftover_containers(tier)
    ok = report["starts_ok"] == n and suite["summary"]["fail"] == 0 and suite["summary"]["error"] == 0 and not report["leftover_containers"]
    report.update(status="done" if ok else "done_with_problems")
    return report


def format_report(r: dict) -> str:
    if r["status"] == "not_run":
        return f"ablation: tier={r['tier']} (variant {r['variant']})\n{r['detail']}\nNo number was measured. This is not a pass."
    c, f, e = r["cold_start_ms"], r["fixture_run_ms"], r["escape"]
    lines = [f"ablation: tier={r['tier']} (variant {r['variant']}) status={r['status']}"]
    lines.append(f"starts: {r['starts_ok']} ok of {r['starts_requested']}")
    if c:
        lines.append(f"cold start ms: p50 {c['p50']}  p95 {c['p95']}  min {c['min']}  max {c['max']}")
        lines.append(f"fixture run ms: p50 {f['p50']}  p95 {f['p95']}")
    lines.append(f"escape probes: {e['probes_passed']} of {e['probes_total']} passed")
    lines.append(f"leftover containers: {r['leftover_containers'] or 'none'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="guard ablation", description=__doc__)
    ap.add_argument("--tier", choices=tuple(VARIANT), required=True)
    ap.add_argument("--n", type=int, default=30, help="how many times to start the container (default 30)")
    ap.add_argument("--out", help="result JSON (default packages/guard/results/ablation-<tier>.json)")
    args = ap.parse_args(argv)

    report = run_ablation(args.tier, args.n)
    print(format_report(report))
    out = Path(args.out or f"packages/guard/results/ablation-{args.tier}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if report["status"] == "not_run":
        return EXIT_NOT_RUN
    return 0 if report["status"] == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
