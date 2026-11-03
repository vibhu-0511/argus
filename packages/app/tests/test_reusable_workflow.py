"""The reusable workflow and the five-line tenant workflow (P8-T04). YAML is parsed; nothing is run."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "argus-reusable.yml"
TENANT = ROOT / "packages" / "app" / "docs" / "tenant-workflow.yml"
MODEL_KEY = "ARGUS_MODEL_API_KEY"
AGENT = re.compile(r"flow\.agent_job|argus_app\.runner")  # the commands that run the agent


def load(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["on"] = doc.pop(True, doc.get("on"))  # PyYAML reads the key `on` as the boolean True
    return doc


def code() -> str:
    """The workflow text without its comment lines (the comments say what is not done)."""
    return "\n".join(ln for ln in WORKFLOW.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("#"))


def steps(doc: dict):
    for job in doc["jobs"].values():
        yield from ((job, step) for step in job["steps"])


def agent_steps(doc: dict) -> list[tuple[dict, dict]]:
    return [(job, s) for job, s in steps(doc) if AGENT.search(s.get("run", ""))]


def env_of(doc: dict, job: dict, step: dict) -> dict:
    """What the step's process sees from the workflow file: workflow, job and step `env`, the last one wins."""
    return {**(doc.get("env") or {}), **(job.get("env") or {}), **(step.get("env") or {})}


def test_it_is_a_reusable_workflow_and_runs_repro_fix_and_verify():
    doc = load(WORKFLOW)
    assert "workflow_call" in doc["on"]
    named = {s["env"]["ARGUS_STEP"] for _, s in agent_steps(doc)}
    assert named == {"repro", "fix", "verify"}


def test_the_agent_step_environment_has_no_github_token():
    doc = load(WORKFLOW)
    found = agent_steps(doc)
    assert len(found) == 3
    for job, step in found:
        env = env_of(doc, job, step)
        assert not {k for k in env if k.upper() in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT")}
        for value in env.values():
            assert "github.token" not in str(value) and "GITHUB_TOKEN" not in str(value)


def test_no_token_reaches_the_agent_through_a_checkout_either():
    doc = load(WORKFLOW)
    checkouts = [s for _, s in steps(doc) if str(s.get("uses", "")).startswith("actions/checkout")]
    assert len(checkouts) == 2
    for step in checkouts:  # without this the clone keeps the token in .git/config, where the agent step can read it
        assert step["with"]["persist-credentials"] is False
        assert "token" not in step["with"]


def test_permissions_are_minimal():
    doc = load(WORKFLOW)
    assert doc["permissions"] == {"contents": "read"}
    for job in doc["jobs"].values():
        assert job.get("permissions", {"contents": "read"}) == {"contents": "read"}


def test_the_only_secret_is_the_tenants_model_key_and_only_the_fix_step_gets_it():
    text = code()
    assert set(re.findall(r"secrets\.([A-Za-z0-9_]+)", text)) == {MODEL_KEY}
    assert "inherit" not in text
    doc = load(WORKFLOW)
    assert list(doc["on"]["workflow_call"]["secrets"]) == [MODEL_KEY]
    holders = {s["env"]["ARGUS_STEP"] for j, s in agent_steps(doc) if MODEL_KEY in env_of(doc, j, s)}
    assert holders == {"fix"}


def test_nothing_in_the_workflow_pushes():
    text = code()
    assert not re.search(r"git (push|remote)|gh pr |pull-requests|contents: write", text)


def test_the_pull_request_trigger_is_limited_to_the_workflow_file():
    assert load(WORKFLOW)["on"]["pull_request"]["paths"] == [".github/workflows/argus-reusable.yml"]


def test_inputs_reach_the_shell_through_env_not_through_the_script():
    for _, step in steps(load(WORKFLOW)):
        assert "${{" not in step.get("run", ""), step.get("name")


# --- the tenant's workflow ---------------------------------------------------------------------------------------


def test_the_tenant_workflow_is_five_lines_and_calls_the_reusable_workflow():
    text = TENANT.read_text(encoding="utf-8")
    assert len([ln for ln in text.splitlines() if ln.strip()]) == 5
    doc = load(TENANT)
    (job,) = doc["jobs"].values()
    repo, _, rest = job["uses"].partition("/.github/workflows/")
    file, _, ref = rest.partition("@")
    assert repo.count("/") == 1 and ref and (ROOT / ".github" / "workflows" / file) == WORKFLOW


def test_the_tenant_passes_one_named_secret_and_no_permission_or_inherit():
    (job,) = load(TENANT)["jobs"].values()
    assert job["secrets"] == {MODEL_KEY: "${{ secrets.%s }}" % MODEL_KEY}
    assert set(job) == {"uses", "secrets"}


def test_the_steps_run_the_tenant_config_runner_on_the_tenants_checkout():
    doc = load(WORKFLOW)
    assert all("argus_app.runner" in s["run"] for _, s in agent_steps(doc))
    assert "flow.agent_job" not in code()  # the seeded-task entry point is not what a tenant run uses
    assert doc["jobs"]["run"]["env"]["ARGUS_TARGET_REPO"].endswith("format('{0}/target', github.workspace) }}")
