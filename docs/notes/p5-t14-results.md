# P5-T14 routing ablation: results (Claude sessions as the model)

Run on 2026-11-01. Harness and method: `docs/notes/p5-t14.md`. Raw evidence: `packages/eval/results/t14/<A|B>/<task>/` (verdict, answers, diff, trajectories). Results files: `packages/eval/results/ablation-A.json` and `ablation-B.json`. Table: `uv run --all-packages python -m eval.ablation table packages/eval/results/ablation-A.json packages/eval/results/ablation-B.json`.

## What was run

- 29 seeded tasks (`seed-e01` to `seed-h10`, `bug-17` out), two variants, one run per task and variant: 58 runs, each driven turn by turn with one fresh subagent per step.
- **A**: every stage on the strong model (sonnet). **B**: repro stage on the cheap model (haiku), fix stage on the strong model (sonnet). Tiers are the subagent's `model` parameter, so the label is `claude-session tiers`, not a provider's tiers.
- Same task list, same fix settings (strategy `cap`, budget 32,000, step cap 20), same repro brief for both variants.

## Table

| Variant | Resolve rate (95% CI) | Tokens/bug (in, out, cached) | $-equivalent/bug | Quota share/bug | p50 latency | p95 latency |
|---|---|---|---|---|---|---|
| A | 70.4% (19/27) [51.5%, 84.1%] | 38,205 / 552 / 0 | $0.0819 | — | 819 s | 1,801 s |
| B | 71.4% (20/28) [52.9%, 84.7%] | 34,471 / 468 / 0 | $0.0694 | — | 1,617 s | 5,098 s |

Denominators exclude runs the scorer could not score (exit 2): A on `seed-h06` and `seed-h09`, B on `seed-h09`. They are listed as excluded in the results files, not counted as resolved or unresolved.

## Reading

- **Resolve rate: no difference seen.** The intervals overlap almost completely. Paired on the 27 tasks scored in both variants: 18 resolved by both, 7 by neither, 1 by A only (`seed-e05`), 1 by B only (`seed-m05`). One run per cell, so single flips are as likely noise as an effect.
- **Tokens and dollars: B is lower by about 10% of tokens and 15% of list-price dollars per bug** (A 38,757 vs B 34,939 tokens; $0.0819 vs $0.0694). **Routing cannot explain most of that.** The cheap tier carried only 21,766 input and 7,959 output tokens in total (86 haiku repro turns), about 2% of all tokens, so moving repro to haiku can account for at most that much. The rest is the fix stage, which is sonnet in both variants but a different draw: A ran 228 fix turns and B 204, and A's sonnet input tokens are 1,031,530 against B's 943,424. With one run per cell this is run-to-run difference, not a routing effect. Tokens are chars/4 estimates of the messages and leave out each subagent's harness overhead.
- **The repro stage did not work for either variant.** `repro_found` is 0 of 29 for A and 1 of 29 for B; every other run ended on `retry-cap` and the fix stage ran with `Repro: not-run`. The dry run's guess (CSS-only bugs are out of reach of `getByRole` selectors) held. So the hypothesis "cheap tier for repro and localize cuts tokens without lowering resolve rate" is only tested on a stage that rarely produces anything, and `localize` makes no chat call, so it was not routed at all.
- **Quota share is a dash.** The only cap on Claude sessions here is the self-imposed one in `eval.t14_turn.SELF_IMPOSED`, which never binds. No provider cap exists to divide by.
- **Latency is not comparable.** B's p50 and p95 are about twice A's, but B includes live repro scripts (up to 300 s each), all runs were driven several at a time on one machine, and B's h06 and h09 were run again after Docker trouble. I did not separate these causes, so do not read the gap as a cost of routing.

## What went wrong, and what was done

- `B-seed-h06` and `B-seed-h09` first stopped with a replay mismatch: the repro stage ended on `tool-unavailable` after one turn (the rig was overloaded), and when the stored answers were replayed the rig responded, so the repro stage asked for another turn and the answers no longer lined up. Both runs were reset and run again from scratch; their first attempts are not in the results. The harness caches successful repro runs but not `tool-unavailable` outcomes, so replay is not deterministic under load. This was not fixed during the run.
- While these two were being reset, two sessions acted on the same run folders for a few minutes (the batch session and the orchestrator). Both final answer logs were checked afterwards (`rrrFFFFFFFFFFF` for h09, `rrrFFFFFF` and a verdict for h06): repro turns first on haiku, then fix turns on sonnet, in order.
- Coordinators miscounted worker tiers for several runs (for example `B-seed-m04`, `B-seed-e02`, `B-seed-h09`). The tables use each run's own `verdict.json`, not the coordinator's text.
- Batch 5 (`seed-h06` to `seed-h10`) was run inside the batch 4 session after it asked for a go-ahead.
- `A-seed-h06` stopped on `consecutive-timeout` and was excluded (scorer exit 2); `seed-h09` is excluded in both variants. Both look like load or setup problems on those tasks, not model results. I did not look into the scorer's exit-2 cause for `seed-h09`.

## What this does not show

- One run per cell, one model family, tiers set by a subagent parameter. Not comparable with the Groq rows in other phases.
- Whether routing helps when the repro stage works, or when a real localize call exists.
- Any real quota effect or any cached-token effect (cached tokens are 0 everywhere).

## Acceptance (`phases/P05-argus-eval.md`, P5-T14)

"Two rows filled from real runs with the same tasks; tokens, quota share, resolve rate and latency reported." Two rows are filled from real runs on the same tasks, with tokens, resolve rate and latency reported. Quota share is a dash with the reason above (no provider cap exists for Claude sessions). **The owner decided on 2026-11-02 that a Claude-session run counts for T14, so the task is ticked.** The caveats above stay.
