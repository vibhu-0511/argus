"""P10-T05: FixLoopRunner drives fix_loop.run_fix with a SCRIPTED model (a plain function) in a temp git repo.

No model is called: `scripted()` hands out answers from a list. The temp repo is made with plain git, offline.
"""

import json
import subprocess
from pathlib import Path

import pytest
from argus_core.client import Completion, Usage
from argus_core.types import StopReason, Trajectory
from flow.states import State

import argus_workbench.fixloop_runner as module
from argus_workbench import fixtures, store
from argus_workbench.fixloop_runner import FixLoopRunner

TICKET = {"id": "T-5", "text": "SIMULATED ticket: make the header colour blue."}


def git(tree, *args):
    subprocess.run(["git", "-C", str(tree), "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args], check=True, capture_output=True)


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    (root / "header.css").write_bytes(b".header {\n  color: red;\n}\n")
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "base")
    return root


def answer(tool, arguments, tokens=(10, 5, 0)):
    content = json.dumps({"tool": tool, "arguments": arguments})
    return Completion(content, Usage(*tokens), {"choices": [{"message": {"content": content}}]})


def scripted(*answers):
    """A model stand-in: the next prepared answer each time it is asked. It touches no network."""
    queue = list(answers)
    return lambda messages: queue.pop(0)


def run(tree, model, **kw):
    store.create_run(TICKET, scenario="normal", run_id="run-fl", clock=fixtures.fixed_clock())
    runner = FixLoopRunner(model, worktree=tree, **kw)
    return runner.play(store.run_dir("run-fl"), clock=fixtures.fixed_clock())


GOOD = (
    answer("read_file", {"path": "header.css"}, (100, 5, 0)),
    answer("edit", {"path": "header.css", "old": "red", "new": "blue"}, (120, 30, 100)),
    answer("submit", {}, (40, 3, 100)),
)


def test_a_scripted_fix_run_becomes_a_valid_simulated_run_folder(tree):
    end = run(tree, scripted(*GOOD))
    assert (end.state, end.stop_reason, end.origin, end.display_state) == (State.FAILED, StopReason.submit, "SIMULATED", "failed")
    raw = (store.run_dir("run-fl") / "trajectory.jsonl").read_text("utf-8")
    trajectory = Trajectory.from_jsonl(raw)  # the argus-core trajectory schema
    assert store.read_file("run-fl", "trajectory.jsonl").steps == trajectory.steps  # and the store accepts it
    assert [s.tool_name for s in trajectory.steps] == ["read_file", "edit", "submit"] and trajectory.steps[-1].stop_reason is StopReason.submit
    assert [(s.tokens_in, s.tokens_out, s.tokens_cached) for s in trajectory.steps] == [(100, 5, 0), (120, 30, 100), (40, 3, 100)]
    assert [s.index for s in trajectory.steps] == [0, 1, 2]
    for step in trajectory.steps:
        assert step.message["origin"] == "SIMULATED" and step.message["stage"] == "fix" and "text" in step.message
    assert trajectory.meta.run_id == "run-fl" and trajectory.meta.task_id == "T-5" and trajectory.meta.host == "simulated"
    assert store.get_state("run-fl") == end


def test_the_patch_is_the_worktree_diff_with_a_simulated_header(tree):
    run(tree, scripted(*GOOD))
    patch = store.read_file("run-fl", "patch.diff")
    assert patch.startswith("# SIMULATED") and "-  color: red;" in patch and "+  color: blue;" in patch
    assert (tree / "header.css").read_text("utf-8") == ".header {\n  color: blue;\n}\n"
    assert sorted(p.name for p in store.run_dir("run-fl").iterdir()) == ["patch.diff", "state.json", "ticket.json", "trajectory.jsonl"]


def test_a_run_with_no_edit_has_no_patch_file(tree):
    run(tree, scripted(answer("read_file", {"path": "header.css"}), answer("submit", {})))
    assert not (store.run_dir("run-fl") / "patch.diff").exists()


def test_stuck_is_carried_over(tree):
    same = answer("read_file", {"path": "header.css"})
    end = run(tree, scripted(same, same, same))
    assert (end.state, end.stop_reason, end.display_state) == (State.FAILED, StopReason.stuck, "stuck")


def test_a_shell_tool_is_refused_by_default(tree):
    end = run(tree, scripted(answer("run_cmd", {"command": "echo pwned > pwned.txt"}), answer("submit", {})))
    steps = store.read_file("run-fl", "trajectory.jsonl").steps
    assert steps[0].tool_error == "not-allowed" and not (tree / "pwned.txt").exists() and end.stop_reason is StopReason.submit


def test_only_legal_transitions_are_taken(tree, monkeypatch):
    seen = []
    real = store.advance
    monkeypatch.setattr(store, "advance", lambda rid, ev, **kw: seen.append(ev.value) or real(rid, ev, **kw))
    run(tree, scripted(*GOOD))
    assert seen == ["start", "repro_ok", "fix_failed"]  # reproducing -> fixing -> failed


def test_the_adapter_needs_a_model_function_and_has_no_default():
    with pytest.raises(TypeError):
        FixLoopRunner(worktree=Path("."))  # no model argument at all
    with pytest.raises(TypeError):
        FixLoopRunner(None, worktree=Path("."))
    with pytest.raises(TypeError):
        FixLoopRunner("a model name", worktree=Path("."))


def test_it_says_never_run_against_a_real_model():
    assert "NEVER RUN AGAINST A REAL MODEL" in module.__doc__
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text("utf-8")
    assert "never run against a real model" in readme.lower()


def test_importing_it_reads_no_secret_env(monkeypatch):
    import importlib
    import re
    import sys

    seen = []
    real_get = __import__("os").environ.get
    monkeypatch.setattr("os.environ.get", lambda k, *a: seen.append(k) or real_get(k, *a), raising=False)
    monkeypatch.delitem(sys.modules, "argus_workbench.fixloop_runner")
    importlib.import_module("argus_workbench.fixloop_runner")
    assert not [k for k in seen if re.search(r"KEY|TOKEN|SECRET|MODEL|URL|OPENAI|ANTHROPIC|OLLAMA", k.upper())]
