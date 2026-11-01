import asyncio
import time
from pathlib import Path

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import StopReason, Ticket, Trajectory

from repro_agent.browser import ReproBrowser, ToolUnavailable
from repro_agent.loop import TreeRun, run_repro

GOOD = """
await page.getByRole("button", { name: "Sign in" }).click();
await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
"""


class _Dead:
    def __init__(self) -> None:
        self.calls = 0

    async def call_tool(self, *_args, **_kwargs):
        self.calls += 1
        raise ConnectionError("server gone")


class _Hang:
    async def call_tool(self, *_args, **_kwargs):
        await asyncio.sleep(30)


def _browser(client: object) -> ReproBrowser:
    browser = ReproBrowser(timeout=0.2)
    browser._client = client
    browser._restarts = 0

    async def restart() -> None:
        browser._restarts += 1
        browser._client = client

    browser._restart = restart
    return browser


def test_a_dead_server_restarts_once_then_stops():
    browser = _browser(_Dead())
    with pytest_raises():
        asyncio.run(browser.call("navigate", {"url": "http://127.0.0.1/login"}))
    assert browser._restarts == 1


def test_a_hang_during_the_call_stays_inside_the_timeout():
    browser = _browser(_Hang())
    started = time.monotonic()
    try:
        asyncio.run(browser.call("navigate", {"url": "http://127.0.0.1/login"}))
        raised = False
    except ToolUnavailable:
        raised = True
    assert raised
    assert time.monotonic() - started < 2
    assert browser._restarts == 1


def test_an_exit_between_calls_is_the_same_stop():
    browser = _browser(_Dead())
    browser._client = None
    try:
        asyncio.run(browser.call("navigate", {"url": "http://127.0.0.1/login"}))
        raised = False
    except ToolUnavailable:
        raised = True
    assert raised
    assert browser._restarts == 1


def test_the_loop_records_tool_unavailable(tmp_path: Path):
    def complete(_messages):
        return Completion(GOOD, Usage(1, 1, 0), {})

    def run_trees(_script):
        raise ToolUnavailable("server exited")

    result = run_repro(
        ticket=Ticket(id="sign-in", text="The Sign in button does nothing."),
        task_dir=tmp_path,
        model="m",
        ledger=_ledger(tmp_path),
        complete=complete,
        run_trees=run_trees,
        out_dir=tmp_path / "run",
        cap=3,
        run_id="r",
        host="local",
        git_commit="abc",
        tool_timeout=0.5,
    )
    assert result.stop_reason is StopReason.tool_unavailable
    trajectory = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
    assert trajectory.steps[-1].stop_reason is StopReason.tool_unavailable


def test_a_hung_tool_does_not_hang_the_loop(tmp_path: Path):
    def complete(_messages):
        return Completion(GOOD, Usage(1, 1, 0), {})

    def run_trees(_script):
        time.sleep(30)
        return TreeRun(True, True)

    started = time.monotonic()
    result = run_repro(
        ticket=Ticket(id="sign-in", text="The Sign in button does nothing."),
        task_dir=tmp_path,
        model="m",
        ledger=_ledger(tmp_path),
        complete=complete,
        run_trees=run_trees,
        out_dir=tmp_path / "run",
        cap=3,
        run_id="r",
        host="local",
        git_commit="abc",
        tool_timeout=0.2,
    )
    assert time.monotonic() - started < 2
    assert result.stop_reason is StopReason.tool_unavailable


def pytest_raises():
    import pytest

    return pytest.raises(ToolUnavailable)


def _ledger(tmp_path: Path) -> Ledger:
    return Ledger(
        tmp_path / "ledger.json",
        {
            "m": ModelQuota(
                requests_per_day=10,
                tokens_per_day=1000,
                requests_per_minute=10,
                tokens_per_minute=1000,
                cached_counts=False,
            )
        },
    )
