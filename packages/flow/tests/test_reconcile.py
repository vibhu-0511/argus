"""P6-T07: the reconciliation poller against recorded GitHub JSON. No network, no LLM, no Postgres.

`fixtures/reconcile/*.json` are GitHub's bodies for one ticket in several situations, as a dropped
webhook leaves them. The reader turns them into a `GitHubState`, `derive_state` maps that onto a
`State`, and `Reconciler` starts the workflow through the shared enqueue.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from flow.enqueue import FakeEnqueuer
from flow.github_read import HttpGitHubReader
from flow.reconcile import (
    GitHubReadError,
    GitHubState,
    NotATicket,
    PollConfig,
    PrView,
    Reconciler,
    RunView,
    WorkflowView,
    derive_state,
    poll_forever,
)
from flow.states import TERMINAL, State
from reconcile_support import FIXTURE_TICKET, NAMES, load, reader_for, transport


class EnqueuerLookup:
    """A workflow exists once the fake enqueuer has been asked for it, like the DBOS id would."""

    def __init__(self, enq: FakeEnqueuer) -> None:
        self.enq = enq

    def get(self, ticket_id: str) -> WorkflowView | None:
        return WorkflowView("PENDING", None) if ticket_id in self.enq.workflows else None


def make(fx: dict, **kwargs) -> tuple[Reconciler, FakeEnqueuer]:
    enq = FakeEnqueuer()
    return Reconciler(reader_for(fx, **kwargs), EnqueuerLookup(enq), enq), enq


def test_there_is_a_fixture_for_every_active_state_and_some_terminal_ones():
    expected = {load(n)["expect"] for n in NAMES}
    assert {"received", "reproducing", "fixing", "verifying", "opening-pr", "awaiting-qa"} <= expected
    assert {"done", "rejected", "failed", "timed-out"} == expected & {s.value for s in TERMINAL}


@pytest.mark.parametrize("name", NAMES)
def test_the_state_is_derived_from_github_json_alone(name):
    fx = load(name)
    state = derive_state(reader_for(fx).read_github_state(FIXTURE_TICKET))
    assert state.value == fx["expect"], fx["why"]


@pytest.mark.parametrize("name", NAMES)
def test_a_dropped_webhook_is_repaired(name):
    """No workflow, no hint: the poller starts one unless GitHub already shows an end state."""
    fx = load(name)
    poller, enq = make(fx)
    out = poller.reconcile(FIXTURE_TICKET)
    assert out.state.value == fx["expect"]
    if out.state in TERMINAL:
        assert out.action == "settled" and enq.calls == []
    else:
        assert out.action == "started" and enq.calls == [FIXTURE_TICKET]


def test_new_ticket_never_seen_starts_one_workflow_under_the_ticket_id():
    poller, enq = make(load("new_ticket"))
    out = poller.reconcile(FIXTURE_TICKET)
    assert (out.state, out.action) == (State.RECEIVED, "started")
    assert enq.workflows == {FIXTURE_TICKET}  # the id the webhook enqueues with (flow.states.workflow_id)


@pytest.mark.parametrize("name", ["new_ticket", "pr_open_run_finished", "awaiting_qa", "fixing"])
def test_polling_twice_is_one_workflow(name):
    poller, enq = make(load(name))
    first, second = poller.reconcile(FIXTURE_TICKET), poller.reconcile(FIXTURE_TICKET)
    assert (first.action, second.action) == ("started", "exists")
    assert first.state == second.state
    assert enq.calls == [FIXTURE_TICKET] and enq.workflows == {FIXTURE_TICKET}


def test_an_existing_workflow_is_never_enqueued_again_and_reports_where_to_resume():
    enq = FakeEnqueuer()
    lookup = type("L", (), {"get": lambda self, t: WorkflowView("SUCCESS", "awaiting-qa")})()
    out = Reconciler(reader_for(load("merged")), lookup, enq).reconcile(FIXTURE_TICKET)
    assert enq.calls == []
    assert (out.action, out.state, out.workflow_state) == ("exists", State.DONE, "awaiting-qa")
    assert out.diverged  # the workflow finished before the merge; GitHub shows the truth


def test_a_github_error_leaves_everything_untouched():
    for fail in ({"/runs": 502}, {"/pulls": 500}, {"/comments": 403}, {"/issues/12": 404}):
        poller, enq = make(load("new_ticket"), fail=fail)
        with pytest.raises(GitHubReadError):
            poller.reconcile(FIXTURE_TICKET)
        assert enq.calls == [] and enq.workflows == set()


def test_a_dropped_connection_is_a_read_error_not_an_empty_answer():
    def boom(request):
        raise httpx.ConnectError("no route", request=request)

    reader = HttpGitHubReader("test-token", transport=httpx.MockTransport(boom))
    enq = FakeEnqueuer()
    with pytest.raises(GitHubReadError, match="ConnectError"):
        Reconciler(reader, EnqueuerLookup(enq), enq).reconcile(FIXTURE_TICKET)
    assert enq.calls == []


def test_a_workflow_lookup_error_enqueues_nothing():
    class Broken:
        def get(self, ticket_id):
            raise ConnectionError("database is down")

    enq = FakeEnqueuer()
    with pytest.raises(ConnectionError):
        Reconciler(reader_for(load("new_ticket")), Broken(), enq).reconcile(FIXTURE_TICKET)
    assert enq.calls == []


def test_a_pull_request_number_is_not_a_ticket():
    fx = load("new_ticket")
    fx["issue"]["pull_request"] = {"url": "https://api.github.com/repos/acme/shop/pulls/12"}
    poller, enq = make(fx)
    with pytest.raises(NotATicket):
        poller.reconcile(FIXTURE_TICKET)
    assert enq.calls == []


def test_the_reader_only_reads_and_the_token_stays_out_of_errors_and_repr():
    seen: list[httpx.Request] = []
    reader = HttpGitHubReader("s3cret-token", transport=transport(load("awaiting_qa"), requests=seen))
    reader.read_github_state(FIXTURE_TICKET)
    assert len(seen) == 5 and {r.method for r in seen} == {"GET"}
    assert all(r.headers["authorization"] == "Bearer s3cret-token" for r in seen)
    assert "s3cret-token" not in repr(reader)
    bad = HttpGitHubReader("s3cret-token", transport=transport(load("awaiting_qa"), fail={"/runs": 502}))
    with pytest.raises(GitHubReadError) as e:
        bad.read_github_state(FIXTURE_TICKET)
    assert "s3cret-token" not in str(e.value) and "502" in str(e.value)


def test_the_token_comes_from_the_environment_only(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
        HttpGitHubReader.from_env()
    monkeypatch.setenv("GITHUB_TOKEN", "from-env")
    assert isinstance(HttpGitHubReader.from_env(), HttpGitHubReader)


# --- derive_state on hand-built states: the ordering rules the fixtures do not reach ---


def gh(**kw) -> GitHubState:
    base = dict(ticket_id="o/r#1", issue_open=True, labels=frozenset(), branch_exists=False, pr=None)
    return GitHubState(**{**base, **kw})


DRAFT, OK = PrView(5, "open", True, False), RunView("completed", "success")


@pytest.mark.parametrize(
    "g, want",
    [
        (gh(), State.RECEIVED),
        (gh(pr=PrView(5, "closed", False, True)), State.DONE),
        (gh(pr=PrView(5, "closed", True, False)), State.REJECTED),
        (gh(pr=PrView(5, "open", False, False)), State.DONE),  # ready for review
        (gh(pr=DRAFT, labels=frozenset({"argus:timed-out"})), State.TIMED_OUT),
        (gh(pr=DRAFT, markers=frozenset({"timed-out"})), State.TIMED_OUT),  # label lagging, comment landed
        (gh(pr=DRAFT, labels=frozenset({"argus:awaiting-qa"})), State.AWAITING_QA),
        (gh(pr=DRAFT, markers=frozenset({"awaiting-qa"})), State.OPENING_PR),  # table: PR without the label
        (gh(labels=frozenset({"argus:awaiting-qa"}), runs={"verify": OK}), State.OPENING_PR),  # label but no PR
        (gh(branch_exists=True), State.OPENING_PR),  # pushed, PR not opened yet
        (gh(issue_open=False), State.REJECTED),
        (gh(runs={"repro": RunView("completed", "cancelled")}), State.FAILED),
        (gh(runs={"repro": OK, "fix": RunView("completed", "timed_out")}), State.FAILED),
        (gh(runs={"repro": OK, "fix": OK, "verify": OK}), State.OPENING_PR),
        (gh(runs={"repro": RunView("queued", None)}), State.REPRODUCING),
        (gh(labels=frozenset({"argus:done", "argus:awaiting-qa"})), State.DONE),
    ],
)
def test_derive_state_rules(g, want):
    assert derive_state(g) is want


def test_derive_state_is_pure():
    g = gh(pr=DRAFT, labels=frozenset({"argus:awaiting-qa"}), runs={"verify": OK})
    assert derive_state(g) is derive_state(g)


# --- poll_once and the loop ---


def issues_transport(pages: list[list[dict]], seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url.path == "/repos/acme/shop/issues" and request.method == "GET"
        page = int(request.url.params["page"])
        return httpx.Response(200, json=pages[page - 1] if page <= len(pages) else [])

    return httpx.MockTransport(handler)


def test_poll_lists_open_tickets_with_a_bounded_page_size_and_skips_pull_requests():
    seen: list[httpx.Request] = []
    pages = [[{"number": 1}, {"number": 2, "pull_request": {}}], [{"number": 3}, {"number": 4}], [{"number": 5}, {"number": 6}]]
    reader = HttpGitHubReader("t", transport=issues_transport(pages, seen))
    tickets = reader.list_open_tickets("acme/shop", "bug", page_size=2, max_pages=2)
    assert tickets == ["acme/shop#1", "acme/shop#3", "acme/shop#4"]  # page 3 never asked for
    assert [r.url.params["page"] for r in seen] == ["1", "2"]
    assert all(r.url.params["per_page"] == "2" and r.url.params["labels"] == "bug" and r.url.params["state"] == "open" for r in seen)


def test_poll_stops_at_a_short_page():
    seen: list[httpx.Request] = []
    reader = HttpGitHubReader("t", transport=issues_transport([[{"number": 1}]], seen))
    assert reader.list_open_tickets("acme/shop", None, page_size=30, max_pages=3) == ["acme/shop#1"]
    assert len(seen) == 1 and "labels" not in seen[0].url.params


class StubReader:
    def __init__(self, tickets, states):
        self.tickets, self.states = tickets, states

    def list_open_tickets(self, repo, label, page_size, max_pages):
        return self.tickets

    def read_github_state(self, ticket_id):
        result = self.states[ticket_id]
        if isinstance(result, Exception):
            raise result
        return result


def test_poll_once_reconciles_each_ticket_and_reports_the_ones_that_failed():
    reader = StubReader(
        ["o/r#1", "o/r#2", "o/r#3"],
        {
            "o/r#1": gh(ticket_id="o/r#1"),
            "o/r#2": GitHubReadError("GET /repos/o/r/issues/2 -> 502"),
            "o/r#3": gh(ticket_id="o/r#3", pr=PrView(9, "closed", False, True)),
        },
    )
    enq = FakeEnqueuer()
    poller = Reconciler(reader, EnqueuerLookup(enq), enq)
    result = poller.poll_once()
    assert [(r.ticket_id, r.action) for r in result.reconciled] == [("o/r#1", "started"), ("o/r#3", "settled")]
    assert result.errors == {"o/r#2": "GET /repos/o/r/issues/2 -> 502"}
    assert enq.calls == ["o/r#1"]  # the failed ticket was left untouched
    again = poller.poll_once()
    assert enq.calls == ["o/r#1"] and again.reconciled[0].action == "exists"  # poll twice = one workflow


def test_a_failed_listing_raises_and_touches_nothing():
    class Down(StubReader):
        def list_open_tickets(self, *a):
            raise GitHubReadError("GET /repos/o/r/issues -> 503")

    enq = FakeEnqueuer()
    with pytest.raises(GitHubReadError):
        Reconciler(Down([], {}), EnqueuerLookup(enq), enq).poll_once()
    assert enq.calls == []


def test_poll_forever_polls_on_the_interval_survives_an_error_and_stops_on_the_event():
    class Counting:
        def __init__(self):
            self.n = 0
            self.config = PollConfig(interval_s=0.01)

        def poll_once(self):
            self.n += 1
            if self.n == 1:
                raise GitHubReadError("first poll fails")

    async def go():
        poller, stop = Counting(), asyncio.Event()
        task = asyncio.create_task(poll_forever(poller, stop))
        while poller.n < 3:
            await asyncio.sleep(0.01)
        stop.set()
        await asyncio.wait_for(task, 2)
        return poller.n

    assert asyncio.run(go()) >= 3


def test_poll_config_comes_from_the_environment_and_is_bounded(monkeypatch):
    for k in ("ARGUS_FLOW_REPO", "ARGUS_FLOW_TICKET_LABEL", "ARGUS_FLOW_POLL_PAGE_SIZE", "ARGUS_FLOW_POLL_MAX_PAGES", "ARGUS_FLOW_POLL_INTERVAL_S"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError, match="ARGUS_FLOW_REPO"):
        PollConfig.from_env()
    monkeypatch.setenv("ARGUS_FLOW_REPO", "acme/shop")
    cfg = PollConfig.from_env()
    assert (cfg.repo, cfg.label, cfg.page_size, cfg.max_pages, cfg.interval_s) == ("acme/shop", None, 30, 3, 300.0)
    monkeypatch.setenv("ARGUS_FLOW_POLL_PAGE_SIZE", "500")
    with pytest.raises(RuntimeError, match="PAGE_SIZE"):
        PollConfig.from_env()
    monkeypatch.setenv("ARGUS_FLOW_POLL_PAGE_SIZE", "10")
    monkeypatch.setenv("ARGUS_FLOW_POLL_INTERVAL_S", "5")
    with pytest.raises(RuntimeError, match="INTERVAL"):
        PollConfig.from_env()
    monkeypatch.setenv("ARGUS_FLOW_POLL_INTERVAL_S", "120")
    monkeypatch.setenv("ARGUS_FLOW_TICKET_LABEL", "argus")
    cfg = PollConfig.from_env()
    assert (cfg.label, cfg.page_size, cfg.interval_s) == ("argus", 10, 120.0)
