# eval

Trajectory metrics and the eval runner. Starts in P5.

```
uv run --package eval python -m eval metrics <dir> [--glob PATTERN] [--json]
uv run --package eval python -m eval run --tasks tasks.json --agent agent.json --out results.json [--run-id ID]
uv run --package eval python -m eval report [previous.json] [this.json]
uv run --package eval python -m eval schema
uv run --all-packages python -m eval.ablation tasks --out tasks.json
uv run --all-packages python -m eval.ablation table A.json B.json
uv run --package eval python packages/eval/scripts/run_noise.py
uv run --package eval python -m eval multimodal prepare|finish|predictions|results ...
uv run pytest packages/eval/tests -q
```

- `metrics`: the five trajectory metrics for every `trajectory.jsonl` under a directory. Formulas: `docs/metrics.md`. Counts for the stored P3 and P4 runs: `results/stored-metrics.txt`.
- `run`: runs an agent over a task list and writes one results JSON.
- `report`: the phase report table (Previous phase, This phase, Delta) from two results files. One file is read as this phase; no file prints the empty template. Tokens/bug is in + out per task; $-equivalent is per task.
- `scripts/run_noise.py`: run-to-run noise of one variant from the five stored draws per task, and the gate rules on every pair of draws. The figures behind `gate.toml` (ADR-017).
- `eval.ablation`: the P5-T14 routing ablation harness (policies in `policies/`, agent factories, the table). Commands and open points: `docs/notes/p5-t14.md`.
- `multimodal`: the SWE-bench Multimodal dev-subset adapter (T19) and the T20 run pieces: checkout + prompt, patch capture, harness predictions file, results table. A patch no harness has graded is `excluded: patch produced, not scored`, never solved. Findings and owner steps: `docs/notes/p5-t20.md`.
- `schema`: prints the results JSON Schema (committed at `schemas/results.schema.json`; a test fails if the file and the models drift).

## What is measured and what is not

- Measured: resolve rate with a Wilson interval, tokens and list-price dollars per bug, five trajectory metrics, a gate against a stored baseline, the routing ablation on 29 seeded tasks (`docs/notes/p5-t14-results.md`).
- Not measured: quota share (Claude sessions have only a self-imposed cap), cached-token savings (cached tokens are 0 everywhere), a real provider tier split, latency that is comparable across runs.
- Not yet seen: a trace in Langfuse (needs your keys), the dashboard on GitHub Pages and the `eval-gate` workflow on GitHub (need a push and Pages switched on). See `docs/notes/p5-t07.md`, `p5-t17.md` and `p5-t22.md`.

## Inputs of `run`

- `tasks.json`: a JSON array of `argus_core` `Task` objects. The runner hands the whole `Task` to the agent, so an agent adapter must keep `golden_patch` out of the model prompt.
- `agent.json`: `{"name", "model", "host", "factory", "params"}`. `factory` is `module:function`; the function takes the config and returns `agent(task) -> Outcome`. The agent does setup, the run and scoring; the runner times it and counts. `eval.stub:make` is a stub with no model call (`params.resolve` lists the task ids it resolves).

## Results JSON (the contract for report, gate, multimodal run and dashboard)

Schema: `schemas/results.schema.json`. A filled example: `schemas/results.example.json`. `schema_version` is 1. Add fields only by bumping it.

| Field | Meaning |
|---|---|
| `schema_version`, `run_id`, `created_at` | Version 1; the caller's run name (default: agent name); UTC time |
| `agent` | `name`, `model`, `host` and the config's free-form `params` |
| `counts` | `resolved`, `unresolved`, `excluded`, `error` task counts |
| `resolve_rate` | `successes`, `total`, `rate`, `ci_low`, `ci_high`, `interval` (`wilson95`). `total` = resolved + unresolved + error. |
| `tokens` | `total` and `per_task` (total / `resolve_rate.total`), each with `tokens_in`, `tokens_out`, `tokens_cached` |
| `latency_s` | `p50`, `p95` in seconds (linear interpolation), and `n`, the number of tasks that have a latency |
| `trajectory_metrics` | The summary from `docs/metrics.md` over the rows that gave a trajectory, or `null` |
| `$_equivalent` | List-price dollar equivalent. Total list-price dollars of the scored tokens, from `argus_core.prices` and the agent's `model`. `null` when there are no tokens. A model with no price row and tokens makes `run` fail with `UnknownModelPrice`. |
| `tasks` | One row per task, none dropped: `task_id`, `tier`, `verdict`, `reason`, `stop_reason`, `steps`, `tokens`, `latency_s`, `trajectory` |

Rules the readers can rely on:

- `excluded` (the task could not be set up or scored; `reason` says why) stays out of `resolve_rate.total`, `tokens` and `latency_s`, and still has a row. `error` (the agent raised) is counted as unresolved.
- A rate or percentile with nothing to compute from is `null`, never `0`.
- Floats are rounded: rates and interval bounds to 6 decimals, latencies to 3.
- A row's `latency_s` is the agent's own figure when it gave one, else wall time around the agent call.
