"""P8-T22: a repo with no test command (or any bad `.argus.yml`) gets a comment, not a crash or a guessed command.

The GitHub side is `httpx.MockTransport` behind the real `flow.github_write.HttpGitHubClient`: no network, no model.
"""
import json
import re

import httpx
import pytest
import yaml
from argus_app.config import ConfigError, TenantConfig
from argus_app.config_intake import check_config, config_error_comment
from flow.github_write import HttpGitHubClient

REPO, TICKET = "acme/shop", "acme/shop#7"
TOKEN = "ghp_fake-token-for-tests-not-real-0000"
VALID = {"start": "make serve", "test": "make check", "routes": ["/", "/login"], "budget": {"max_tokens": 1000, "max_steps": 5}}
MISSING_TEST = ".argus.yml: missing required field 'test' (the test command)"


class Issue:
    """Just the issue comment endpoints; any other request is a bug in the code under test and answers 500."""

    def __init__(self) -> None:
        self.comments: list[dict] = []
        self.log: list[str] = []

    def handle(self, req: httpx.Request) -> httpx.Response:
        self.log.append(f"{req.method} {req.url.path}")
        if req.url.path == f"/repos/{REPO}/issues/7/comments":
            if req.method == "GET":
                return httpx.Response(200, json=self.comments)
            if req.method == "POST":
                self.comments.append({"body": json.loads(req.content)["body"]})
                return httpx.Response(201, json={})
        return httpx.Response(500, json={"message": f"unexpected {req.method} {req.url.path}"})


@pytest.fixture
def issue():
    return Issue()


@pytest.fixture
def client(issue):
    return HttpGitHubClient(TOKEN, REPO, transport=httpx.MockTransport(issue.handle))


def text(**change) -> str:
    return yaml.safe_dump({**VALID, **change})


def without(*names: str) -> str:
    return yaml.safe_dump({k: v for k, v in VALID.items() if k not in names})


def test_a_missing_test_command_is_a_comment_with_the_typed_message(client, issue):
    assert check_config(client, TICKET, lambda: without("test")) is None
    assert len(issue.comments) == 1
    body = issue.comments[0]["body"]
    assert MISSING_TEST in body
    assert "did not guess" in body and "docs/onboarding.md" in body


def test_it_does_not_guess_a_command_and_starts_nothing(client, issue):
    check_config(client, TICKET, lambda: without("test"))
    body = issue.comments[0]["body"]
    assert "make serve" not in body and "npm" not in body and "pytest" not in body  # no value, no fallback command named
    assert sorted(set(issue.log)) == [f"GET /repos/{REPO}/issues/7/comments", f"POST /repos/{REPO}/issues/7/comments"]  # no label, branch, PR, push


def test_a_valid_config_is_returned_and_nothing_is_posted(client, issue):
    config = check_config(client, TICKET, lambda: text())
    assert isinstance(config, TenantConfig) and config.test == "make check"
    assert issue.log == []


def test_the_same_problem_on_a_second_label_event_posts_one_comment(client, issue):
    for _ in range(2):
        assert check_config(client, TICKET, lambda: without("test")) is None
    assert len(issue.comments) == 1


def test_a_different_problem_is_a_new_comment(client, issue):
    check_config(client, TICKET, lambda: without("test"))
    check_config(client, TICKET, lambda: without("start"))
    assert len(issue.comments) == 2 and "'start'" in issue.comments[1]["body"]


@pytest.mark.parametrize(
    "read, shown",
    [
        (lambda: None, "file not found"),
        (lambda: "", "missing required field 'test'"),
        (lambda: "start: [unclosed", "not valid YAML"),
        (lambda: "- just\n- a list\n", "must be a YAML mapping"),
        (lambda: text(test="   "), "field 'test': must not be empty"),
        (lambda: text(test=["make", "check"]), "field 'test'"),
        (lambda: text(speed="fast"), "unknown field 'speed'"),
        (lambda: text(budget={"max_tokens": 0, "max_steps": 5}), "budget.max_tokens"),
    ],
)
def test_every_kind_of_bad_config_gets_a_comment_and_no_crash(client, issue, read, shown):
    assert check_config(client, TICKET, read) is None
    assert len(issue.comments) == 1 and shown in issue.comments[0]["body"]


def test_all_problems_are_listed_in_one_comment(client, issue):
    check_config(client, TICKET, lambda: without("start", "test"))
    assert len(issue.comments) == 1
    body = issue.comments[0]["body"]
    assert "'start'" in body and "'test'" in body


def test_tenant_text_stays_in_the_code_block_and_secrets_are_masked(client, issue):
    token_like = "ghp_" + "notarealtoken_" * 3
    hostile = text(routes=[f"/x`@everyone` {token_like}"])
    check_config(client, TICKET, lambda: hostile)
    body = issue.comments[0]["body"]
    block = re.search(r"```text\n(.*?)\n```", body, re.S)
    assert block and "@everyone" in block[1]  # shown, but inside the block, where it does not ping
    assert "`" not in block[1] and token_like not in body and "***" in body


def test_a_huge_error_list_is_cut(client, issue):
    many = {f"extra{i}": 1 for i in range(40)}
    check_config(client, TICKET, lambda: text(**many))
    body = issue.comments[0]["body"]
    assert body.count("unknown field") == 10 and "and 30 more" in body


def test_the_comment_function_is_pure_and_names_the_file():
    with pytest.raises(ConfigError) as e:
        from argus_app.config import load_config_text

        load_config_text(without("test"))
    assert MISSING_TEST in config_error_comment(e.value)


def test_a_failing_post_is_not_hidden(issue):
    issue.handle = lambda req: httpx.Response(500, json={"message": "down"})
    client = HttpGitHubClient(TOKEN, REPO, transport=httpx.MockTransport(issue.handle))
    with pytest.raises(Exception) as e:  # the caller (intake) decides about retry; the token is not in the error
        check_config(client, TICKET, lambda: without("test"))
    assert TOKEN not in str(e.value)
