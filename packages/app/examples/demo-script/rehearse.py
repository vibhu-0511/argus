"""P8-T18 rehearsal: run the repro and verify steps of the tenant runner on a scratch copy of the demo shop, with a patch that
is handed over by hand (no model, no GitHub, no network). From the repo root:

    uv run --all-packages python packages/app/examples/demo-script/rehearse.py good   # the one-line fix: verify passes
    uv run --all-packages python packages/app/examples/demo-script/rehearse.py bad    # a plausible wrong fix: verify rejects it

Prints each step's exit code and its result.json. The scratch folder is removed at the end. Exit code: that of verify.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent / "demo-repo"
TICKET = {"issue": {"title": "Cart badge says 2 items", "body": "Two mugs and one sticker pack show 2 items, expected 3."}}


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def step(name: str, repo: Path, work: Path) -> int:
    env = {**os.environ, "ARGUS_TARGET_REPO": str(repo), "ARGUS_OUT": str(work / "out"), "ARGUS_STEP": name, "ARGUS_TICKET_ID": "demo/shop#1",
           "ARGUS_RUN_KEY": "argus:rehearsal:1", "GITHUB_EVENT_PATH": str(work / "event.json"), "ARGUS_START_TIMEOUT": "30"}
    code = subprocess.run([sys.executable, "-m", "argus_app.runner"], env=env).returncode
    print(f"== {name}: exit code {code}")
    print(json.dumps(json.loads((work / "out" / name / "result.json").read_text(encoding="utf-8")), indent=2))
    return code


def main(argv: list[str]) -> int:
    if argv not in (["good"], ["bad"]):
        print("usage: rehearse.py good|bad", file=sys.stderr)
        return 2
    work = Path(tempfile.mkdtemp(prefix="argus-rehearsal-"))
    try:
        repo = work / "repo"
        shutil.copytree(DEMO, repo, ignore=shutil.ignore_patterns("__pycache__"))
        git(repo, "init", "-q", "-b", "main")
        for key, value in (("user.name", "demo"), ("user.email", "demo@example.test"), ("core.autocrlf", "false")):
            git(repo, "config", key, value)
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "demo shop")
        (work / "event.json").write_text(json.dumps(TICKET), encoding="utf-8")
        step("repro", repo, work)  # the baseline: app up, routes answer, the tests already fail
        (work / "out" / "fix").mkdir(parents=True)
        shutil.copy(HERE / f"{argv[0]}.diff", work / "out" / "fix" / "patch.diff")  # stands in for the fix step
        print(f"== patch handed to verify ({argv[0]}.diff)")
        return step("verify", repo, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
