"""Variant E run (P3-T17/T20): mini-swe-agent through the relay, in the Argus Docker sandbox, scored like the other variants.

    mini_run.py <task dir> <run id> [port]      blocks until the run ends (run it with run_in_background)

Run it through mini_run.sh: the pinned mini venv (.local/mini-venv) runs it, ARGUS_PYTHON (the main venv) scores.
Config is mini.yaml with the ADR-011 overrides: cost_limit 0, cost_tracking ignore_errors, --network none (plus the Argus
cpu and memory caps, worktree mount, read-only checks mount), interpreter ["bash", "-lc"]. One addition: step_limit 20, the
same cap as the Argus loop, because stock mini has no step cap and every step here is a subagent. Endpoint: litellm reads OPENAI_BASE_URL.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from minisweagent.agents.default import DefaultAgent
from minisweagent.config import builtin_config_dir
from minisweagent.environments.docker import DockerEnvironment
from minisweagent.models.litellm_model import LitellmModel

from argus_core.types import StopReason, Trajectory, TrajectoryMeta, TrajectoryStep
from fix_loop import sandbox, turn, worktree

RUNS, REPO = turn.RUNS, turn.REPO
IMAGE = "argus-mini-sandbox:p3"
STEP_LIMIT = 20
EXIT_REASON = {"Submitted": StopReason.submit, "LimitsExceeded": StopReason.step_cap}  # other mini exits keep mini's name


def est(text: str) -> int:
    return max(1, len(text) // 4)


def convert(messages: list[dict], meta: TrajectoryMeta, exit_status: str) -> str:
    """Map the mini message list to Trajectory JSONL: one step per assistant message, the observation as its message."""
    steps = []
    for i, msg in enumerate(messages):
        if msg.get("role") != "assistant":
            continue
        before = json.dumps([{k: v for k, v in m.items() if k != "extra"} for m in messages[:i]])
        calls = msg.get("tool_calls") or []
        raw = calls[0]["function"]["arguments"] if calls else (msg.get("content") or "")
        nxt = messages[i + 1] if i + 1 < len(messages) else {}
        text = str(nxt.get("content") or "")
        failed = nxt.get("role") == "user"  # a format error comes back as a user message
        steps.append(TrajectoryStep(
            index=len(steps), tokens_in=est(before), tokens_out=est(raw), raw_response=raw, tool_name="bash" if calls else None,
            tool_error=text[:200] if failed else None, message={"text": text},
        ))
    if steps and exit_status in EXIT_REASON:
        steps[-1] = steps[-1].model_copy(update={"stop_reason": EXIT_REASON[exit_status]})
    return Trajectory(meta=meta, steps=steps).to_jsonl()


def main(task: Path, run_id: str, port: str = "8765") -> int:
    out = RUNS / run_id
    (out / "mini").mkdir(parents=True, exist_ok=False)
    checks = out / "checks"
    checks.mkdir()
    shutil.copy(task / "checks.json", checks / "checks.json")  # golden.patch stays out of the mount
    tree = worktree.create(turn._platform(), task.name, "HEAD", root=out)
    turn._reset(tree, (task / "bug.patch").read_text(encoding="utf-8"))
    ticket = json.loads((task / "ticket.json").read_text(encoding="utf-8"))
    (out / "task.json").write_text(json.dumps({"task": str(task), "tree": str(tree), "strategy": "mini", "budget": None}), encoding="utf-8")
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{port}/{run_id}/v1"
    os.environ["OPENAI_API_KEY"] = "relay-local"  # not a credential: the relay ignores it
    cfg = yaml.safe_load((builtin_config_dir / "mini.yaml").read_text(encoding="utf-8"))
    model = LitellmModel(model_name=f"openai/{turn.MODEL}", cost_tracking="ignore_errors",
                         model_kwargs={**cfg["model"]["model_kwargs"], "timeout": 4 * 3600},
                         observation_template=cfg["model"]["observation_template"], format_error_template=cfg["model"]["format_error_template"])
    env = DockerEnvironment(image=IMAGE, cwd="/work", env=cfg["environment"]["env"], timeout=30, interpreter=["bash", "-lc"], container_timeout="12h",
                            run_args=["--rm", "--network", "none", "--cpus", sandbox.CPUS, "--memory", sandbox.MEMORY,
                                      "-v", f"{tree.resolve()}:/work", "-v", f"{checks.resolve()}:/checks:ro"])
    agent = DefaultAgent(model, env, **{**cfg["agent"], "cost_limit": 0, "step_limit": STEP_LIMIT, "output_path": out / "mini-traj.json"})
    try:
        info = agent.run(ticket["text"])
        exit_status = info.get("exit_status", "")
    except Exception as exc:  # mini re-raises after saving an exit message; keep the name
        exit_status = type(exc).__name__
    subprocess.run(["docker", "rm", "-f", env.container_id], capture_output=True)  # mini's own cleanup uses a POSIX shell line that fails on Windows
    code = subprocess.run([os.environ["ARGUS_PYTHON"], "-m", "argus_bench.cli", "score", str(task), "--tree", str(tree)],
                          cwd=REPO, capture_output=True, text=True, encoding="utf-8").returncode
    system = agent.messages[0]["content"] + agent.messages[1]["content"] if len(agent.messages) > 1 else ""
    meta = TrajectoryMeta(run_id=run_id, task_id=ticket["id"], model=turn.MODEL, host=turn.HOST, prompt_hash=hashlib.sha256(system.encode()).hexdigest(), git_commit=turn._head())
    (out / "trajectory.jsonl").write_text(convert(agent.messages, meta, exit_status), encoding="utf-8", newline="\n")
    verdict = {"task_id": ticket["id"], "stop_reason": str(getattr(EXIT_REASON.get(exit_status), "value", exit_status)), "score_exit": code,
               "verdict": "excluded" if code == 2 else "resolved" if code == 0 else "unresolved", "model": turn.MODEL,
               "model_turns": agent.n_calls, "token_source": "chars/4 estimate", "variant": "E mini-swe-agent"}
    (out / "diff.patch").write_text(turn._git(tree, "diff").stdout, encoding="utf-8", newline="\n")
    worktree.destroy(turn._platform(), tree)
    (out / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]).resolve(), sys.argv[2], *sys.argv[3:4]))
