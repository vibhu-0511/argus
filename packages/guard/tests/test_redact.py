"""P7-T03: a planted fake secret is masked in a trajectory file and in OTel spans. No model call, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.telemetry import record_tool_error, start_tracing, tool_span
from argus_core.types import Trajectory
from fix_loop.loop import run_fix
from fix_loop.tools import ToolResult
from guard.redact import MASK, redact

# Obviously fake: every value carries FAKE and none is a real credential.
FAKE_PAT = "ghp_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE0000"
FAKE_APP_TOKEN = "ghs_123456_FAKEFAKE.FAKEFAKEFAKEFAKE-FAKE.FAKEFAKEFAKE0000"
FAKE_FINE_GRAINED = "github_pat_FAKEFAKEFAKEFAKEFAKEFAKE_FAKEFAKEFAKE0000"
FAKE_SK = "sk-FAKEFAKEFAKEFAKEFAKEFAKE0000"
FAKE_ENV_VALUE = "model-key-FAKE-not-a-real-value"
FAKE_URL = "https://x-access-token:ghs_FAKEFAKEFAKEFAKEFAKE0000@github.com/vibhu-0511/argus.git"
ENV = {"ARGUS_MODEL_API_KEY": FAKE_ENV_VALUE, "ARGUS_STEP": "fix"}


@pytest.mark.parametrize("secret", [FAKE_PAT, FAKE_APP_TOKEN, FAKE_FINE_GRAINED, FAKE_SK, FAKE_ENV_VALUE, FAKE_URL])
def test_each_shape_is_masked(secret):
    out = redact(f"before {secret} after", ENV)
    assert "FAKE" not in out.replace("FAKE_", "")  # nothing of the secret is left (the host and path of a URL have no FAKE)
    assert MASK in out and out.startswith("before ") and out.endswith(" after")


def test_bearer_value_is_masked_and_the_url_host_stays():
    assert redact("Authorization: Bearer FAKEFAKEFAKE.0000", {}) == f"Authorization: {MASK}"
    assert redact(FAKE_URL, {}) == f"https://{MASK}@github.com/vibhu-0511/argus.git"


def test_ordinary_text_is_left_alone():
    text = "task-runner ran sk-short and ARGUS_STEP=fix at https://github.com/vibhu-0511/argus.git"
    assert redact(text, ENV) == text


def _run(tmp_path: Path, reply_text: str, tool_text: str):
    model = "openai/gpt-oss-20b"
    replies = iter(
        [
            Completion(json.dumps({"tool": "read_file", "arguments": {}}) + " " + reply_text, Usage(10, 5, 0), {}),
            Completion(json.dumps({"tool": "submit", "arguments": {}}), Usage(10, 5, 0), {}),
        ]
    )
    return run_fix(
        worktree=tmp_path,
        model=model,
        ledger=Ledger(tmp_path / "ledger.json", {model: ModelQuota(100, 10**9, 100, 10**9, False)}),
        complete=lambda _messages: next(replies),
        out_dir=tmp_path / "out",
        step_cap=5,
        token_cap=1000,
        run_id="run-1",
        host="test",
        git_commit="abc",
        task_id="bug-17",
        system="system",
        user="fix it",
        execute=lambda name, _payload: ToolResult(tool=name, text=tool_text),
    )


def test_trajectory_file_has_no_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGUS_MODEL_API_KEY", FAKE_ENV_VALUE)
    _run(tmp_path, f"token {FAKE_PAT}", f"env dump: ARGUS_MODEL_API_KEY={FAKE_ENV_VALUE} remote {FAKE_URL}")
    text = (tmp_path / "out" / "trajectory.jsonl").read_text(encoding="utf-8")
    for secret in (FAKE_PAT, FAKE_ENV_VALUE, "ghs_FAKEFAKEFAKEFAKEFAKE0000"):
        assert secret not in text
    assert MASK in text
    Trajectory.from_jsonl(text)  # still a valid trajectory


def test_spans_have_no_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGUS_MODEL_API_KEY", FAKE_ENV_VALUE)
    exporter = InMemorySpanExporter()
    start_tracing(exporter)
    _run(tmp_path, f"token {FAKE_PAT}", "ok")
    with pytest.raises(RuntimeError):
        with tool_span("run_cmd", run_id="run-1", step=2) as span:
            record_tool_error(span, f"failed: Bearer {FAKE_APP_TOKEN}", failed=False)
            raise RuntimeError(f"push to {FAKE_URL} with {FAKE_ENV_VALUE}")
    spans = exporter.get_finished_spans()
    assert len(spans) >= 5
    dump = json.dumps(
        [
            {
                "attributes": dict(s.attributes),
                "events": [dict(e.attributes or {}) for e in s.events],
                "status": s.status.description,
            }
            for s in spans
        ],
        default=str,
    )
    for secret in (FAKE_PAT, FAKE_ENV_VALUE, FAKE_APP_TOKEN, "ghs_FAKEFAKEFAKEFAKEFAKE0000"):
        assert secret not in dump
    failed = next(s for s in spans if s.name == "execute_tool run_cmd")
    assert MASK in failed.status.description and MASK in failed.attributes["argus.tool.error"]
    assert any(MASK in str(e.attributes) for e in failed.events)  # the recorded exception is masked too
