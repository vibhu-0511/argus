"""SWE-bench Multimodal subset adapter. Pins split `dev`, records every exclusion with a reason, and keeps the gold patch out of the agent prompt.

Field names come from the dataset card (princeton-nlp/SWE-bench_Multimodal): repo, instance_id, base_commit, patch, test_patch,
problem_statement, hints_text, created_at, image_assets, version, FAIL_TO_PASS, PASS_TO_PASS. `image_assets` is a JSON string
with the keys problem_statement, patch and test_patch. The `test` split withholds patch, test_patch and image_assets.

A row is not an argus_core `Task`: that type needs a bug patch and Playwright checks on the Canvas app, while SWE-bench scores
with repo test names. `MultimodalTask` is the smallest honest output. It has no patch field at all, so the gold patch cannot reach a prompt.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from argus_core.types import Ticket
from pydantic import BaseModel, ConfigDict, Field

DATASET = "princeton-nlp/SWE-bench_Multimodal"
SPLIT = "dev"  # pinned; `test` has no gold patch or image_assets
SERVER = "https://datasets-server.huggingface.co/rows"
PAGE = 10  # the server answers 502/503 on big pages; small pages with retries get through
KEEP = (
    "split", "repo", "instance_id", "base_commit", "problem_statement", "hints_text",
    "created_at", "image_assets", "version", "FAIL_TO_PASS",
)  # not patch, test_patch (gold) or PASS_TO_PASS (up to 170 KB a row; the scorer in T20 reads it from the dataset)
MAX_PATCH = 4000  # selection rule: small gold patches keep the leak-test fixture small
PER_REPO = 3
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "multimodal"


class MultimodalTask(BaseModel):
    """What the agent may see. There is deliberately no patch or test_patch field."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    repo: str
    base_commit: str
    version: str
    ticket: Ticket  # text is problem_statement; hints_text is dropped because issue comments often quote the fix
    image_urls: list[str] = Field(min_length=1)
    fail_to_pass: list[str]  # scorer-only: test names, kept out of the prompt


class Exclusion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance_id: str
    split: str
    reason: str
    detail: str


def _exclude(row: dict[str, Any], reason: str, detail: str) -> Exclusion:
    return Exclusion(instance_id=row["instance_id"], split=row.get("split", "?"), reason=reason, detail=detail)


def _image_urls(row: dict[str, Any]) -> tuple[list[str], str]:
    """(urls from image_assets.problem_statement, problem text or '')."""
    try:
        urls = json.loads(row.get("image_assets") or "")["problem_statement"]
    except (ValueError, KeyError, TypeError):
        return [], "image_assets is empty or not the expected JSON"
    if not urls:
        return [], "image_assets.problem_statement has no URLs"
    bad = [u for u in urls if not (isinstance(u, str) and u.startswith(("http://", "https://")))]
    return ([], f"non-http image URL: {bad[0]!r}") if bad else (urls, "")


def gold_lines(patch: str) -> list[str]:
    """Added lines of a diff long enough to be a fingerprint of the fix."""
    return [s for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++") and len(s := line[1:].strip()) >= 25]


def leaks_gold(text: str, patch: str) -> str | None:
    """The first piece of the gold patch found in text, or None."""
    if patch and patch.strip() in text:
        return patch.strip()[:80]
    return next((line for line in gold_lines(patch) if line in text), None)


def to_task(row: dict[str, Any]) -> MultimodalTask:
    urls, _ = _image_urls(row)
    return MultimodalTask(
        id=row["instance_id"], repo=row["repo"], base_commit=row["base_commit"], version=row["version"],
        ticket=Ticket(id=row["instance_id"], text=row["problem_statement"]), image_urls=urls,
        fail_to_pass=json.loads(row["FAIL_TO_PASS"]),
    )


def adapt(rows: list[dict[str, Any]]) -> tuple[list[MultimodalTask], list[Exclusion]]:
    """Turn rows into tasks. Every row that is not turned into a task gets an Exclusion. Rows need a `split` key."""
    tasks, excluded = [], []
    for row in rows:
        if row.get("split") != SPLIT:
            excluded.append(_exclude(row, "wrong-split", f"split {row.get('split')!r}; only {SPLIT!r} has the gold patch and image_assets"))
        elif (parsed := _image_urls(row))[1]:
            excluded.append(_exclude(row, "missing-image-assets", parsed[1]))
        elif (hit := leaks_gold(row["problem_statement"], row.get("patch", ""))):
            excluded.append(_exclude(row, "statement-quotes-gold-patch", f"issue text contains {hit!r}"))
        else:
            tasks.append(to_task(row))
    return tasks, excluded


def build_prompt(task: MultimodalTask) -> str:
    """The only text an agent gets for a task. Built from the task, which holds no patch."""
    images = "\n".join(f"- {u}" for u in task.image_urls)
    return (
        f"Repository: {task.repo} at commit {task.base_commit}\n\nIssue:\n{task.ticket.text}\n\n"
        f"Screenshots attached to the issue:\n{images}\n\nFix the issue by editing the repository."
    )


def fetch_dev(attempts: int = 6) -> list[dict[str, Any]]:
    """Read the dev split from the Hugging Face datasets server in small pages. Returns rows tagged split='dev'."""
    rows, offset, total = [], 0, 1
    while offset < total:
        url = f"{SERVER}?dataset={DATASET}&config=default&split={SPLIT}&offset={offset}&length={PAGE}"
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(url, timeout=60) as resp:
                    page = json.load(resp)
                break
            except (urllib.error.URLError, ValueError):  # 502/503 are HTTPError, a URLError subclass
                if attempt == attempts - 1:
                    raise
                time.sleep(6)
        total = page["num_rows_total"]
        rows += [{"split": SPLIT, **r["row"]} for r in page["rows"]]
        offset += PAGE
    return rows


def select(tasks: list[MultimodalTask], patches: dict[str, str]) -> tuple[list[MultimodalTask], list[Exclusion]]:
    """Up to PER_REPO tasks per repo (sorted by id) whose gold patch is at most MAX_PATCH chars. The rest are listed as not-selected."""
    picked, rest, taken = [], [], {}
    for t in sorted(tasks, key=lambda t: (t.repo, t.id)):
        if len(patches[t.id]) <= MAX_PATCH and taken.get(t.repo, 0) < PER_REPO:
            taken[t.repo] = taken.get(t.repo, 0) + 1
            picked.append(t)
        else:
            why = f"gold patch {len(patches[t.id])} chars > {MAX_PATCH}" if len(patches[t.id]) > MAX_PATCH else f"repo already has {PER_REPO} tasks"
            rest.append(Exclusion(instance_id=t.id, split=SPLIT, reason="not-selected", detail=why))
    return picked, rest


def build(raw: Path, out: Path = DATA_DIR) -> list[MultimodalTask]:
    """From the raw fetch (with patches, kept outside the repo) write the committed subset, exclusions and leak-test patches."""
    rows = json.loads(raw.read_text(encoding="utf-8"))
    tasks, excluded = adapt(rows)
    patches = {r["instance_id"]: r["patch"] for r in rows}
    picked, rest = select(tasks, patches)
    ids = [t.id for t in picked]
    out.mkdir(parents=True, exist_ok=True)
    by_id = {r["instance_id"]: r for r in rows}
    subset = {"dataset": DATASET, "split": SPLIT, "instance_ids": ids, "rows": [{k: by_id[i][k] for k in KEEP} for i in ids]}
    (out / "subset.json").write_text(json.dumps(subset, indent=1) + "\n", encoding="utf-8")
    (out / "gold_patches.json").write_text(json.dumps({i: patches[i] for i in ids}, indent=1) + "\n", encoding="utf-8")
    bad = [e.model_dump() for e in excluded + rest]
    (out / "excluded.json").write_text(json.dumps({"dev_rows": len(rows), "selected": len(ids), "excluded": bad}, indent=1) + "\n", encoding="utf-8")
    return picked


def load_subset(path: Path = DATA_DIR / "subset.json") -> list[MultimodalTask]:
    """The committed subset as tasks, no network. Needs the pinned split on the file and on every row."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["split"] != SPLIT:
        raise ValueError(f"subset file is split {data['split']!r}, adapter pins {SPLIT!r}")
    tasks, excluded = adapt(data["rows"])
    if excluded:
        raise ValueError(f"committed subset has rows the adapter excludes: {[e.instance_id for e in excluded]}")
    return tasks


def add_cli(sub: Any) -> None:
    """Register `multimodal fetch|build|prompt` on an argparse subparsers object."""
    mm = sub.add_parser("multimodal", help="SWE-bench Multimodal dev subset adapter")
    cmds = mm.add_subparsers(dest="mm_command", required=True)
    f = cmds.add_parser("fetch", help="download the dev split rows (with patches) to a file outside the repo")
    f.add_argument("--out", type=Path, required=True)
    b = cmds.add_parser("build", help="select the subset from a fetched file and write the committed data files")
    b.add_argument("--raw", type=Path, required=True)
    b.add_argument("--out", type=Path, default=DATA_DIR)
    p = cmds.add_parser("prompt", help="print the agent prompt of one committed task")
    p.add_argument("instance_id")


def run_cli(args: Any) -> int:
    if args.mm_command == "fetch":
        rows = fetch_dev()
        args.out.write_text(json.dumps(rows), encoding="utf-8")
        print(f"fetched {len(rows)} {SPLIT} rows, {args.out.stat().st_size} bytes -> {args.out}")
    elif args.mm_command == "build":
        picked = build(args.raw, args.out)
        print(f"selected {len(picked)} tasks, wrote {args.out}")
    else:
        task = next((t for t in load_subset() if t.id == args.instance_id), None)
        if task is None:
            raise SystemExit(f"{args.instance_id} is not in the committed subset")
        print(build_prompt(task))
    return 0
