"""The demo repo for P8-T16 (`packages/app/examples/demo-repo`): the folder is a valid Argus tenant, the bug is real and one
line fixes it. Nothing here touches GitHub or a model. The real install and the real issue are owner steps."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from argus_app.config import load_config
from argus_app.runner import build_steps, run

DEMO = Path(__file__).parents[1] / "examples" / "demo-repo"
SCRIPT = Path(__file__).parents[1] / "examples" / "demo-script"  # P8-T18 rehearsal files
TICKET = "acme/demo#1"
BUG, FIX = "count = len(cart)", "count = sum(qty for _, qty in cart)"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True).stdout.decode("utf-8")


def copy(tmp_path: Path) -> Path:
    shutil.copytree(DEMO, tmp_path, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def unittest_run(repo: Path) -> subprocess.CompletedProcess:
    assert load_config(repo).test == "python -m unittest discover -s tests -p \"check_*.py\""  # run here without a shell
    return subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "check_*.py"], cwd=repo, capture_output=True, text=True)


def test_the_folder_validates_as_a_tenant_config():
    config = load_config(DEMO)
    assert config.routes == ["/", "/cart"] and config.base_url == "http://127.0.0.1:18770"
    assert config.start.endswith("18770") and config.budget.max_steps > 0


def test_the_tenant_workflow_is_the_five_line_caller():
    caller = (DEMO / ".github" / "workflows" / "argus.yml").read_text(encoding="utf-8")
    assert caller == (DEMO.parent.parent / "docs" / "tenant-workflow.yml").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert len(caller.splitlines()) == 5 and "argus-reusable.yml" in caller


def test_the_issue_template_is_a_labelled_bug():
    template = (DEMO / ".github" / "ISSUE_TEMPLATE" / "bug.md").read_text(encoding="utf-8")
    assert template.startswith("---\n") and "labels: bug" in template


def test_the_folder_holds_only_made_up_public_code():
    for f in DEMO.rglob("*"):
        assert f.suffix in ("", ".py", ".yml", ".md"), f  # no images, binaries or archives
    text = " ".join(f.read_text(encoding="utf-8").lower() for f in DEMO.rglob("*") if f.is_file())
    for needle in ("dcortex", "ghp_", "-----begin", "api_key=", "password"):
        assert needle not in text, needle


def test_the_seeded_bug_fails_the_tests_and_one_line_fixes_it(tmp_path):
    repo = copy(tmp_path)
    broken = unittest_run(repo)
    assert broken.returncode != 0 and "test_badge_counts_items_not_lines" in broken.stderr and "2 items" in broken.stderr
    page = repo / "shopsite" / "pages.py"
    page.write_text(page.read_text(encoding="utf-8").replace(BUG, FIX), encoding="utf-8")
    fixed = unittest_run(repo)
    assert fixed.returncode == 0, fixed.stderr


def test_repro_fix_and_verify_run_on_the_demo_with_a_fake_fix_agent(tmp_path):
    repo = copy(tmp_path / "repo")
    git(repo, "init", "-q")
    for k, v in (("core.autocrlf", "false"), ("user.name", "t"), ("user.email", "t@example.test")):
        git(repo, "config", k, v)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "demo")
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"issue": {"title": "Cart badge says 2 items", "body": "two mugs and a sticker pack"}}), encoding="utf-8")
    keep = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA")
    base = {k: v for k, v in os.environ.items() if k.upper() in keep}

    def fixer(tree, job, config, ticket):
        page = tree / "shopsite" / "pages.py"
        page.write_bytes(page.read_bytes().replace(BUG.encode(), FIX.encode()))
        return "submit", '{"step": 0}\n'

    out = {}
    for step in ("repro", "fix", "verify"):
        env = {**base, "ARGUS_TARGET_REPO": str(repo), "ARGUS_OUT": str(tmp_path / "out"), "ARGUS_STEP": step, "ARGUS_TICKET_ID": TICKET,
               "ARGUS_RUN_KEY": "argus:demo:1", "GITHUB_EVENT_PATH": str(event), "ARGUS_START_TIMEOUT": "20"}
        assert run(env, build_steps(env, fixer)) == 0, step
        out[step] = json.loads((tmp_path / "out" / step / "result.json").read_text(encoding="utf-8"))
    assert "routes answered: /, /cart" in out["repro"]["output"] and "exited 1" in out["repro"]["output"]  # the bug is seen
    assert BUG in out["fix"]["output"] and FIX in out["fix"]["output"]
    assert out["verify"]["ok"] and "exited 0" in out["verify"]["output"]


def test_the_rehearsal_patches_apply_and_one_fixes_the_bug_and_one_does_not(tmp_path):
    for name, passes in (("good", True), ("bad", False)):
        repo = copy(tmp_path / name)
        subprocess.run(["git", "apply", str(SCRIPT / f"{name}.diff")], cwd=repo, check=True, capture_output=True)  # works outside a repo too
        assert (unittest_run(repo).returncode == 0) is passes, name


def test_the_quota_rehearsal_refuses_before_a_second_request_is_sent():
    out = subprocess.run([sys.executable, str(SCRIPT / "quota_refusal.py")], capture_output=True, text=True, check=True).stdout
    assert "REFUSED before sending" in out and out.count("call allowed") >= 1
    refused = [line for line in out.splitlines() if "REFUSED" in line]
    assert all("requests sent so far: 1)" in line for line in refused[:1])  # nothing was sent for the refused call
