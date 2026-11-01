"""P5-T06: a stubbed fix-loop run emits agent, model-call and tool-call spans to an in-memory exporter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.telemetry import start_tracing

from fix_loop.loop import run_fix
from fix_loop.tools import ToolResult


def _completion(tool: str, tokens_in: int, tokens_cached: int) -> Completion:
    content = json.dumps({"tool": tool, "arguments": {}})
    raw = {"id": "cmpl-1", "model": "m", "choices": [{"finish_reason": "stop", "message": {"content": content}}]}
    return Completion(content, Usage(tokens_in, 7, tokens_cached), raw)


def _run(tmp_path: Path, model: str):
    exporter = InMemorySpanExporter()
    start_tracing(exporter)
    quota = ModelQuota(100, 10**9, 100, 10**9, False)
    replies = iter([_completion("read_file", 100, 40), _completion("submit", 100, 0)])
    result = run_fix(
        worktree=tmp_path,
        model=model,
        ledger=Ledger(tmp_path / "ledger.json", {model: quota}),
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
        execute=lambda name, _payload: ToolResult(tool=name, text="ok"),
    )
    return result, {span.name: span for span in reversed(exporter.get_finished_spans())}, exporter.get_finished_spans()


def test_priced_model_spans(tmp_path: Path):
    result, _, spans = _run(tmp_path, "openai/gpt-oss-20b")
    agent = next(s for s in spans if s.name == "invoke_agent fix-loop")
    chats = [s for s in spans if s.name.startswith("chat ")]
    tools = [s for s in spans if s.name.startswith("execute_tool ")]
    assert agent.attributes["argus.stop_reason"] == result.stop_reason.value == "submit"
    assert agent.attributes["gen_ai.conversation.id"] == "run-1"
    assert agent.attributes["argus.task.id"] == "bug-17"
    assert [s.name for s in tools] == ["execute_tool read_file", "execute_tool submit"]
    assert len(chats) == 2
    first = min(chats, key=lambda s: s.attributes["argus.step.index"])
    assert first.name == "chat openai/gpt-oss-20b"
    assert first.attributes["gen_ai.request.model"] == "openai/gpt-oss-20b"
    assert first.attributes["gen_ai.usage.input_tokens"] == 100
    assert first.attributes["gen_ai.usage.output_tokens"] == 7
    assert first.attributes["gen_ai.usage.cache_read.input_tokens"] == 40
    assert first.attributes["gen_ai.response.finish_reasons"] == ("stop",)
    assert first.attributes["argus.usage.cost_usd"] == pytest.approx((60 * 0.075 + 40 * 0.0375 + 7 * 0.30) / 1e6)
    assert "gen_ai.usage.cache_read.input_tokens" not in max(chats, key=lambda s: s.attributes["argus.step.index"]).attributes
    assert all(s.parent.span_id == agent.context.span_id for s in chats + tools)
    assert all(s.resource.attributes["argus.trace.schema_version"] == "1" for s in spans)


def test_unpriced_model_still_runs_and_has_no_cost(tmp_path: Path):
    result, _, spans = _run(tmp_path, "no-such-model")
    assert result.stop_reason.value == "submit"
    chats = [s for s in spans if s.name.startswith("chat ")]
    assert len(chats) == 2
    assert all("argus.usage.cost_usd" not in s.attributes for s in chats)
    assert all(s.attributes["gen_ai.usage.input_tokens"] == 100 for s in chats)
