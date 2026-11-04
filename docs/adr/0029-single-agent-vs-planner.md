# ADR-029: Single agent vs planner and subagents

Status: proposed (P8-T15), drafted by Claude at the owner's request, for the owner to decide. It is accepted when the owner approves it. **The comparison it is about has not been measured.** P8-T12 (20 tasks, both variants) did not run: the only model allowed for it, the local `gemma4:e4b`, is not on the build machine. Both rows of the Ablation table in `phases/P08-argus-app.md` are dashes. So this ADR states the keep rule and applies it to what exists, and what exists is nothing. **No decision between the two variants can be drawn from data.** The single agent stays the default. No number below is a result of Argus; every figure about multi-agent cost is a claim from a source, labelled as such.

## Context

The fix loop today is one agent: `fix_loop.loop.run_fix` (P3-T06) reads the ticket, uses tools, and proposes a patch inside one message history. P8-T11 added a second shape, `fix_loop.planner.run_planned`:

| Variant | What it is | Where |
|---|---|---|
| A, single agent | One model, one message history, one token and step cap | `fix_loop.loop.run_fix` |
| B, planner and subagents | One planner call turns the ticket and repo context into 1 to 5 typed sub-tasks. Each sub-task runs `run_fix` as a subagent with its own history and its own share of the token cap. Subagents run one after the other in one worktree. A plan that does not parse raises `PlanError` and the bug is scored unresolved, keeping the planner's tokens | `packages/fix-loop/src/fix_loop/planner.py` (P8-T11) |

B reuses A's loop, router and ledger unchanged, but it adds a planner prompt, a plan schema, a failure mode (`PlanError`), sequential sub-runs that can undo each other in one worktree, and more places where tokens are spent. That is the "extra moving parts" the phase asks about.

The question the phase set: does the measured gain on success and on tokens justify those parts? The harness to answer it is built (`docs/notes/p8-t12.md`): same 20 tasks, same model, same caps, `params.variant` the only difference, tokens summed over the planner and every subagent, Wilson 95% intervals, a subagent-calls-per-bug column.

## What was measured

Nothing, for this question.

| Variant | Tasks run | Resolve rate (95% CI) | Tokens per bug | Subagent calls per bug |
|---|---|---|---|---|
| A | 0 of 20 | — | — | — |
| B | 0 of 20 | — | — | — |

The same dashes are in the Ablation table of `phases/P08-argus-app.md` ("Status (2026-11-04): not measured"). Reason, from `docs/notes/p8-t12.md`: no Ollama server on the machine, no `ollama` binary, an empty model folder. Fetching the model needs the owner's yes, and hosted or free-tier APIs are not allowed for this run.

Two things that look like evidence and are not:

- `packages/eval/results/ablation-A.json` and `ablation-B.json` are the **P5-T14 routing ablation** (strong-only against routed models, from a Claude session). They do not compare a single agent with a planner and say nothing here.
- The harness tests (`packages/eval/tests/test_ablation_run.py`) use stub models. They show the plumbing counts tokens and subagent calls correctly. They do not show how either variant performs.

What exists from sources, as expectation only:

- Anthropic's multi-agent research post (2025-06-13) says a single agent uses about 4 times the tokens of a chat and a multi-agent system about 15 times, for its own research feature, not for coding and not for Argus. It names coding, and tasks where all agents need the same context, as a poor fit. It also says token use alone explained 80% of the variance on one benchmark, so a gain from more tokens is not a gain from structure. Notes and section references: `docs/notes/p8-t01-multi-agent-notes.md` (a first pass by Claude; the owner should read the posts).
- That gives a prior, not a result: B probably costs more tokens per bug on a coding task, so passing the rule is expected to be hard.

## Decision

### The keep rule

Written before any number exists, so it cannot be fitted to one.

**B replaces A as the default only if it wins on BOTH resolve rate AND tokens per bug, on the same 20 tasks, the same model and the same caps, with tokens counted over every agent (planner, every subagent, every retry).**

A win on one axis is not a keep. A resolve-rate gain alone can come from spending more tokens; a token saving alone can come from giving up sooner. Requiring both removes those two explanations.

How each side of the rule is read, so the owner does not have to argue it after seeing the table:

| Side | B wins when | B does not win when |
|---|---|---|
| Resolve rate | B's rate is higher **and** its Wilson 95% interval does not overlap A's | B's rate is equal or lower, or the intervals overlap. With 20 tasks they are wide (10 of 20 is about 30% to 70%), so overlap means "no difference shown", not "B is worse" |
| Tokens per bug | B's tokens per bug (in plus out, all agents) are lower than A's | B's are equal or higher |

A win on resolve rate needs separated intervals; a win on tokens needs only a lower mean, since tokens per bug is a count and not a rate with an interval in the table. The owner may ask for a stricter test on tokens (a spread over bugs) when the numbers exist. This ADR does not invent one.

Not part of the rule: latency, `$`-equivalent and quota share. They are reported next to the rows. They do not turn a loss on the two axes into a keep, and they do not turn a win into a loss. If B wins both and is much slower, the owner decides whether to keep it; the rule only says it earned the right to be considered.

### Applying the rule to the measured rows

| Check | Row A | Row B | Result |
|---|---|---|---|
| Both rows filled from the same 20 tasks | no, 0 tasks | no, 0 tasks | fails |
| Resolve rate, separated intervals, B higher | dash | dash | cannot be evaluated |
| Tokens per bug, B lower | dash | dash | cannot be evaluated |

**The rule is not met, because it cannot be evaluated.** No measured row exists, so nothing wins. **Decision: no variant is chosen on evidence. The single agent (A) stays the default** and B stays an opt-in variant behind `params.variant` that is not used in the pipeline. That is the status quo and the lower-cost choice, and it is also the choice the rule itself gives when a gain is not shown: B has to earn the change.

This is not a finding that A is better. It is a finding that nothing has been shown.

### Limits to state wherever a future table is quoted

These come from `docs/notes/p8-t12.md` and decide how far a future result reaches.

- The model is `gemma4:e4b`, a small local model, not the production model. A loss for B on it does not show B loses on a strong model, and a win does not show it wins.
- One run per task per variant, 20 tasks, no repeat for noise.
- Subagents run one after the other in one worktree, so B is not the parallel design the source post describes.
- `repro` is off in both configs, so the repro stage is not part of the comparison.
- Say how many of the 20 tasks touch more than one file. The multi-agent case is strongest on those; if the 20 are mostly one-file bugs, the planner cannot show a gain.
- Latency is wall clock on one CPU machine with `repro` off.

### What must happen before this ADR can be revisited

1. The owner installs Ollama and pulls `gemma4:e4b` (steps in `docs/notes/p8-t12.md`).
2. Run A, then B, on the same 20 tasks with the committed configs `packages/eval/policies/p8-t12-A.agent.json` and `p8-t12-B.agent.json`, and fill both rows of the Ablation table.
3. Apply the table above. Change the Status line of this ADR, and either keep A or ask the owner to approve B as the default.
4. If the rows are filled from fewer than 20 tasks or one variant is partial, the result is the same as today: no decision, A stays.

## Alternatives

- **Make B the default now because multi-agent is common in the field.** Rejected: the one source read says it fits coding with shared context badly and costs about 3.75 times a single agent in tokens (15 against 4, its own figures, a different task). There is no Argus number to override that.
- **Remove B until it is measured.** Not chosen: it is built, tested with stubs, and cheap to keep behind a switch. Removal would cost the rebuild when the owner runs T12.
- **Decide on resolve rate alone.** Rejected: a planner that spends more tokens can raise resolve rate by spending. The phase set the rule as both.
- **Fill the rows from an estimate or from a hosted model.** Rejected: an estimate is an invented number, and hosted or free-tier APIs are not allowed for this run.
- **Count only the lead agent's tokens.** Rejected: it hides most of B's cost.

## Consequences

- The pipeline is unchanged: single agent by default. No code changes from this ADR.
- P8-T12 stays unticked. This ADR depends on it for evidence and records that it has none.
- The phase's "single agent vs planner" success line in `phases/P08-argus-app.md` is not met until T12 runs; this ADR does not meet it.
- When T12 runs, only the Status line and the "Applying the rule" table here change; the rule does not.
- Nothing here was run: no command in this ADR produced a number.
