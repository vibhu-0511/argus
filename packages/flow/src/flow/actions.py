"""`Runner` backed by GitHub Actions: the execution plane of the ticket workflow (P6-T04).

One `ActionsRunner` runs one pipeline step (repro, fix or verify) by dispatching the
`agent-job.yml` workflow and reading back the artifact it uploads. It talks to GitHub's REST API
through an injectable `httpx.Client`, so tests use `httpx.MockTransport` and need no network.

`run(ticket_id, run_key, upstream)` finds before it starts. The workflow is dispatched with
`run_key` as input and the workflow sets its `run-name` to that key, so the run is found again by
its title (`display_title`) after a crash or a DBOS step retry: a run that exists is waited for,
never dispatched a second time. The key carries the attempt (`flow.states.effect_key`), so two
deliberate attempts have two titles. `agent-job.yml` also serialises runs of one key in a
concurrency group; that is the backstop for a dispatch whose run has not shown up in the list yet.

The artifact `argus-result` holds `result.json` (`{"ok": bool, "output": str}`, always written),
and `patch.diff` and `trajectory.jsonl` when the step made them. `Outcome.output` is
`result.json`'s `output` (repro script, patch or verdict text, what the next step takes as
upstream). The patch and trajectory are kept whole in `self.artifacts[run_key]`.

The token is read from `GITHUB_DISPATCH_TOKEN`, sent only as the `Authorization` header of API
requests, and scrubbed from every error text. A transport error is reported by its class name
only, because an HTTP library may echo request headers. httpx drops `Authorization` when the
artifact download redirects to GitHub's blob storage (another origin); a test checks it.

Errors that a retry may fix (HTTP error, run not listed in time) raise `ActionsError`, and the
DBOS step retries. Errors that no retry fixes (bad artifact, upstream too large, run timed out,
run failed) come back as `Outcome(False, reason)`.

ponytail: the upstream is passed inline as a dispatch input (GitHub caps the whole payload at
65,535 characters), so a patch above `MAX_UPSTREAM` fails the step instead of travelling as an
artifact reference. The runner only receives text, so a reference would need a lookup of the
earlier run's artifact; add it when a real patch comes near the cap.
ponytail: the runs list is read once, newest 100 of the workflow. Enough for one executor that
dispatches a few runs an hour; paginate or add `created=` if the list ever overflows.
ponytail: polling every 10 s is about 360 of the 5,000 hourly API calls per waiting run; use
`If-None-Match` or the `workflow_run` webhook if many runs wait at once.
"""

from __future__ import annotations

import io
import json
import os
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from flow.states import DISPATCH_STEPS
from flow.workflow import Outcome

TOKEN_ENV = "GITHUB_DISPATCH_TOKEN"
API = "https://api.github.com"
ARTIFACT_NAME = "argus-result"
MAX_UPSTREAM = 50_000  # characters; GitHub caps the dispatch payload at 65,535
MAX_ARTIFACT = 20 * 1024 * 1024  # bytes of zip
MAX_MEMBER = 5 * 1024 * 1024  # bytes of one unpacked file


class ActionsError(RuntimeError):
    """A GitHub call failed in a way a retry may fix. Never contains the token."""


class BadArtifact(ValueError):
    """The run finished but its artifact is missing or malformed. Retrying does not help."""


@dataclass(frozen=True)
class Artifact:
    ok: bool
    output: str
    patch: str = ""
    trajectory: str = ""
    run_url: str = ""


class ActionsRunner:
    def __init__(
        self,
        step: str,
        *,
        repo: str,
        token: str,
        workflow: str = "agent-job.yml",
        ref: str = "main",
        client: httpx.Client | None = None,
        base_url: str = API,
        poll_interval: float = 10.0,
        timeout: float = 2400.0,
        appear_interval: float = 2.0,
        appear_timeout: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if step not in DISPATCH_STEPS:
            raise ValueError(f"unknown step {step!r}, expected one of {DISPATCH_STEPS}")
        if "/" not in repo:
            raise ValueError("repo must be 'owner/name'")
        if not token:
            raise ValueError("token must not be empty")
        self.step = step
        self.artifacts: dict[str, Artifact] = {}  # run_key -> what the run uploaded
        self._repo, self._workflow, self._ref = repo, workflow, ref
        self._token = token
        self._client = client or httpx.Client(timeout=30)
        self._base = base_url.rstrip("/")
        self._poll = (poll_interval, timeout)
        self._appear = (appear_interval, appear_timeout)
        self._sleep, self._clock = sleep, clock

    @classmethod
    def from_env(cls, step: str, *, repo: str, **kwargs) -> ActionsRunner:
        token = os.environ.get(TOKEN_ENV, "")
        if not token:
            raise RuntimeError(f"{TOKEN_ENV} is not set")
        return cls(step, repo=repo, token=token, **kwargs)

    def __repr__(self) -> str:  # keep the token out of any log that prints the object
        return f"ActionsRunner(step={self.step!r}, repo={self._repo!r}, token=<set>)"

    def run(self, ticket_id: str, run_key: str, upstream: str) -> Outcome:
        run = self._find(run_key)
        if run is None:
            if len(upstream) > MAX_UPSTREAM:
                return Outcome(False, f"upstream is {len(upstream)} characters, over the dispatch limit {MAX_UPSTREAM}")
            self._dispatch(ticket_id, run_key, upstream)
            run = self._wait_listed(run_key)
        run = self._wait_done(run)
        if run is None:
            return Outcome(False, f"run for {run_key} did not finish within {self._poll[1]:g}s")
        conclusion = run.get("conclusion")
        try:
            artifact = self._artifact(run)
        except BadArtifact as e:
            return Outcome(False, f"run concluded {conclusion}: {e} ({run.get('html_url', '')})")
        self.artifacts[run_key] = artifact
        if conclusion != "success":
            return Outcome(False, f"run concluded {conclusion}: {artifact.output} ({artifact.run_url})")
        return Outcome(artifact.ok, artifact.output)

    # --- GitHub calls -------------------------------------------------------------------------

    def _call(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        failure = ""
        try:
            response = self._client.request(method, self._base + path, headers=headers, **kwargs)
        except httpx.HTTPError as e:
            failure = type(e).__name__
        if failure:  # raised outside the except block so no __context__ keeps the original message
            raise ActionsError(f"{method} {path}: {failure}")
        if response.status_code >= 400:
            raise ActionsError(f"{method} {path} -> {response.status_code}: {self._message(response)}")
        return response

    def _message(self, response: httpx.Response) -> str:
        try:
            text = str(response.json().get("message", ""))
        except (ValueError, AttributeError):
            text = ""
        return text.replace(self._token, "***")[:200]

    def _runs_path(self) -> str:
        return f"/repos/{self._repo}/actions"

    def _find(self, run_key: str) -> dict | None:
        """The newest dispatched run of the workflow whose title is `run_key`."""
        response = self._call(
            "GET",
            f"{self._runs_path()}/workflows/{self._workflow}/runs",
            params={"event": "workflow_dispatch", "per_page": 100},
        )
        hits = [r for r in response.json().get("workflow_runs", []) if r.get("display_title") == run_key]
        return max(hits, key=lambda r: r.get("created_at", ""), default=None)

    def _dispatch(self, ticket_id: str, run_key: str, upstream: str) -> None:
        inputs = {"ticket_id": ticket_id, "step": self.step, "run_key": run_key, "upstream": upstream}
        self._call(
            "POST",
            f"{self._runs_path()}/workflows/{self._workflow}/dispatches",
            json={"ref": self._ref, "inputs": inputs},
        )

    def _wait_listed(self, run_key: str) -> dict:
        """The dispatch call returns no run id, so wait (bounded) for the run to appear in the list."""
        interval, timeout = self._appear
        deadline = self._clock() + timeout
        while True:
            run = self._find(run_key)
            if run is not None:
                return run
            if self._clock() >= deadline:
                raise ActionsError(f"run for {run_key} not listed within {timeout:g}s of dispatch")
            self._sleep(interval)

    def _wait_done(self, run: dict) -> dict | None:
        interval, timeout = self._poll
        deadline = self._clock() + timeout
        while run.get("status") != "completed":
            if self._clock() >= deadline:
                return None
            self._sleep(interval)
            run = self._call("GET", f"{self._runs_path()}/runs/{run['id']}").json()
        return run

    def _artifact(self, run: dict) -> Artifact:
        listing = self._call("GET", f"{self._runs_path()}/runs/{run['id']}/artifacts").json()
        found = [a for a in listing.get("artifacts", []) if a.get("name") == ARTIFACT_NAME and not a.get("expired")]
        if not found:
            raise BadArtifact(f"no artifact named {ARTIFACT_NAME}")
        # follow_redirects: the zip is served from blob storage; httpx drops Authorization on that hop.
        download = self._call("GET", f"{self._runs_path()}/artifacts/{found[0]['id']}/zip", follow_redirects=True)
        if len(download.content) > MAX_ARTIFACT:
            raise BadArtifact(f"artifact is over {MAX_ARTIFACT} bytes")
        return parse_artifact(download.content, run.get("html_url", ""))


def parse_artifact(data: bytes, run_url: str = "") -> Artifact:
    """Read `result.json` and the optional `patch.diff` and `trajectory.jsonl` out of the zip."""

    def read(zf: zipfile.ZipFile, name: str, *, required: bool = False) -> str:
        try:
            info = zf.getinfo(name)
        except KeyError:
            if required:
                raise BadArtifact(f"artifact has no {name}") from None
            return ""
        if info.file_size > MAX_MEMBER:
            raise BadArtifact(f"{name} is over {MAX_MEMBER} bytes")
        try:
            return zf.read(info).decode("utf-8")
        except UnicodeDecodeError:
            raise BadArtifact(f"{name} is not UTF-8") from None

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            result = read(zf, "result.json", required=True)
            patch = read(zf, "patch.diff")
            trajectory = read(zf, "trajectory.jsonl")
    except zipfile.BadZipFile:
        raise BadArtifact("artifact is not a valid zip") from None
    try:
        parsed = json.loads(result)
    except ValueError:
        raise BadArtifact("result.json is not JSON") from None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("ok"), bool) or not isinstance(parsed.get("output"), str):
        raise BadArtifact('result.json must be {"ok": bool, "output": str}')
    return Artifact(parsed["ok"], parsed["output"], patch, trajectory, run_url)
