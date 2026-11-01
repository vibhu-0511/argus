"""Generate validated CSS mutants. Same seed, same task-set hash."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path

from argus_bench.golden import platform_repo
from argus_bench.score import close_score_session, open_score_session, score_task
from argus_bench.task_dir import load_task_dir
from argus_bench.validity import judge_mutant

_BENCH = Path(__file__).resolve().parents[2]
_REPO = _BENCH.parents[1]
_SCRIPT = Path(__file__).resolve().parents[1] / "css-candidates.mjs"
_FLOWS = ("/login", "/ops/radar", "/desk?sel=console", "/admin/users", "/admin/audit")
_HUNK = re.compile(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@(.*)$")


def task_set_hash(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def mutate_all(
    seed: int,
    *,
    repo: Path | None = None,
    out: Path | None = None,
    cache_path: Path | None = None,
    candidates: Callable[[int, Path], Iterator[dict]] | None = None,
    score: Callable[[str, Path], int] | None = None,
    limit: int = 300,
) -> int:
    repo = repo or platform_repo()
    out = out or (_BENCH / "tasks" / "mutated")
    cache_path = cache_path or (_REPO / ".local" / "mutate-verdicts.json")
    real = score is None
    if real:
        _browsers()
        score_fn: Callable[[str, Path], int] = score_task
    else:
        score_fn = score
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    cache = _load_cache(cache_path)
    work = _worktree(repo) if real else None
    kept = 0
    seen = 0
    dropped: Counter[str] = Counter()
    stream = None
    try:
        stream = (candidates or _node_candidates)(seed, repo)
        for index, row in enumerate(stream):
            if kept >= limit:
                break
            seen += 1
            reason = _one(
                seed,
                repo,
                out,
                cache_path,
                cache,
                work,
                score_fn,
                real,
                index,
                row,
                kept,
            )
            if reason == "keep":
                kept += 1
                print(f"keep mut-{kept:04d}")
            else:
                dropped[reason] += 1
            if seen % 25 == 0:
                print(f"seen {seen} kept {kept}", file=sys.stderr)
    finally:
        if real:
            close_score_session()
        closer = getattr(stream, "close", None)
        if closer is not None:
            closer()
        if work is not None:
            subprocess.run(
                ["git", "-C", str(repo), "worktree", "remove", "--force", str(work)],
                check=False,
                capture_output=True,
            )
            shutil.rmtree(work, ignore_errors=True)
    digest = task_set_hash(out)
    print(f"kept {kept}")
    print(f"hash {digest}")
    for reason, count in sorted(dropped.items()):
        print(f"dropped {reason} {count}")
    return 0 if kept >= limit else 1


def _one(
    seed: int,
    repo: Path,
    out: Path,
    cache_path: Path,
    cache: dict,
    work: Path | None,
    score_fn: Callable[[str, Path], int],
    real: bool,
    index: int,
    row: dict,
    kept: int,
) -> str:
    checks = _checks(row, index)
    if not checks:
        _keep, reason = judge_mutant(None, None, checks)
        return reason
    source = _source_bytes(repo, row["path"])
    bug = str(row["patch"]).replace("\r\n", "\n").replace("\r", "")
    if not bug.endswith("\n"):
        bug += "\n"
    golden = _reverse_patch(bug)
    key = _cache_key(seed, str(row["operatorId"]), source, bug, checks)
    cached = cache.get(key)
    if cached is not None:
        mutant = cached["mutant"]
        original = cached["original"]
    else:
        tree = work if work is not None else repo
        staged = out / "_staging"
        if staged.exists():
            shutil.rmtree(staged)
        _write(staged, "pending", row, checks, seed, bug, golden)
        load_task_dir(staged)
        if real:
            if work is None or not _apply(work, bug, check=True):
                shutil.rmtree(staged, ignore_errors=True)
                return "apply-fail"
            _reset(work)
            if not _apply(work, bug, check=False) or not _apply(work, golden, check=True):
                shutil.rmtree(staged, ignore_errors=True)
                if work is not None:
                    _reset(work)
                return "apply-fail"
        if real:
            open_score_session()
        mutant = _exit(score_fn, staged, tree if real else repo)
        original = None
        if mutant not in (0, 2):
            if real:
                if work is None or not _apply(work, golden, check=False):
                    shutil.rmtree(staged, ignore_errors=True)
                    if work is not None:
                        _reset(work)
                    return "apply-fail"
            original = _exit(score_fn, staged, tree if real else repo)
        if real and work is not None:
            _reset(work)
        cache[key] = {"mutant": mutant, "original": original}
        _save_cache(cache_path, cache)
        shutil.rmtree(staged, ignore_errors=True)
    keep, reason = judge_mutant(mutant, original, checks)
    if not keep:
        return reason
    final = out / f"mut-{kept + 1:04d}"
    _write(final, final.name, row, checks, seed, bug, golden)
    load_task_dir(final)
    return "keep"


def _checks(row: dict, index: int) -> list[dict]:
    selector = row.get("selector")
    prop = row.get("property")
    expected = row.get("expected")
    if not selector or not prop or not expected:
        return []
    return [
        {
            "params": {
                "css": row["path"],
                "expected": expected,
                "flow": _FLOWS[index % len(_FLOWS)],
                "property": prop,
                "selector": selector,
            },
            "type": "computed_style",
        }
    ]


def _write(directory: Path, task_id: str, row: dict, checks: list[dict], seed: int, bug: str, golden: str) -> None:
    directory.mkdir(parents=True)
    text = f"{row['property']} on {row['selector']} changed from {row['expected']}."
    _dump(directory / "ticket.json", {"id": task_id, "text": text})
    _dump(
        directory / "meta.json",
        {"archetype": row["archetype"], "seed": seed, "source": "mutated", "tier": "easy"},
    )
    _dump(directory / "checks.json", checks)
    (directory / "bug.patch").write_text(bug, encoding="utf-8", newline="\n")
    (directory / "golden.patch").write_text(golden, encoding="utf-8", newline="\n")


def _dump(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _reverse_patch(patch: str) -> str:
    out: list[str] = []
    for line in patch.splitlines():
        match = _HUNK.match(line)
        if match:
            old, old_n, new, new_n, rest = match.groups()
            out.append(f"@@ -{new},{new_n} +{old},{old_n} @@{rest}")
        elif line.startswith("+") and not line.startswith("+++"):
            out.append("-" + line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            out.append("+" + line[1:])
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def _cache_key(seed: int, operator_id: str, source: bytes, patch: str, checks: list[dict]) -> str:
    digest = hashlib.sha256()
    digest.update(str(seed).encode())
    digest.update(b"\0")
    digest.update(operator_id.encode())
    digest.update(b"\0")
    digest.update(source)
    digest.update(b"\0")
    digest.update(patch.encode())
    digest.update(b"\0")
    digest.update(json.dumps(checks, sort_keys=True, separators=(",", ":")).encode())
    return digest.hexdigest()


def _source_bytes(repo: Path, rel: str) -> bytes:
    path = repo / rel
    if path.is_file():
        return path.read_bytes()
    return b""


def _exit(score_fn: Callable[[str, Path], int], task: Path, tree: Path) -> int:
    code = _call(score_fn, task, tree)
    if code == 2:
        code = _call(score_fn, task, tree)
    return code


def _call(score_fn: Callable[[str, Path], int], task: Path, tree: Path) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        return score_fn(str(task), tree)


def _node_candidates(seed: int, repo: Path) -> Iterator[dict]:
    proc = subprocess.Popen(
        ["node", str(_SCRIPT), str(repo), str(seed)],
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.strip()
            if line:
                yield json.loads(line)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()


def _worktree(repo: Path) -> Path:
    work = Path(tempfile.mkdtemp(prefix="argus-mutate-"))
    added = subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "--detach", str(work), "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if added.returncode != 0:
        shutil.rmtree(work, ignore_errors=True)
        raise RuntimeError(added.stderr or added.stdout or "worktree add failed")
    return work


def _reset(work: Path) -> None:
    subprocess.run(["git", "-C", str(work), "checkout", "--", "."], check=False, capture_output=True)


def _apply(work: Path, patch: str, *, check: bool) -> bool:
    cmd = ["git", "-C", str(work), "apply"]
    if check:
        cmd.append("--check")
    proc = subprocess.run(cmd, input=patch, text=True, capture_output=True, encoding="utf-8")
    return proc.returncode == 0


def _load_cache(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, sort_keys=True), encoding="utf-8", newline="\n")


def _browsers() -> None:
    from argus_bench.score import _with_browsers

    chosen = _with_browsers(os.environ.copy()).get("PLAYWRIGHT_BROWSERS_PATH")
    if chosen:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = chosen
