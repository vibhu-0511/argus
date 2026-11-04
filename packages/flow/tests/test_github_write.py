"""The GitHub write client against a stateful fake GitHub over `httpx.MockTransport`. No network.

Covers the repeat-call cases (every method called twice changes nothing the second time), the 422 race
on create, a lookup error, the draft rule, no closing keyword, and the token staying out of exceptions,
reprs and logs. The whole workflow with this client is in `test_github_write_workflow.py`.
"""

from __future__ import annotations

import logging
import re

import httpx
import pytest

from flow.github_write import GitHubWriteError, HttpGitHubClient
from flow.states import branch_name, comment_marker, effect_key
from flow.workflow import PullRequest, find_or_create_pr
from github_api_fake import NEW_FILES, PATCH, REPO, FakeGitHubApi

TOKEN = "ghp_write-token-not-real-7c1e"
TICKET = f"{REPO}#7"
BRANCH = branch_name(TICKET)
KEY = effect_key(TICKET, "push-branch")
CLOSING = re.compile(r"\b(close[sd]?|fix(es|ed)?|resolve[sd]?)\b\s+#\d+", re.I)


@pytest.fixture
def api():
    return FakeGitHubApi(leak=TOKEN)


@pytest.fixture
def client(api):
    return HttpGitHubClient(TOKEN, REPO, transport=api.transport())


# -- push ------------------------------------------------------------------------------------


def test_push_makes_the_branch_with_one_patch_commit_keyed_by_the_trailer(client, api):
    client.push_branch(BRANCH, PATCH, KEY)
    assert api.files_at(BRANCH) == NEW_FILES
    commit = api.commits[api.refs[BRANCH]]
    assert commit["parents"] == ["c0"] and f"Argus-Key: {KEY}" in commit["message"].splitlines()
    assert api.refs["main"] == "c0"  # the default branch is not touched


def test_pushing_the_same_key_again_changes_nothing(client, api):
    client.push_branch(BRANCH, PATCH, KEY)
    writes = sum(r.method != "GET" for r in api.requests)
    head = api.refs[BRANCH]
    client.push_branch(BRANCH, PATCH, KEY)
    assert api.refs[BRANCH] == head and len(api.commits) == 2
    assert sum(r.method != "GET" for r in api.requests) == writes, "the repeat made no write"


def test_a_branch_without_the_key_gets_the_patch_on_top_and_is_never_forced(client, api):
    api.refs[BRANCH] = "c0"  # someone made the branch first
    client.push_branch(BRANCH, PATCH, KEY)
    assert api.commits[api.refs[BRANCH]]["parents"] == ["c0"]
    (patch_call,) = [r for r in api.requests if r.method == "PATCH"]
    assert b'"force":false' in patch_call.content.replace(b" ", b"")


def test_the_file_mode_of_the_diff_is_kept(client, api):
    client.push_branch(BRANCH, PATCH.replace("100644 \n", "100755 \n").replace("index 111..222 100644", "index 111..222 100755"), KEY)
    assert api.modes["src/a.py"] == "100755" and api.modes["docs/new.md"] == "100644"


def test_a_patch_that_does_not_apply_writes_nothing(client, api):
    api.trees["t0"]["src/a.py"] = "x = 99\n"
    with pytest.raises(GitHubWriteError, match="cannot apply the patch"):
        client.push_branch(BRANCH, PATCH, KEY)
    assert BRANCH not in api.refs and len(api.commits) == 1 and api.count("POST") == 0


# -- pull request ----------------------------------------------------------------------------


def test_find_is_none_before_and_the_pr_after_create_and_create_is_a_draft_with_the_default_base(client, api):
    assert client.find_pr(BRANCH) is None
    pr = client.create_draft_pr(BRANCH, "Argus fix for acme/shop#7", "Draft fix, awaiting QA.")
    assert pr == PullRequest(1, f"https://github.test/{REPO}/pull/1", True)
    assert client.find_pr(BRANCH) == pr
    assert (api.pulls[0]["draft"], api.pulls[0]["base"]) == (True, "main")


def test_find_or_create_twice_makes_one_pr(client, api):
    first = find_or_create_pr(client, TICKET)
    again = find_or_create_pr(client, TICKET)
    assert first == again and len(api.pulls) == 1 and api.count("POST /repos/acme/shop/pulls") == 1


def test_find_sees_a_closed_pr_so_a_second_one_is_not_made(client, api):
    api.add_pr(BRANCH, state="closed")
    assert find_or_create_pr(client, TICKET).number == 1
    assert len(api.pulls) == 1 and api.count("POST /repos/acme/shop/pulls") == 0


def test_a_422_on_create_looks_the_pr_up_again_and_returns_it(client, api):
    pr = api.add_pr(BRANCH)  # a racing worker made it between our find and our create
    api.stale_pull_lists = 1  # our find did not see it yet
    got = find_or_create_pr(client, TICKET)
    assert got.number == pr["number"] and len(api.pulls) == 1
    assert api.count("POST /repos/acme/shop/pulls") == 1 and api.count("GET /repos/acme/shop/pulls") == 2


def test_a_422_with_no_pr_to_find_raises_instead_of_pretending(client, api):
    api.fail[("POST", f"/repos/{REPO}/pulls")] = 422
    with pytest.raises(GitHubWriteError, match="422 and no PR"):
        client.create_draft_pr(BRANCH, "t", "b")


def test_a_lookup_error_leaves_the_existing_pr_alone_and_creates_nothing(client, api):
    api.add_pr(BRANCH)
    api.fail[("GET", f"/repos/{REPO}/pulls")] = 500
    with pytest.raises(GitHubWriteError, match="500"):
        find_or_create_pr(client, TICKET)
    assert api.count("POST") == 0 and api.count("PATCH") == 0
    assert len(api.pulls) == 1 and api.pulls[0]["draft"] and api.pulls[0]["state"] == "open"


def test_ready_marks_a_draft_once_and_a_repeat_skips(client, api):
    api.add_pr(BRANCH)
    client.ready_pr(BRANCH)
    assert api.pulls[0]["draft"] is False
    client.ready_pr(BRANCH)
    assert api.count("POST /graphql") == 1


def test_a_graphql_error_in_a_200_answer_is_an_error_without_the_token(client, api):
    api.add_pr(BRANCH)
    api.graphql_error = f"denied for {TOKEN}"
    with pytest.raises(GitHubWriteError, match="markPullRequestReadyForReview") as e:
        client.ready_pr(BRANCH)
    assert TOKEN not in str(e.value) and api.pulls[0]["draft"]


def test_close_closes_once_and_a_repeat_skips(client, api):
    api.add_pr(BRANCH)
    client.close_pr(BRANCH)
    client.close_pr(BRANCH)
    assert api.pulls[0]["state"] == "closed" and api.count("PATCH /repos/acme/shop/pulls") == 1


def test_update_pr_edits_an_open_pr_once_and_leaves_a_closed_one(client, api):
    client.create_draft_pr(BRANCH, "t", "b1")
    assert client.update_pr(BRANCH, "t", "b2").number == 1
    client.update_pr(BRANCH, "t", "b2")  # unchanged: no second write
    assert api.pulls[0]["body"] == "b2" and api.pulls[0]["draft"] is True and api.count("PATCH ") == 1
    client.close_pr(BRANCH)
    client.update_pr(BRANCH, "t", "b3")
    assert api.pulls[0]["body"] == "b2"


def test_update_pr_without_a_pr_raises(client):
    with pytest.raises(GitHubWriteError, match="no PR"):
        client.update_pr(BRANCH, "t", "b")


def test_ready_and_close_without_a_pr_raise(client):
    for call in (client.ready_pr, client.close_pr):
        with pytest.raises(GitHubWriteError, match="no PR"):
            call(BRANCH)


# -- issue -----------------------------------------------------------------------------------


def test_a_comment_is_posted_once_per_key_and_carries_the_hidden_marker(client, api):
    key = effect_key(TICKET, "comment-awaiting-qa")
    client.post_comment(TICKET, key, "Draft PR: x.")
    client.post_comment(TICKET, key, "Draft PR: x.")
    assert [c["body"] for c in api.comments] == [f"Draft PR: x.\n\n{comment_marker(key)}"]
    client.post_comment(TICKET, effect_key(TICKET, "comment-done"), "Argus: done.")
    assert len(api.comments) == 2


def test_a_comment_past_the_first_page_is_still_found(client, api):
    key = effect_key(TICKET, "comment-done")
    api.comments = [{"body": f"noise {i}"} for i in range(100)] + [{"body": f"old\n\n{comment_marker(key)}"}]
    client.post_comment(TICKET, key, "again")
    assert len(api.comments) == 101


def test_labels_are_set_idempotently_and_other_argus_labels_are_dropped(client, api):
    api.labels = ["bug", "argus:reproducing"]
    client.set_label(TICKET, "awaiting-qa")
    assert sorted(api.labels) == ["argus:awaiting-qa", "bug"]
    before = len(api.log)
    client.set_label(TICKET, "awaiting-qa")
    assert [line for line in api.log[before:] if not line.startswith("GET")] == [], "the repeat only read"
    client.set_label(TICKET, "done")
    assert sorted(api.labels) == ["argus:done", "bug"]


def test_a_label_that_vanished_between_read_and_delete_is_ignored(client, api):
    api.labels = ["argus:fixing"]
    api.labels_vanish = True
    client.set_label(TICKET, "failed")  # the DELETE answers 404; no error
    assert api.count("DELETE") == 1 and "argus:failed" in api.labels


def test_a_ticket_of_another_repository_is_refused(client, api):
    with pytest.raises(ValueError, match="not acme/shop#number"):
        client.post_comment("other/repo#7", "k", "b")
    assert api.log == []


# -- no closing keyword, no secret -----------------------------------------------------------


def test_nothing_the_client_sends_links_the_pr_to_an_issue_by_a_closing_keyword(client, api):
    pr = find_or_create_pr(client, TICKET)
    client.push_branch(BRANCH, PATCH, KEY)
    client.post_comment(TICKET, effect_key(TICKET, "comment-awaiting-qa"), f"Draft PR: {pr.url}. Awaiting QA.")
    sent = [r.content.decode() for r in api.requests if r.content]
    assert sent and not [s for s in sent if CLOSING.search(s)]


def test_the_token_is_in_no_repr_no_exception_and_no_log(api, caplog):
    client = HttpGitHubClient(TOKEN, REPO, transport=api.transport())
    assert TOKEN not in repr(client) and TOKEN not in str(client)
    errors: list[str] = []
    with caplog.at_level(logging.DEBUG):
        client.find_pr(BRANCH)
        for status in (401, 403, 404, 422, 500):  # GitHub echoing the credential in its message
            api.fail[("GET", f"/repos/{REPO}/pulls")] = status
            with pytest.raises(GitHubWriteError) as e:
                client.find_pr(BRANCH)
            errors.append(repr(e.value) + str(e.value))
        api.fail.clear()

        def boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError(f"cannot connect, headers were {dict(request.headers)}")  # a library that echoes headers

        with pytest.raises(GitHubWriteError) as e:
            HttpGitHubClient(TOKEN, REPO, transport=httpx.MockTransport(boom)).find_pr(BRANCH)
        errors.append(repr(e.value) + str(e.value))
        assert e.value.__cause__ is None and e.value.__suppress_context__
    assert "500" in errors[-2] and "ConnectError" in errors[-1]
    assert not [text for text in errors if TOKEN in text]
    assert TOKEN not in caplog.text


def test_the_token_is_only_sent_as_the_authorization_header(client, api):
    client.find_pr(BRANCH)
    client.create_draft_pr(BRANCH, "t", "b")
    for r in api.requests:
        assert r.headers["authorization"] == f"Bearer {TOKEN}"
        assert TOKEN not in str(r.url) and TOKEN.encode() not in r.content


def test_construction_checks(monkeypatch):
    with pytest.raises(ValueError):
        HttpGitHubClient("", REPO)
    with pytest.raises(ValueError, match="owner/name"):
        HttpGitHubClient(TOKEN, "shop")
    monkeypatch.delenv("GITHUB_WRITE_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="GITHUB_WRITE_TOKEN"):
        HttpGitHubClient.from_env(REPO)
    monkeypatch.setenv("GITHUB_WRITE_TOKEN", TOKEN)
    assert isinstance(HttpGitHubClient.from_env(REPO), HttpGitHubClient)
