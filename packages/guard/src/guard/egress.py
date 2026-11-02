"""P7-T05: the no-egress probe. Runs inside the fix-loop sandbox and tries TCP, HTTPS and DNS to an external host.

Each check ends as `reached`, `connect-failed` or `tool-missing`. The policy holds only if all three are `connect-failed`.
`--control` runs the same script in a container WITH a network. A probe that cannot see `reached` there proves nothing.
Same command locally and on GitHub Actions (`.github/workflows/egress.yml`); only `--context` differs.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fix_loop import sandbox

HOST = "example.com"
IP = "1.1.1.1"

# name: (tool the image must have, command; exit 0 means the target answered)
# https goes to the IP, so it does not depend on DNS (the machine's DNS can fail even with network on); the certificate is not checked
# because only the connection matters. dns counts as reached when the resolver answers at all, even "no answer": the query left the box.
CHECKS = {
    "tcp": ("nc", f"nc -w 3 {IP} 443 </dev/null"),
    "https": ("wget", f"wget -q -T 5 --no-check-certificate -O /dev/null https://{IP}/"),
    "dns": ("nslookup", f"nslookup {HOST}"),
}


def check_script(names: list[str] | None = None) -> str:
    """Shell that prints `<name>=reached|connect-failed|tool-missing` for each check."""
    parts = []
    for name in names or list(CHECKS):
        tool, cmd = CHECKS[name]
        parts.append(
            f"if ! command -v {tool} >/dev/null 2>&1; then echo {name}=tool-missing;"
            f" elif {cmd} >/dev/null 2>&1; then echo {name}=reached; else echo {name}=connect-failed; fi"
        )
    return "; ".join(parts)


def parse(stdout: str) -> dict[str, str]:
    seen = dict(ln.strip().split("=", 1) for ln in stdout.splitlines() if "=" in ln)
    return {name: seen.get(name, "no-output") for name in CHECKS}


def run_sandboxed() -> tuple[dict[str, str], str]:
    """Run the checks the way fix-loop starts its container (`fix_loop.sandbox.run`: network none, same image and caps)."""
    with tempfile.TemporaryDirectory(prefix="guard-egress-") as tmp:
        work, checks = Path(tmp) / "work", Path(tmp) / "checks"
        work.mkdir()
        checks.mkdir()
        proc = sandbox.run(work, checks, ["sh", "-c", check_script()], timeout=60)
    return parse(proc.stdout), (proc.stderr or "").strip()[:300]


def run_control() -> tuple[dict[str, str], str]:
    """Same script, same image, but on Docker's default bridge network. Throwaway name, removed afterwards."""
    name = f"guard-egress-ctl-{uuid.uuid4().hex[:8]}"
    try:
        proc = subprocess.run(
            ["docker", "run", "--rm", "--name", name, sandbox.IMAGE, "sh", "-c", check_script()],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
        )
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    return parse(proc.stdout), (proc.stderr or "").strip()[:300]


def _image_present() -> bool:
    return subprocess.run(["docker", "image", "inspect", sandbox.IMAGE], capture_output=True).returncode == 0


def _docker_version() -> str:
    proc = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True)
    return proc.stdout.strip() or "unknown"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="guard.egress", description=__doc__)
    ap.add_argument("--context", default="local", help="label stored in the result: local or actions")
    ap.add_argument("--control", action="store_true", help="also run the probe with network on, to prove it can see `reached`")
    ap.add_argument("--out", help="write the result JSON here")
    args = ap.parse_args(argv)

    if not _image_present():
        sandbox.build_image()
    results, stderr = run_sandboxed()
    held = all(v == "connect-failed" for v in results.values())
    report: dict = {
        "probe": "egress",
        "context": args.context,
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": platform.platform(),
        "docker_server": _docker_version(),
        "image": sandbox.IMAGE,
        "targets": {"tcp": f"{IP}:443", "https": f"https://{IP}/", "dns": HOST},
        "sandbox_results": results,
        "no_egress_held": held,
    }
    if stderr:
        report["sandbox_stderr"] = stderr
    if args.control:
        control, _ = run_control()
        report["control_results"] = control
        report["control_saw_reached"] = any(v == "reached" for v in control.values())
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    # exit 0 only when the policy held. A control that cannot see `reached` (no internet on the machine) does not fail the run, it is in the file.
    return 0 if held else 1


if __name__ == "__main__":
    sys.exit(main())
