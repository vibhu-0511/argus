"""The CI job for the App (P8-T20) and the structural lint of the reusable workflow. YAML is parsed; nothing is run on GitHub.

`.github/workflows/app.yml` also runs the pinned `actionlint` (a container, so it is not run here); the checks in this file are the
ones that need no download and run in that job as well as on a laptop.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"
APP = WORKFLOWS / "app.yml"
REUSABLE = WORKFLOWS / "argus-reusable.yml"
UNTRUSTED = re.compile(r"github\.(event\.\S*(title|body|head_ref|label|comment|name|email|message)|head_ref)", re.IGNORECASE)


def load(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["on"] = doc.pop(True, doc.get("on"))  # PyYAML reads the key `on` as the boolean True
    return doc


def runs(doc: dict) -> list[str]:
    return [s["run"] for job in doc["jobs"].values() for s in job["steps"] if "run" in s]


def lint(doc: dict) -> list[str]:
    """Structural problems of a workflow: what a parser can see without actionlint."""
    problems = []
    if not doc.get("on"):
        problems.append("no trigger")
    if "permissions" not in doc:
        problems.append("no top-level permissions")
    for name, job in (doc.get("jobs") or {}).items():
        if "uses" not in job and "runs-on" not in job:
            problems.append(f"job {name}: no runs-on")
        for need in [job["needs"]] if isinstance(job.get("needs"), str) else job.get("needs", []):
            if need not in doc["jobs"]:
                problems.append(f"job {name}: needs {need}, which is not a job")
        for i, step in enumerate(job.get("steps", [])):
            if ("uses" in step) == ("run" in step):
                problems.append(f"job {name} step {i}: needs exactly one of uses and run")
            if "uses" in step and not re.search(r"@\S+$", step["uses"]):
                problems.append(f"job {name} step {i}: {step['uses']} is not pinned")
            for text in map(str, step.values()):
                if text.count("${{") != text.count("}}"):
                    problems.append(f"job {name} step {i}: unbalanced expression")
    return problems


# --- lint ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", [REUSABLE, APP], ids=lambda p: p.name)
def test_the_lint_passes_on_the_workflow_files(path):
    assert lint(load(path)) == []


def test_the_lint_is_not_vacuous():
    broken = {
        "on": {"push": None},
        "jobs": {
            "a": {"needs": "ghost", "steps": [{"run": "x", "uses": "actions/checkout@v4"}, {"uses": "actions/checkout"}, {"run": "${{ x }"}]},
        },
    }
    found = lint(broken)
    for part in ("no top-level permissions", "no runs-on", "ghost", "exactly one", "not pinned", "unbalanced"):
        assert any(part in p for p in found), part


# --- the shape of app.yml --------------------------------------------------------------------------------------------


def test_the_triggers_are_pull_request_push_with_paths_and_dispatch():
    on = load(APP)["on"]
    assert set(on) == {"push", "pull_request", "workflow_dispatch"}
    for event in ("push", "pull_request"):
        assert {"packages/app/**", ".github/workflows/app.yml", ".github/workflows/argus-reusable.yml", "uv.lock"} <= set(on[event]["paths"])


def test_the_token_is_read_only_everywhere():
    doc = load(APP)
    assert doc["permissions"] == {"contents": "read"}
    (job,) = doc["jobs"].values()
    assert "permissions" not in job and job["runs-on"] == "ubuntu-latest"
    for step in job["steps"]:
        if str(step.get("uses", "")).startswith("actions/checkout"):
            assert step["with"]["persist-credentials"] is False


def test_no_secret_is_named_and_no_model_or_github_token_is_set():
    text = APP.read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    for marker in ("secrets.", "ARGUS_MODEL_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "github.token", "inherit"):
        assert marker not in code, marker
    for marker in ("secrets.", "ARGUS_MODEL_API_KEY"):  # the repo secret scan (check_no_secrets.py) reads comments too
        assert marker not in text, marker


def test_the_flow_tests_get_a_postgres_service_with_a_health_check():
    (job,) = load(APP)["jobs"].values()
    pg = job["services"]["postgres"]
    assert pg["image"].startswith("postgres:") and "pg_isready" in pg["options"]
    assert job["env"]["ARGUS_FLOW_DATABASE_URL"].startswith("postgresql://postgres:")
    assert "localhost:5432" in job["env"]["ARGUS_FLOW_DATABASE_URL"]


def test_dependencies_are_installed_from_the_lock_before_any_test():
    (job,) = load(APP)["jobs"].values()
    commands = [s["run"] for s in job["steps"] if "run" in s]
    sync = next(i for i, c in enumerate(commands) if c.strip() == "uv sync --all-packages --locked")
    assert all("pytest" in c for c in commands[sync + 1 :])
    assert not any("pytest" in c for c in commands[:sync])


def test_the_job_names_the_four_checks_and_the_files_they_run_exist():
    commands = runs(load(APP))
    joined = "\n".join(commands)
    assert re.search(r"rhysd/actionlint:\d+\.\d+\.\d+ .*argus-reusable\.yml", joined)  # pinned, not "latest"
    assert "-k" in joined and all(n in joined for n in ("test_app_token", "test_installations", "test_intake"))  # minting and labels
    assert "test_tenant_ledger.py" in joined and "test_ledger.py" in joined  # the budget assertion (P8-T07 is kept)
    assert "pytest packages/app/tests" in joined
    for path in re.findall(r"packages/[\w./-]+", joined):
        assert (ROOT / path).exists(), path
    assert "latest" not in joined


def test_token_minting_tests_exist_where_the_job_looks_for_them():
    flow = ROOT / "packages" / "flow" / "tests"
    assert (flow / "test_app_token.py").exists() and (flow / "test_installations.py").exists()


# --- a title with a command in it is text ----------------------------------------------------------------------------


@pytest.mark.parametrize("path", [APP, REUSABLE], ids=lambda p: p.name)
def test_no_script_reads_an_event_field_directly(path):
    for script in runs(load(path)):
        assert "${{" not in script and not UNTRUSTED.search(script), script


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_a_title_with_a_command_substitution_is_not_executed_when_it_comes_through_env(tmp_path):
    marker = tmp_path / "ran"
    title = f"fix: $(touch '{marker.as_posix()}') `touch '{marker.as_posix()}'` ; touch '{marker.as_posix()}'"
    # the way a workflow step should take a title: an environment variable, quoted in the script
    out = subprocess.run(["sh", "-c", 'printf "%s" "$PR_TITLE"'], env={**os.environ, "PR_TITLE": title}, capture_output=True, text=True, check=True)
    assert out.stdout == title and not marker.exists()
