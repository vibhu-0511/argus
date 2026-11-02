# ADR-017: CI gate thresholds

Status: proposed (P5-T18), drafted by Claude at the owner's request, for the owner to review. It is accepted when the owner approves it.

## Context

`.github/workflows/eval-gate.yml` runs `python -m eval gate packages/eval/results/current.json --baseline packages/eval/results/baseline.json` on every push (wiring: `docs/notes/p5-t17.md`). The gate has two rules and three numbers, all in `packages/eval/gate.toml`:

1. **Resolve rate.** Fail when the run's resolve rate is below the baseline's Wilson lower bound (at `z`) minus `margin`.
2. **Tokens per bug.** Fail when the mean of tokens in + out per scored task is more than `max_growth` above the baseline's.

A threshold set below the run-to-run noise turns the gate red on code that did not change, and people stop reading it. A threshold set far above the noise lets a real regression through. So each number is chosen against the noise of one variant run again and again. `uv run --package eval python packages/eval/scripts/run_noise.py` prints every figure below from stored files; it makes no model call.

## Observed noise

The only repeats of one configuration that exist are the five draws of P3 variant A (the stateful Claude-session fix loop, 29 runnable seeded tasks, step cap 20, token cap 400000): draw 1 is the P3 run, draws 2 to 5 are the P4-T20 reruns (`packages/fix-loop/runs/p4-t20-subset29-claude-session.json`, `docs/notes/p4-finish.md`). Same model, same tasks, same caps. The other P3 variants (none, cap, offload, summary, mini-swe-agent) differ in method, so their spread is not noise and is not used.

| Draw | Resolved | Rate | Tokens per bug (in + out) | Token-cap stops |
|---|---|---|---|---|
| 1 (P3) | 20/29 | 0.6897 | 203,109 | 5 |
| 2 | 22/29 | 0.7586 | 87,785 | 2 |
| 3 | 18/29 | 0.6207 | 111,213 | 4 |
| 4 | 20/28 | 0.7143 | 73,230 | 1 |
| 5 | 18/29 | 0.6207 | 127,411 | 3 |

Draw 4 has 28 scored tasks: `seed-e07-d4` stopped on `step-cap` and could not be scored, and an excluded task is outside the denominator, as in the gate. Tokens are chars/4 estimates of the loop's messages, not provider usage.

**Resolve rate.** Mean of the five rates 0.6808; sample standard deviation 0.0602 (about 1.7 tasks); range 0.6207 to 0.7586, a spread of 4 tasks. 8 of the 29 tasks changed verdict between draws, so the noise is a handful of coin-flip tasks, not a global drift. The spread is below what the Wilson interval assumes: independent tasks at p = 0.68 would give sqrt(0.68 x 0.32 / 29) = 0.087, but the same 29 tasks are drawn each time. The interval is therefore the wider, safer yardstick.

**Tokens per bug.** The mean swings with how many runs hit the 400000-token cap: one more cap stop adds about 400,000 / 29 = 13,800 to the mean. Draws 2 to 5: mean 99,910, sample sd 24,103, largest ratio 127,411 / 73,230 = 1.74, that is +74.0% between the lightest and the heaviest draw. Draw 1 is different: 203,109, which is +177.4% over draw 4 and +131.4% over draw 2. Why draw 1 costs about twice as much as the four later draws is **not established**: the median per task is 225,485 against 35,000 to 47,000, so it is not a few cap stops. It is the P3 run, made before the P4 reruns, and the stored files do not say what else differed.

**Too few repeats.** Five draws of one variant on one model give a standard deviation that is itself uncertain: with 4 degrees of freedom the 95% interval for the true sd of the resolve rate is 0.0602 x sqrt(4 / 11.143) = 0.036 to 0.0602 x sqrt(4 / 0.484) = 0.173. The noise is known only to within a factor of three either way. No latency was recorded in any stored run, so there is no latency threshold.

## Decision

`packages/eval/gate.toml` keeps its values. The comment in the file now points here.

| Threshold | Value | Why |
|---|---|---|
| `resolve_rate.z` | 1.96 | The floor is the lower bound of the 95% Wilson interval of the baseline. With the baseline at 20/29 it is 0.5077, which is 0.6808 - 0.5077 = 0.1731 below the rerun mean, 2.9 sample sd. The lowest rerun, 0.6207, is 0.113 (3.3 tasks) above it. On all 20 ordered (baseline draw, run draw) pairs the resolve rule fires 0 times; the highest floor, from draw 2 (22/29), is 0.5789, still under the lowest rerun. |
| `resolve_rate.margin` | 0.0 | The noise gives no reason for slack: the floor already sits 2.9 sd below the mean and the interval is wider than the observed spread. Because the sd is known only within a factor of three, 2.9 sd could be 1 sd if the truth is at the top of its range. If the gate goes red on unchanged code, the response is to add reruns of the same variant and revisit this ADR, not to add slack now. |
| `tokens_per_bug.max_growth` | 1.0 (+100%) | Must be above the +74.0% seen between same-harness draws 2 to 5, or unchanged code fails; 1.0 leaves 26 points of room. Against the stored baseline (draw 1, the heaviest) no rerun is above +0%, so the rule never fires on noise there. It would fire on 2 of the 20 pairs (draw 2 -> draw 1, +131.4%; draw 4 -> draw 1, +177.4%), both pairs in which the run is the unexplained heavy draw. Raising the limit above 1.77 to cover them would let a doubling of cost pass, and a doubling is what the rule is for. So it stays at 1.0 and the draw-1 gap stays an open question. It holds only when both files count tokens the same way (chars/4 here). |

What the gate can and cannot see, from the same arithmetic: against a 20/29 baseline a run must resolve 14 or fewer of 29 to fail (14/29 = 0.4828 < 0.5077; 15/29 = 0.5172 passes). A loss of up to 5 tasks, 17 points, passes. That is the price of 29 tasks and a 95% interval. P5-T27 (the fix step forced onto the cheap tier) will turn this gate red only if it costs six or more tasks; that run has not been made.

## Who may override

The repo owner, and only by editing `packages/eval/gate.toml` (a threshold) or replacing `packages/eval/results/baseline.json` (a new baseline) in a pull request that is reviewed before it is merged. The pull request names the run the new baseline is, or the noise measurement the new value rests on. The workflow has no skip flag, label, `continue-on-error` or secret that turns the gate off. A red run is fixed in the code or answered by that reviewed change; `gate.toml` and `baseline.json` are not edited just to turn a run green. An agent session (including Claude) does not change them to pass the gate unless the owner asked for exactly that change.

## Alternatives

- **Lower the token limit to +50%.** Tighter, and it would fire on unchanged code: draws 2 to 5 differ by +74%.
- **Raise it to +200% to cover draw 1.** Quiet on all 20 pairs, and lets a doubling of cost through.
- **A positive margin on the resolve rate.** The noise gives no reason, see above.
- **Gate on the point estimate.** A one-task move (3.4 points) is inside the observed spread, so the gate would flap.

## Consequences

The gate is conservative on resolve rate, loose on tokens, and has no latency rule. The numbers rest on one variant, one model and five draws. Revisit them when the baseline changes (a P5 run with provider token counts replaces the chars/4 baseline), when the routed runs of P5-T14 have been repeated and give noise for another configuration, when the gate goes red on unchanged code, or when draw 1's extra cost is explained. Until then `gate.toml` stays as it is.
