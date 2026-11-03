"""P6-T21 break it: the worker is killed right after the PR is opened, before the step result is stored.

The kill is real: the T19 harness starts a child process running the DBOS workflow, the child stops
at `open-pr:pr-created` (the PR exists in the ledger, `open_pr_step` has not returned), and the harness
kills the process tree from outside. A second process then recovers the workflow. Four more tests cover
what the write-up claims: a lookup error leaves an existing PR alone (with `flow.fakes.FakeGitHub` and
with the whole workflow), and the code has no `closes #N` or commit-message search. Write-up:
docs/notes/p6-t21-break-it.md. The kill tests need `ARGUS_FLOW_DATABASE_URL`; the others do not.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import uuid
from pathlib import Path

import pytest
from dbos import DBOS

from flow.config import DATABASE_URL_ENV, FlowSettings
from flow.dbos_runtime import launch, shutdown
from flow.fakes import FakeGitHub
from flow.states import branch_name
from flow.workflow import Deps, PullRequest, find_or_create_pr, set_deps
from suspend_support import World

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "p6_t19_crash_recovery.py"
SRC = Path(__file__).resolve().parents[1] / "src" / "flow"
needs_postgres = pytest.mark.skipif(not os.environ.get(DATABASE_URL_ENV), reason=f"{DATABASE_URL_ENV} is not set; needs a real Postgres")


@pytest.fixture(scope="module")
def harness():
    spec = importlib.util.spec_from_file_location("p6_t19_crash_recovery", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def of(rows, op):
    return [r for r in rows if r["op"] == op]


@needs_postgres
def test_kill_after_the_pr_is_opened_restart_opens_no_second_pr(harness, tmp_path):
    r = harness.run_one("B", "open-pr:pr-created", tmp_path, keep_rows=True)
    rows, ticket = r["ledger"], r["ticket"]
    branch = branch_name(ticket)
    assert r["reached"] and r["completed"] and r["final_state"] == "done"
    # the kill came after the PR and before the step's result: verify is stored, open_pr_step is not
    assert r["stored_steps_at_kill"] == ["repro_step", "fix_step", "verify_step"]
    assert [x["op"] for x in rows[: r["rows_at_kill"]]] == [  # what exists when the process dies: three runs, the push, the lookup, the PR
        "dispatch-repro", "dispatch-fix", "dispatch-verify", "push-branch", "find-pr", "create-pr",
    ]
    # exactly one PR was made, and the restart never tried to make another: find-or-create found it
    assert [x["made"] for x in of(rows, "create-pr")] == [True]
    assert [x["made"] for x in of(rows, "find-pr")] == [False, False]  # one lookup before the kill (none), one after (found)
    assert r["duplicates"] == 0 and r["every_effect_once"]
    # the repeat at-least-once call is the step running again from its top: push_branch (found) and the lookup
    assert sorted(c.split()[0] for c in r["repeated_calls"]) == ["find-pr", "push-branch"]
    # one stable branch for every branch-keyed call
    assert {x["key"] for x in of(rows, "create-pr") + of(rows, "find-pr") + of(rows, "ready-pr")} == {branch}
    assert {x["branch"] for x in of(rows, "push-branch")} == {branch}


@needs_postgres
def test_the_pr_is_a_draft_until_the_qa_signal(harness, tmp_path):
    r = harness.run_one("B", "open-pr:pr-created", tmp_path, keep_rows=True)
    rows = r["ledger"]
    (created,) = [x for x in of(rows, "create-pr") if x["made"]]
    (ready,) = [x for x in of(rows, "ready-pr") if x["made"]]
    awaiting = next(x for x in of(rows, "label") if x["key"].endswith(":awaiting-qa") and x["made"])
    assert created["draft"] is True
    assert created["seq"] < awaiting["seq"] < ready["seq"]  # ready-for-review comes after the awaiting-qa label, and only then
    assert r["completed"]


def test_a_lookup_error_leaves_the_existing_pr_untouched():
    github, ticket = FakeGitHub(), "acme/web#21"
    opened = find_or_create_pr(github, ticket)
    assert opened.draft and github.calls.count("create_draft_pr") == 1
    before, prs = dict(github.prs), github.bodies.copy()
    github.lookup_error = RuntimeError("502 from GitHub")
    with pytest.raises(RuntimeError, match="502"):
        find_or_create_pr(github, ticket)
    assert github.calls.count("create_draft_pr") == 1  # an error is not "no PR": nothing was created
    assert github.prs == before and github.bodies == prs and github.closed == set()
    github.lookup_error = None
    assert find_or_create_pr(github, ticket) == opened  # and the next lookup finds the same PR


@pytest.fixture(scope="module")
def enqueuer():
    enq = launch(FlowSettings.from_env(), Deps(None, None, None, None))
    yield enq
    shutdown()


@needs_postgres
def test_a_lookup_error_in_the_workflow_ends_failed_and_the_pr_is_not_touched(enqueuer):
    ticket = f"acme/{uuid.uuid4().hex[:8]}#21"
    branch = branch_name(ticket)
    world = World()
    existing = PullRequest(7, "https://example.test/pr/7", True)
    world.github.prs[branch] = existing  # the PR a crashed run opened
    world.github.lookup_error = RuntimeError("502 from GitHub")
    set_deps(world.deps)
    out = enqueuer.enqueue(ticket).get_result()
    assert out["state"] == "failed" and "open_pr_step" in out["reason"]
    assert world.github.prs == {branch: existing}  # same PR, still a draft
    assert world.github.calls.count("create_draft_pr") == 0
    assert "ready_pr" not in world.github.calls and "close_pr" not in world.github.calls
    assert world.github.calls.count("find_pr") == 3  # the step's three attempts, each one raised
    assert len(DBOS.list_workflows(workflow_ids=[ticket])) == 1


def _code_strings(path: Path) -> list[str]:
    """String constants in the module that are not docstrings (comments are not in the AST at all)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]


def test_the_pr_lookup_has_no_closes_issue_or_commit_search_heuristic():
    closes = re.compile(r"\b(close[sd]?|fix(e[sd])?|resolve[sd]?)\s*:?\s*#(\d|\{)", re.I)
    found = [
        (p.name, s)
        for p in sorted(SRC.glob("*.py"))
        for s in _code_strings(p)
        if closes.search(s) or "/search/" in s or "search/commits" in s
    ]
    assert found == []
    # the lookup is by head branch: `GET /pulls?head=<owner>:<branch>&state=all` (flow.github_read), not by commit text
    assert '"head": f"{owner}:{branch}"' in (SRC / "github_read.py").read_text(encoding="utf-8")
