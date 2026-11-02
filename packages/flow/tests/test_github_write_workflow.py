"""The whole `ticket_workflow` with the real GitHub write client over a fake GitHub (httpx MockTransport).

Runners are fakes (the fix runner returns a real unified diff); everything the workflow writes to
GitHub goes through `HttpGitHubClient` and lands in `FakeGitHubApi`. Needs `ARGUS_FLOW_DATABASE_URL`
(skipped with a reason without it). No network, no LLM.
"""

from __future__ import annotations

import os
import random

import pytest

from flow.config import DATABASE_URL_ENV, FlowSettings
from flow.dbos_runtime import launch, shutdown
from flow.fakes import FakeRunner
from flow.github_write import HttpGitHubClient
from flow.qa import send_qa_signal
from flow.states import branch_name, comment_marker, effect_key
from flow.workflow import Deps, Outcome, set_deps
from github_api_fake import NEW_FILES, PATCH, REPO, FakeGitHubApi

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not os.environ.get(DATABASE_URL_ENV), reason=f"{DATABASE_URL_ENV} is not set; needs a real Postgres"),
]


@pytest.fixture(scope="module")
def enqueuer():
    enq = launch(FlowSettings.from_env(), Deps(None, None, None, None))
    yield enq
    shutdown()


def start(enqueuer, decision: str, *, api: FakeGitHubApi | None = None):
    api = api or FakeGitHubApi()
    client = HttpGitHubClient("token-not-real", REPO, transport=api.transport())
    set_deps(Deps(FakeRunner(Outcome(True, "repro.sh")), FakeRunner(Outcome(True, PATCH)), FakeRunner(), client, qa_timeout_seconds=60.0))
    ticket = f"{REPO}#{random.randrange(10**6, 10**7)}"
    handle = enqueuer.enqueue(ticket)
    send_qa_signal(ticket, decision, "review-comment", "1", by="reviewer")
    return ticket, api, handle.get_result()


def test_approve_ends_done_with_a_pushed_branch_a_ready_pr_two_comments_and_one_label(enqueuer):
    ticket, api, out = start(enqueuer, "approve")
    assert out["state"] == "done"
    branch = branch_name(ticket)
    assert api.files_at(branch) == NEW_FILES
    assert len(api.pulls) == 1 and api.pulls[0]["head"]["ref"] == branch
    assert api.pulls[0]["draft"] is False and api.pulls[0]["state"] == "open"
    assert api.count("POST /repos/acme/shop/pulls") == 1 and api.count("POST /graphql") == 1
    assert [comment_marker(effect_key(ticket, f"comment-{s}")) in c["body"] for s, c in zip(("awaiting-qa", "done"), api.comments)] == [True, True]
    assert len(api.comments) == 2
    assert api.labels == ["argus:done"]
    assert "closes" not in (api.pulls[0]["title"] + api.pulls[0]["body"]).lower()


def test_reject_closes_the_pr_and_labels_rejected(enqueuer):
    ticket, api, out = start(enqueuer, "reject")
    assert out["state"] == "rejected"
    assert api.pulls[0]["state"] == "closed" and api.pulls[0]["draft"] is True  # never marked ready
    assert api.count("POST /graphql") == 0
    assert api.labels == ["argus:rejected"]


def test_a_failed_lookup_ends_the_ticket_failed_and_creates_no_pr(enqueuer):
    api = FakeGitHubApi()
    api.fail[("GET", f"/repos/{REPO}/pulls")] = 500
    ticket, api, out = start(enqueuer, "approve", api=api)
    assert out["state"] == "failed" and "open_pr_step failed after 3 attempts" in out["reason"]
    assert api.pulls == [] and api.count("POST /repos/acme/shop/pulls") == 0
    assert api.labels == ["argus:failed"]  # finish_step still labels the issue
