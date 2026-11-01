# P3 failure taxonomy (P3-T21)

Drafted by Claude at the owner's request, for the owner to review. Scope: every `unresolved` run of the stateless context ablation (P3-T19): 37 runs, 4 strategies x the 29 seeded tasks, model `claude-session`, one run per cell. The 3 excluded runs are on their own line below and carry no label. Nothing is ticked: P3-T21 is the owner's call.

Sources: `verdict.json`, `trajectory.jsonl`, `diff.patch` and `bug.patch` of each run folder in `packages/fix-loop/runs/`; `golden.patch`, `checks.json` and `ticket.json` of `packages/bench/tasks/seeded/seed-<id>`; the stop-reason table in ADR-008 and `StopReason` in `argus_core/types.py`; `STEP_CAP = 20` and `TOKEN_CAP = 400_000` in `fix_loop/turn.py`. Run ids and the 37-run set follow `swarm/tally.py`.

## Label list (closed enum)

One label per run. Rule: if the run's `stop_reason` is not `submit`, the label is that stop reason. If it is `submit` and the check still failed, the label is a cause label chosen from the final diff. The stop-reason labels use the stop-reason code as written in the trajectory; no cause label reuses a stop-reason name.

Stop-reason labels (all P3-T06 / ADR-008 codes except `submit`):

| Label | Definition |
|---|---|
| `step-cap` | The run reached `STEP_CAP` (20) without a successful `submit`. |
| `token-cap` | Cumulative tokens in plus out reached `TOKEN_CAP` (400,000) before the next tool ran. |
| `stuck` | The last 3 tool calls were the same name and arguments. |
| `QuotaExceeded` | The ledger refused the call. |
| `consecutive-timeout` | 3 command timeouts in a row. |
| `retry-cap` | 3 malformed tool calls in a row. |
| `summary` | The summary was not shorter than the turns it replaced. |
| `verify-reject` | The verifier rejected the submitted patch and then rejected the next submit too (P4). |

`submit` is the sixth P3-T06 reason. It is not a failure label: a run that submitted and failed gets a cause label. `tool-unavailable` is on the schema enum but this loop never records it, so it is not a label.

Cause labels (stop reason `submit`, check failed):

| Label | Definition |
|---|---|
| `wrong-value` | The rule the check reads was edited (or re-added) to a value other than the check's expected value. |
| `no-op-edit` | The rule the check reads was edited, but its value was left at, or declared as, the bug's value, not the expected one. |
| `wrong-target` | The submitted diff does not touch the rule the check reads (the bug is left in place there). |
| `check-tampering` | The diff changes a test, check or scorer file instead of the source. |

`FailureKind` is not used. The labels are not derived from the per-step `tool_error` field.

## Failed runs and labels (37)

"exp" is the value in `checks.json`. Diffs are read as follows: `diff.patch` is the tree against the clean commit, so a hunk absent from it is back to the clean value, and a diff equal to `bug.patch` (line sets compared) means no edit survived. No diff in the 37 touches a file other than `ops.css`, `radar.css`, `landing.css` or `tokens.css`, so none is `check-tampering`.

### none (10)

| Run | Label | Evidence |
|---|---|---|
| p4b-pilot2-none-e05 | `wrong-value` | `.radar-clock-time` re-added with font-size 18px (exp 20px) plus letter-spacing, color, tabular-nums. |
| p4b-pilot-none2-e07 | `token-cap` | 7 steps, 545,732 est. tokens; a search of `.` for `admin` returned 1,816,027 chars; diff = bug.patch. |
| p4b-full-none-m01 | `wrong-value` | `.radar-clock-time` 14px (exp 20px); `.radar-row-title` restored. |
| p4b-full-none-m04 | `wrong-value` | `.auth-backdrop` z-index 50 (exp 100); the landing bar was restored. |
| p4b-full-none-m05 | `wrong-value` | `.radar-clock-time` re-added at 18px plus extras (exp 20px); the label rule was restored. |
| p4b-full-none-h01 | `wrong-value` | `.landing-brand` 18px (exp 20px); `.glabel` restored. |
| p4b-full-none-h04 | `wrong-value` | `.auth-backdrop` z-index 50 (exp 100); map controls restored. |
| p4b-full-none-h05 | `token-cap` | 7 steps, 405,861 est. tokens; first search of `radar` returned 229,045 chars; the step-6 edit was recorded with `token-cap` and did not run; diff = bug.patch. |
| p4b-full-none-h07 | `wrong-value` | `.radar-clock-time` 14px (exp 20px); `.glabel` also changed to 11px (golden 10px). |
| p4b-full-none-h10 | `no-op-edit` | Both z-indexes replaced by `var(--z-landing-band)` / `var(--z-map-controls)`, declared as 5 and 9, the bug values; exp 1. |

### cap (7)

| Run | Label | Evidence |
|---|---|---|
| p4b-full-cap-m01 | `wrong-value` | `.radar-clock-time` 14px (exp 20px); `.radar-row-title` 13px (golden 14px). |
| p4b-full-cap-m04 | `wrong-value` | `.auth-backdrop` z-index 50 (exp 100); landing bar 5 (golden 2). |
| p4b-full-cap-m07 | `wrong-value` | `.landing-brand` 18px (exp 20px); login heading 18px (golden 17px). |
| p4b-full-cap-h01 | `wrong-value` | `.landing-brand` 16px (exp 20px); `.glabel` 11px (golden 10px). |
| p4b-full-cap-h04 | `wrong-value` | `.auth-backdrop` z-index 50 (exp 100); map controls 5 (golden 1). |
| p4b-full-cap-h07 | `wrong-value` | `.radar-clock-time` 12px (exp 20px). |
| p4b-full-cap-h10 | `no-op-edit` | Same pattern as none-h10: `--z-landing-band: 5` and `--z-ops-map-controls: 9`; exp 1. |

### offload (8)

| Run | Label | Evidence |
|---|---|---|
| p4b-full-offload-m01 | `wrong-value` | `.radar-clock-time` 12px (exp 20px); `.radar-row-title` 12px (golden 14px). |
| p4b-full-offload-m04 | `wrong-value` | `.auth-backdrop` z-index 50 (exp 100); landing bar restored. |
| p4b-full-offload-h01 | `wrong-value` | `.landing-brand` 18px (exp 20px); `.glabel` 11px (golden 10px). |
| p4b-full-offload-h03 | `step-cap` | 20 steps, no edit call, diff = bug.patch; `.radar-modes` was in a search result at step 4, steps 5 to 19 went to test files and other searches. |
| p4b-full-offload-h04 | `wrong-value` | `.auth-backdrop` z-index 50 (exp 100); map controls left at 9 (golden 1). |
| p4b-full-offload-h05 | `step-cap` | 20 steps, no edit call, diff = bug.patch; step 19 was a 30 s command timeout (one, not consecutive); the clock and brand rules were searched for but not re-added. |
| p4b-full-offload-h07 | `wrong-value` | `.radar-clock-time` 10px (exp 20px); `.glabel` restored. |
| p4b-full-offload-h10 | `step-cap` | 20 steps, no edit call, diff = bug.patch; `ops.css:86` z-index was found at step 6; the last steps searched `--z-` and `platform/canvas-ui`. |

### summary (12)

| Run | Label | Evidence |
|---|---|---|
| p4b-full-summary-e02 | `step-cap` | 20 steps, no edit, diff = bug.patch; read `platform/canvas-ui/styles.css` 4 times and `Shell.tsx` 3 times for `.shell-root`; never opened `apps/canvas/src/ops`, where `.ops-app` is. |
| p4b-pilot2-summary-e05 | `wrong-value` | `.radar-clock-time` re-added at 18px plus letter-spacing and color (exp 20px). |
| p4b-full-summary-m01 | `wrong-value` | `.radar-clock-time` 12px (exp 20px); `.radar-row-title` 12px (golden 14px). |
| p4b-full-summary-m02 | `step-cap` | 20 steps, no edit, diff = bug.patch; worked on `DeskTimelineBoard` and `.tl-*` in `platform/canvas-ui`; `ops.css` was first searched in the last step. |
| p4b-full-summary-m03 | `step-cap` | 20 steps; one edit (step 9: `.radar-list` overflow-y auto, as golden), `.radar-modes` (the checked rule) left at visible; `radar.css` read 4 times afterwards. Judgment call, see below. |
| p4b-full-summary-m04 | `wrong-value` | `.auth-backdrop` z-index 50 (exp 100); landing bar 5 (golden 2). |
| p4b-full-summary-m05 | `step-cap` | 20 steps, no edit, diff = bug.patch; 11 repeated calls, `radar.css` read 5 times; `.radar-clock-time` was never re-added. |
| p4b-full-summary-h01 | `wrong-value` | `.landing-brand` 16px (exp 20px); `.glabel` 11px (golden 10px). |
| p4b-full-summary-h04 | `wrong-value` | `.auth-backdrop` z-index 50 (exp 100); map controls left at 9 (golden 1). |
| p4b-full-summary-h05 | `stuck` | 15 steps, no edit, diff = bug.patch; steps 12 to 14 are the same `search radar-clock` call. |
| p4b-full-summary-h07 | `wrong-value` | `.radar-clock-time` 10px (exp 20px); `.glabel` restored. |
| p4b-full-summary-h10 | `step-cap` | 20 steps, no edit, diff = bug.patch; 7 repeated calls (`z-index` searches of `ops.css` and `landing.css`). |

### Excluded (not failures, no label)

`p4b-full-offload-m07`, `p4b-full-none-h08`, `p4b-full-cap-h05`: scorer exit 2 (infrastructure code), verdict `excluded`. Which exit-2 cause applied is not recorded (see `docs/notes/p3-finish.md`). They are in no count below.

## Counts per label (37 failed runs)

| Label | Count | Runs |
|---|---|---|
| `wrong-value` | 24 | none 7, cap 6, offload 5, summary 6 |
| `step-cap` | 8 | offload h03, h05, h10; summary e02, m02, m03, m05, h10 |
| `token-cap` | 2 | none e07 (pilot), none h05 |
| `no-op-edit` | 2 | none h10, cap h10 |
| `stuck` | 1 | summary h05 |
| `wrong-target`, `check-tampering`, `QuotaExceeded`, `consecutive-timeout`, `retry-cap`, `summary`, `verify-reject` | 0 | none |

## Counts per strategy

| Strategy | Failed | `wrong-value` | `no-op-edit` | `step-cap` | `token-cap` | `stuck` |
|---|---|---|---|---|---|---|
| none | 10 | 7 | 1 | 0 | 2 | 0 |
| cap | 7 | 6 | 1 | 0 | 0 | 0 |
| offload | 8 | 5 | 0 | 3 | 0 | 0 |
| summary | 12 | 6 | 0 | 5 | 0 | 1 |
| total | 37 | 24 | 2 | 8 | 2 | 1 |

The failed counts equal the unresolved counts in `docs/notes/p3-finish.md` (10, 7, 8, 12).

## Where a label is a judgment call

- **Precedence rule.** A non-`submit` stop reason wins over the diff. `summary-m03` is the one case where it matters: it ended at `step-cap` with a correct partial edit (`.radar-list`) and the checked rule unfixed. A diff-first rule would label it by the diff instead. The other 7 `step-cap`, 2 `token-cap` and 1 `stuck` runs have no surviving edit, so both rules agree on them.
- **`no-op-edit` (none-h10, cap-h10).** The computed value was not measured. The label rests on the declared variable values (5 and 9, equal to the bug). The hunk sits next to a `html[data-theme="dark"]` block, so the variable's scope was not checked. Either way the value is not the expected 1.
- **`wrong-value`.** The label says the value differs from the check; it does not say why. The trajectories store tool calls, not reasoning, so "guessed" is not claimed. In all 8 tasks with a `wrong-value` run (e05, m01, m04, m05, m07, h01, h04, h07) the ticket states no target value (at most the bug's "8 px"). The same wrong value recurs across strategies (m04 and h04 backdrop 50 in all four), which fits a shared prior rather than a context effect, but one run per cell does not test that.
- **Evidence on the 11 stop-reason runs** (which file was open, repeated reads) is what the trajectories show. It does not establish that the context strategy caused the stop: `offload-h03` and `-h10` also ended without an edit with few repeated calls.
- **Only the checked rule decides.** A run was `unresolved` because the one check in `checks.json` failed. Secondary values (a `.glabel` 11px, a map-control z-index 5) are noted in the evidence column but did not change a label.
- `p4b-pilot-summary2-e07` (stop reason `retry-cap`) exists in `runs/` but is not in the tally; the `summary` e07 cell uses `p4b-pilot-summary3-e07` (resolved). It is not counted.

## Done-when status (P3-T21)

Every one of the 37 failed runs has one label from the list above, the list contains the P3-T06 stop reasons, the labels are a closed set (the `stuck` label is used only for a run whose stop reason is `stuck`), `FailureKind` is not used, and the counts per label are above. The owner's review of the labels is outstanding.

## Earlier draft: variant A (not part of the counts above)

The previous version of this file labelled the 9 unresolved variant A runs (`no-edit` 3, `guessed-value` 6, `wrong-target` 0) from `packages/fix-loop/runs/README.md`. Those labels are an earlier set, were not re-checked against this list, and are not in the 37-run counts.
