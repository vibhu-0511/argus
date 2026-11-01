import json
from pathlib import Path

import httpx
import pytest

import argus_core.client as client_mod
from argus_bench.baseline import baseline_task
from argus_core.ledger import QuotaExceeded

PATCH = (
    "--- a/apps/canvas/src/styles/landing.css\n"
    "+++ b/apps/canvas/src/styles/landing.css\n"
    "@@\n"
    "-font-size: 8px;\n"
    "+font-size: 16px;\n"
)
GOLDEN = "GOLDEN-DISTINCTIVE-NOT-SENT"
HUNK = "HUNK-ONLY-IN-BUG-PATCH"
CSS = "apps/canvas/src/styles/landing.css"


def _task(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "ticket.json").write_text(
        json.dumps({"id": "baseline-probe", "text": "The label is 8 px."}),
        encoding="utf-8",
    )
    (directory / "meta.json").write_text(
        json.dumps({"source": "seeded", "archetype": "font-size", "tier": "easy", "seed": None}),
        encoding="utf-8",
    )
    (directory / "checks.json").write_text(
        json.dumps(
            [
                {
                    "type": "computed_style",
                    "params": {
                        "flow": "/login",
                        "selector": "#probe",
                        "property": "font-size",
                        "expected": "16px",
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    (directory / "bug.patch").write_text(
        f"--- a/{CSS}\n+++ b/{CSS}\n@@\n-{HUNK}\n+kept\n",
        encoding="utf-8",
    )
    (directory / "golden.patch").write_text(
        f"--- a/{CSS}\n+++ b/{CSS}\n@@\n-kept\n+{GOLDEN}\n",
        encoding="utf-8",
    )


def _world(tmp_path: Path) -> tuple[Path, Path, Path]:
    task = tmp_path / "task"
    _task(task)
    tree = tmp_path / "tree"
    css = tree / CSS
    css.parent.mkdir(parents=True)
    css.write_text("font-size: 8px;", encoding="utf-8")
    return task, tree, tmp_path / "ledger.json"


def _install(monkeypatch, calls: list) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": PATCH}}],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "prompt_tokens_details": {"cached_tokens": 3},
                },
            },
        )

    transport = httpx.MockTransport(handler)
    real = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(client_mod.httpx, "Client", factory)


def test_baseline_one_call_records_tokens(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("ARGUS_MODEL_API_KEY", "unit-test-not-a-secret")
    task, tree, ledger = _world(tmp_path)
    calls: list = []
    _install(monkeypatch, calls)
    css = tree / CSS
    before = css.read_text(encoding="utf-8")

    assert baseline_task(str(task), tree, ledger_path=ledger) == 0

    captured = capsys.readouterr()
    assert captured.out == PATCH
    assert "unit-test-not-a-secret" not in captured.out
    assert "unit-test-not-a-secret" not in captured.err
    assert css.read_text(encoding="utf-8") == before
    assert len(calls) == 1
    body = calls[0]
    assert "tools" not in body
    assert len(body["messages"]) == 1
    assert body["messages"][0]["role"] == "user"
    content = body["messages"][0]["content"]
    assert "The label is 8 px." in content
    assert "font-size: 8px;" in content
    assert GOLDEN not in content
    assert HUNK not in content
    assert "computed_style" not in content
    state = json.loads(ledger.read_text(encoding="utf-8"))
    bucket = state["models"]["openai/gpt-oss-20b"]
    assert bucket["requests"] == 1
    assert bucket["tokens"] == 15


def test_unknown_model_raises_before_http(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ARGUS_MODEL_API_KEY", "unit-test-not-a-secret")
    task, tree, ledger = _world(tmp_path)
    calls: list = []
    _install(monkeypatch, calls)
    with pytest.raises(QuotaExceeded):
        baseline_task(str(task), tree, model="no-such-model", ledger_path=ledger)
    assert calls == []


def test_key_unset_skips_http(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.delenv("ARGUS_MODEL_API_KEY", raising=False)
    task, tree, ledger = _world(tmp_path)
    calls: list = []
    _install(monkeypatch, calls)
    assert baseline_task(str(task), tree, ledger_path=ledger) == 2
    assert "key unset" in capsys.readouterr().out
    assert calls == []


def test_missing_task_skips_http(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("ARGUS_MODEL_API_KEY", "unit-test-not-a-secret")
    calls: list = []
    _install(monkeypatch, calls)
    code = baseline_task(str(tmp_path / "nope"), tmp_path, ledger_path=tmp_path / "ledger.json")
    captured = capsys.readouterr()
    assert code == 2
    assert "missing task" in captured.err
    assert "unit-test-not-a-secret" not in captured.err
    assert calls == []
