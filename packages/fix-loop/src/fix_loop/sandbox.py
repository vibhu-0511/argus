"""Docker sandbox. No network. The worktree is writable. Checks are read-only."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger("fix_loop.policy")

IMAGE = "argus-fix-sandbox:p3"
CPUS = "1"
MEMORY = "512m"
RUNTIME_ENV = "ARGUS_SANDBOX_RUNTIME"  # P7-T10: unset means Docker's default runtime (runc); `runsc` is gVisor

# ponytail: the container reports a blocked route or a write to the read-only mount only as text on stderr, so the policy
# event is found by those message strings (busybox/musl wording). A different image or tool may word them differently.
_BLOCKED = {
    "network-blocked": ("bad address", "Network unreachable", "Network is unreachable", "Temporary failure in name resolution"),
    "checks-write-blocked": ("Read-only file system",),
}

_DOCKER = Path(__file__).resolve().parents[2] / "docker"


class RuntimeUnavailable(RuntimeError):
    """The Docker runtime that was asked for is not there. The sandbox never falls back to another runtime."""


def build_image() -> None:
    proc = subprocess.run(
        ["docker", "build", "-t", IMAGE, str(_DOCKER)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "docker build failed").strip())


def configured_runtime() -> str | None:
    """The runtime from `ARGUS_SANDBOX_RUNTIME`, or None for Docker's default."""
    return os.environ.get(RUNTIME_ENV, "").strip() or None


def docker_runtimes() -> list[str]:
    """Names of the runtimes the Docker daemon has registered."""
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{json .Runtimes}}"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeUnavailable(f"cannot ask Docker for its runtimes: {exc}") from exc
    if proc.returncode != 0:
        raise RuntimeUnavailable(f"the Docker daemon is not reachable: {proc.stderr.strip()[:200]}")
    return sorted(json.loads(proc.stdout or "{}"))


def check_runtime(runtime: str) -> None:
    have = docker_runtimes()
    if runtime not in have:
        raise RuntimeUnavailable(
            f"Docker has no runtime {runtime!r} registered (it has: {', '.join(have) or 'none'}). "
            "Not falling back to the default runtime."
        )


def docker_argv(work: Path, checks: Path, command: list[str], runtime: str | None = None) -> list[str]:
    """The exact `docker run` argument list. `runtime` None adds no flag, so the default stays as it was before P7."""
    return [
        "docker",
        "run",
        "--rm",
        *(["--runtime", runtime] if runtime else []),
        "--network",
        "none",
        "--cpus",
        CPUS,
        "--memory",
        MEMORY,
        "-v",
        f"{work}:/work",
        "-v",
        f"{checks}:/checks:ro",
        "-w",
        "/work",
        IMAGE,
        *command,
    ]


def run(
    worktree: Path,
    checks: Path,
    command: list[str],
    *,
    timeout: int = 30,
    runtime: str | None = None,
) -> subprocess.CompletedProcess[str]:
    work = worktree.resolve()
    checks = checks.resolve()
    if not work.is_dir():
        raise FileNotFoundError(work)
    if not checks.is_dir():
        raise FileNotFoundError(checks)
    runtime = runtime or configured_runtime()
    if runtime:
        check_runtime(runtime)
    proc = subprocess.run(
        docker_argv(work, checks, command, runtime),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        _log_policy(proc.stderr or "")
    return proc


def _log_policy(stderr: str) -> None:
    """One WARNING per kind on logger `fix_loop.policy`. It holds the kind and the first matching line, never the command."""
    for kind, markers in _BLOCKED.items():
        line = next((ln for ln in stderr.splitlines() if any(m in ln for m in markers)), None)
        if line is not None:
            log.warning("policy event: %s: %s", kind, line.strip()[:200])
