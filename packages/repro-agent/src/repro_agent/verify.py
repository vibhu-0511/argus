"""Repro verdicts. A script is valid only when it fails on the bug and passes on the fix."""

from __future__ import annotations

import json
import re
import subprocess
from enum import StrEnum
from pathlib import Path

_SKIP = re.compile(r"\btest\.(?:skip|fixme)\b")
_IMAGE = "argus-repro:p1"
_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "verify"


class Verdict(StrEnum):
    valid = "valid"
    passes_on_bug = "passes-on-bug"
    fails_on_golden = "fails-on-golden"
    error = "error"


def verify(script: str, buggy: str, golden: str) -> Verdict:
    if _SKIP.search(script) or buggy == "error" or golden == "error":
        return Verdict.error
    if buggy == "fail" and golden == "pass":
        return Verdict.valid
    if buggy == "pass":
        return Verdict.passes_on_bug
    return Verdict.fails_on_golden


def run_fixture_scripts() -> dict[str, dict[str, str]]:
    """Run the three behavioral scripts on both trees inside the sandbox image."""
    proc = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--ipc=host",
            "-v",
            f"{_FIXTURES}:/work:ro",
            "-v",
            f"{_FIXTURES / 'run.mjs'}:/opt/argus-repro/run-verify.mjs:ro",
            "-w",
            "/opt/argus-repro",
            "--entrypoint",
            "node",
            _IMAGE,
            "/opt/argus-repro/run-verify.mjs",
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-2000:] or proc.stdout[-2000:])
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    return payload
