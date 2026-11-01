"""Run-to-run noise of one variant, from the five stored draws per task (P5-T18, ADR-017). No model call.

    uv run --package eval python packages/eval/scripts/run_noise.py

Draw 1 is the P3 variant A run, draws 2 to 5 are the P4-T20 reruns of the same variant (same model, same tasks, same
caps), all in `packages/fix-loop/runs/p4-t20-subset29-claude-session.json`. Prints, per draw, the resolve rate and the
tokens per bug the gate would see, then runs the gate's two rules on every ordered pair (baseline draw, run draw).
"""

from __future__ import annotations

import json
import statistics as st
from pathlib import Path

from eval.gate import load_config
from eval.stats import wilson

DRAWS = Path(__file__).resolve().parents[3] / "packages/fix-loop/runs/p4-t20-subset29-claude-session.json"
cfg = load_config()
z, margin, limit = cfg.resolve_rate.z, cfg.resolve_rate.margin, cfg.tokens_per_bug.max_growth

data = json.loads(DRAWS.read_text(encoding="utf-8"))["draws"]
rows = []  # per draw: successes, scored tasks, mean tokens (in + out) per scored task, token-cap stops
for n in range(5):
    scored = [t[n] for t in data.values() if t[n]["verdict"] != "excluded"]  # excluded stay out of the denominator
    rows.append((
        sum(r["verdict"] == "resolved" for r in scored),
        len(scored),
        st.mean(r["tokens_in"] + r["tokens_out"] for r in scored),
        sum(r["stop_reason"] == "token-cap" for r in scored),
    ))

print("draw  resolved  rate    tokens/bug  token-cap stops")
for n, (s, t, tok, caps) in enumerate(rows, 1):
    print(f"{n:>4}  {s:>2}/{t:<2}    {s / t:.4f}  {tok:>10,.0f}  {caps}")
rates = [s / t for s, t, _, _ in rows]
toks = [tok for _, _, tok, _ in rows]
print(f"\nresolve rate: mean {st.mean(rates):.4f}, sample sd {st.stdev(rates):.4f}, range {min(rates):.4f} to {max(rates):.4f}")
print(f"tokens/bug, all 5 draws: mean {st.mean(toks):,.0f}, sample sd {st.stdev(toks):,.0f}, max/min {max(toks) / min(toks):.2f}")
print(f"tokens/bug, draws 2-5:   mean {st.mean(toks[1:]):,.0f}, sample sd {st.stdev(toks[1:]):,.0f}, max/min {max(toks[1:]) / min(toks[1:]):.2f}")
mixed = sum(len({r["verdict"] for r in t if r["verdict"] != "excluded"}) > 1 for t in data.values())
print(f"tasks whose verdict changed between draws: {mixed} of {len(data)}")

print(f"\ngate rules at z={z}, margin={margin}, max_growth={limit}: ordered pairs (baseline draw -> run draw)")
fails = []
for b, (bs, bt, btok, _) in enumerate(rows, 1):
    floor = wilson(bs, bt, z)[0] - margin
    for r, (rs, rt, rtok, _) in enumerate(rows, 1):
        if b == r:
            continue
        if rs / rt < floor:
            fails.append((b, r, f"resolve rate {rs / rt:.4f} < floor {floor:.4f}"))
        if rtok / btok - 1 > limit:
            fails.append((b, r, f"tokens {rtok / btok - 1:+.1%} > +{limit:.0%}"))
print(f"{len(fails)} of 20 pairs would fail on noise alone" + "".join(f"\n  {b}->{r}: {why}" for b, r, why in fails))
tight = [(b, r) for b in range(1, 6) for r in range(1, 6) if b != r and rows[r - 1][2] / rows[b - 1][2] - 1 > 0.74]
print("pairs with token growth over +74% (the largest among draws 2-5):", tight)
