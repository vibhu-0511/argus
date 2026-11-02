"""Grade multimodal instances with the SWE-bench harness, one instance per call, and keep one summary.

Does by script what was done by hand on 2026-11-01: `docker pull` the instance image, run
`python -m swebench.harness.run_evaluation` for that one instance (UTF-8 mode on), read its report.json. A failure
on one instance is recorded and the loop goes on. `--predictions gold` checks the reference patches; a JSONL from
`eval multimodal predictions` grades the agent's patches. Output: <out>/summary.json and a table. Re-running skips
instances that already resolved in the summary (use --force to redo).

ponytail: sequential, one worker. The images are big and Docker Desktop's pipe dies if it restarts mid-run; add a pool when that is not the limit.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from eval.multimodal import DATASET_V2, load_subset

TIMEOUT_S = 40 * 60  # per instance, pull included


def image_name(instance_id: str) -> str:
    """swebench/sweb.eval.x86_64.<owner>_1776_<repo>-<n>:latest, the `image` field of the dataset rows."""
    return "swebench/sweb.eval.x86_64." + instance_id.replace("__", "_1776_").lower() + ":latest"


def windows_fix_missing(python: str) -> bool:
    """True when the harness on native Windows still writes eval.sh with CRLFs (no newline="" on its write_text)."""
    if os.name != "nt":
        return False
    code = "import importlib.util as u;print(u.find_spec('swebench.harness.run_evaluation').origin)"
    path = subprocess.run([python, "-c", code], capture_output=True, text=True).stdout.strip()
    return 'newline=""' not in Path(path).read_text(encoding="utf-8")


def newest_report(logs: Path, run_id: str, instance_id: str) -> dict | None:
    found = sorted((logs / "run_evaluation" / run_id).glob(f"*/{instance_id}/report.json"), key=lambda p: p.stat().st_mtime)
    return json.loads(found[-1].read_text(encoding="utf-8"))[instance_id] if found else None


def summarize(report: dict | None, note: str = "") -> dict:
    if report is None:
        return {"status": "error", "resolved": False, "note": note or "no report.json"}
    if "tests_status" not in report:  # the harness writes a bare report when the run itself failed (e.g. test timeout); that is not a verdict
        return {"status": "error", "resolved": False, "note": note or "report without test results"}
    status = "resolved" if report["resolved"] else "infra_failure" if report.get("infra_failure") else "unresolved"
    return {"status": status, "resolved": bool(report["resolved"]), "patch_applied": report.get("patch_successfully_applied"), "note": note}


def grade(args) -> int:
    py, out = args.swebench_python, args.cwd
    out.mkdir(parents=True, exist_ok=True)
    if windows_fix_missing(py):
        raise SystemExit('the swebench harness on Windows needs `newline=""` on its eval.sh/patch.diff write_text calls (docs/notes/p5-t20.md); not applied in ' + py)
    ids = args.ids or ([json.loads(line)["instance_id"] for line in Path(args.predictions).read_text(encoding="utf-8").splitlines() if line.strip()]
                       if args.predictions != "gold" and Path(args.predictions).exists() else [t.id for t in load_subset()])
    summary_path = out / f"summary-{args.run_prefix}.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    env = {**os.environ, "PYTHONUTF8": "1"}
    for n, iid in enumerate(ids, 1):
        if summary.get(iid, {}).get("resolved") and not args.force:
            print(f"[{n}/{len(ids)}] {iid}: already resolved, skipped")
            continue
        run_id = f"{args.run_prefix}-{iid}"
        cmd = [py, "-m", "swebench.harness.run_evaluation", "--dataset_name", DATASET_V2, "--split", "dev", "--predictions_path", str(args.predictions),
               "--instance_ids", iid, "--max_workers", "1", "--run_id", run_id]
        if args.dry_run:
            print("docker pull", image_name(iid), "\n", " ".join(cmd))
            continue
        print(f"[{n}/{len(ids)}] {iid}: pulling and grading ...", flush=True)
        note = ""
        try:
            subprocess.run(["docker", "pull", "-q", image_name(iid)], check=True, capture_output=True, timeout=TIMEOUT_S)
            subprocess.run(cmd, cwd=out, env=env, check=True, capture_output=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            note = f"timed out after {TIMEOUT_S} s"
        except subprocess.CalledProcessError as exc:
            note = f"{exc.cmd[0]} exited {exc.returncode}: {(exc.stderr or b'').decode('utf-8', 'replace').strip().splitlines()[-1:]}"
        summary[iid] = summarize(newest_report(out / "logs", run_id, iid) if (out / "logs").exists() else None, note)
        summary_path.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
        print(f"    -> {summary[iid]['status']} {summary[iid]['note']}", flush=True)
        if args.remove_images:
            subprocess.run(["docker", "rmi", image_name(iid)], capture_output=True)
    if summary:
        print("\n| instance | status | note |\n|---|---|---|")
        print("\n".join(f"| {i} | {v['status']} | {v['note']} |" for i, v in summary.items()))
        done = sum(v["resolved"] for v in summary.values())
        print(f"\n{done}/{len(summary)} resolved; summary: {summary_path}")
    return 0


def add_cli(cmds) -> None:
    p = cmds.add_parser("grade", help="grade instances with the SWE-bench harness (gold or a predictions file), one at a time")
    p.add_argument("--swebench-python", default=sys.executable, help="python of the venv that has `swebench` installed")
    p.add_argument("--predictions", default="gold", help="'gold' or a predictions JSONL")
    p.add_argument("--ids", nargs="*", help="default: the whole subset (or the ids in the predictions file)")
    p.add_argument("--run-prefix", default="t20-gold", help="harness run ids are <prefix>-<instance id>")
    p.add_argument("--cwd", type=Path, default=Path("grading"), help="where logs/ and the summary are written (large; outside the repo)")
    p.add_argument("--force", action="store_true", help="redo instances already resolved in the summary")
    p.add_argument("--remove-images", action="store_true", help="docker rmi each image after grading to save disk")
    p.add_argument("--dry-run", action="store_true")
