"""P6-T23 break it: Render sleeps and a webhook is lost. A local stand-in, not the real Render sleep.

The story is `render_sleep_demo.scenario`: a signed webhook for a new ticket reaches an app whose
enqueue is unavailable (no workflow starts), `Reconciler.poll_once` over the recorded GitHub JSON then
starts exactly one workflow, and a late redelivery of the same webhook still ends in one workflow.
The first test needs nothing; the second runs the real DBOS workflow and needs `ARGUS_FLOW_DATABASE_URL`
(skipped with a reason when it is unset). Write-up and owner steps: docs/notes/p6-t23-break-it.md.
"""

from __future__ import annotations

import os
import uuid

import pytest
from dbos import DBOS

from flow.config import DATABASE_URL_ENV, FlowSettings
from flow.dbos_runtime import launch, shutdown
from flow.enqueue import FakeEnqueuer
from flow.fakes import FakeGitHub, FakeRunner
from flow.qa import send_qa_signal
from flow.reconcile import DbosLookup
from flow.states import State
from flow.webhook import SECRET_ENV
from flow.workflow import Deps, Outcome
from render_sleep_demo import FIXTURE_TICKET, SECRET, FakeLookup, scenario


def test_a_lost_webhook_is_recovered_by_the_poller_and_a_late_redelivery_adds_nothing(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    fake = FakeEnqueuer()
    s = scenario(FIXTURE_TICKET, fake, FakeLookup(fake), lambda t: int(t in fake.workflows))
    # 1. the delivery is lost: the app answered, its enqueue was refused, nothing started, no reaction
    assert (s.lost_status, s.refused, s.workflows_after_loss) == (202, 1, 0)
    # 2. the poller finds the new ticket from GitHub alone and starts one workflow
    [found] = s.poll.reconciled
    assert (found.ticket_id, found.state, found.action) == (FIXTURE_TICKET, State.RECEIVED, "started")
    assert s.poll.errors == {} and s.workflows_after_poll == 1
    # 3. GitHub's late redelivery (same delivery id) is let through, because the failed enqueue forgot the id,
    #    and still lands on the one workflow
    assert (s.redelivery_status, s.workflows_after_redelivery) == ("accepted", 1)
    # 4. the next poll sees the workflow and starts nothing
    assert [r.action for r in s.poll_again.reconciled] == ["exists"] and s.workflows_at_end == 1
    assert fake.workflows == {FIXTURE_TICKET}


@pytest.mark.postgres
@pytest.mark.skipif(not os.environ.get(DATABASE_URL_ENV), reason=f"{DATABASE_URL_ENV} is not set; needs a real Postgres")
def test_the_same_story_on_the_real_dbos_workflow_gives_one_workflow_and_one_pr(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, SECRET)
    repro, fix, verify, github = FakeRunner(Outcome(True, "repro.sh")), FakeRunner(Outcome(True, "the patch")), FakeRunner(), FakeGitHub()
    enqueuer = launch(FlowSettings.from_env(), Deps(repro, fix, verify, github, qa_timeout_seconds=60.0))
    try:
        ticket = f"acme/{uuid.uuid4().hex[:8]}#12"  # own id: runs do not meet in the shared system database
        s = scenario(ticket, enqueuer, DbosLookup(), lambda t: len(DBOS.list_workflows(workflow_ids=[t])))
        assert (s.lost_status, s.workflows_after_loss) == (202, 0)
        assert [r.action for r in s.poll.reconciled] == ["started"] and s.workflows_after_poll == 1
        assert (s.redelivery_status, s.workflows_after_redelivery) == ("accepted", 1)
        assert [r.action for r in s.poll_again.reconciled] == ["exists"] and s.workflows_at_end == 1
        send_qa_signal(ticket, "approve", "review-comment", "t23", by="reviewer")  # let the one workflow finish
        assert DBOS.retrieve_workflow(ticket).get_result()["state"] == "done"
        assert github.calls.count("create_draft_pr") == 1 and len(github.prs) == 1
        assert [len(r.runs) for r in (repro, fix, verify)] == [1, 1, 1]
    finally:
        shutdown()
