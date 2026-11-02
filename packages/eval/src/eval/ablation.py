"""P5-T14 routing ablation harness. Nothing here calls a model unless the agent config says so.

Two variants over the same task list, run with `python -m eval run`:
  A  every stage on the strong tier   (`policies/strong-only.yaml`, factory `eval.ablation:strong_only`)
  B  routing.yaml as it is            (`argus_core/routing.yaml`,   factory `eval.ablation:routed`)

Per task the agent runs repro, then fix, each through a `Router`. Every trajectory step records its tier, host and
model, so tokens split by tier afterwards. Layout: `<out_dir>/<task id>/{repro,fix}/trajectory.jsonl`; the results
row points at the fix one. `table` reads two results files plus those trajectories and prints the 'Ablation' table
of phases/P05-argus-eval.md. Anything it cannot measure prints as a dash.

Agent config `params`: `out_dir` (required), `stub` (no model call, no git, no scorer), `resolve` (stub: task ids
to resolve), `quotas`, `ledger`, `hosts` ({host: {base_url, key_env}}), `clients` (`module:function` returning
{host: client}, to bring your own model host), `repro` (default true), `run_trees` (`module:function` returning a function
task directory -> repro tree runner; `repro_agent.trees:live` is the live one, it needs `python -m repro_agent.trees up`), `step_cap`, `token_cap`, `repro_cap`, `context_budget`, `strategy`
(`none` or `cap`).

ponytail: `localize` is in both policies but nothing in the pipeline makes a chat call for it (dom2src locates with
embeddings). Quota charge is recomputed from trajectories with the ledger's rule because the ledger file resets each
day; a test checks the two agree.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from argus_core.client import Completion, ModelClient, Usage
from argus_core.ledger import Ledger, ModelQuota, load_quotas
from argus_core.prices import UnknownModelPrice, dollar_equivalent
from argus_core.router import ROUTING_PATH, Policy, Router, load_policy
from argus_core.types import Task, Trajectory

from eval.results import Results
from eval.runner import AgentConfig, Outcome

ROOT = Path(__file__).resolve().parents[4]
POLICIES = Path(__file__).resolve().parents[2] / "policies"
STRONG_ONLY = POLICIES / "strong-only.yaml"
QUOTAS = ROOT / "docs" / "quotas.md"
SEEDED = ROOT / "packages" / "bench" / "tasks" / "seeded"
DASH = "—"
HOSTS = {  # config/profiles.md; the key env var is the one docs/quotas.md names for Groq
    "groq": ("https://api.groq.com/openai/v1", "ARGUS_MODEL_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
}


def strong_only(config: AgentConfig):
    return _agent(config, STRONG_ONLY)


def routed(config: AgentConfig):
    return _agent(config, ROUTING_PATH)


# --- the agent ---------------------------------------------------------------------------------------------


def _est(text: str) -> int:
    return max(1, len(text) // 4)


class StubClient:
    """No network. A repro request gets a script; a fix request gets `list_dir`, then `submit`. The system message
    counts as cached from the second call on, a stand-in for a prompt-cache hit."""

    SCRIPT = (
        'await page.getByRole("button", { name: "Sign in" }).click();\n'
        'await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();\n'
    )

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, model: str, messages: list[dict]) -> Completion:
        self.calls += 1
        system = str(messages[0]["content"])
        if "Write one Playwright script" in system:
            content = self.SCRIPT
        elif any(m["role"] == "assistant" for m in messages):
            content = json.dumps({"tool": "submit", "arguments": {}})
        else:
            content = json.dumps({"tool": "list_dir", "arguments": {"path": "."}})
        tokens_in = sum(_est(str(m["content"])) for m in messages)
        cached = min(_est(system), tokens_in) if self.calls > 1 else 0
        return Completion(content, Usage(tokens_in, _est(content), cached), {})


def _import(spec: str):
    module, _, attr = spec.partition(":")
    return getattr(importlib.import_module(module), attr)


def _clients(params: dict[str, Any], policy: Policy) -> dict[str, Any]:
    if params.get("clients"):
        return dict(_import(params["clients"])())
    hosts = {r.host for t in policy.tiers.values() for r in (t.primary, t.fallback) if r}
    if params.get("stub"):
        return {h: StubClient() for h in hosts}
    primary = {t.primary.host for t in policy.tiers.values()}
    clients = {}
    for host in sorted(hosts):
        url, key_env = HOSTS.get(host, (None, None))
        given = (params.get("hosts") or {}).get(host, {})
        url, key_env = given.get("base_url", url), given.get("key_env", key_env)
        if url is None:
            raise ValueError(f"no base_url for host {host!r}: pass params.hosts.{host}.base_url or params.clients")
        key = os.environ.get(key_env, "") if key_env else ""
        if key_env and not key and host in primary:  # a fallback host may go without: the ledger refuses it before any call if it has no quota row
            raise ValueError(f"host {host!r} needs the env var {key_env}")
        clients[host] = ModelClient(url, key)
    return clients


def _git_head() -> str:
    proc = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    return proc.stdout.strip() or "unknown"


def _agent(config: AgentConfig, policy_path: Path):
    from fix_loop.loop import run_fix
    from fix_loop.strategies import cap_strategy
    from fix_loop.turn import PROTOCOL, STEP_CAP, TOKEN_CAP
    from repro_agent.loop import TreeRun, run_repro

    p = config.params
    stub = bool(p.get("stub"))
    out_dir = Path(p["out_dir"])
    policy = load_policy(policy_path)
    quotas = load_quotas(Path(p.get("quotas", QUOTAS)))
    if stub:  # a stub answers in microseconds, so the per-minute caps would end the run; the per-day caps stay real
        quotas = {m: replace(q, requests_per_minute=10**9, tokens_per_minute=10**9) for m, q in quotas.items()}
    router = Router(policy, Ledger(Path(p.get("ledger", out_dir / "ledger.json")), quotas), _clients(p, policy))
    use_repro = bool(p.get("repro", True))
    trees_for = _import(p["run_trees"])() if p.get("run_trees") else None
    if use_repro and trees_for is None and not stub:
        raise ValueError("no live repro tree runner given: pass params.run_trees (repro_agent.trees:live) or params.repro=false")
    if p.get("strategy", "none") not in ("none", "cap"):
        raise ValueError("params.strategy must be 'none' or 'cap'")
    budget = int(p["context_budget"]) if p.get("context_budget") else None
    strategy = cap_strategy if p.get("strategy") == "cap" else None
    commit = _git_head()

    def agent(task: Task) -> Outcome:
        work = out_dir / task.id
        tree = out_dir / "trees" / task.id
        execute = None
        if stub:
            tree.mkdir(parents=True, exist_ok=True)
            from fix_loop.tools import ToolResult

            execute = lambda name, payload: ToolResult(tool=name, text="ok")  # noqa: E731
        else:
            tree, execute = _live_prepare(task, work, out_dir)
        try:
            script = None
            paths = []
            if use_repro:
                repro = run_repro(
                    ticket=task.ticket, task_dir=Path(p.get("tasks_dir", SEEDED)) / task.id, model=config.model,
                    run_trees=trees_for(Path(p.get("tasks_dir", SEEDED)) / task.id) if trees_for else (lambda _script: TreeRun(True, True)), out_dir=work / "repro", cap=int(p.get("repro_cap", 3)),
                    run_id=task.id, host=config.host, git_commit=commit, router=router, stage="repro",
                )
                script, paths = repro.script, [repro.trajectory_path]
            fix = run_fix(
                worktree=tree, model=config.model, host=config.host, router=router, stage="fix", out_dir=work / "fix",
                step_cap=int(p.get("step_cap", STEP_CAP)), token_cap=int(p.get("token_cap", TOKEN_CAP)), run_id=task.id,
                git_commit=commit, task_id=task.id, system=PROTOCOL, execute=execute,
                user=f"Ticket:\n{task.ticket.text}\n\nRepro: {script or 'not-run'}\nLocate: none\n",
                context_budget=budget, strategy=strategy if budget else None,
            )
            paths.append(fix.trajectory_path)
            verdict = _stub_score(task, p) if stub else _live_score(task, tree)
        finally:
            if not stub:
                _live_cleanup(tree)
        tin, tout, tcached, dollars = _totals(paths)
        steps = len(Trajectory.from_jsonl(fix.trajectory_path.read_text(encoding="utf-8")).steps)
        return Outcome(
            verdict, reason="scorer exit 2" if verdict == "excluded" else None, stop_reason=fix.stop_reason.value, steps=steps,
            tokens_in=tin, tokens_out=tout, tokens_cached=tcached, trajectory=str(fix.trajectory_path), dollars=dollars,
        )

    return agent


def _totals(paths: list[Path]) -> tuple[int, int, int, float | None]:
    tin = tout = tcached = 0
    dollars: float | None = 0.0
    for path in paths:
        for s in Trajectory.from_jsonl(path.read_text(encoding="utf-8")).steps:
            tin, tout, tcached = tin + s.tokens_in, tout + s.tokens_out, tcached + s.tokens_cached
            if (s.tokens_in or s.tokens_out) and dollars is not None:
                try:
                    dollars += dollar_equivalent(s.model or "", s.tokens_in, s.tokens_out, s.tokens_cached)
                except UnknownModelPrice:
                    dollars = None  # one unpriced model makes the task's figure unknown, never a guess
    return tin, tout, tcached, None if dollars is None else round(dollars, 8)


def _stub_score(task: Task, params: dict[str, Any]) -> str:
    return "resolved" if task.id in set(params.get("resolve", [])) else "unresolved"


def _live_prepare(task: Task, work: Path, out_dir: Path):
    """A worktree of the platform repo with the bug patch applied, and a sandboxed `run_cmd`. Not run by any test."""
    from argus_bench.golden import platform_repo
    from fix_loop import worktree
    from fix_loop.turn import _execute, _reset

    tree = worktree.create(platform_repo(), task.id, "HEAD", root=out_dir / "trees")
    _reset(tree, task.bug_patch)
    checks = work / "checks"
    checks.mkdir(parents=True, exist_ok=True)  # only the checks go into the mount; golden.patch stays out
    (checks / "checks.json").write_text(json.dumps([c.model_dump(mode="json") for c in task.checks]), encoding="utf-8")
    return tree, _execute(tree, checks)


def _live_cleanup(tree: Path) -> None:
    from argus_bench.golden import platform_repo
    from fix_loop import worktree

    worktree.destroy(platform_repo(), tree)


def _live_score(task: Task, tree: Path) -> str:
    code = subprocess.run(
        [sys.executable, "-m", "argus_bench.cli", "score", task.id, "--tree", str(tree)], capture_output=True, text=True, encoding="utf-8"
    ).returncode
    return "excluded" if code == 2 else "resolved" if code == 0 else "unresolved"


# --- the table ---------------------------------------------------------------------------------------------


@dataclass
class Use:
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cached: int = 0
    calls: int = 0
    charged: int = 0  # what the ledger counts against the model's daily token cap


@dataclass
class Measured:
    results: Results
    use: dict[tuple[str, str], Use] | None = field(default=None)  # (tier, model) -> Use; None when not measurable


def _resolve(path: str, base: Path) -> Path:
    found = Path(path)
    return found if found.is_absolute() or found.exists() else base / found


def tier_usage(results: Results, base: Path, quotas: dict[str, ModelQuota]) -> dict[tuple[str, str], Use] | None:
    """Token use per (tier, model) from the stage trajectories next to each row's trajectory. None unless the steps
    add up to the results file's token totals, so a missing stage file shows as a dash, not as a smaller number."""
    use: dict[tuple[str, str], Use] = {}
    for row in results.tasks:
        if row.verdict == "excluded":
            continue
        if row.trajectory is None:
            if row.tokens.tokens_in or row.tokens.tokens_out:
                return None
            continue
        fix = _resolve(row.trajectory, base)
        for file in sorted(fix.parent.parent.glob("*/trajectory.jsonl")):
            for s in Trajectory.from_jsonl(file.read_text(encoding="utf-8")).steps:
                if not (s.tokens_in or s.tokens_out):
                    continue
                u = use.setdefault((s.tier or "untiered", s.model or "unknown"), Use())
                u.tokens_in, u.tokens_out, u.tokens_cached, u.calls = (
                    u.tokens_in + s.tokens_in, u.tokens_out + s.tokens_out, u.tokens_cached + s.tokens_cached, u.calls + 1,
                )
                q = quotas.get(s.model or "")
                if q is not None:
                    u.charged += max(s.tokens_in + s.tokens_out - (0 if q.cached_counts else s.tokens_cached), 0)
    total = results.tokens.total
    seen = (sum(u.tokens_in for u in use.values()), sum(u.tokens_out for u in use.values()), sum(u.tokens_cached for u in use.values()))
    return use if seen == (total.tokens_in, total.tokens_out, total.tokens_cached) else None


def quota_share(m: Measured, quotas: dict[str, ModelQuota]) -> float | None:
    """Largest share of one model's daily token cap used per bug, over the models the variant touched."""
    bugs = m.results.resolve_rate.total
    if not m.use or not bugs:
        return None
    shares = []
    for (_, model), u in m.use.items():
        if model not in quotas:
            return None
        shares.append(u.charged / quotas[model].tokens_per_day / bugs)
    return max(shares)


def _cells(m: Measured, quotas: dict[str, ModelQuota]) -> list[str]:
    r = m.results
    rr, per, lat = r.resolve_rate, r.tokens.per_task, r.latency_s
    share = quota_share(m, quotas)
    return [
        DASH if rr.rate is None else f"{rr.rate:.1%} ({rr.successes}/{rr.total}) [{rr.ci_low:.1%}, {rr.ci_high:.1%}]",
        DASH if per is None else f"{per.tokens_in:,.0f} / {per.tokens_out:,.0f} / {per.tokens_cached:,.0f}",
        DASH if r.dollar_equivalent is None or not rr.total else f"${r.dollar_equivalent / rr.total:.4f}",
        DASH if share is None else f"{share:.1%}",
        DASH if lat.p50 is None else f"{lat.p50:.1f} s",
        DASH if lat.p95 is None else f"{lat.p95:.1f} s",
    ]


HEADER = (
    "| Variant | Resolve rate (95% CI) | Tokens/bug (in / out / cached) | $-equivalent/bug | Quota share/bug | p50 latency | p95 latency |\n"
    "|---|---|---|---|---|---|---|"
)


def render(a: Measured, b: Measured, quotas: dict[str, ModelQuota]) -> str:
    out = []
    if any(m.results.agent.params.get("stub") for m in (a, b)):
        out.append("**STUB RUN: these figures come from a stub model, not from a real run. They measure nothing.**\n")
    if any(m.results.agent.params.get("claude_session") for m in (a, b)):
        out.append("**Claude-session tiers (sonnet = strong, haiku = cheap, via the subagent model parameter). Tokens are chars/4 estimates of the messages and leave out each subagent's harness overhead; $ is their list-price equivalent; latency is wall clock with several tasks at once; the quota cell is a dash because the only cap is self-imposed.**\n")
    out += [HEADER]
    for label, m in (("A", a), ("B", b)):
        out.append(f"| {label} ({m.results.agent.name}) | " + " | ".join(_cells(m, quotas)) + " |")
    out.append("\nQuota share/bug: the largest share of one model's daily token cap (docs/quotas.md; cached tokens excluded where the file says they do not count) used per bug.\n")
    for label, m in (("A", a), ("B", b)):
        out.append(f"Variant {label} by tier (tokens in / out / cached, calls, share of the model's daily cap per bug):")
        if m.use is None:
            out.append(f"  {DASH} (stage trajectories missing or not matching the results file)")
            continue
        for (tier, model), u in sorted(m.use.items()):
            q = quotas.get(model)
            share = DASH if q is None or not m.results.resolve_rate.total else f"{u.charged / q.tokens_per_day / m.results.resolve_rate.total:.2%}"
            out.append(f"  {tier:8} {model}: {u.tokens_in:,} / {u.tokens_out:,} / {u.tokens_cached:,}, {u.calls} calls, {share}")
    return "\n".join(out) + "\n"


def table(path_a: Path, path_b: Path, quotas_path: Path = QUOTAS) -> str:
    quotas = load_quotas(quotas_path)
    measured = []
    for path in (path_a, path_b):
        results = Results.model_validate_json(path.read_text(encoding="utf-8"))
        measured.append(Measured(results, tier_usage(results, path.parent, quotas)))
    return render(measured[0], measured[1], quotas)


def task_list(root: Path = SEEDED, exclude: tuple[str, ...] = ("bug-17",)) -> list[dict]:
    from argus_bench.task_dir import load_task_dir

    dirs = sorted(d for d in root.iterdir() if d.is_dir() and (d / "meta.json").is_file() and d.name not in exclude)
    return [load_task_dir(d).model_dump(mode="json") for d in dirs]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval.ablation")
    sub = parser.add_subparsers(dest="command", required=True)
    tab = sub.add_parser("table", help="print the ablation table from the variant A and variant B results files")
    tab.add_argument("a", type=Path)
    tab.add_argument("b", type=Path)
    tab.add_argument("--quotas", type=Path, default=QUOTAS)
    tasks = sub.add_parser("tasks", help="write the shared task list (seeded bench tasks) for both variants")
    tasks.add_argument("--out", type=Path, required=True)
    tasks.add_argument("--root", type=Path, default=SEEDED)
    tasks.add_argument("--exclude", nargs="*", default=["bug-17"], help="task directory names to leave out")
    args = parser.parse_args(argv)
    if args.command == "table":
        print(table(args.a, args.b, args.quotas), end="")
    else:
        found = task_list(args.root, tuple(args.exclude))
        args.out.write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {len(found)} tasks to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
