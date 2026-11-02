"""Run the loop from commit 1cba1a0 (the P5-T14 runs) and today's loop with skills=None on the same scripted turns; compare."""
import importlib.util, json, sys, tempfile
from pathlib import Path
from argus_core.client import Completion, Usage
from argus_core.ledger import Ledger, ModelQuota
from fix_loop import loop as new
from fix_loop.turn import PROTOCOL
spec = importlib.util.spec_from_file_location("old_loop", sys.argv[1]); old = importlib.util.module_from_spec(spec); sys.modules["old_loop"] = old; spec.loader.exec_module(old)
CALLS = [{"tool": "search", "arguments": {"query": "x", "path": "."}}, {"tool": "read_file", "arguments": {"path": "a.css"}},
         {"tool": "load_skill", "arguments": {"name": "nope"}}, {"tool": "submit", "arguments": {}}]
def go(mod, root):
    seen, script = [], iter(CALLS)
    def complete(messages):
        seen.append(json.dumps(messages, sort_keys=True)); return Completion(json.dumps(next(script)), Usage(1, 1, 0), {})
    work = root / "w"; work.mkdir(); (work / "a.css").write_text(".x{}\n", encoding="utf-8")
    kw = dict(skills=None) if mod is new else {}
    r = mod.run_fix(worktree=work, model="fake", ledger=Ledger(root / "l.json", {"fake": ModelQuota(100, 10**9, 100, 10**9, False)}), complete=complete,
                    out_dir=root / "o", step_cap=5, token_cap=10**6, run_id="r", host="h", git_commit="c", task_id="t", system=PROTOCOL, user="Ticket: x", **kw)
    steps = [json.loads(l) for l in r.trajectory_path.read_text(encoding="utf-8").splitlines()][1:]
    return seen, steps, r.stop_reason
with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
    o, n = go(old, Path(a)), go(new, Path(b))
print("messages identical:", o[0] == n[0], "| steps identical:", o[1] == n[1], "| stop:", o[2], n[2], "| turns:", len(o[0]))
