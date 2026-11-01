"""ActionsRunner against a fake GitHub served by httpx.MockTransport (P6-T04). No network, no LLM."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest

from flow.actions import ActionsError, ActionsRunner, BadArtifact, parse_artifact
from flow.states import effect_key
from flow.workflow import Outcome

TOKEN = "ghp_SECRET_TOKEN_VALUE_123"
REPO = "acme/app"
KEY = effect_key("acme/app#7", "dispatch-fix")
BLOB = "https://blob.example.test/zip"


def make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return buf.getvalue()


GOOD = make_zip({
    "result.json": json.dumps({"ok": True, "output": "diff --git a/x b/x"}),
    "patch.diff": "diff --git a/x b/x\n",
    "trajectory.jsonl": '{"step": 0}\n',
})


class FakeGitHub:
    """Just enough of the Actions API. `polls` is how many status reads return in_progress first."""

    def __init__(self, *, polls: int = 1, conclusion: str = "success", archive: bytes | None = GOOD,
                 list_runs_after: int = 0) -> None:
        self.runs: list[dict] = []
        self.dispatches: list[dict] = []
        self.requests: list[httpx.Request] = []
        self.polls, self.conclusion, self.archive = polls, conclusion, archive
        self.list_runs_after = list_runs_after  # list calls that still hide a dispatched run
        self._reads: dict[int, int] = {}
        self.fail: tuple[str, int] | None = None  # (path fragment, status)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if self.fail and self.fail[0] in path:
            return httpx.Response(self.fail[1], json={"message": f"boom {TOKEN}"})
        if request.method == "POST" and path.endswith("/dispatches"):
            body = json.loads(request.content)
            self.dispatches.append(body)
            run_id = 100 + len(self.runs)
            self.runs.append({"id": run_id, "display_title": body["inputs"]["run_key"], "status": "queued",
                              "conclusion": None, "created_at": f"2026-11-01T00:00:{run_id % 60:02d}Z",
                              "html_url": f"https://github.test/{REPO}/actions/runs/{run_id}"})
            return httpx.Response(204)
        if path.endswith("/workflows/agent-job.yml/runs"):
            if self.list_runs_after > 0 and self.dispatches:
                self.list_runs_after -= 1
                return httpx.Response(200, json={"workflow_runs": []})
            return httpx.Response(200, json={"workflow_runs": self.runs})
        if path.endswith("/artifacts") and "/runs/" in path:
            arts = [] if self.archive is None else [{"id": 9, "name": "argus-result", "expired": False}]
            return httpx.Response(200, json={"artifacts": arts})
        if path.endswith("/artifacts/9/zip"):
            return httpx.Response(302, headers={"Location": BLOB})
        if request.url == BLOB:
            return httpx.Response(200, content=self.archive)
        if "/actions/runs/" in path:
            run = next(r for r in self.runs if str(r["id"]) == path.rsplit("/", 1)[1])
            n = self._reads[run["id"]] = self._reads.get(run["id"], 0) + 1
            if n > self.polls:
                run.update(status="completed", conclusion=self.conclusion)
            else:
                run["status"] = "in_progress"
            return httpx.Response(200, json=run)
        return httpx.Response(404, json={"message": "not found"})


class Clock:
    """A fake clock: sleeping moves time, nothing waits."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def runner(gh: FakeGitHub, step: str = "fix", **kwargs) -> ActionsRunner:
    clock = Clock()
    return ActionsRunner(
        step, repo=REPO, token=TOKEN, client=httpx.Client(transport=httpx.MockTransport(gh.handler)),
        sleep=clock.sleep, clock=clock, **kwargs,
    )


def test_dispatch_carries_inputs_and_returns_the_artifact():
    gh = FakeGitHub()
    r = runner(gh)
    out = r.run("acme/app#7", KEY, "repro script")
    assert out == Outcome(True, "diff --git a/x b/x")
    assert gh.dispatches == [{"ref": "main", "inputs": {
        "ticket_id": "acme/app#7", "step": "fix", "run_key": KEY, "upstream": "repro script"}}]
    kept = r.artifacts[KEY]
    assert kept.patch == "diff --git a/x b/x\n" and kept.trajectory == '{"step": 0}\n'
    assert kept.run_url.endswith("/actions/runs/100")


def test_second_call_with_the_same_key_finds_the_run_and_does_not_dispatch():
    gh = FakeGitHub()
    r = runner(gh)
    first = r.run("acme/app#7", KEY, "u")
    second = runner(gh).run("acme/app#7", KEY, "u")  # a fresh runner, as after a restart
    assert first == second
    assert len(gh.dispatches) == 1 and len(gh.runs) == 1


def test_a_different_key_starts_a_different_run():
    gh = FakeGitHub()
    r = runner(gh)
    r.run("acme/app#7", KEY, "u")
    r.run("acme/app#7", effect_key("acme/app#7", "dispatch-fix", 2), "u")
    assert len(gh.dispatches) == 2


def test_waits_until_the_dispatched_run_is_listed():
    gh = FakeGitHub(list_runs_after=3)
    assert runner(gh).run("acme/app#7", KEY, "").ok
    assert len(gh.dispatches) == 1


def test_run_never_listed_raises_and_a_retry_does_not_double_dispatch_once_it_shows():
    gh = FakeGitHub(list_runs_after=10_000)
    r = runner(gh, appear_timeout=6)
    with pytest.raises(ActionsError, match="not listed"):
        r.run("acme/app#7", KEY, "")
    gh.list_runs_after = 0  # the run shows up late
    assert r.run("acme/app#7", KEY, "").ok
    assert len(gh.dispatches) == 1


def test_polls_until_completed():
    gh = FakeGitHub(polls=4)
    assert runner(gh).run("acme/app#7", KEY, "").ok
    status_reads = [q for q in gh.requests if q.url.path.endswith("/actions/runs/100")]
    assert len(status_reads) == 5  # four in progress, then completed


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out"])
def test_a_run_that_did_not_succeed_is_a_failed_outcome_even_if_the_artifact_says_ok(conclusion):
    gh = FakeGitHub(conclusion=conclusion)  # GOOD says ok: true
    out = runner(gh).run("acme/app#7", KEY, "")
    assert out.ok is False and conclusion in out.output


def test_failed_run_reports_the_reason_from_its_artifact():
    gh = FakeGitHub(conclusion="failure", archive=make_zip({"result.json": '{"ok": false, "output": "budget hit"}'}))
    out = runner(gh).run("acme/app#7", KEY, "")
    assert not out.ok and "budget hit" in out.output


def test_success_with_ok_false_in_the_artifact_is_a_failed_outcome():
    gh = FakeGitHub(archive=make_zip({"result.json": '{"ok": false, "output": "did not reproduce"}'}))
    assert runner(gh).run("acme/app#7", KEY, "") == Outcome(False, "did not reproduce")


def test_polling_timeout_is_a_failed_outcome_and_bounded():
    gh = FakeGitHub(polls=10**9)
    clock = Clock()
    r = ActionsRunner("fix", repo=REPO, token=TOKEN, client=httpx.Client(transport=httpx.MockTransport(gh.handler)),
                      sleep=clock.sleep, clock=clock, poll_interval=10, timeout=100)
    out = r.run("acme/app#7", KEY, "")
    assert not out.ok and "did not finish within 100s" in out.output
    assert clock.now <= 110
    assert len([q for q in gh.requests if q.url.path.endswith("/actions/runs/100")]) <= 11


def test_missing_artifact_is_a_failed_outcome_not_an_exception():
    gh = FakeGitHub(archive=None)
    out = runner(gh).run("acme/app#7", KEY, "")
    assert not out.ok and "no artifact named argus-result" in out.output


def test_upstream_over_the_limit_fails_before_any_dispatch():
    gh = FakeGitHub()
    out = runner(gh).run("acme/app#7", KEY, "x" * 50_001)
    assert not out.ok and "dispatch limit" in out.output
    assert gh.dispatches == []


def test_token_is_sent_to_the_api_but_not_on_the_blob_redirect():
    gh = FakeGitHub()
    runner(gh).run("acme/app#7", KEY, "")
    api = [q for q in gh.requests if q.url.host == "api.github.com"]
    blob = [q for q in gh.requests if q.url.host == "blob.example.test"]
    assert api and all(q.headers["authorization"] == f"Bearer {TOKEN}" for q in api)
    assert blob and all("authorization" not in q.headers for q in blob)


def test_http_error_text_never_holds_the_token():
    gh = FakeGitHub()
    gh.fail = ("/dispatches", 422)  # the body echoes the token to simulate a hostile message
    with pytest.raises(ActionsError) as e:
        runner(gh).run("acme/app#7", KEY, "")
    assert "422" in str(e.value) and TOKEN not in str(e.value) and TOKEN not in repr(e.value)


def test_transport_error_text_never_holds_the_token():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot connect, headers {dict(request.headers)}")

    r = ActionsRunner("fix", repo=REPO, token=TOKEN, client=httpx.Client(transport=httpx.MockTransport(boom)))
    with pytest.raises(ActionsError) as e:
        r.run("acme/app#7", KEY, "")
    assert TOKEN not in str(e.value) and TOKEN not in repr(e.value)
    assert TOKEN not in "".join(repr(x) for x in (e.value.__cause__, e.value.__context__))


def test_token_is_not_in_repr():
    assert TOKEN not in repr(runner(FakeGitHub()))


def test_from_env_reads_the_token_and_refuses_without_it(monkeypatch):
    monkeypatch.delenv("GITHUB_DISPATCH_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="GITHUB_DISPATCH_TOKEN is not set"):
        ActionsRunner.from_env("fix", repo=REPO)
    monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", TOKEN)
    assert ActionsRunner.from_env("fix", repo=REPO).step == "fix"


def test_constructor_rejects_bad_arguments():
    with pytest.raises(ValueError):
        ActionsRunner("deploy", repo=REPO, token=TOKEN)
    with pytest.raises(ValueError):
        ActionsRunner("fix", repo="noslash", token=TOKEN)
    with pytest.raises(ValueError):
        ActionsRunner("fix", repo=REPO, token="")


def test_parse_artifact_reads_all_three_files():
    a = parse_artifact(GOOD, "https://run")
    assert (a.ok, a.output, a.patch, a.trajectory, a.run_url) == (
        True, "diff --git a/x b/x", "diff --git a/x b/x\n", '{"step": 0}\n', "https://run")


def test_parse_artifact_patch_and_trajectory_are_optional():
    a = parse_artifact(make_zip({"result.json": '{"ok": true, "output": "script"}'}))
    assert (a.output, a.patch, a.trajectory) == ("script", "", "")


@pytest.mark.parametrize("data", [
    b"not a zip",
    make_zip({"patch.diff": "x"}),
    make_zip({"result.json": "not json"}),
    make_zip({"result.json": '{"ok": "yes", "output": "x"}'}),
    make_zip({"result.json": '{"ok": true}'}),
    make_zip({"result.json": "[]"}),
])
def test_parse_artifact_rejects_malformed(data):
    with pytest.raises(BadArtifact):
        parse_artifact(data)


def test_parse_artifact_refuses_a_huge_member():
    with pytest.raises(BadArtifact, match="over"):
        parse_artifact(make_zip({"result.json": '{"ok": true, "output": ""}', "patch.diff": "x" * (5 * 1024 * 1024 + 1)}))


def test_agent_job_workflow_is_valid_and_keeps_the_contract():
    yaml = pytest.importorskip("yaml")
    path = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "agent-job.yml"
    text = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    triggers = doc[True]  # YAML 1.1 reads the key `on` as True
    assert list(triggers) == ["workflow_dispatch"]
    assert set(triggers["workflow_dispatch"]["inputs"]) == {"ticket_id", "step", "run_key", "upstream"}
    assert doc["run-name"] == "${{ inputs.run_key }}"  # how the runner finds the run
    assert doc["concurrency"]["group"] == "argus-${{ inputs.run_key }}"
    assert triggers["workflow_dispatch"]["inputs"]["step"]["options"] == ["repro", "fix", "verify"]
    # the only secret is the model key, as a reference; inputs never sit inside a script
    assert text.count("secrets.") == 1 and "ARGUS_MODEL_API_KEY: ${{ secrets.ARGUS_MODEL_API_KEY }}" in text
    for job in doc["jobs"].values():
        for step in job["steps"]:
            assert "inputs." not in step.get("run", "")
