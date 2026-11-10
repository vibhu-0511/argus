"""The target-agnostic runner (P8-T06). The second repo is a real tiny app started and tested for real; no model is called and
no dcortex checkout is needed (its config is only loaded and planned)."""
import ast
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from argus_app import runner
from argus_app.config import load_config
from argus_app.runner import build_steps, main, plan, read_ticket, run
from flow.agent_job import StepUnavailable

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).parent / "fixtures" / "second-repo"
DCORTEX = ROOT / "config" / "dcortex.argus.yml"
TICKET = "acme/tiny#1"
KEY = "fake-model-key-for-tests-0123456789"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True).stdout.decode("utf-8")


def make_repo(tmp_path: Path, sub: str = "", broken: bool = True, crlf: bool = False) -> Path:
    """The fixture as a git repo; with `sub`, as that folder of a bigger repo. `broken` commits a typo on top (the bug to fix).
    Returns the folder the config is in."""
    shutil.copytree(FIXTURE, tmp_path / sub, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    if crlf:  # a repo whose files have Windows line ends: no .gitattributes, every text file rewritten
        (tmp_path / sub / ".gitattributes").unlink()
        for f in (tmp_path / sub).rglob("*"):
            if f.is_file():
                f.write_bytes(f.read_bytes().replace(b"\n", b"\r\n"))
    git(tmp_path, "init", "-q")
    for k, v in (("core.autocrlf", "false"), ("user.name", "t"), ("user.email", "t@example.test")):
        git(tmp_path, "config", k, v)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "fixture")
    if broken:
        page = tmp_path / sub / "tinysite" / "pages.py"
        page.write_bytes(page.read_bytes().replace(b"Hello", b"Helo"))
        git(tmp_path, "commit", "-qam", "typo")
    return tmp_path / sub


def set_config(repo: Path, **change) -> None:
    config = {**yaml.safe_load((repo / ".argus.yml").read_text(encoding="utf-8")), **change}
    (repo / ".argus.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    git(repo, "commit", "-qam", "config")


def env_for(tmp_path: Path, repo: Path, step: str, **extra: str) -> dict[str, str]:
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"issue": {"title": "Home page says Helo", "body": "typo"}}), encoding="utf-8")
    base = {k: v for k, v in os.environ.items() if k.upper() in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA")}
    return {**base, "ARGUS_TARGET_REPO": str(repo), "ARGUS_OUT": str(tmp_path / "out"), "ARGUS_STEP": step, "ARGUS_TICKET_ID": TICKET,
            "ARGUS_RUN_KEY": "argus:test:1", "GITHUB_EVENT_PATH": str(event), "ARGUS_START_TIMEOUT": "20", **extra}


def result(tmp_path: Path, step: str) -> dict:
    return json.loads((tmp_path / "out" / step / "result.json").read_text(encoding="utf-8"))


def fixer(seen: list | None = None):
    """A fix agent that makes the real fix, like the model should: no model call."""
    def agent(tree, job, config, ticket):
        if seen is not None:
            seen.append((tree, config, ticket, job.upstream))
        page = tree / "tinysite" / "pages.py"
        page.write_bytes(page.read_bytes().replace(b"Helo", b"Hello"))
        return "submit", '{"step": 0}\n'
    return agent


# --- one runner, two configs ----------------------------------------------------------------------------------------


def test_the_same_code_plans_both_targets_from_their_configs():
    dcortex, second = plan(load_config(DCORTEX)), plan(load_config(FIXTURE))
    assert "route: http://localhost:19080/ops/radar" in dcortex and "start: docker compose --profile copa-local up --build" in dcortex
    assert "route: http://127.0.0.1:18765/about" in second and "start: python -m tinysite 18765" in second
    assert not set(dcortex) & {ln for ln in second if ln.startswith(("start", "route"))}  # nothing is shared


def test_the_dcortex_routes_are_the_flows_in_config_platform_md():
    platform = (ROOT / "config" / "platform.md").read_text(encoding="utf-8")
    for route in load_config(DCORTEX).routes:
        assert route.split("?")[0] in platform, route


def test_the_runner_source_names_no_repo_command_port_or_route():
    tree = ast.parse(Path(runner.__file__).read_text(encoding="utf-8"))
    docstrings = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, ast.Module | ast.FunctionDef | ast.ClassDef) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    literals = " ".join(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings).lower()
    for needle in ("dcortex", "canvas", "vite", "pnpm", "npm", "docker", "/ops/", "/login", "19080", "18765", "tinysite", "argus_platform_repo"):
        assert needle not in literals, needle


# --- repro, fix and verify on the second repo, for real -------------------------------------------------------------


@pytest.mark.parametrize("sub, crlf", [("", False), ("apps/site", False), ("", True)])
def test_repro_fix_and_verify_run_on_the_second_repo(tmp_path, sub, crlf):
    repo = make_repo(tmp_path, sub, crlf=crlf)
    seen: list = []
    for step in ("repro", "fix", "verify"):
        env = env_for(tmp_path, repo, step)
        assert run(env, build_steps(env, fixer(seen))) == 0, (step, result(tmp_path, step))
    repro, fix, verify = (result(tmp_path, s) for s in ("repro", "fix", "verify"))
    assert repro["ok"] and "routes answered: /, /about" in repro["output"] and "exited 1" in repro["output"]  # the bug is seen
    patch = (tmp_path / "out" / "fix" / "patch.diff").read_bytes().decode("utf-8")
    assert "-PAGES" in patch and "+PAGES" in patch and "Hello from tinysite" in patch
    assert ("\r\n" in patch) == crlf  # the patch keeps the line ends of the file it changes
    assert fix == {"ok": True, "output": patch}
    assert verify["ok"] and "exited 0" in verify["output"]
    tree, config, ticket, upstream = seen[0]
    assert config.budget.max_steps == 10 and ticket.startswith("Home page says Helo") and "exited 1" in upstream  # baseline handed to fix
    assert (tmp_path / "out" / "verify" / "upstream.txt").read_bytes().decode("utf-8") == patch  # patch handed to verify
    assert git(tmp_path, "worktree", "list").count("\n") == 1  # every worktree is removed again
    assert (repo / "tinysite" / "pages.py").read_text(encoding="utf-8").count("Helo") == 1  # the checkout itself is untouched


def test_verify_fails_when_the_patch_does_not_fix_it(tmp_path):
    repo = make_repo(tmp_path)
    page = repo / "tinysite" / "pages.py"
    page.write_text(page.read_text(encoding="utf-8").replace("About tinysite", "About us"), encoding="utf-8")
    patch = git(repo, "diff")
    git(repo, "checkout", "--", ".")
    env = env_for(tmp_path, repo, "verify")
    (tmp_path / "out" / "fix").mkdir(parents=True)
    (tmp_path / "out" / "fix" / "patch.diff").write_bytes(patch.encode("utf-8"))
    assert run(env) == 1
    assert "exited 1" in result(tmp_path, "verify")["output"]


def test_a_patch_that_edits_argus_yml_cannot_change_the_commands_verify_runs(tmp_path):
    repo = make_repo(tmp_path)
    (repo / ".argus.yml").write_text((repo / ".argus.yml").read_text(encoding="utf-8").replace("check_*.py", "none_*.py").replace("unittest discover", "unittest discover -v"), encoding="utf-8")
    patch = git(repo, "diff")
    git(repo, "checkout", "--", ".")
    (tmp_path / "out" / "fix").mkdir(parents=True)
    (tmp_path / "out" / "fix" / "patch.diff").write_bytes(patch.encode("utf-8"))
    assert run(env_for(tmp_path, repo, "verify")) == 1  # the original command still runs the failing check
    assert "exited 1" in result(tmp_path, "verify")["output"]


def test_a_patch_that_does_not_apply_fails_verify_with_the_reason(tmp_path):
    repo = make_repo(tmp_path)
    (tmp_path / "out" / "fix").mkdir(parents=True)
    (tmp_path / "out" / "fix" / "patch.diff").write_text("diff --git a/nope b/nope\n--- a/nope\n+++ b/nope\n@@ -1 +1 @@\n-a\n+b\n", encoding="utf-8")
    assert run(env_for(tmp_path, repo, "verify")) == 1
    assert "the patch does not apply" in result(tmp_path, "verify")["output"]


def test_verify_with_no_patch_checks_the_checkout_as_it_is(tmp_path):
    assert run(env_for(tmp_path, make_repo(tmp_path, broken=False), "verify")) == 0  # the fixture is correct as committed (the self-test run)
    assert "exited 0" in result(tmp_path, "verify")["output"]
    broken = tmp_path / "again"
    broken.mkdir()
    assert run(env_for(broken, make_repo(broken), "verify")) == 1  # with the typo on top it fails
    assert "exited 1" in result(broken, "verify")["output"]


# --- failures are results, not crashes ------------------------------------------------------------------------------


def test_a_start_command_that_exits_is_a_failed_baseline_with_its_output(tmp_path):
    repo = make_repo(tmp_path)
    set_config(repo, start='python -c "print(\'boom on start\')"')
    assert run(env_for(tmp_path, repo, "repro")) == 1
    out = result(tmp_path, "repro")["output"]
    assert "exited with code 0 before the app answered" in out and "boom on start" in out


def test_a_route_that_never_answers_is_named(tmp_path):
    repo = make_repo(tmp_path)
    set_config(repo, routes=["/", "/missing"])
    assert run(env_for(tmp_path, repo, "repro", ARGUS_START_TIMEOUT="3")) == 1
    assert "/missing" in result(tmp_path, "repro")["output"] and "status 404" in result(tmp_path, "repro")["output"]


def test_a_missing_test_command_is_the_typed_error_in_the_result(tmp_path):
    repo = make_repo(tmp_path)
    config = yaml.safe_load((repo / ".argus.yml").read_text(encoding="utf-8"))
    del config["test"]
    (repo / ".argus.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    assert run(env_for(tmp_path, repo, "verify")) == 1
    assert result(tmp_path, "verify")["output"] == "MissingFieldError: .argus.yml: missing required field 'test' (the test command)"


def test_no_argus_yml_is_a_failure_result(tmp_path):
    repo = make_repo(tmp_path)
    git(repo, "rm", "-q", ".argus.yml")
    git(repo, "commit", "-qm", "rm")
    assert run(env_for(tmp_path, repo, "repro")) == 1
    assert result(tmp_path, "repro")["output"].startswith("ConfigNotFoundError: .argus.yml: file not found")


def test_the_model_key_never_reaches_the_tenants_own_commands(tmp_path):
    repo = make_repo(tmp_path)
    set_config(repo, test="python -c \"import os, sys; sys.exit(3 if 'ARGUS_MODEL_API_KEY' in os.environ else 0)\"")
    env = env_for(tmp_path, repo, "verify", ARGUS_MODEL_API_KEY=KEY)
    assert run(env) == 0 and "exited 0" in result(tmp_path, "verify")["output"]


def test_fix_without_a_ticket_is_a_failure_result(tmp_path):
    repo = make_repo(tmp_path)
    env = {k: v for k, v in env_for(tmp_path, repo, "fix").items() if k != "GITHUB_EVENT_PATH"}
    assert run(env, build_steps(env, fixer())) == 1
    assert "no ticket" in result(tmp_path, "fix")["output"]


def test_the_ticket_comes_from_the_event_payload(tmp_path):
    event = tmp_path / "e.json"
    event.write_text(json.dumps({"issue": {"title": "T", "body": None}}), encoding="utf-8")
    assert read_ticket({"GITHUB_EVENT_PATH": str(event)}) == "T\n\n"
    event.write_text(json.dumps({"pull_request": {}}), encoding="utf-8")
    with pytest.raises(StepUnavailable, match="no issue"):
        read_ticket({"GITHUB_EVENT_PATH": str(event)})


def test_the_command_line(capsys):
    assert main(["plan", str(FIXTURE)]) == 0
    assert "start: python -m tinysite 18765" in capsys.readouterr().out
    assert main(["bogus"]) == 2
