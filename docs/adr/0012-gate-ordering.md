# ADR-012: Gate ordering and short-circuit policy

Status: accepted (P4-T07).

## Context

A patch can look fixed on the ticketed control and still be broken. The verifier has four deterministic checks. They should run in one order, and a hard failure should stop the run before a later check, or a model, spends more work. A soft failure is a recorded warning. It is not a reason to hide the rest of the results, and it is not a reason to reject the patch.

## Decision

The order is `pixel`, `overflow`, `axe`, `console`. It is the tuple `ORDER` in `packages/verify/src/verify/pipeline.py`. Pixel is first because it is the screenshot regression and it does not need a DOM walk. Overflow is next because a clipped control at 375 px is the layout failure pixel noise can miss. Axe reports rule ids that are new versus the clean baseline. Console reports errors and warnings that are new versus that baseline.

A check with `hard=True` that fails stops the pipeline. The verdict carries the checks that ran, the failing check's name, and that check's reason. The four shipped checks are hard. A check with `hard=False` is stored and the pipeline continues. Soft failures do not set `ok` to false.

The judge is not in `ORDER`. It does not override a passed check run.

On submit, fix-loop runs the existing build gates first. Then it calls `verify`. The first rejection is a user message, `{"error": "<reason>", "verify": "<check>"}`, and the loop continues. `VERIFY_RETRIES` is 1. The second rejection stops as `verify-reject`. A verifier that raises is a rejection whose reason is `error`, not a pass.

## Alternatives

- Run axe first. It is slower and it does not catch a shifted layout that is still labelled.
- Average a soft failure into a hard stop. A warning would then reject a patch the screenshot checks accepted.
- Let the judge flip a passed pixel check. That makes a down or injected judge the gate. ADR-013 keeps the judge advisory until α is shown.

## Consequences

Changing `ORDER` or `VERIFY_RETRIES` is a change to this decision. A new hard check has to be added to `ORDER` and given a clean-pass and a matching-fail test. The phase report does not claim a live resolve rate from this gate.
