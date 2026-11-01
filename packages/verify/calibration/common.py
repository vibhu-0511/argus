"""Shared helpers for building the real calibration set from the seeded bench tasks and the P3 runs.

A "tree" here is only the four CSS files the seeded tasks edit. Patches are applied to the platform's HEAD text with
`git apply` in a scratch directory, so the platform checkout is never written.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

PLATFORM = Path(r"C:\Users\vibha\Downloads\data\dcortex\dcortex_claude\dcortex-platform")
PLATFORM_HEAD = "ac86acc75"
CSS_FILES = (
    "apps/canvas/src/ops/ops.css",
    "apps/canvas/src/ops/radar.css",
    "apps/canvas/src/styles/landing.css",
    "apps/canvas/src/styles/tokens.css",
)
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SEEDED = ROOT / "packages" / "bench" / "tasks" / "seeded"
RUNS = ROOT / "packages" / "fix-loop" / "runs"
CHROME = r"C:\Users\vibha\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
PLAYWRIGHT = "file:///C:/Users/vibha/Downloads/data/personal/argus/packages/bench/node_modules/@playwright/test/index.mjs"
BENCH_MODULES = Path(r"C:\Users\vibha\Downloads\data\personal\argus\packages\bench\node_modules")
VIEWS = ("landing", "landing-login", "ops-radar", "ops-radar-departures", "ops-operations")


def head_css() -> dict[str, str]:
    out = {}
    for name in CSS_FILES:
        shown = subprocess.run(
            ["git", "-C", str(PLATFORM), "show", f"{PLATFORM_HEAD}:{name}"], capture_output=True, check=True
        )
        out[name] = shown.stdout.decode("utf-8")
    return out


def apply_patches(patches: list[str]) -> dict[str, str] | None:
    """HEAD css with each patch applied in order, or None when a patch does not apply."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for name, text in head_css().items():
            target = base / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
        for index, patch in enumerate(patches):
            file = base / f"p{index}.patch"
            file.write_bytes(patch.encode("utf-8"))
            done = subprocess.run(["git", "apply", "--whitespace=nowarn", file.name], cwd=base, capture_output=True)
            if done.returncode != 0:
                return None
        return {name: (base / name).read_bytes().decode("utf-8") for name in CSS_FILES}


def css_cache(tree: dict[str, str], cache: Path) -> dict[str, str]:
    """Write every file of the tree; return {platform path: file}. HEAD files are overridden too, so that every shot
    takes the same path through the renderer (an override is raw text, Vite's own output can differ in small ways)."""
    cache.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, text in tree.items():
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        file = cache / f"{digest}.css"
        file.write_bytes(text.encode("utf-8"))
        out[name] = str(file)
    return out


def render(shots: list[dict], work: Path) -> list[dict]:
    """shots: [{out, view, css}]. Runs render.mjs and returns its report."""
    work.mkdir(parents=True, exist_ok=True)
    jobs = work / "jobs.json"
    jobs.write_text(json.dumps({"base": "http://localhost:5199", "chrome": CHROME, "shots": shots}), encoding="utf-8")
    env = dict(os.environ, PLAYWRIGHT_MODULE=PLAYWRIGHT)
    subprocess.run(["node", str(HERE / "render.mjs"), str(jobs)], check=True, env=env)
    return json.loads(Path(str(jobs) + ".report.json").read_text(encoding="utf-8"))


def pixel_ratios(pairs: list[tuple[str, str]]) -> list[float]:
    """Changed-pixel ratio per (a, b) PNG pair, using the bench's pixelmatch at its own threshold."""
    script = HERE / "diff.mjs"
    env = dict(os.environ, BENCH_MODULES=str(BENCH_MODULES))
    done = subprocess.run(
        ["node", str(script)], input=json.dumps(pairs), capture_output=True, text=True, check=True, env=env
    )
    return json.loads(done.stdout)
