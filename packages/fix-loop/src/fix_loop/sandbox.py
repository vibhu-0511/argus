"""Docker sandbox. No network. The worktree is writable. Checks are read-only."""

from __future__ import annotations

import subprocess
from pathlib import Path

IMAGE = "argus-fix-sandbox:p3"
CPUS = "1"
MEMORY = "512m"

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
    return subprocess.run(
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
