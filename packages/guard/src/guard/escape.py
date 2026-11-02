"""P7-T12: the escape-test suite. `guard escape --tier docker|gvisor|firecracker`.

Every probe is a shell script run inside a sandbox. It prints one line: `BLOCKED <why>` (pass), `ESCAPED <what>` (fail) or
`ERROR <why>` (could not tell). A probe passes only when it printed BLOCKED. A tier that cannot run here prints
"tier not available here" and exits 3; it never reports a pass.

Containers are started with the fix-loop sandbox flags (`fix_loop.sandbox`: image, --network none, CPUS, MEMORY, work rw, checks ro)
plus `--pids-limit`, which the fix-loop sandbox does not set today. The suite adds it so the fork probe cannot hurt the host.
The only host paths mounted are two folders inside one throwaway temp dir. The docker socket is never mounted.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fix_loop import sandbox

from guard import egress

PIDS_LIMIT = 128
FORK_COUNT = 300  # bounded on purpose: even with no cap the loop stops here, so it cannot take the host down
FAKE_SECRET = "guard-fake-secret-not-real"
CANARY_TOKEN = "GUARD-CANARY-" + uuid.uuid4().hex
EXIT_UNAVAILABLE = 3
TIERS = ("docker", "gvisor", "firecracker")


@dataclass(frozen=True)
class Probe:
    id: str
    what: str
    script: str
    expected: str = "blocked"


def host_candidates(path: Path) -> list[str]:
    """Where a container could find a host path if the host filesystem leaked in (Docker Desktop and Linux spellings)."""
    s = str(path)
    if len(s) > 1 and s[1] == ":":
        d, rest = s[0].lower(), s[2:].replace("\\", "/")
        return [s.replace("\\", "/"), f"/host_mnt/{d}{rest}", f"/run/desktop/mnt/host/{d}{rest}", f"/mnt/host/{d}{rest}", f"/mnt/{d}{rest}", f"/{d}{rest}"]
    return [s, f"/host_mnt{s}", f"/rootfs{s}", f"/mnt/host{s}"]


def _net(name: str) -> str:
    tool, cmd = egress.CHECKS[name]
    return (
        f'command -v {tool} >/dev/null 2>&1 || {{ echo "ERROR {tool} missing, cannot tell"; exit 0; }}; '
        f'if {cmd} >/dev/null 2>&1; then echo "ESCAPED {name} reached the outside"; else echo "BLOCKED {name} could not connect"; fi'
    )


def probes(canary_file: Path) -> list[Probe]:
    """The probe table. `canary_file` is a host file that is NOT mounted; the probes look for its token."""
    files = [shlex.quote(p) for p in host_candidates(canary_file)]
    dirs = [shlex.quote(p) for p in host_candidates(canary_file.parent)]
    meta = "wget -q -T 3 -O /dev/null http://169.254.169.254/latest/meta-data/"
    return [
        Probe("network-tcp", "TCP connect to an external IP", _net("tcp")),
        Probe("network-https", "HTTPS request to an external IP", _net("https")),
        Probe("dns-lookup", "DNS lookup of an external name", _net("dns")),
        Probe(
            "metadata-address", "HTTP to the cloud metadata address 169.254.169.254",
            f'command -v wget >/dev/null 2>&1 || {{ echo "ERROR wget missing, cannot tell"; exit 0; }}; '
            f'if {meta} >/dev/null 2>&1; then echo "ESCAPED metadata address answered"; else echo "BLOCKED metadata address unreachable"; fi',
        ),
        Probe(
            "host-fs-read", "read a host file outside the mounts, by its host path and the usual host-mount spellings",
            f'for p in {" ".join(files)}; do if [ -r "$p" ] && grep -q {CANARY_TOKEN} "$p" 2>/dev/null; then echo "ESCAPED read host file at $p"; exit 0; fi; done; '
            f'echo "BLOCKED host file not readable at {len(files)} paths"',
        ),
        Probe(
            "readonly-mount-write", "write, create and delete in the read-only /checks mount",
            'if echo changed > /checks/keep.txt 2>/dev/null || touch /checks/new.txt 2>/dev/null || rm /checks/keep.txt 2>/dev/null; '
            'then echo "ESCAPED wrote to /checks"; elif [ "$(cat /checks/keep.txt)" = same ] && [ ! -e /checks/new.txt ]; '
            'then echo "BLOCKED /checks is read-only and unchanged"; else echo "ERROR /checks is not in the expected state"; fi',
        ),
        Probe(
            "docker-socket", "docker socket reachable inside the container",
            'for s in /var/run/docker.sock /run/docker.sock /docker.sock; do if [ -S "$s" ]; then echo "ESCAPED socket at $s"; exit 0; fi; done; '
            'echo "BLOCKED no docker socket"',
        ),
        Probe(
            "fork-bomb", f"bounded fork loop ({FORK_COUNT} processes) against a pids limit of {PIDS_LIMIT}",
            # busybox sh exits when a background fork fails, so the loop runs in a subshell; the count uses a glob, not `ls | grep`, because a full pid table cannot fork either
            f'( i=0; while [ $i -lt {FORK_COUNT} ]; do sleep 25 & i=$((i+1)); done ) 2>/dev/null; '
            f"set -- /proc/[0-9]*; n=$#; "
            f'if [ "$n" -le {PIDS_LIMIT} ]; then echo "BLOCKED fork stopped at $n processes"; else echo "ESCAPED $n processes alive, no cap"; fi',
        ),
        Probe(
            "symlink-escape", "symlink in the rw mount pointing at the host folder, then read through it",
            f'i=0; for d in {" ".join(dirs)}; do i=$((i+1)); '
            f'ln -s "$d" /work/hostlink$i 2>/dev/null || {{ echo "ERROR cannot create a symlink in /work"; exit 0; }}; '
            f'if grep -q {CANARY_TOKEN} /work/hostlink$i/{shlex.quote(canary_file.name)} 2>/dev/null; then echo "ESCAPED read host file through symlink to $d"; exit 0; fi; done; '
            f'echo "BLOCKED $i symlinks to the host folder lead nowhere"',
        ),
        Probe(
            "env-no-secrets", "environment of the process holds no secret (the launcher had a fake key set)",
            f'if env | grep -q {FAKE_SECRET}; then echo "ESCAPED fake secret value in env"; '
            f'elif env | grep -Eiq "^[A-Za-z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)[A-Za-z0-9_]*="; then echo "ESCAPED secret-named variable in env"; '
            f'else echo "BLOCKED no secret in env"; fi',
        ),
        Probe(
            "host-proc", "see host processes through /proc (own pid namespace expected)",
            "n=$(ls /proc | grep -c '^[0-9][0-9]*$'); first=$(tr '\\0' ' ' < /proc/1/cmdline); "
            'case "$first" in "sh -c"*) if [ "$n" -le 20 ]; then echo "BLOCKED own pid namespace, $n processes, pid 1 is the probe shell"; '
            'else echo "ESCAPED $n processes visible"; fi;; *) echo "ESCAPED pid 1 is: $first";; esac',
        ),
        Probe(
            "mount-syscall", "mount a filesystem (needs CAP_SYS_ADMIN)",
            'mkdir -p /mnt/t; if mount -t tmpfs none /mnt/t 2>/dev/null; then echo "ESCAPED mount succeeded"; else echo "BLOCKED mount refused"; fi',
        ),
    ]


def judge(stdout: str, returncode: int) -> tuple[str, str]:
    """(status, detail). Only a printed BLOCKED is a pass; no verdict line is an error."""
    for line in stdout.splitlines():
        word, _, detail = line.strip().partition(" ")
        if word == "BLOCKED":
            return "pass", detail
        if word == "ESCAPED":
            return "fail", detail
        if word == "ERROR":
            return "error", detail
    return "error", f"no verdict line (exit {returncode})"


def docker_argv(name: str, work: Path, checks: Path, script: str, runtime: str | None = None, extra: tuple[str, ...] = ()) -> list[str]:
    argv = ["docker", "run", "--rm", "--name", name]
    if runtime:
        argv += ["--runtime", runtime]
    argv += [
        "--network", "none", "--cpus", sandbox.CPUS, "--memory", sandbox.MEMORY, "--pids-limit", str(PIDS_LIMIT),
        "-v", f"{work.resolve()}:/work", "-v", f"{checks.resolve()}:/checks:ro", "-w", "/work", *extra,
        sandbox.IMAGE, "sh", "-c", script,
    ]
    return argv


def _docker_info(fmt: str) -> str | None:
    try:
        proc = subprocess.run(["docker", "info", "--format", fmt], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def unavailable(tier: str, runtime: str | None, launcher: str | None) -> str | None:
    """None when the tier can run here, else the reason."""
    if tier == "firecracker":
        if not launcher:
            return "no launcher set (--launcher or ARGUS_FIRECRACKER_LAUNCHER); the Firecracker launcher is built in P7-T11"
        return None
    if _docker_info("{{.ServerVersion}}") is None:
        return "the Docker daemon is not reachable"
    if tier == "gvisor":
        runtimes = _docker_info("{{json .Runtimes}}") or ""
        if (runtime or "runsc") not in runtimes:
            return f"Docker has no runtime {runtime or 'runsc'!r} registered (gVisor is Linux only and is set up in P7-T10)"
    return None


def run_one(argv: list[str], name: str | None, timeout: int) -> tuple[str, str]:
    env = dict(os.environ, ARGUS_MODEL_API_KEY=FAKE_SECRET)  # in the launcher's env, never passed on with -e
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return "error", f"hard timeout after {timeout}s"
    except OSError as exc:
        return "error", f"could not start: {exc}"
    finally:
        if name:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    status, detail = judge(proc.stdout, proc.returncode)
    if status == "error" and proc.stderr.strip():
        detail += f"; stderr: {proc.stderr.strip()[:200]}"
    return status, detail


def run_probe(tier: str, probe: Probe, work: Path, checks: Path, runtime: str | None, launcher: str | None, timeout: int,
              extra: tuple[str, ...] = ()) -> tuple[str, str]:
    """Run one probe in the tier. `extra` (docker flags) exists so tests can deliberately weaken the sandbox and see a probe fail."""
    if tier == "firecracker":
        return run_one([*shlex.split(launcher or ""), "sh", "-c", probe.script], None, timeout)
    name = f"guard-esc-{probe.id}-{uuid.uuid4().hex[:6]}"
    return run_one(docker_argv(name, work, checks, probe.script, runtime if tier == "gvisor" else None, extra), name, timeout)


def run_suite(tier: str, runtime: str | None, launcher: str | None, timeout: int = 60) -> dict:
    if tier != "firecracker" and not egress._image_present():
        sandbox.build_image()
    results = []
    with tempfile.TemporaryDirectory(prefix="guard-escape-", ignore_cleanup_errors=True) as tmp, \
            tempfile.TemporaryDirectory(prefix="guard-canary-", ignore_cleanup_errors=True) as canary_dir:
        work, checks = Path(tmp) / "work", Path(tmp) / "checks"
        work.mkdir()
        checks.mkdir()
        (checks / "keep.txt").write_text("same", encoding="utf-8")
        canary = Path(canary_dir) / "canary.txt"
        canary.write_text(CANARY_TOKEN, encoding="utf-8")
        for probe in probes(canary):
            status, detail = run_probe(tier, probe, work, checks, runtime, launcher, timeout)
            results.append({"id": probe.id, "what": probe.what, "expected": probe.expected, "status": status, "detail": detail})
    count = {s: sum(r["status"] == s for r in results) for s in ("pass", "fail", "error")}
    return {
        "suite": "escape", "tier": tier,
        "runtime": (runtime or "runsc") if tier == "gvisor" else ("launcher" if tier == "firecracker" else "default"),
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "docker_server": egress._docker_version() if tier != "firecracker" else None,
        "image": sandbox.IMAGE,
        "flags": {"network": "none", "cpus": sandbox.CPUS, "memory": sandbox.MEMORY, "pids_limit": PIDS_LIMIT, "checks": "ro", "added_by_suite": "pids_limit"},
        "probes": results, "summary": count,
    }


def format_report(report: dict) -> str:
    lines = [f"escape suite: tier={report['tier']} runtime={report['runtime']}"]
    for r in report["probes"]:
        lines.append(f"{r['status'].upper():5} {r['id']:22} {r['detail']}")
    s = report["summary"]
    lines.append(f"{len(report['probes'])} probes: {s['pass']} pass, {s['fail']} fail, {s['error']} error")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="guard escape", description=__doc__)
    ap.add_argument("--tier", choices=TIERS, required=True)
    ap.add_argument("--runtime", help="docker runtime for the gvisor tier (default runsc)")
    ap.add_argument("--launcher", default=os.environ.get("ARGUS_FIRECRACKER_LAUNCHER"),
                    help="firecracker tier: command prefix; it gets `sh -c <probe>` and must give the guest /work (rw) and /checks (ro)")
    ap.add_argument("--timeout", type=int, default=60, help="hard timeout per probe, seconds")
    ap.add_argument("--out", help="write the result JSON here")
    args = ap.parse_args(argv)

    why = unavailable(args.tier, args.runtime, args.launcher)
    if why:
        print(f"escape suite: tier={args.tier}\ntier not available here: {why}\nNo probe ran. This is not a pass.")
        return EXIT_UNAVAILABLE
    report = run_suite(args.tier, args.runtime, args.launcher, args.timeout)
    print(format_report(report))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    s = report["summary"]
    return 0 if s["fail"] == 0 and s["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
