# Gate fixtures

Inputs for `python -m eval gate` and `packages/eval/tests/test_gate.py`. Both files follow `packages/eval/schemas/results.schema.json`.

```
uv run --package eval python -m eval gate packages/eval/fixtures/gate/baseline.json --baseline packages/eval/fixtures/gate/baseline.json   # exit 0
uv run --package eval python -m eval gate packages/eval/fixtures/gate/worse.json --baseline packages/eval/fixtures/gate/baseline.json      # exit 1
```

## `baseline.json` (real numbers)

The P3 variant A run (Claude session as the model, 29 scored seeded tasks), converted from `packages/fix-loop/runs/p3-a-claude-results.json`:

- Real: every task row (task id, tier, verdict, stop reason, steps, tokens in/out, trajectory path), `bug-17` excluded, resolve rate 20/29 = 0.689655 with Wilson 95% [0.507695, 0.827246] (matches `packages/fix-loop/runs/README.md`), tokens per task 202,904 in and 205 out.
- Chosen by hand: `run_id`, `agent` names, `created_at` (the day this fixture was written), and the exclusion `reason` text (copied from the runs README).
- Left empty because P3 never recorded them: latency (`null`, `n` 0), cached tokens (0), `trajectory_metrics` (`null`; `stored-metrics.txt` has the P3 numbers), `$_equivalent`.
- Token counts are chars/4 estimates, not provider usage (see the runs README). Compare a new run's tokens with this file only when the new run counts the same way.

## `worse.json` (made up)

The baseline with two edits, so it is not a real run:

- The first 8 resolved tasks in file order (`seed-e01` to `seed-e04`, `seed-e06` to `seed-e09`) are flipped to `unresolved`. Resolve rate becomes 12/29 = 0.413793, Wilson [0.255129, 0.592625], under the baseline's lower bound 0.507695.
- Every task's `tokens_in` is multiplied by 1.6, so tokens per bug is +59.9% on the baseline's. That is under the gate's +100% limit, so this file fails on resolve rate alone.
- Its `run_id` is `worse-made-up` and `agent.params.source` says it is made up. Nothing here is a measurement.
