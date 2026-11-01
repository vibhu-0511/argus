"""P5-T20 runner pieces for the SWE-bench Multimodal subset. No model call here.

`prepare` makes a checkout at `base_commit` plus the prompt (issue text and local copies of the issue images; the gold patch is not
in `MultimodalTask`, so it cannot get in). The agent edits the checkout. `finish` captures its diff as the produced patch and proves
it applies to a clean base. `predictions` writes the file the SWE-bench harness reads. `results` builds the results JSON and the
solved / unsolved / excluded table.

A patch only counts as resolved or unresolved when the SWE-bench harness has graded it (`--reports`, the harness's
logs/evaluation/<run_id>/<model> folder) or it is empty. Any other produced patch is `excluded` with the reason
"patch produced, not scored": never resolved, never in the resolve-rate denominator.

Layout under --root: <id>/checkout/, <id>/images/, <id>/prompt.txt, <id>/model.diff, <id>/setup_error.txt (a task that could not be set up), <id>/excluded.txt (a task found invalid; its text is the reason).
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from eval.multimodal import MultimodalTask, build_prompt, load_subset
from eval.results import Results, TaskRow, TokenCounts
from eval.runner import AgentConfig, _aggregate

NOT_SCORED = "patch produced, not scored"


class SetupError(Exception):
    """The task cannot be run (clone, fetch or image download failed). It becomes an excluded row with this message."""


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True)  # bytes: text mode would rewrite CRLFs inside a diff
    if done.returncode:
        raise SetupError(f"git {' '.join(args)}: {done.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return done.stdout.decode("utf-8")


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as resp:  # some hosts 403 the default Python agent
        dest.write_bytes(resp.read())


def prepare(
    task: MultimodalTask, root: Path, repo_url: str | None = None, download: Callable[[str, Path], None] = _download
) -> str:
    """Checkout at base_commit (one commit fetched, not the history) and the images; returns the prompt, also saved as prompt.txt."""
    work = root / task.id
    checkout, images = work / "checkout", work / "images"
    try:
        if not checkout.exists():
            checkout.mkdir(parents=True)
            _git(checkout, "init", "-q")
            _git(checkout, "fetch", "-q", "--depth", "1", repo_url or f"https://github.com/{task.repo}.git", task.base_commit)
            _git(checkout, "checkout", "-q", "FETCH_HEAD")
        images.mkdir(exist_ok=True)
        paths = []
        for n, url in enumerate(task.image_urls, 1):
            path = images / f"{n:02d}{Path(urlparse(url).path).suffix or '.png'}"
            if not path.exists():
                download(url, path)
            paths.append(path)
    except (SetupError, OSError) as exc:
        (work / "setup_error.txt").write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
        raise SetupError(str(exc)) from exc
    (work / "setup_error.txt").unlink(missing_ok=True)  # a retry that worked
    prompt = build_prompt(task.model_copy(update={"image_urls": [str(p) for p in paths]}))
    (work / "prompt.txt").write_text(prompt, encoding="utf-8", newline="")  # the issue text has CRLFs; keep them as they are
    return prompt


def apply_patch(checkout: Path, patch: str) -> None:
    """Apply a unified diff to a checkout; raises SetupError if it does not apply."""
    data = patch.encode("utf-8")
    check = subprocess.run(["git", "apply", "--check", "-"], cwd=checkout, input=data, capture_output=True)
    if check.returncode:
        raise SetupError(f"patch does not apply: {check.stderr.decode('utf-8', 'replace').strip()[:300]}")
    subprocess.run(["git", "apply", "-"], cwd=checkout, input=data, check=True)


def finish(task: MultimodalTask, root: Path) -> str:
    """Capture the agent's edits as a diff against base_commit, save it as model.diff, check it applies to a clean base."""
    work = root / task.id
    checkout = work / "checkout"
    _git(checkout, "add", "-A")
    patch = _git(checkout, "diff", "--cached", "--binary", task.base_commit)
    (work / "model.diff").write_text(patch, encoding="utf-8", newline="")
    if patch.strip():
        _git(checkout, "reset", "-q", "--hard", task.base_commit)
        try:
            apply_patch(checkout, patch)  # proves the saved diff applies on its own
        finally:
            _git(checkout, "add", "-A")
    return patch


def predictions(tasks: list[MultimodalTask], root: Path, model: str) -> list[dict[str, str]]:
    """SWE-bench harness input: one row per non-empty produced patch."""
    rows = []
    for t in tasks:
        diff = root / t.id / "model.diff"
        if diff.exists() and (patch := diff.read_bytes().decode("utf-8")).strip():
            rows.append({"instance_id": t.id, "model_name_or_path": model, "model_patch": patch})
    return rows


def _graded(reports: Path | None, task_id: str) -> bool | None:
    """resolved flag from the harness's report.json for this instance, None when there is none."""
    found = sorted(reports.glob(f"**/{task_id}/report.json"), key=lambda p: p.stat().st_mtime) if reports else []  # newest wins after a re-run
    return bool(json.loads(found[-1].read_text(encoding="utf-8"))[task_id]["resolved"]) if found else None


def task_row(task: MultimodalTask, root: Path, reports: Path | None = None) -> TaskRow:
    work = root / task.id
    verdict, reason = "excluded", None
    if (work / "excluded.txt").exists():  # written by hand when the task itself is invalid (e.g. ticket and gold patch disagree)
        reason = f"invalid task: {(work / 'excluded.txt').read_text(encoding='utf-8').strip()}"
    elif (work / "setup_error.txt").exists():
        reason = f"setup failed: {(work / 'setup_error.txt').read_text(encoding='utf-8')}"
    elif not (work / "model.diff").exists():
        reason = "not run: no patch captured yet"
    elif not (work / "model.diff").read_text(encoding="utf-8").strip():
        verdict, reason = "unresolved", "empty patch (the agent changed nothing; not run through the harness)"
    elif (graded := _graded(reports, task.id)) is None:
        reason = f"{NOT_SCORED}: no harness report for it yet"
    else:
        verdict = "resolved" if graded else "unresolved"
    return TaskRow(
        task_id=task.id, tier=None, verdict=verdict, reason=reason, stop_reason=None, steps=None,
        tokens=TokenCounts(tokens_in=0, tokens_out=0, tokens_cached=0), latency_s=None, trajectory=None,
    )


def results(tasks: list[MultimodalTask], root: Path, config: AgentConfig, reports: Path | None = None, run_id: str | None = None) -> Results:
    rows = [task_row(t, root, reports) for t in tasks]
    return _aggregate(rows, config, run_id or config.name, datetime.now(UTC), {})


def table(res: Results) -> str:
    """One line per task and the counts. Produced-but-not-graded patches are their own line, apart from solved."""
    kind = lambda r: "solved" if r.verdict == "resolved" else NOT_SCORED if (r.reason or "").startswith(NOT_SCORED) else r.verdict
    counts = Counter(kind(r) for r in res.tasks)
    lines = [f"| {r.task_id} | {kind(r)} | {r.reason or ''} |" for r in res.tasks]
    head = "| task | outcome | reason |\n|---|---|---|\n"
    total = ", ".join(f"{k} {v}" for k, v in counts.items())
    return head + "\n".join(lines) + f"\n\nsolved/unsolved/excluded/{NOT_SCORED} counts: {total} (of {len(res.tasks)} tasks)\n"


def add_cli(cmds) -> None:
    """Register prepare|finish|predictions|results on the `multimodal` subparsers."""
    for name, helptext in (
        ("prepare", "checkout at base_commit + images + prompt for one task"),
        ("finish", "capture the agent's edits as model.diff and check it applies"),
    ):
        p = cmds.add_parser(name, help=helptext)
        p.add_argument("instance_id")
        p.add_argument("--root", type=Path, required=True)
        if name == "prepare":
            p.add_argument("--repo-url", help="default: https://github.com/<repo>.git")
    for name, helptext in (("predictions", "write the SWE-bench predictions JSONL"), ("results", "write the results JSON, print the table")):
        p = cmds.add_parser(name, help=helptext)
        p.add_argument("--root", type=Path, required=True)
        p.add_argument("--model", default="claude-session", help="agent model name in the file")
        p.add_argument("--out", type=Path, required=True)
        if name == "results":
            p.add_argument("--reports", type=Path, help="harness logs/evaluation/<run_id>/<model> folder")
            p.add_argument("--run-id")


def run_cli(args) -> int:
    tasks = load_subset()
    if args.mm_command in ("prepare", "finish"):
        task = next((t for t in tasks if t.id == args.instance_id), None)
        if task is None:
            raise SystemExit(f"{args.instance_id} is not in the committed subset")
        if args.mm_command == "prepare":
            prepare(task, args.root, args.repo_url)
            print(f"checkout: {args.root / task.id / 'checkout'}\nprompt:   {args.root / task.id / 'prompt.txt'}")
        else:
            print(f"model.diff: {len(finish(task, args.root).splitlines())} lines")
    elif args.mm_command == "predictions":
        rows = predictions(tasks, args.root, args.model)
        args.out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        print(f"{len(rows)} predictions of {len(tasks)} tasks -> {args.out}")
    else:
        res = results(tasks, args.root, AgentConfig(name=args.model, model=args.model, factory="none:none"), args.reports, args.run_id)
        args.out.write_text(res.to_json(), encoding="utf-8")
        print(table(res), end="")
    return 0
