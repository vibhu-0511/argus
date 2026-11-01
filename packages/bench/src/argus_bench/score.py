"""Score a task directory against a tree.

Exit 0 when every check passes, 1 when a check fails, 2 when the task or tree
is missing or the runner crashes. The verdict log is the full check text.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from pydantic import ValidationError

from argus_bench.task_dir import load_task_dir
from argus_bench.verdict import CheckResult, Verdict
from argus_core.types import Task

_BENCH = Path(__file__).resolve().parents[2]
_RUNNER = Path(__file__).resolve().parents[1] / "run-checks.ts"
_session: subprocess.Popen[str] | None = None


def open_score_session() -> None:
    """One browser for later score_task calls. bench score without this stays one-shot."""
    global _session
    if _session is not None and _session.poll() is None:
        return
    _session = subprocess.Popen(
        ["node", str(_RUNNER), "--serve"],
        cwd=_BENCH,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        env=_with_browsers(os.environ.copy()),
        bufsize=1,
    )


def close_score_session() -> None:
    global _session
    proc = _session
    _session = None
    if proc is None:
        return
    if proc.stdin is not None:
        proc.stdin.close()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


def score_task(task: str, tree: Path) -> int:
    try:
        directory = _task_dir(task)
    except FileNotFoundError as exc:
        return _emit(_verdict(task or "unknown", log=str(exc)), 2)
    try:
        loaded = load_task_dir(directory)
    except (OSError, ValidationError, ValueError, KeyError) as exc:
        return _emit(_verdict(task or directory.name, log=str(exc)), 2)
    if not tree.is_dir():
        return _emit(_verdict(loaded.id, log=f"missing tree: {tree}"), 2)
    if not loaded.checks:
        return _emit(_verdict(loaded.id, log="task has no checks"), 2)
    if _session is not None and _session.poll() is None:
        return _run_live(loaded, directory, tree)
    return _run(loaded, directory, tree)


def _task_dir(arg: str) -> Path:
    direct = Path(arg)
    if direct.is_dir():
        return direct
    for candidate in (_BENCH / "tasks" / "seeded" / arg, _BENCH / "tasks" / "mutated" / arg):
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"missing task: {arg}")


def _run(task: Task, directory: Path, tree: Path) -> int:
    payload = {
        "tree": str(tree.resolve()),
        "task_dir": str(directory.resolve()),
        "checks": [check.model_dump(mode="json") for check in task.checks],
    }
    try:
        proc = subprocess.run(
            ["node", str(_RUNNER)],
            cwd=_BENCH,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_with_browsers(os.environ.copy()),
            timeout=120,
            check=False,
        )
    except FileNotFoundError as exc:
        return _emit(_verdict(task.id, log=str(exc)), 2)
    except subprocess.TimeoutExpired as exc:
        return _emit(_verdict(task.id, log=_timeout_log(exc)), 2)
    if proc.returncode != 0:
        return _emit(_verdict(task.id, log=f"{proc.stdout}{proc.stderr}"), 2)
    try:
        results = _parse(proc.stdout, len(task.checks))
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError, KeyError) as exc:
        return _emit(_verdict(task.id, log=f"{exc}\n{proc.stdout}"), 2)
    log = "\n".join(item.reason for item in results)
    ok = all(item.ok for item in results)
    return _emit(Verdict(task_id=task.id, ok=ok, checks=results, log=log), 0 if ok else 1)


def _run_live(task: Task, directory: Path, tree: Path) -> int:
    proc = _session
    if proc is None or proc.stdin is None or proc.stdout is None or proc.poll() is not None:
        return _emit(_verdict(task.id, log="score session is closed"), 2)
    payload = {
        "tree": str(tree.resolve()),
        "task_dir": str(directory.resolve()),
        "checks": [check.model_dump(mode="json") for check in task.checks],
    }
    try:
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()
    except OSError as exc:
        close_score_session()
        return _emit(_verdict(task.id, log=str(exc)), 2)
    line = _read_line(proc.stdout, 120)
    if line is None:
        close_score_session()
        return _emit(_verdict(task.id, log="timed out"), 2)
    if not line:
        close_score_session()
        return _emit(_verdict(task.id, log="score session ended"), 2)
    try:
        results = _parse(line, len(task.checks))
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError, KeyError) as exc:
        return _emit(_verdict(task.id, log=f"{exc}\n{line}"), 2)
    log = "\n".join(item.reason for item in results)
    ok = all(item.ok for item in results)
    return _emit(Verdict(task_id=task.id, ok=ok, checks=results, log=log), 0 if ok else 1)


def _read_line(stdout: object, timeout: float) -> str | None:
    box: list[str] = []

    def read() -> None:
        box.append(stdout.readline())  # type: ignore[attr-defined]

    worker = threading.Thread(target=read, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        return None
    return box[0] if box else ""


def _parse(stdout: str, expected: int) -> list[CheckResult]:
    payload = json.loads(stdout)
    checks = payload["checks"]
    if not isinstance(checks, list) or len(checks) != expected:
        got = len(checks) if isinstance(checks, list) else "no"
        raise ValueError(f"runner log has {got} checks, expected {expected}")
    return [CheckResult.model_validate(item) for item in checks]


def _shell_dir(path: Path, revision: str | None) -> bool:
    if revision:
        exe = path / f"chromium_headless_shell-{revision}" / "chrome-headless-shell-win64" / "chrome-headless-shell.exe"
        return exe.is_file()
    return any(path.glob("chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe"))


def _with_browsers(env: dict[str, str]) -> dict[str, str]:
    revision = _chromium_revision()
    current = env.get("PLAYWRIGHT_BROWSERS_PATH")
    if current and _shell_dir(Path(current), revision):
        return env
    roots = [
        Path(tempfile.gettempdir()) / "cursor-sandbox-cache",
        Path.home() / "AppData" / "Local" / "ms-playwright",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        if _shell_dir(root, revision):
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(root)
            return env
        for child in root.iterdir():
            browsers = child / "playwright"
            if browsers.is_dir() and _shell_dir(browsers, revision):
                env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)
                return env
    return env


def _chromium_revision() -> str | None:
    root = _BENCH.parents[1] / "node_modules" / ".pnpm"
    matches = sorted(root.glob("playwright-core@*/node_modules/playwright-core/browsers.json"))
    if not matches:
        return None
    data = json.loads(matches[-1].read_text(encoding="utf-8"))
    for item in data.get("browsers", []):
        if item.get("name") == "chromium":
            revision = item.get("revision")
            return str(revision) if revision else None
    return None


def _timeout_log(exc: subprocess.TimeoutExpired) -> str:
    stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
    stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
    return f"timed out\n{stdout}{stderr}"


def _verdict(task_id: str, *, log: str) -> Verdict:
    return Verdict(task_id=task_id or "unknown", ok=False, checks=[], log=log)


def _emit(verdict: Verdict, code: int) -> int:
    payload = verdict.model_dump(mode="json")
    Verdict.model_validate(payload)
    print(json.dumps(payload, indent=2))
    return code
