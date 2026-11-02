"""Docker sandbox. No network. The worktree is writable. Checks are read-only."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger("fix_loop.policy")

IMAGE = "argus-fix-sandbox:p3"
CPUS = "1"
MEMORY = "512m"

# ponytail: the container reports a blocked route or a write to the read-only mount only as text on stderr, so the policy
# event is found by those message strings (busybox/musl wording). A different image or tool may word them differently.
_BLOCKED = {
    "network-blocked": ("bad address", "Network unreachable", "Network is unreachable", "Temporary failure in name resolution"),
    "checks-write-blocked": ("Read-only file system",),
}

_DOCKER = Path(__file__).resolve().parents[2] / "docker"


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


def run(
    worktree: Path,
    checks: Path,
    command: list[str],
    *,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    work = worktree.resolve()
    checks = checks.resolve()
    if not work.is_dir():
        raise FileNotFoundError(work)
    if not checks.is_dir():
        raise FileNotFoundError(checks)
    proc = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
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
        ],
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
