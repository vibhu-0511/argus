"""P8-T09: the PR carries the verdict, judge label, trajectory link and two screenshots; every clause of the task row has a test.

The real `flow.github_write.HttpGitHubClient` runs against the stateful `FakeGitHubApi` of the flow tests (an
httpx MockTransport): no network, no model. The links are made-up `https://artifacts.test/...` values given by the test;
the module never invents one. Not run against the real GitHub (docs/notes/p8-t09.md).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

def _load_fake():  # the shared fake of the flow tests, loaded by path so the two test folders do not shadow each other
    path = Path(__file__).resolve().parents[2] / "flow" / "tests" / "github_api_fake.py"
    spec = importlib.util.spec_from_file_location("github_api_fake", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["github_api_fake"] = module
    spec.loader.exec_module(module)
    return module


_fake = _load_fake()
PATCH, REPO, FakeGitHubApi = _fake.PATCH, _fake.REPO, _fake.FakeGitHubApi
from flow.app_token import InstallationToken  # noqa: E402
from flow.github_write import GitHubWriteError, HttpGitHubClient  # noqa: E402
from flow.installations import ScopedToken  # noqa: E402
from flow.states import branch_name  # noqa: E402

from argus_app.pr import Evidence, EvidenceError, creator_client, load_evidence, open_or_update_pr, pr_body  # noqa: E402

TICKET = "acme/shop#7"
APP_TOKEN = "app-installation-token-not-real"
TRAJ, BEFORE, AFTER = "https://artifacts.test/run/1/trajectory.jsonl", "https://artifacts.test/run/1/before.png", "https://artifacts.test/run/1/after.png"
SRC = Path(__file__).resolve().parents[2]


def evidence_dir(tmp_path: Path, *, ok: bool = True, judge: str | None = "pass", pngs: bool = True) -> Path:
    d = tmp_path / "verify"
    d.mkdir(exist_ok=True)
    verdict = {"ok": True} if ok else {"ok": False, "failed_check": "pixel", "first_failure": "changed 9% of pixels"}
    (d / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
    if judge:
        (d / "judge.json").write_text(json.dumps({"label": judge}), encoding="utf-8")
    if pngs:
        (d / "before.png").write_bytes(b"png-before")
        (d / "after.png").write_bytes(b"png-after")
    return d


def evidence(tmp_path: Path, **kw) -> Evidence:
    return load_evidence(evidence_dir(tmp_path, **kw), trajectory_url=TRAJ, before_url=BEFORE, after_url=AFTER)


@pytest.fixture
def api():
    return FakeGitHubApi()


@pytest.fixture
def client(api):
    return HttpGitHubClient(APP_TOKEN, REPO, transport=api.transport())


def writes(api: FakeGitHubApi) -> list[str]:
    return [line for line in api.log if not line.startswith("GET ")]


def test_the_body_has_verdict_judge_label_trajectory_and_two_screenshots(api, client, tmp_path):
    pr = open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path, judge="collateral"), issue_title="Button is cut off")
    assert pr is not None and pr.draft
    body = api.pulls[0]["body"]
    assert "| Verifier verdict | ok |" in body
    assert "| Judge label (advisory) | collateral |" in body
    assert f"[trajectory]({TRAJ})" in body
    assert f"![before]({BEFORE})" in body and f"![after]({AFTER})" in body
    assert body.count("![") == 2
    assert "closes #" not in body.lower() and "fixes #" not in body.lower()


def test_a_rejected_verdict_is_written_as_it_is(api, client, tmp_path):
    open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path, ok=False, judge="fail"))
    assert "| Verifier verdict | rejected (pixel: changed 9% of pixels) |" in api.pulls[0]["body"]


def test_a_missing_judge_or_screenshot_or_link_is_not_made_up(api, client, tmp_path):
    ev = load_evidence(evidence_dir(tmp_path, judge=None, pngs=False))
    open_or_update_pr(client, TICKET, PATCH, ev)
    body = api.pulls[0]["body"]
    assert "| Judge label (advisory) | not run |" in body and "| Trajectory | not available |" in body
    assert "![" not in body and "http" not in body
    assert "before screenshot: not available" in body and "after screenshot: not available" in body


def test_a_link_without_its_png_is_not_used(tmp_path):
    d = evidence_dir(tmp_path)
    (d / "after.png").unlink()
    ev = load_evidence(d, trajectory_url=TRAJ, before_url=BEFORE, after_url=AFTER)
    assert ev.before_url == BEFORE and ev.after_url is None


@pytest.mark.parametrize("bad", ["http://artifacts.test/a.png", "javascript:alert(1)", "https://x.test/a b.png", "https://x.test/a).png", 'https://x.test/a"onerror=x', "https://x.test/<img>", "/relative/path.png", ""])
def test_a_link_that_is_not_a_plain_https_url_is_refused(tmp_path, bad):
    with pytest.raises(EvidenceError):
        load_evidence(evidence_dir(tmp_path), before_url=bad)


def test_the_evidence_files_are_checked(tmp_path):
    with pytest.raises(EvidenceError):
        load_evidence(tmp_path / "nothing")
    (tmp_path / "verdict.json").write_text('{"ok": "yes"}')
    with pytest.raises(EvidenceError):
        load_evidence(tmp_path)
    (tmp_path / "b").mkdir()
    d = evidence_dir(tmp_path / "b", judge="great")
    with pytest.raises(EvidenceError):
        load_evidence(d)


# -- built through the API, nothing runs ----------------------------------------------------------------------


def test_title_and_body_are_json_fields_and_a_command_substitution_is_not_executed(api, client, tmp_path, monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("a process was started")

    for target in ("run", "Popen", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, target, forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(os, "popen", forbidden)
    monkeypatch.chdir(tmp_path)
    hostile = "$(touch PWNED); `touch PWNED2`; ${HOME}"
    ticket = f"acme/shop#7"
    title = f"Argus fix for {ticket}"
    open_or_update_pr(client, ticket, PATCH, evidence(tmp_path), issue_title=hostile)
    sent = next(r for r in api.requests if r.method == "POST" and r.url.path == f"/repos/{REPO}/pulls")
    assert sent.headers["content-type"] == "application/json"
    fields = json.loads(sent.content)
    assert set(fields) == {"title", "head", "base", "body", "draft"}
    assert fields["title"] == title and fields["draft"] is True
    assert "$(touch PWNED)" in fields["body"]  # kept as text, inside a code span
    assert not (tmp_path / "PWNED").exists() and not (tmp_path / "PWNED2").exists()


def test_a_title_with_a_command_substitution_in_the_ticket_id_is_text(api, tmp_path, monkeypatch):
    """The title is `Argus fix for <ticket id>`; a hostile id (a fixture, GitHub never gives one) stays a JSON string."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a process was started")))
    monkeypatch.chdir(tmp_path)
    ticket = f"{REPO}$(touch PWNED)#7"
    fake_client = HttpGitHubClient(APP_TOKEN, REPO, transport=api.transport())
    # push_branch checks the ticket id against the repo only for comments; a PR is keyed by the branch
    pr = open_or_update_pr(fake_client, ticket, PATCH, evidence(tmp_path))
    assert pr is not None
    assert api.pulls[0]["title"] == f"Argus fix for {ticket}" and "$(touch PWNED)" in api.pulls[0]["title"]
    assert not (tmp_path / "PWNED").exists()


def test_no_module_on_the_path_builds_a_command_line():
    for name in (SRC / "app" / "src" / "argus_app" / "pr.py", SRC / "flow" / "src" / "flow" / "github_write.py"):
        text = name.read_text(encoding="utf-8")
        for needle in ("subprocess", "os.system", "os.popen", "shell=", "eval(", "exec("):
            assert needle not in text.replace("`subprocess`", ""), f"{needle} in {name.name}"


def test_issue_title_cannot_break_out_of_the_code_span_or_leak_a_token(api, client, tmp_path):
    secret = "ghp_" + "a" * 30
    open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path), issue_title=f"x`\n| fake | row |\n@everyone {secret}")
    body = api.pulls[0]["body"]
    assert secret not in body
    issue_line = next(line for line in body.splitlines() if line.startswith("Issue: "))
    assert issue_line.count("`") == 2 and "\n" not in issue_line
    assert "| fake | row |" not in body.splitlines()


# -- one stable branch, one creator, draft ---------------------------------------------------------------------


def test_one_stable_branch_and_one_pr_across_runs(api, client, tmp_path):
    a = open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path))
    b = open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path))
    assert a.number == b.number == 1 and len(api.pulls) == 1
    assert sorted(api.refs) == sorted(["main", branch_name(TICKET)])
    assert api.pulls[0]["head"]["ref"] == branch_name(TICKET)
    assert api.count("POST /repos/acme/shop/pulls") == 1


def test_it_is_draft_and_never_marked_ready(api, client, tmp_path):
    open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path))
    open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path, judge="fail"))  # a re-run
    assert api.pulls[0]["draft"] is True
    assert api.count("POST /graphql") == 0


def test_every_call_is_made_by_the_one_creator_with_the_app_token(api, tmp_path, monkeypatch):
    for name in ("ARGUS_MODEL_API_KEY", "GITHUB_TOKEN", "GITHUB_WRITE_TOKEN"):
        monkeypatch.setenv(name, "agent-side-token-not-real")  # what the agent's environment could hold
    scoped = ScopedToken(InstallationToken(APP_TOKEN, "2099-01-01T00:00:00Z", {"contents": "write"}), "4242", 99, REPO)
    client = creator_client(scoped, transport=api.transport())
    open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path))
    open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path, judge="fail"))
    assert {r.headers["authorization"] for r in api.requests if r.url.path != "/graphql"} == {f"Bearer {APP_TOKEN}"}
    assert APP_TOKEN not in repr(client) and "agent-side-token-not-real" not in repr(client)


def test_the_agent_code_cannot_write_to_github():
    """The fix loop and the repro agent have no GitHub write code and no GitHub token: the PR is not the agent's."""
    for package in ("fix-loop/src", "repro-agent/src"):
        for path in (SRC / package).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for needle in ("api.github.com", "create_draft_pr", "github_write", "GITHUB_WRITE_TOKEN", "/pulls"):
                assert needle not in text, f"{needle} in {path}"


# -- no PR, lookup error, re-run ------------------------------------------------------------------------------


@pytest.mark.parametrize("patch", ["", "   \n\t\n"])
def test_no_pr_when_the_patch_is_empty(api, client, tmp_path, patch):
    assert open_or_update_pr(client, TICKET, patch, evidence(tmp_path)) is None
    assert api.log == [] and api.pulls == []  # not one call, not even a lookup


def test_an_empty_patch_leaves_an_existing_pr_alone(api, client, tmp_path):
    open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path))
    before, log = dict(api.pulls[0]), len(api.log)
    assert open_or_update_pr(client, TICKET, "", evidence(tmp_path, judge="fail")) is None
    assert api.pulls[0] == before and len(api.log) == log


def test_a_lookup_error_creates_nothing_and_touches_nothing(api, client, tmp_path):
    api.fail[("GET", f"/repos/{REPO}/pulls")] = 502
    with pytest.raises(GitHubWriteError, match="502"):
        open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path))
    assert writes(api) == [] and api.pulls == [] and list(api.refs) == ["main"]  # no PR, no branch


def test_a_lookup_error_leaves_the_existing_pr_untouched(api, client, tmp_path):
    open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path))
    before, refs, mark = dict(api.pulls[0]), dict(api.refs), len(api.log)
    api.fail[("GET", f"/repos/{REPO}/pulls")] = 500
    with pytest.raises(GitHubWriteError):
        open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path, judge="fail"))
    assert api.pulls == [before] and api.refs == refs
    assert writes(api)[len([line for line in api.log[:mark] if not line.startswith("GET ")]) :] == []  # nothing written after the error


def test_a_rerun_updates_the_same_pr(api, client, tmp_path):
    first = open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path, judge="pass"))
    second = open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path, judge="collateral"))
    assert first.number == second.number == 1 and len(api.pulls) == 1
    assert "| Judge label (advisory) | collateral |" in api.pulls[0]["body"]
    assert api.count("PATCH /repos/acme/shop/pulls/1") == 1


def test_a_rerun_with_the_same_evidence_writes_nothing(api, client, tmp_path):
    open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path))
    mark = len(writes(api))
    open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path))
    assert len(writes(api)) == mark


def test_a_closed_pr_is_not_edited_or_reopened(api, client, tmp_path):
    open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path))
    api.pulls[0]["state"] = "closed"
    before = dict(api.pulls[0])
    pr = open_or_update_pr(client, TICKET, PATCH, evidence(tmp_path, judge="fail"))
    assert pr.number == 1 and api.pulls == [before]


def test_the_body_text_function_is_plain_text():
    body = pr_body(TICKET, "t", Evidence(True, "", "pass", None, None, None))
    assert body.endswith("\n") and "\r" not in body
