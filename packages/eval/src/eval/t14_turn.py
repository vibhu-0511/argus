"""P5-T14 with Claude sessions as the model: repro stage, then fix stage, one fresh subagent per model turn.

No provider call. Each driver call replays the whole pipeline for one task from `answers.jsonl` (as `fix_loop.turn` does for
the fix loop alone): `run_repro` (stage `repro`), then `run_fix` (stage `fix`), both through a `Router` over the variant's
policy. The first model call with no stored answer ends the call and prints what that turn's model must see. Every
stored answer records its stage, tier and model, and every trajectory step carries the same tier, host and model.

    python -m eval.t14_turn start <A|B|S|T> <task id>    e.g. start B seed-h05   (run id: B-seed-h05)
    python -m eval.t14_turn show <run id>                print the pending turn (stage, tier, worker model, messages)
    python -m eval.t14_turn answer <run id> < reply      store one reply; prints one status line, not the next turn
    python -m eval.t14_turn status <run id>              the status line again (what the coordinator needs), or the verdict
    python -m eval.t14_turn results <A|B> --tasks F --out F [--only ID ...]   fold finished runs into a results JSON

The status line says which subagent model the next worker must run on (`worker_model=sonnet|haiku`), or is the verdict.
Variant A: every stage on sonnet. Variant B: repro on haiku, fix on sonnet (policies/claude-*.yaml). Variant T (P5.5-T04): a
train mutant from packages/bench/tasks/mutated, fix stage only on sonnet (no repro stage), runs under runs/p55-t04/<task id>. Variant S (P5.5-T08): a seeded task, fix stage only on sonnet, with the reviewed skills
loaded (`skills=packages/skills/skills`), runs under runs/p55-t08/<task id>. Tokens are chars/4
estimates of the messages, not provider usage, and exclude the harness overhead of each subagent.

ponytail: the repro tree runner needs the rig up (`python -m repro_agent.trees up`) and ARGUS_PLATFORM_REPO. A replay runs the
fix tools again from a clean tree each turn, so cost per turn grows with the answers so far (as in the P3/P4 driver).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from argus_core.router import Router, load_policy
from argus_core.types import Task, Ticket, Trajectory

from eval.ablation import POLICIES, SEEDED, _totals
from eval.runner import AgentConfig, Outcome, load_tasks, run_eval

HOST = "claude-session"
RUNS = Path(os.environ.get("T14_RUNS") or Path(__file__).resolve().parents[2] / "runs" / "t14")
TRAIN_RUNS = Path(__file__).resolve().parents[2] / "runs" / "p55-t04"  # variant T: no <variant> folder, the task ids are mut-NNNN
SKILL_RUNS = Path(__file__).resolve().parents[2] / "runs" / "p55-t08"  # variant S: no <variant> folder, the task ids are seed-xNN
SKILLS = Path(__file__).resolve().parents[2].parent / "skills" / "skills"  # variant S: the T06 reviewed skills, pinned in ../skills.lock.json
NO_REPRO = frozenset({"S", "T"})  # fix stage only; the repro stage found a script in 0 of 29 variant A runs, so A's fix prompt said `Repro: not-run` too
MUTATED = SEEDED.parent / "mutated"
VARIANTS = {"A": ("ablation-A-claude-strong-only", POLICIES / "claude-strong-only.yaml"), "B": ("ablation-B-claude-routed", POLICIES / "claude-routed.yaml"),
            "C": ("breakit-C-claude-cheap-fix", POLICIES / "claude-cheap-fix.yaml"),  # C: P5-T27 break-it, fix on the cheap tier
            "T": ("p55-t04-train-fix-only", POLICIES / "claude-strong-only.yaml"),  # T: P5.5-T04, train mutants, fix stage only
            "S": ("p55-t08-skills-fix-only", POLICIES / "claude-strong-only.yaml")}  # S: P5.5-T08, seeded tasks, fix stage only, skills on
WORKER_MODEL = {"claude-sonnet-5-5": "sonnet", "claude-haiku-5-5": "haiku"}  # the Agent tool's `model` parameter
STRATEGY, BUDGET_TOKENS = "cap", 32_000  # the fix loop's context strategy and budget, the P3/P4 harness defaults
REPRO_CAP = 3
TOOL_TIMEOUT = 300  # run_repro's per-script limit; a script takes 15 to 25 s on an idle machine, more when several runs share it
# Self-imposed run budget, NOT a provider limit (docs/quotas.md has no Claude row and none was added). The ledger refuses a
# model without a row, so the two tiers get one that never binds: a fresh ledger is built on every replay.
SELF_IMPOSED = ModelQuota(300, 10**7, 300, 10**7, False)
BUDGET = {model: SELF_IMPOSED for model in WORKER_MODEL}

BRIEF = """

Where the script runs: the dcortex Canvas console, served at a base URL. `page` is a Playwright page already open on /login
(the signed-out landing screen). Use relative URLs, for example `await page.goto('/ops/radar')`. Signed-in screens
(session mocked, no backend, the data is made up): /ops/radar, /ops/operations, /ops/launchpad, /ops/rules.
`expect` supports, on a locator: toBeVisible, toBeHidden, toBeEnabled, toBeDisabled, toBeChecked, toHaveText,
toContainText, toHaveCount, toHaveCSS(name, value), toHaveAttribute, toHaveClass, toHaveValue; on page: toHaveURL,
toHaveTitle; and `.not`. You cannot see the source code. The script is run on a buggy and on a fixed copy of the app."""


class NeedTurn(Exception):
    def __init__(self, model: str, messages: list[dict]):
        self.model, self.messages = model, messages
        self.stage = self.tier = ""


def _est(text: str) -> int:
    return max(1, len(text) // 4)


class _Replay:
    def __init__(self, answers: list[dict]):
        self.answers, self.n = answers, 0

    def complete(self, model: str, messages: list[dict]) -> Completion:
        if self.n >= len(self.answers):
            raise NeedTurn(model, messages)
        given = self.answers[self.n]
        if given["model"] != model:
            raise RuntimeError(f"answer {self.n} was recorded for {given['model']}, the policy now routes it to {model}")
        self.n += 1
        return Completion(given["reply"], Usage(_est(json.dumps(messages)), _est(given["reply"]), 0), {})


class _StageRouter(Router):
    def complete(self, stage: str, messages: list[dict], *, token_estimate: int = 0):
        try:
            return super().complete(stage, messages, token_estimate=token_estimate)
        except NeedTurn as need:
            need.stage, need.tier = stage, self.policy.stages[stage]
            raise


def _variant_dir(variant: str) -> Path:
    return {"T": TRAIN_RUNS, "S": SKILL_RUNS}.get(variant, RUNS / variant)


def _run_dir(run_id: str) -> Path:
    variant, _, task = run_id.partition("-")
    if variant not in VARIANTS or not task:
        raise SystemExit(f"run id must look like A-seed-h05 or B-seed-h05, got {run_id!r}")
    return _variant_dir(variant) / task


def start(variant: str, task_id: str) -> int:
    from argus_bench.golden import platform_repo
    from fix_loop import worktree

    task = (MUTATED if variant == "T" else SEEDED) / task_id
    if variant not in VARIANTS or not (task / "ticket.json").is_file():
        raise SystemExit(f"usage: start <A|B|S|T> <task id>; {task} not found")
    out = _variant_dir(variant) / task_id
    out.mkdir(parents=True, exist_ok=False)
    (out / "checks").mkdir()
    shutil.copy(task / "checks.json", out / "checks" / "checks.json")  # golden.patch stays out of the mount
    tree = worktree.create(platform_repo(), task_id, "HEAD", root=out / "trees")
    meta = {"task": str(task), "tree": str(tree), "variant": variant, "strategy": STRATEGY, "budget": BUDGET_TOKENS, "started_at": time.time()}
    (out / "task.json").write_text(json.dumps(meta), encoding="utf-8")
    (out / "answers.jsonl").write_text("", encoding="utf-8")
    return _replay(out, quiet=True)


def answer(run_id: str, reply: str) -> int:
    out = _run_dir(run_id)
    if (out / "verdict.json").exists():
        print((out / "verdict.json").read_text(encoding="utf-8"))
        return 0
    pending = json.loads((out / "pending.json").read_text(encoding="utf-8"))
    problem = _wrong_kind(pending["stage"], reply)
    if problem:
        print(f"rejected, nothing recorded: {problem}")
        return 3
    record = {"stage": pending["stage"], "tier": pending["tier"], "model": pending["model"], "reply": reply}
    with (out / "answers.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record) + "\n")
    return _replay(out, quiet=True)


def _wrong_kind(stage: str, reply: str) -> str | None:
    try:
        body = json.loads(reply)
    except json.JSONDecodeError:
        body = None
    is_call = isinstance(body, dict) and "tool" in body
    if stage == "fix" and not is_call:
        return 'this turn is a fix step: reply with one JSON tool call {"tool": ..., "arguments": {...}}'
    if stage == "repro" and (is_call or not reply.strip()):
        return "this turn is a repro step: reply with the Playwright script as plain text, not a tool call"
    return None


def _head() -> str:
    repo = Path(__file__).resolve().parents[4]
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"


def _replay(out: Path, quiet: bool = False) -> int:
    from fix_loop import worktree
    from fix_loop.loop import run_fix
    from fix_loop.strategies import cap_strategy
    from fix_loop.turn import PROTOCOL, STEP_CAP, TOKEN_CAP, _execute, _git, _print_full, _reset
    from argus_bench.golden import platform_repo
    from repro_agent.loop import run_repro
    from repro_agent.trees import trees_for

    meta = json.loads((out / "task.json").read_text(encoding="utf-8"))
    task, tree, variant = Path(meta["task"]), Path(meta["tree"]), meta["variant"]
    ticket = Ticket.model_validate_json((task / "ticket.json").read_text(encoding="utf-8"))
    answers = [json.loads(line) for line in (out / "answers.jsonl").read_text(encoding="utf-8").splitlines() if line]
    policy = load_policy(VARIANTS[variant][1])
    strong = policy.tiers["strong"].primary.model
    run_id = f"{variant}-{ticket.id}"
    _reset(tree, (task / "bug.patch").read_text(encoding="utf-8"))
    # T: the tree is HEAD plus the bug, so a fix that undoes the bug exactly diffs to nothing against HEAD; diff against the bug state
    bug_state = _git(tree, "stash", "create").stdout.strip() if variant in NO_REPRO else ""
    if variant in NO_REPRO and not bug_state:
        raise RuntimeError("git stash create gave no commit; a diff against HEAD would be empty for an exact revert")
    with tempfile.TemporaryDirectory() as scratch:
        router = _StageRouter(policy, Ledger(Path(scratch) / "ledger.json", BUDGET), {HOST: _Replay(answers)})
        try:
            repro = None if variant in NO_REPRO else run_repro(  # S, T: fix stage only (repro found a script in 1 of 58 runs in P5-T14)
                ticket=ticket.model_copy(update={"text": ticket.text + BRIEF}), task_dir=task, model=strong, out_dir=out / "repro", cap=REPRO_CAP,
                run_trees=trees_for(task, out / "trees-cache"), run_id=run_id, host=HOST, git_commit=_head(), router=router, stage="repro",
                tool_timeout=TOOL_TIMEOUT,
            )
            fix = run_fix(
                worktree=tree, model=strong, host=HOST, router=router, stage="fix", out_dir=out / "fix", step_cap=STEP_CAP, token_cap=TOKEN_CAP,
                run_id=run_id, git_commit=_head(), task_id=ticket.id, system=PROTOCOL, execute=_execute(tree, out / "checks"),
                user=f"Ticket:\n{ticket.text}\n\nRepro: {(repro and repro.script) or 'not-run'}\nLocate: none\n",
                context_budget=BUDGET_TOKENS, strategy=cap_strategy, skills=SKILLS if variant == "S" else None,
            )
        except NeedTurn as need:
            worker = WORKER_MODEL[need.model]
            (out / "pending.json").write_text(json.dumps({"stage": need.stage, "tier": need.tier, "model": need.model}), encoding="utf-8")
            if quiet:
                print(f"recorded {len(answers)} answers; next: stage={need.stage} tier={need.tier} worker_model={worker}")
            else:
                print(f"[STAGE {need.stage} | TIER {need.tier} | worker model {worker}]")
                if need.stage == "repro":
                    print("[REPLY WITH THE PLAYWRIGHT SCRIPT AS PLAIN TEXT (a ```js fence is fine), NOT JSON.]")
                _print_full(out, need.messages)
            return 0
    code = subprocess.run(
        [sys.executable, "-m", "argus_bench.cli", "score", str(task), "--tree", str(tree)], capture_output=True, text=True, encoding="utf-8"
    ).returncode
    by_stage: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    for a in answers:
        by_stage[a["stage"]] = by_stage.get(a["stage"], 0) + 1
        by_tier[a["tier"]] = by_tier.get(a["tier"], 0) + 1
    now = time.time()
    verdict = {
        "task_id": ticket.id, "variant": variant, "stop_reason": fix.stop_reason.value, "repro_stop_reason": repro.stop_reason.value if repro else "off",
        "repro_found": repro is not None and repro.script is not None, "score_exit": code,
        "verdict": "excluded" if code == 2 else "resolved" if code == 0 else "unresolved",
        "model_turns": len(answers), "turns_by_stage": by_stage, "turns_by_tier": by_tier, "models": sorted({a["model"] for a in answers}),
        "token_source": "chars/4 estimate", "started_at": meta["started_at"], "finished_at": now, "wall_s": round(now - meta["started_at"], 1),
    }
    (out / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    (out / "diff.patch").write_text(
        subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(tree), "diff", *([bug_state] if bug_state else [])], capture_output=True, text=True, encoding="utf-8").stdout,
        encoding="utf-8", newline="\n",
    )
    worktree.destroy(platform_repo(), tree)
    print(json.dumps(verdict))
    return 0


# --- results -----------------------------------------------------------------------------------------------


def replay(config: AgentConfig):
    """Agent factory for `eval.runner.run_eval`: reads the finished runs under params.out_dir, calls no model.
    `params.fix_only` leaves the repro trajectory out of the totals (P5.5-T17: variant A next to variant S, which has no repro stage)."""
    base = Path(config.params["out_dir"])
    stages = ("fix",) if config.params.get("fix_only") else ("repro", "fix")

    def agent(task: Task) -> Outcome:
        out = base / task.id
        try:
            verdict = json.loads((out / "verdict.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            return Outcome("error", reason="no verdict.json: the run did not finish")
        paths = [p for p in (out / s / "trajectory.jsonl" for s in stages) if p.exists()]
        tin, tout, tcached, dollars = _totals(paths)
        fix = out / "fix" / "trajectory.jsonl"
        steps = len(Trajectory.from_jsonl(fix.read_text(encoding="utf-8")).steps) if fix.exists() else None
        return Outcome(
            verdict["verdict"], reason="scorer exit 2" if verdict["verdict"] == "excluded" else None, stop_reason=verdict["stop_reason"], steps=steps,
            tokens_in=tin, tokens_out=tout, tokens_cached=tcached, latency_s=verdict.get("wall_s"), trajectory=str(fix) if fix.exists() else None,
            dollars=dollars,
        )

    return agent


def results(variant: str, tasks_file: Path, out_file: Path, only: list[str]) -> int:
    name, policy_path = VARIANTS[variant]
    policy = load_policy(policy_path)
    config = AgentConfig(
        name=name, model=policy.tiers["strong"].primary.model, host=HOST, factory="eval.t14_turn:replay",
        params={
            "out_dir": str(_variant_dir(variant)), "claude_session": True, "token_source": "chars/4 estimate of the messages; excludes subagent harness overhead",
            "worker_models": {t: WORKER_MODEL[r.primary.model] for t, r in policy.tiers.items()}, "stages": policy.stages,
            "fix_context": {"strategy": STRATEGY, "budget": BUDGET_TOKENS}, "repro_cap": REPRO_CAP,
            "latency": "wall clock of the whole task including coordinator waits; several tasks ran at once",
        },
    )
    tasks = load_tasks(tasks_file)
    if only:
        tasks = [t for t in tasks if t.id in only]
    res = run_eval(tasks, replay(config), config, run_id=name)
    out_file.write_text(res.to_json(), encoding="utf-8")
    rate = res.resolve_rate
    print(f"{name}: {rate.successes}/{rate.total} resolved over {len(tasks)} tasks, wrote {out_file}")
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 3 and args[0] == "start":
        return start(args[1], args[2])
    if len(args) == 2 and args[0] == "show":
        out = _run_dir(args[1])
        if (out / "verdict.json").exists():
            print((out / "verdict.json").read_text(encoding="utf-8"))
            return 0
        return _replay(out)
    if len(args) == 2 and args[0] == "status":
        out = _run_dir(args[1])
        if (out / "verdict.json").exists():
            print((out / "verdict.json").read_text(encoding="utf-8"))
            return 0
        pending = json.loads((out / "pending.json").read_text(encoding="utf-8"))
        n = len((out / "answers.jsonl").read_text(encoding="utf-8").splitlines())
        print(f"recorded {n} answers; next: stage={pending['stage']} tier={pending['tier']} worker_model={WORKER_MODEL[pending['model']]}")
        return 0
    if len(args) == 2 and args[0] == "answer":
        return answer(args[1], sys.stdin.read().strip())
    if args and args[0] == "results":
        parser = argparse.ArgumentParser(prog="eval.t14_turn results")
        parser.add_argument("variant", choices=sorted(VARIANTS))
        parser.add_argument("--tasks", type=Path, required=True)
        parser.add_argument("--out", type=Path, required=True)
        parser.add_argument("--only", nargs="*", default=[])
        ns = parser.parse_args(args[1:])
        return results(ns.variant, ns.tasks, ns.out, ns.only)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
