# ADR-014: Best-of-k policy and cost cap

Status: accepted (P4-T21).

## Context

Best-of-k draws several patches and keeps one. It raises the resolve rate only when the selector is better than chance. Each extra sample multiplies the fixer's token use. The 30-task runs at k = 1, 3, and 5 were not made, so there is no measured curve.

## Decision

The default k is 1. The cap is 5 candidates per bug. `best_of_k` records tokens in, out, and cached for every candidate on the usage ledger. Checks run first. The judge does not override a passed check run. If no candidate passes the checks, the selection is empty and the reason is `checks-fail`.

More samples stop paying at the cap, because the curve was not measured. Spending k = 3 or k = 5 before that curve exists spends quota for an unknown gain. When rows C, D, and E are filled from real runs, this ADR is revised if a larger k beats k = 1 inside the cap. Until P5, the dollar-equivalent cell stays "—".

## Alternatives

- Default to k = 5 because the plan's ablation includes it. That makes the most expensive arm the production path before the arm is measured.
- Cap at k = 1 forever. The sampler still has to exist so the ablation can be run. The default is 1. The cap is 5.

## Consequences

A caller who passes k = 3 is over the default and inside the cap. The ledger row is the evidence of what it cost. The phase report does not invent a resolve rate for that call.

## Update 2026-10-31 (facts only; the decision is unchanged)

A measured curve now exists, with a caveat: best-of-k with k = 1, 3, 5 ran on the 29 runnable seeded tasks with a Claude session as the model (`claude-session`) and the task's own scorer as an oracle selector. Resolved 20, 24 and 24 of 29 (Wilson 95% 0.508 to 0.827, 0.655 to 0.924, 0.655 to 0.924), at mean loop tokens per task of about 203k, 402k and 608k. k = 3 captured every gain (four tasks); k = 5 added none. The intervals overlap and the selector was perfect, so this is an upper bound for the checks-plus-judge selector, which could not be measured (the judge is at chance, ADR-013). Default k = 1 and the cap of 5 are unchanged; whether to lower the cap to 3 is the owner's call. Details: `docs/notes/p4-finish.md`, `phases/P04-verify.md`.

