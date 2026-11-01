"""Live `run_trees` for the repro loop (P5-T14). A script runs on the buggy and on the golden tree of a seeded task.

Needs the platform checkout (`ARGUS_PLATFORM_REPO`), node, and Docker with the `argus-repro:p1` image. One rig serves all tasks:

    python -m repro_agent.trees up        start Canvas (Vite, 127.0.0.1 only) and the sandbox network
    python -m repro_agent.trees status
    python -m repro_agent.trees run <task dir> <script file>     one script, both trees, prints the verdict
    python -m repro_agent.trees down

The two trees differ only in the CSS files the task's patches touch (the seeded bugs are CSS mutations), so they are not
two checkouts: `bug.patch` and then `golden.patch` are applied to the files' contents at platform HEAD, and the browser
swaps those texts in (rig/run-script.mjs). The checkout is only read. The script runs in the repro image on an internal
Docker network: the app is reachable through a proxy container, the internet is not.

ponytail: the app has no backend; /api answers are a fixed mock, the session is signed out only on /login (the landing screen; / just redirects to /ops). A bug
that needs real data or another signed-in state cannot be reproduced here. One script, one container, a fresh browser.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

from repro_agent.browser import ToolUnavailable
from repro_agent.loop import TreeRun
from repro_agent.verify import Verdict, verify

RIG = Path(__file__).resolve().parents[2] / "rig"
IMAGE = "argus-repro:p1"
NET, PROXY, ALIAS = "argus-t14-net", "argus-t14-proxy", "argus-app"
PORT = int(os.environ.get("RIG_PORT", "5297"))
STATE = Path(tempfile.gettempdir()) / "argus-t14-rig.json"
DOCKER_TIMEOUT = 150
FORWARD = (  # inside the proxy container: NET alias :PORT -> the host's loopback, which Docker Desktop names host.docker.internal
    'import net from "node:net";'
    f'net.createServer((c)=>{{const u=net.connect({PORT},"host.docker.internal");c.pipe(u);u.pipe(c);'
    "c.on('error',()=>u.destroy());u.on('error',()=>c.destroy());}"
    f").listen({PORT});"
)


def platform_repo() -> Path:
    path = os.environ.get("ARGUS_PLATFORM_REPO")
    if not path:
        raise ToolUnavailable("set ARGUS_PLATFORM_REPO to the dcortex-platform checkout (see config/platform.md)")
    return Path(path)


def _docker(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _app_up() -> bool:
    try:
        return urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=5).status == 200
    except OSError:
        return False


def _proxy_up() -> bool:
    proc = _docker("inspect", "-f", "{{.State.Running}}", PROXY)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def up() -> None:
    repo = platform_repo()
    if not _app_up():
        canvas = repo / "apps" / "canvas"
        env = {**os.environ, "ARGUS_PLATFORM_REPO": str(repo), "RIG_PORT": str(PORT), "RIG_CACHE": str(Path(tempfile.gettempdir()) / "argus-t14-vite-cache")}
        log = (Path(tempfile.gettempdir()) / "argus-t14-vite.log").open("w")
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        proc = subprocess.Popen(
            [shutil.which("node") or "node", str(canvas / "node_modules" / "vite" / "bin" / "vite.js"), "--config", str(RIG / "vite.config.mjs")],
            cwd=canvas, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=flags,
        )
        STATE.write_text(json.dumps({"vite_pid": proc.pid}), encoding="utf-8")
        for _ in range(60):
            if _app_up():
                break
            time.sleep(1)
        else:
            raise ToolUnavailable("Canvas (Vite) did not answer on 127.0.0.1 within 60 s; see argus-t14-vite.log in the temp dir")
    if not _proxy_up():
        _docker("network", "create", "--internal", NET)
        _docker("rm", "-f", PROXY)
        started = _docker("run", "-d", "--name", PROXY, "--entrypoint", "node", IMAGE, "--input-type=module", "-e", FORWARD)
        if started.returncode != 0:
            raise ToolUnavailable(f"proxy container did not start: {started.stderr.strip()[-300:]}")
        joined = _docker("network", "connect", "--alias", ALIAS, NET, PROXY)
        if joined.returncode != 0:
            raise ToolUnavailable(f"proxy container did not join {NET}: {joined.stderr.strip()[-300:]}")


def down() -> None:
    if STATE.exists():
        pid = json.loads(STATE.read_text(encoding="utf-8")).get("vite_pid")
        if pid:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"] if os.name == "nt" else ["kill", str(pid)], capture_output=True)
        STATE.unlink()
    _docker("rm", "-f", PROXY)
    _docker("network", "rm", NET)


def status() -> dict[str, bool]:
    return {"canvas": _app_up(), "proxy": _proxy_up()}


# --- the two trees -----------------------------------------------------------------------------------------


def _apply(patch: Path, cwd: Path) -> None:
    # the checked-out patch files may have CRLF line ends on Windows; read_text turns them into LF, the file blobs have LF
    lf = cwd.parent / f"{cwd.name}-{patch.name}"
    lf.write_bytes(patch.read_text(encoding="utf-8").encode("utf-8"))
    proc = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "apply", "--whitespace=nowarn", str(lf)], cwd=cwd, capture_output=True, text=True, encoding="utf-8"
    )
    lf.unlink()
    if proc.returncode != 0:
        raise RuntimeError(f"{patch.name} does not apply: {proc.stderr.strip()[:300]}")


def css_trees(task_dir: Path, repo: Path) -> dict[str, dict[str, bytes]]:
    """{'buggy': {repo path: bytes}, 'golden': {...}} for the files the task's bug patch touches, at platform HEAD."""
    bug, golden = task_dir / "bug.patch", task_dir / "golden.patch"
    files = re.findall(r"^\+\+\+ b/(.+)$", bug.read_text(encoding="utf-8"), re.M)
    out: dict[str, dict[str, bytes]] = {}
    with tempfile.TemporaryDirectory(prefix="argus-t14-css-") as tmp:
        root = Path(tmp)
        for name in files:
            shown = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{name}"], capture_output=True)
            if shown.returncode != 0:
                raise RuntimeError(f"{name} is not at platform HEAD")
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_bytes(shown.stdout)
        _apply(bug, root)
        out["buggy"] = {n: (root / n).read_bytes() for n in files}
        _apply(golden, root)
        out["golden"] = {n: (root / n).read_bytes() for n in files}
    return out


def run_both(script: str, task_dir: Path) -> dict[str, dict[str, str]]:
    """Run `script` on both trees in the sandbox; {'buggy': {'result', 'detail'}, 'golden': {...}}."""
    trees = css_trees(task_dir, platform_repo())
    with tempfile.TemporaryDirectory(prefix="argus-t14-") as tmp:
        work = Path(tmp)
        (work / "css").mkdir()
        (work / "script.txt").write_text(script, encoding="utf-8", newline="\n")
        mapping: dict[str, dict[str, str]] = {"buggy": {}, "golden": {}}
        for tree, files in trees.items():
            for i, (name, data) in enumerate(files.items()):
                rel = f"css/{tree}{i}.css"
                (work / rel).write_bytes(data)
                mapping[tree][name] = rel
        (work / "meta.json").write_text(json.dumps({"base": f"http://{ALIAS}:{PORT}", "trees": mapping}), encoding="utf-8")
        try:
            proc = _docker(
                "run", "--rm", "--network", NET, "--ipc=host", "--memory", "2g", "-v", f"{work}:/work:ro",
                "-v", f"{RIG / 'run-script.mjs'}:/opt/argus-repro/run-script.mjs:ro", "-w", "/opt/argus-repro",
                "--entrypoint", "node", IMAGE, "/opt/argus-repro/run-script.mjs", "/work", timeout=DOCKER_TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolUnavailable(f"sandbox run timed out after {DOCKER_TIMEOUT} s") from exc
    lines = proc.stdout.strip().splitlines()
    if proc.returncode != 0 or not lines:
        raise ToolUnavailable(f"sandbox run failed: {(proc.stderr or proc.stdout).strip()[-400:]}")
    return json.loads(lines[-1])


def trees_for(task_dir: Path, cache_dir: Path | None = None) -> Callable[[str], TreeRun]:
    """The `run_trees` callable of one task. With `cache_dir`, a script already run for this task is not run again
    (the turn driver replays the repro loop from the start on every turn)."""
    if not status()["canvas"] or not _proxy_up():
        raise ToolUnavailable("repro rig is not up: python -m repro_agent.trees up")

    def run_trees(script: str) -> TreeRun:
        key = hashlib.sha256(f"{task_dir.name}\n{script}".encode()).hexdigest()[:24]
        cached = cache_dir / f"{key}.json" if cache_dir else None
        if cached is not None and cached.exists():
            result = json.loads(cached.read_text(encoding="utf-8"))["result"]
        else:
            result = run_both(script, task_dir)
            if cached is not None:
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(json.dumps({"task": task_dir.name, "script": script, "result": result}, indent=1), encoding="utf-8")
        buggy, golden = result["buggy"]["result"], result["golden"]["result"]
        skipped = verify(script, "fail", "pass") is Verdict.error  # a test.skip / test.fixme in the script
        return TreeRun(failed_on_buggy=buggy == "fail" and not skipped, passed_on_golden=golden == "pass" and not skipped)

    return run_trees


def live() -> Callable[[Path], Callable[[str], TreeRun]]:
    """For eval's `params.run_trees` (`repro_agent.trees:live`): a function that takes the task directory."""
    return trees_for


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["up"]:
        up()
        print(status())
    elif args == ["down"]:
        down()
    elif args == ["status"]:
        print(status())
    elif len(args) == 3 and args[0] == "run":
        result = run_both(Path(args[2]).read_text(encoding="utf-8"), Path(args[1]).resolve())
        print(json.dumps(result, indent=1))
        print(verify(Path(args[2]).read_text(encoding="utf-8"), result["buggy"]["result"], result["golden"]["result"]).value)
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
