"""flow.agent_job with fake steps (P6-T04). No model call, no network, no Docker."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from test_actions import FakeGitHub, make_zip, runner

from flow import agent_job
from flow.actions import MAX_MEMBER, parse_artifact
from flow.agent_job import Job, StepResult, StepUnavailable, main, scrub
from flow.states import effect_key
from flow.workflow import Outcome

TOKEN = "ghp_0123456789abcdefghijklmnopqrstuv"
MODEL_KEY = "gsk_abcdefghijklmnopqrstuvwxyz0123"
TICKET = "acme/app#7"
KEY = effect_key(TICKET, "dispatch-fix")


def env_for(out: Path, step: str = "fix", **extra: str) -> dict[str, str]:
    return {"ARGUS_TICKET_ID": TICKET, "ARGUS_STEP": step, "ARGUS_RUN_KEY": KEY, "ARGUS_OUT": str(out), **extra}


def only(step: str, fn):
    """Steps where the two other steps must not be called."""
    def boom(job: Job) -> StepResult:
        raise AssertionError("the wrong step ran")
    return {s: (fn if s == step else boom) for s in ("repro", "fix", "verify")}


def result_of(out: Path) -> dict:
    return json.loads((out / "result.json").read_text(encoding="utf-8"))


def artifact_of(out: Path) -> bytes:
    """What actions/upload-artifact makes of the three files: a zip with them at the root."""
    files = {p.name: p.read_text(encoding="utf-8") for p in out.iterdir() if p.name in ("result.json", "patch.diff", "trajectory.jsonl")}
    return make_zip(files)


@pytest.mark.parametrize("step", ["repro", "fix", "verify"])
def test_runs_exactly_the_named_step_and_writes_its_files(tmp_path, step):
    seen: list[Job] = []

    def fake(job: Job) -> StepResult:
        seen.append(job)
        return StepResult(True, f"{step} output", patch="diff --git a/x b/x\n", trajectory='{"step": 0}\n')

    code = main(env_for(tmp_path, step, ARGUS_UPSTREAM="from env"), only(step, fake))
    assert code == 0
    assert [j.step for j in seen] == [step] and seen[0].ticket_id == TICKET and seen[0].run_key == KEY
    assert result_of(tmp_path) == {"ok": True, "output": f"{step} output"}
    assert (tmp_path / "patch.diff").read_text(encoding="utf-8") == "diff --git a/x b/x\n"
    assert (tmp_path / "trajectory.jsonl").read_text(encoding="utf-8") == '{"step": 0}\n'


def test_empty_patch_and_trajectory_are_not_written(tmp_path):
    assert main(env_for(tmp_path), only("fix", lambda job: StepResult(True, "x"))) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["result.json"]


def test_upstream_file_wins_over_env_and_env_is_the_fallback(tmp_path):
    got: list[str] = []
    fake = lambda job: got.append(job.upstream) or StepResult(True, "")  # noqa: E731
    (tmp_path / "upstream.txt").write_text("from file", encoding="utf-8")
    main(env_for(tmp_path, ARGUS_UPSTREAM="from env"), only("fix", fake))
    (tmp_path / "upstream.txt").unlink()
    main(env_for(tmp_path, ARGUS_UPSTREAM="from env"), only("fix", fake))
    assert got == ["from file", "from env"]


def test_a_step_that_reports_failure_exits_1_with_ok_false(tmp_path):
    code = main(env_for(tmp_path), only("fix", lambda job: StepResult(False, "no valid reproduction: step-cap", trajectory="{}\n")))
    assert code == 1
    assert result_of(tmp_path) == {"ok": False, "output": "no valid reproduction: step-cap"}
    assert (tmp_path / "trajectory.jsonl").exists()  # a failed step keeps its trajectory


def test_a_crash_becomes_a_failure_result_without_the_secret(tmp_path):
    def crash(job: Job) -> StepResult:
        raise RuntimeError(f"401 from the model host, header Authorization: Bearer {MODEL_KEY} and token {TOKEN}")

    env = env_for(tmp_path, ARGUS_MODEL_API_KEY=MODEL_KEY, GITHUB_TOKEN=TOKEN)
    assert main(env, only("fix", crash)) == 1
    result = result_of(tmp_path)
    assert result["ok"] is False and result["output"].startswith("RuntimeError: 401 from the model host")
    for name in tmp_path.iterdir():
        text = name.read_text(encoding="utf-8")
        assert MODEL_KEY not in text and TOKEN not in text


def test_a_failure_reason_from_the_step_is_scrubbed_too(tmp_path):
    env = env_for(tmp_path, SOME_PASSWORD="hunter2-hunter2")
    main(env, only("fix", lambda job: StepResult(False, "login failed for hunter2-hunter2")))
    assert result_of(tmp_path)["output"] == "login failed for ***"


def test_scrub_catches_token_shapes_that_are_not_in_the_environment():
    text = f"a {TOKEN} b github_pat_{'A' * 30} c sk-{'b' * 24} d Bearer abc.def"
    assert scrub(text, {}) == "a *** b *** c *** d ***"
    assert scrub("ARGUS_STEP=fix", {"ARGUS_STEP": "fix", "OTHER_KEY": "xy"}) == "ARGUS_STEP=fix"  # not secret-named, or too short


@pytest.mark.parametrize("bad", [{"ARGUS_STEP": "deploy"}, {"ARGUS_STEP": ""}, {"ARGUS_TICKET_ID": ""}, {"ARGUS_RUN_KEY": ""}])
def test_bad_environment_is_a_failure_result_and_no_step_runs(tmp_path, bad):
    env = {**env_for(tmp_path), **bad}
    assert main(env, only("none", lambda job: StepResult(True, ""))) == 1
    result = result_of(tmp_path)
    assert result["ok"] is False and ("must be set" in result["output"] or "ARGUS_STEP" in result["output"])


def test_output_over_the_artifact_limit_is_a_failure_not_a_broken_artifact(tmp_path):
    big = "x" * (MAX_MEMBER + 1)
    assert main(env_for(tmp_path), only("fix", lambda job: StepResult(True, "ok", patch=big))) == 1
    result = result_of(tmp_path)
    assert result["ok"] is False and "patch.diff" in result["output"]
    assert not (tmp_path / "patch.diff").exists()
    parse_artifact(artifact_of(tmp_path))  # still a readable artifact


def test_no_half_written_result_file_is_left_behind(tmp_path):
    main(env_for(tmp_path), only("fix", lambda job: StepResult(True, "x")))
    assert not (tmp_path / "result.json.tmp").exists()


# --- the runner reads what the job wrote ---------------------------------------------------------------------


def test_round_trip_through_parse_artifact_for_success_and_failure(tmp_path):
    ok_dir, bad_dir = tmp_path / "ok", tmp_path / "bad"
    main(env_for(ok_dir), only("fix", lambda job: StepResult(True, "the patch", patch="the patch", trajectory="{}\n")))
    main(env_for(bad_dir), only("fix", lambda job: (_ for _ in ()).throw(ValueError(f"bad {TOKEN}"))), )
    ok = parse_artifact(artifact_of(ok_dir), "https://run")
    assert (ok.ok, ok.output, ok.patch, ok.trajectory, ok.run_url) == (True, "the patch", "the patch", "{}\n", "https://run")
    bad = parse_artifact(artifact_of(bad_dir))
    assert bad.ok is False and bad.output.startswith("ValueError: bad ") and TOKEN not in bad.output


def test_actions_runner_returns_the_outcome_the_job_wrote(tmp_path):
    main(env_for(tmp_path), only("fix", lambda job: StepResult(True, "diff --git a/x b/x\n", patch="diff --git a/x b/x\n", trajectory='{"step": 0}\n')))
    gh = FakeGitHub(archive=artifact_of(tmp_path))
    r = runner(gh)
    assert r.run(TICKET, KEY, "repro script") == Outcome(True, "diff --git a/x b/x\n")
    assert r.artifacts[KEY].trajectory == '{"step": 0}\n'


def test_actions_runner_returns_a_failed_job_as_outcome_false_with_the_reason(tmp_path):
    main(env_for(tmp_path, GITHUB_TOKEN=TOKEN), only("fix", lambda job: (_ for _ in ()).throw(RuntimeError(f"nope {TOKEN}"))))
    gh = FakeGitHub(archive=artifact_of(tmp_path), conclusion="failure")  # exit code 1 makes the run fail
    out = runner(gh).run(TICKET, KEY, "")
    assert out.ok is False and "RuntimeError: nope ***" in out.output and TOKEN not in out.output


# --- the default steps and the real command line ---------------------------------------------------------------


@pytest.mark.parametrize("step", ["repro", "fix", "verify"])
def test_default_steps_refuse_a_live_issue_with_a_reason(tmp_path, step):
    assert main(env_for(tmp_path, step, ARGUS_MODEL_API_KEY=MODEL_KEY)) == 1
    result = result_of(tmp_path)
    assert result["ok"] is False and "not a seeded task" in result["output"] and MODEL_KEY not in result["output"]


def test_default_steps_need_the_model_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ARGUS_MODEL_API_KEY", raising=False)
    seeded = next(agent_job.SEEDED.iterdir()).name
    env = {**env_for(tmp_path, "repro"), "ARGUS_TICKET_ID": seeded}
    assert main(env) == 1
    assert "ARGUS_MODEL_API_KEY is not set" in result_of(tmp_path)["output"]


def test_python_dash_m_flow_agent_job_runs_the_way_the_workflow_runs_it(tmp_path):
    env = {**os.environ, **env_for(tmp_path, "verify")}
    done = subprocess.run([sys.executable, "-m", "flow.agent_job"], env=env, capture_output=True, text=True, timeout=120)
    assert done.returncode == 1
    assert result_of(tmp_path)["ok"] is False
    assert zipfile.is_zipfile(artifact_of_path(tmp_path))


def artifact_of_path(out: Path) -> Path:
    path = out.parent / (out.name + ".zip")
    path.write_bytes(artifact_of(out))
    return path


def test_step_unavailable_is_a_plain_runtime_error():
    assert issubclass(StepUnavailable, RuntimeError)
