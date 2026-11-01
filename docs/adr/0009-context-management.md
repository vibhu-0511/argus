# ADR-009: Context management policy

Status: **proposed, not accepted** (P3-T23). Drafted by Claude at the owner's request, for the owner to review and decide. The default below is a planning choice, not a measured result.

## Context

Long tool outputs stay in the message list and are re-sent on every later step. The loop has three ways to keep the window small, and one way not to (below). The Ablation table in `phases/P03-fix-loop.md` compares them. The run-by-run numbers come from `packages/fix-loop/swarm/tally.py`, which reads `verdict.json` and `trajectory.jsonl` for each run, and are written up in `docs/notes/p3-finish.md` (section "Stateless context ablation on 29 tasks").

The method: one fresh Claude subagent per loop step, so the message list is all the model sees and a strategy cannot be hidden by the model's own memory. 29 runnable seeded tasks (`bug-17` excluded), four strategies, the model labelled `claude-session`.

| Variant | Strategy | Resolved (Wilson 95%) | Mean model turns | Mean est. loop tokens in / out per task | Peak prompt tokens (mean of per-task max, max) | Stop reasons |
|---|---|---|---|---|---|---|
| A (stateful, full memory) | none | 20/29 [0.507695, 0.827246] | not tallied | 202904 / 205 | 37407, 179383 | not tallied |
| A (stateless) | none | 18/28 [0.458300, 0.792944] | 6.24 | 100467 / 170 | 34060, 484541 | submit 27, token-cap 2 |
| B | output caps | 21/28 [0.566440, 0.873237] | 7.55 | 43105 / 200 | 7276, 18118 | submit 29 |
| C | offload to files | 20/28 [0.529404, 0.847462] | 8.97 | 32430 / 228 | 5505, 14400 | submit 26, step-cap 3 |
| D | rolling summary | 17/29 [0.407375, 0.744871] | 13.31 (9.79 loop steps) | 23485 / 250 | 5180, 8339 | submit 21, step-cap 5, summary 2, stuck 1 |

Tokens are chars/4 estimates and cached tokens are 0 in every row. The summarizer's own calls are not trajectory step rows, so D's token cells undercount. Three runs scored exit 2 (an infrastructure code) and are counted as neither resolved nor unresolved: `p4b-full-offload-m07`, `p4b-full-none-h08`, `p4b-full-cap-h05`. The stateful A row is a different method and is not a baseline for B to D.

## Limits of this evidence

- **The Wilson intervals overlap for all four strategies.** The point estimates (21, 20, 18, 17 resolved) do not separate them.
- **One run per cell.** Run-to-run noise of a single subagent chain was not measured. The strategies disagree on 10 of 29 tasks, and one run each cannot say how many of those flips are the strategy and how many are chance.
- **One model.** `claude-session`, not comparable with a Groq or Mistral run, and not a Devstral row.
- **The harness choices were not measured:** the 32,000-token budget, the 20,000-character cut the driver applies to displayed output, and the strategy running at 80% of the budget. `OUTPUT_CAP` (8000 characters) and `HEAD` (200) in `strategies.py` are prefix sizes chosen at build time.
- Latency, quota share and dollar cost were not recorded.

## Decision

**Default strategy: output caps (variant B, `cap_strategy`).** This is a planning choice. The data cannot decide between B and C. Reasons, each from the table:

- Against no compaction, B used 43105 input tokens per task against 100467 (about 2.3x less) and a mean peak prompt of 7276 against 34060 (about 4.7x less), with a resolve point estimate that is not lower (21/28 against 18/28, overlapping intervals).
- C went lower still, 32430 input (about 3.1x less than none) and a mean peak of 5505 (about 6.2x less), with 20/28. B needed fewer turns (7.55 against 8.97), and C had 3 `step-cap` stops where B had none.
- B has the highest resolve point estimate and every B run ended on `submit`. That is a point estimate inside overlapping intervals.

**When to switch:**

- **Offload (C)** when a cap-truncated tail is the cause of a failed run. `cap_text` drops the tail, which is where an error often is. C keeps the whole body reachable through a path under `.argus/`, at the cost of an extra `read_file` step. The ablation did not isolate such a case, so this rule is a hypothesis.
- **Not no compaction (A) outside small outputs.** Stateless A hit `token-cap` twice and reached a peak prompt of 484541 tokens on one task. A is kept as the ablation control.
- **Not rolling summary (D) as a default.** D had the lowest resolve point estimate (17/29), the most turns (13.31 against 6.24 to 8.97), and its 5 `step-cap` runs and 1 `stuck` run were all unresolved. On e02, m02, m03 and m05 it took 31 to 33 turns and ended unresolved while the other three strategies mostly resolved them. Its token savings are the largest, but its token cells undercount. Use it only if a window is too small for B or C, and only with the stop below.

Changing the default needs a repeat of the ablation with more than one run per cell, or a different model. This ADR is then revisited.

## Invariants (implemented in `src/fix_loop/strategies.py` and `loop.py`)

- **The system prompt and the first user message survive every strategy.** `cap_strategy` and `offload` change only the latest observation. `rolling_summary` rebuilds the list as `messages[0]`, `messages[1]`, and one summary message.
- **A summary that does not shrink is a stop, not a retry.** `rolling_summary` raises `SummaryDidNotShrink` when the rebuilt list is not shorter in characters than the original, and `loop.py` ends the run with `StopReason.summary` (ADR-008). Two D runs stopped this way, h03 and h09, and both were scored `resolved` from the worktree diff, as ADR-008 decides for every stop reason. The stop reason stays `summary`.
- **Last-N elision is not added**, including "keep the five most recent files". Dropping turns by position can drop the one observation that matters, and nothing in the ablation tested it.
- Summary tokens are counted in the ledger (`ledger.call` in `rolling_summary`).
- A strategy runs when the run's cumulative tokens reach 80% of the budget (`apply_budget` in `budget.py`).

## Alternatives

- Pick the strategy with the highest point estimate and call it measured. The intervals overlap, so that would claim more than one run per cell shows.
- Make D the default because it cuts the most tokens. It had the lowest resolve estimate and the most turns.
- Add last-N elision as a fourth strategy. It was not run and the phase does not ask for it.
- Retry a summary that did not shrink. The loop would spend another cheap-tier call on the same input.

## Consequences

`OUTPUT_CAP`, `HEAD` and the 80% rule are build-time choices. Changing them or the default is a change to this decision. Re-scoring the three excluded runs would change the denominators by one each; it has not been done.
