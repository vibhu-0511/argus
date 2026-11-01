# ADR-016: Routing policy

Status: accepted (P5-T15). Revisit when the repro stage works or when `localize` makes a model call.

## Context

Argus has three stages that can call a model: repro (write a script that fails on the bug), localize (find the file) and fix (write the patch). The cheap tier is cheaper per token but weaker. The question is which stages can go to the cheap tier without lowering the resolve rate.

Evidence is one ablation (`docs/notes/p5-t14-results.md`): 29 seeded tasks, A = all stages on the strong model, B = repro on the cheap model and fix on the strong one, a Claude session as the model (sonnet strong, haiku cheap), one run per task and variant.

- Resolve rate: A 19 of 27 (70.4%, interval 51.5% to 84.1%), B 20 of 28 (71.4%, 52.9% to 84.7%). Paired on 27 tasks: 18 both, 7 neither, 1 A only, 1 B only.
- Tokens and dollars per bug: B is lower by about 10% and 15%, but the cheap tier carried only about 2% of all tokens. The rest is a different draw of the fix stage.
- The repro stage found a repro in 1 of 58 runs. `localize` makes no model call (dom2src finds the file with embeddings), so it was not routed.

## Decision

The policy is data in `packages/argus-core/src/argus_core/routing.yaml`:

| Stage | Tier | Why |
|---|---|---|
| repro | cheap | The repro prompt is short, the stage rarely produces a script on these CSS bugs, and a wrong answer only costs a retry. Moving it did not lower the resolve rate in the ablation. |
| localize | cheap | No model call exists today. The row is there so a future call cannot silently run on the strong tier. |
| fix | strong | The patch decides the result. This stage is 70% of all turns and nearly all tokens. No run in the ablation put it on the cheap tier. |

A call falls back to the tier's other host once, and only when the first host refuses on quota (`quota_exceeded` or HTTP 429). Any other error ends the call: a fallback that hides a real error would hide a broken stage. A stage not in the file is an error, never a default tier.

The gate (ADR-017) is the guard: a change that moves `fix` to a cheaper model must pass `python -m eval gate` against the stored baseline before it is merged.

## Alternatives

- Everything on the strong tier. Simpler, and the ablation found no resolve-rate benefit from routing. Kept as variant A for comparison. Rejected because it spends strong-tier tokens on the repro stage for no measured gain, and the policy file costs nothing to keep.
- Fix on the cheap tier. Not measured in the ablation. See "What this does not show".

## Consequences

- The policy can change without code: edit the YAML, run the ablation harness, and compare.
- The saving from routing is small today, because repro rarely works. If the repro stage is rebuilt so that it produces scripts (for example by selecting on CSS instead of roles), the cheap tier carries more tokens and the same ablation should be run again.
- Latency, quota share and cached-token effects are not measured (see the results note).

## What this does not show

One run per cell, one model family, tiers set by a subagent parameter and not by a provider. The resolve-rate intervals overlap by almost their whole width, so the ablation can rule out a large drop but not a small one. The wrong-tier break-it (P5-T27, fix on the cheap tier) has not been run at the time of writing; this ADR does not claim the gate catches it.
