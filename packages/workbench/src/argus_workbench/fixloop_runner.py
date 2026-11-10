"""FixLoopRunner: an adapter that runs `fix_loop.run_fix` with a SCRIPTED model and maps its trajectory into a run folder.

NEVER RUN AGAINST A REAL MODEL. The constructor requires `model`, a plain Python function that takes the message
list and returns the next answer (the shape `fix_loop` tests use). There is no default, no key, no URL and no model
name read here or at import, and this module builds no client. A caller that hands in a function which calls a
network breaks the P10 rule (no model call in P10); the workbench never does, and `tests/test_no_model.py` keeps it so.

    runner = FixLoopRunner(scripted_model, worktree=tree)   # tree: a git repo the scripted model edits
    runner.play(run_dir, clock=..., tick=..., stop=...)     # Runner protocol of runner.py

What it does: `run_fix` runs to its end first (it writes its own `trajectory.jsonl` in a temp folder), then its steps
are copied into the run, one per tick, stamped `stage: fix` and `origin: SIMULATED` (the fix-loop message keeps its
`text` and `returncode`). `patch.diff` is `git diff` of the worktree, with a SIMULATED header line when it is not
empty. Only the fix stage runs: the state passes through `reproducing` with no repro step.

The run ends in `failed` with the stop reason `run_fix` returned (`submit`, `stuck`, `step-cap`, `QuotaExceeded`, and
so on). It never reaches awaiting-qa, because nothing here runs the verify pipeline and so no verdict exists.

Tools: `run_cmd` and `ast_grep` are refused (`not-allowed`) unless `allow_shell=True`, so a scripted model cannot run
a shell command on this machine by default. `read_file`, `list_dir`, `search`, `edit` and `submit` work inside `worktree`.

ponytail: `stop` is checked between copied steps, not inside `run_fix`; a stop cannot interrupt the model loop (a
scripted loop is instant). The worktree is edited in place; give it a throwaway copy.
"""

from __future__ import annotations

import subprocess
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from argus_core.ledger import Ledger, ModelQuota
from argus_core.types import Trajectory
from fix_loop.loop import run_fix
from fix_loop.tools import ToolError, call

from argus_workbench import store
from argus_workbench.runner import MODEL, Playback, Stopped, Tick

PATCH_HEADER = "# SIMULATED run (scripted model), not a model result\n"
_SHELL_TOOLS = ("run_cmd", "ast_grep")


class FixLoopRunner:
    origin: store.Origin = "SIMULATED"

    def __init__(
        self,
        model: Callable[[list[dict]], object],
        *,
        worktree: Path,
        system: str = "Fix the ticket by editing the files in the worktree, then submit.",
        step_cap: int = 20,
        token_cap: int = 1_000_000,
        allow_shell: bool = False,
    ):
        if not callable(model):
            raise TypeError("model must be a function: messages in, an answer out (a scripted one; never a real model)")
        self.model, self.worktree = model, Path(worktree)
        self.system, self.step_cap, self.token_cap, self.allow_shell = system, step_cap, token_cap, allow_shell

    def _execute(self, name: str, payload: dict):
        if name in _SHELL_TOOLS and not self.allow_shell:
            return ToolError(error="not-allowed", message=f"{name} is off in the workbench adapter")
        return call(name, payload, self.worktree)

    def _patch(self) -> str:
        proc = subprocess.run(["git", "-C", str(self.worktree), "diff", "--no-color"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(f"git diff failed in the worktree: {proc.stderr.strip()[:200]}")
        return PATCH_HEADER + proc.stdout if proc.stdout.strip() else ""

    def play(self, run_dir: Path, *, clock: store.Clock = store.utc_now, tick: Tick = lambda: None,
             stop: threading.Event | None = None) -> store.RunState:
        stop = stop or threading.Event()
        run_dir = run_dir.resolve()
        ticket = store.read_file(run_dir.name, "ticket.json", root=run_dir.parent)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / "ledger.json", {MODEL: ModelQuota(10**6, 10**9, 10**6, 10**9, cached_counts=False)})
            result = run_fix(
                worktree=self.worktree, model=MODEL, out_dir=Path(tmp) / "out", step_cap=self.step_cap, token_cap=self.token_cap,
                run_id=run_dir.name, host="simulated", git_commit="none", task_id=ticket.id, system=self.system, user=ticket.text,
                ledger=ledger, complete=self.model, execute=self._execute,
            )
            recorded = Trajectory.from_jsonl(result.trajectory_path.read_text(encoding="utf-8"))
        patch = self._patch()
        pb = Playback(run_dir, origin=self.origin, meta=recorded.meta, clock=clock, tick=tick, stop=stop)
        try:
            for step in recorded.steps:
                pb.step("fix", step)
            if patch:
                store.write_file(pb.run_id, "patch.diff", patch, root=pb.root)
            return pb.fail(result.stop_reason)
        except Stopped:
            return pb.stopped()
