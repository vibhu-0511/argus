# Trajectory metrics

Five numbers that describe how a run got to its answer, not only whether it did. Each is an exact formula over one trajectory file (`trajectory.jsonl`, schema in `packages/argus-core/src/argus_core/types.py`: `Trajectory`, `TrajectoryStep`). The worked example at the end of this file is computed by hand from one stored trajectory.

## Notation

A trajectory `T` has a meta line and `n` step lines `s_0 … s_(n-1)`, in file order. The fields used:

| Field | Meaning |
|---|---|
| `tool_name` | Name of the tool the loop executed on this step. `null` when no tool ran (a reply that was not a tool call, the step that hit the token cap, a quota refusal). |
| `tool_error` | Error code the loop recorded for this step (`not-found`, `failed`, `timeout`, `tool-unavailable`, `not-a-repro`, `QuotaExceeded`), or `null`. |
| `stop_reason` | Set on the last step of a run (`submit`, `step-cap`, `stuck`, …). `null` on every other step. |
| `raw_response` | The model's reply text. For a tool call it is JSON. |

A **call** is a step with `tool_name ≠ null`.

The **key** of a call is `tool_name + "\n" + canonical(args)`. `args` is read from `raw_response` parsed as JSON: if it is an object with an `arguments` object, that object; otherwise the parsed value itself (the mini runner stores the bare arguments); a reply that is not JSON is used as the raw string. `canonical` is `json.dumps(args, sort_keys=True)`. Two calls with equal keys are the same call. This is the same key `fix_loop/loop.py` uses for its stuck rule.

## Metrics, per trajectory

### 1. steps

```
steps(T) = n
```

The number of step lines. Across a set of trajectories: the total, the mean and the median of `steps(T)`.

### 2. tool-error rate

```
tool_errors(T)     = |{ i : s_i.tool_error ≠ null }|
tool_error_rate(T) = tool_errors(T) / n
```

Every step with an error code counts, including a reply that was not a tool call (`failed`) and a quota refusal (`QuotaExceeded`). Undefined (`null`) when `n = 0`.

### 3. redundant-call rate

Walk the calls in file order with a set `seen`, empty at the start.

- `submit` call: skipped (not counted, not added). A second `submit` after a rejected one is a needed retry.
- `edit` call: counted in the denominator, never redundant, and it empties `seen`. The tree changed, so reading the same file again is not a repeat.
- any other call with key `k`: if `k ∈ seen` it is **redundant**; then `k` is added to `seen`.

```
calls(T)           = |{ calls other than submit }|
redundant(T)       = number of redundant calls
redundant_rate(T)  = redundant(T) / calls(T)
```

Undefined (`null`) when `calls(T) = 0`. An errored call that is repeated unchanged is redundant like any other.

### 4. stuck

```
stuck(T) = 1  if there is an i with s_i, s_(i+1), s_(i+2) all calls and key(s_i) = key(s_(i+1)) = key(s_(i+2))
           0  otherwise
```

Three identical calls in a row. This is the loop's own stop rule (`REPEAT = 3` in `fix_loop/loop.py`), applied to the file so a run from a driver that does not stop on it is still caught. A malformed reply between two calls (`tool_name = null`) breaks the run of three, as it does in the loop.

### 5. recover-after-gate-failure

A **rejected submit** is a step with `tool_name = "submit"`, `tool_error = null` and `stop_reason = null`. The loop sets `stop_reason = submit` only when the gates (and the verifier) pass, so a `submit` with no stop reason is one that was sent back to the model with a gate message. A rejected submit is **recovered** when a later step has `stop_reason = submit`.

```
gate_failures(T)  = number of rejected submits
recovered(T)      = number of rejected submits at index i with some j > i where s_j.stop_reason = submit
recover_rate(T)   = recovered(T) / gate_failures(T)
```

Undefined (`null`) when `gate_failures(T) = 0`. Limit: a rejected submit on the very last step is relabelled `step-cap` by the loop, so it is not seen as a rejection. That case is a failure to recover that this formula misses.

## Metrics, over a set of trajectories

Rates are pooled (sum of numerators over sum of denominators), not averaged per run, so a long run weighs more than a short one. Each is stored as `{value, num, den}` with `value = null` when `den = 0`.

| Metric | Formula over trajectories `T_1 … T_N` |
|---|---|
| steps | total `Σ steps`, mean and median of `steps(T_j)` |
| tool-error rate | `Σ tool_errors / Σ steps` |
| redundant-call rate | `Σ redundant / Σ calls` |
| stuck rate | `Σ stuck / N` |
| recover-after-gate-failure rate | `Σ recovered / Σ gate_failures` |

The stored P3 and P4 runs were driven by `fix_loop.turn`, which does not run the gates, so none of them has a rejected submit. Their recover rate is `null` (0 gate failures).

## Worked example

File: `packages/fix-loop/runs/p4b-full-summary-h10/trajectory.jsonl` (P4 context-strategy run, task `seed-h10`, model `claude-session`). It has 20 steps and ends with `stop_reason = step-cap`. Every step is a call (`tool_name ≠ null`), there is no `edit` and no `submit`. Calls with the same letter have the same key.

| i | tool | args (short) | tool_error | key | redundant? |
|---|---|---|---|---|---|
| 0 | search | `z-index` in `apps/canvas/src` | | A | |
| 1 | read_file | `landing.css` | | B | |
| 2 | search | `--z-` in `apps/canvas/src` | not-found | C | |
| 3 | search | `zIndex` in `apps/canvas/src` | | D | |
| 4 | search | `z-index` in `platform/canvas-ui` | | E | |
| 5 | search | `--z` in `platform/canvas-ui` | not-found | F | |
| 6 | search | `stack` in `apps/canvas/src` | | G | |
| 7 | search | `z-index: 9` in `ops.css` | | H | |
| 8 | search | `z-index` in `landing.css` | | I | |
| 9 | search | `z-index` in `ops.css` | | J | |
| 10 | search | `zIndex` in `apps/canvas/src` | | D | yes (= step 3) |
| 11 | search | `z-index` in `landing.css` | | I | yes (= step 8) |
| 12 | search | `band` in `landing.css` | | K | |
| 13 | search | `z-index` in `landing.css` | | I | yes (= step 8) |
| 14 | search | `ops-map-controls` in `apps/canvas/src` | | L | |
| 15 | read_file | `landing.css` | | B | yes (= step 1) |
| 16 | search | `z-index` in `ops.css` | | J | yes (= step 9) |
| 17 | search | `ops-map-controls` in `apps/canvas/src` | | L | yes (= step 14) |
| 18 | read_file | `SessionExpiryGuard.tsx` | | M | |
| 19 | search | `z-index` in `ops.css` | | J | yes (= step 9) |

By hand:

1. **steps** = 20.
2. **tool-error rate**: steps 2 and 5 carry `not-found`, so `tool_errors = 2` and the rate is `2 / 20 = 0.10`.
3. **redundant-call rate**: `calls = 20` (no `submit`). Redundant steps are 10, 11, 13, 15, 16, 17, 19, so `redundant = 7` and the rate is `7 / 20 = 0.35`.
4. **stuck**: no three adjacent steps share a key (the closest are steps 8, 9, 10 = I, J, D). `stuck = 0`.
5. **recover-after-gate-failure**: there is no `submit` step, so `gate_failures = 0` and the rate is undefined (`null`).
