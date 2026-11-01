"""P6-T07: the dropped-webhook fixture against the real DBOS workflow on a real local Postgres.

The reader serves recorded GitHub JSON; the runners and the GitHub client of the workflow are the
fakes from `flow.fakes`, seeded with the same facts, so the workflow finds the runs and the PR that
GitHub shows. Needs `ARGUS_FLOW_DATABASE_URL` (docs/notes/p6-t07.md); skipped with a reason when unset.
Each test moves the fixture to its own ticket id, so runs do not meet in the shared system database.
"""

from __future__ import annotations

import os
import uuid

import pytest
from dbos import DBOS

from flow.config import DATABASE_URL_ENV, FlowSettings
from flow.dbos_runtime import DbosEnqueuer, launch, shutdown
from flow.fakes import FakeGitHub, FakeRunner
from flow.github_read import HttpGitHubReader
from flow.reconcile import DbosLookup, GitHubReadError, PollConfig, Reconciler
from flow.states import TERMINAL, branch_name, effect_key
from flow.workflow import Deps, Outcome, PullRequest, set_deps
from reconcile_support import load, reader_for, transport

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not os.environ.get(DATABASE_URL_ENV), reason=f"{DATABASE_URL_ENV} is not set; needs a real Postgres"),
]


@pytest.fixture(scope="module")
def enqueuer():
    enq = launch(FlowSettings.from_env(), Deps(None, None, None, None))
    yield enq
    shutdown()


class World:
    """Fakes for one test, seeded to match what the fixture's GitHub JSON shows."""

    def __init__(self, ticket: str, fx: dict) -> None:
        self.repro, self.fix, self.verify = FakeRunner(Outcome(True, "repro.sh")), FakeRunner(Outcome(True, "the patch")), FakeRunner()
        self.github = FakeGitHub()
        done = {r["display_title"] for r in fx["runs"]["workflow_runs"] if r["conclusion"] == "success"}
        for step, runner, out in (("repro", self.repro, "repro.sh"), ("fix", self.fix, "the patch"), ("verify", self.verify, "ok")):
            if effect_key(ticket, f"dispatch-{step}") in done:
                runner.runs[effect_key(ticket, f"dispatch-{step}")] = Outcome(True, out)
        if fx["pulls"]:
            self.github.prs[branch_name(ticket)] = PullRequest(fx["pulls"][0]["number"], "https://example.test/pr/31", True)
        if fx["ref"]:
            self.github.branches[branch_name(ticket)] = {effect_key(ticket, "push-branch")}


def setup(enqueuer, name: str):
    ticket = f"acme/{uuid.uuid4().hex[:8]}#12"
    fx = load(name, ticket)
    world = World(ticket, fx)
    set_deps(Deps(world.repro, world.fix, world.verify, world.github))
    poller = Reconciler(reader_for(fx), DbosLookup(), enqueuer)
    return ticket, fx, world, poller


def workflows(ticket: str) -> int:
    return len(DBOS.list_workflows(workflow_ids=[ticket]))


def test_a_new_ticket_never_seen_gets_one_workflow_and_one_pr(enqueuer):
    ticket, fx, world, poller = setup(enqueuer, "new_ticket")
    first = poller.reconcile(ticket)
    assert (first.state.value, first.action) == ("received", "started")
    out = DBOS.retrieve_workflow(ticket).get_result()
    assert out["state"] == "done"
    second = poller.reconcile(ticket)  # poll again
    assert second.action == "exists" and (second.workflow_status, second.workflow_state) == ("SUCCESS", "done")
    assert workflows(ticket) == 1
    assert world.github.calls.count("create_draft_pr") == 1 and len(world.github.prs) == 1


@pytest.mark.parametrize("name, state", [("fixing", "fixing"), ("pr_open_run_finished", "opening-pr"), ("awaiting_qa", "awaiting-qa")])
def test_a_workflow_started_from_github_state_finds_the_runs_and_the_pr(enqueuer, name, state):
    ticket, fx, world, poller = setup(enqueuer, name)
    out = poller.reconcile(ticket)
    assert (out.state.value, out.action) == (state, "started")
    assert DBOS.retrieve_workflow(ticket).get_result()["state"] == "done"
    assert workflows(ticket) == 1
    for runner, step in ((world.repro, "repro"), (world.fix, "fix"), (world.verify, "verify")):
        assert len(runner.runs) == 1, step  # one run per step key, the existing one reused
    if fx["pulls"]:
        assert "create_draft_pr" not in world.github.calls  # the PR GitHub shows is reused: no second PR
        assert len(world.github.prs) == 1
    assert poller.reconcile(ticket).action == "exists" and workflows(ticket) == 1


@pytest.mark.parametrize("name", ["merged", "closed_unmerged", "run_failed", "timed_out"])
def test_an_end_state_on_github_starts_no_workflow(enqueuer, name):
    ticket, fx, world, poller = setup(enqueuer, name)
    out = poller.reconcile(ticket)
    assert out.state in TERMINAL and out.action == "settled" and out.state.value == fx["expect"]
    assert DBOS.get_workflow_status(ticket) is None
    assert world.github.calls == [] and world.repro.calls == []


def test_webhook_and_poller_meet_on_one_workflow(enqueuer):
    ticket, fx, world, poller = setup(enqueuer, "pr_open_run_finished")
    enqueuer.enqueue_reconcile(ticket)  # the webhook's call, as in flow.webhook
    out = poller.reconcile(ticket)  # the poller finds it
    assert out.action == "exists"
    DBOS.retrieve_workflow(ticket).get_result()
    enqueuer.enqueue_reconcile(ticket)  # a late hint
    assert workflows(ticket) == 1 and len(world.github.prs) == 1 and len(world.repro.runs) == 1


def test_the_other_order_poller_first_then_webhook_is_also_one_workflow(enqueuer):
    ticket, fx, world, poller = setup(enqueuer, "new_ticket")
    assert poller.reconcile(ticket).action == "started"
    enqueuer.enqueue_reconcile(ticket)
    DBOS.retrieve_workflow(ticket).get_result()
    assert workflows(ticket) == 1 and len(world.github.prs) == 1


def test_a_github_error_leaves_the_workflow_store_untouched(enqueuer):
    ticket, fx, world, poller = setup(enqueuer, "new_ticket")
    poller = Reconciler(reader_for(fx, fail={"/runs": 502}), DbosLookup(), enqueuer)
    with pytest.raises(GitHubReadError):
        poller.reconcile(ticket)
    assert DBOS.get_workflow_status(ticket) is None and workflows(ticket) == 0
    assert world.github.calls == []


def test_poll_once_twice_leaves_one_workflow_per_ticket(enqueuer):
    ticket, fx, world, _ = setup(enqueuer, "awaiting_qa")

    class OneIssue(HttpGitHubReader):
        def list_open_tickets(self, repo, label, page_size, max_pages):
            return [ticket]

    reader = OneIssue("t", transport=transport(fx))  # same recorded JSON
    poller = Reconciler(reader, DbosLookup(), enqueuer, PollConfig(repo="acme/x"))
    first = poller.poll_once()
    DBOS.retrieve_workflow(ticket).get_result()
    second = poller.poll_once()
    assert [r.action for r in first.reconciled] == ["started"] and [r.action for r in second.reconciled] == ["exists"]
    assert first.errors == second.errors == {} and workflows(ticket) == 1 and len(world.github.prs) == 1
