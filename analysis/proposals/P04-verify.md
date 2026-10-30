# Proposal for `phases/P04-verify.md`

Plan text only. No new tasks. No hour changes.

### DESIGN-008
- Severity: Med
- Section: P4-T02
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P4-T02 | Build pixel-diff check against the golden screenshot with region masks | [PAIR] | build | 2 | P3-T14 | Passes on a clean tree, fails on a tree with a 4 px shift in a masked-out-of-scope area; threshold is a named constant |
```

- Proposed text:

```
| P4-T02 | Build pixel-diff check against the golden screenshot with region masks | [PAIR] | build | 2 | P3-T14 | Passes on a clean tree; passes when the only difference is inside the mask, and fails when a 4 px shift is outside the mask; the mask keeps layout; the constant is a changed-pixel ratio written next to its unit; a size change fails without scaling; the 4 px shift exceeds the fringe cap; a repeated fingerprint stays a hard failure |
```

Delta: the mask keeps layout, the constant is a changed-pixel ratio written next to its unit, a size change fails without scaling, the 4 px shift exceeds the fringe cap, and a repeated fingerprint stays a hard failure. The pass/fail clause is PLAN-009. If both are accepted, use this row.

### DESIGN-010
- Severity: Med
- Section: Done when; P4-T24
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
- Krippendorff's α between the judge and your labels is at least 0.80 on that set, with a bootstrap interval. If it is not reached within the T14 budget, ADR-013 records the shortfall and the judge is advisory only; that is a written decision, not a silent one.
```

```
| P4-T24 | Break it: swap the order of before and after images, and pad the explanation | [ME] | test | 2 | P4-T13 | Judge verdict flips or drifts on swapped order; written up with the mitigation |
```

```
1. **Order swap and padding (P4-T24).** *Induced failure:* present the same pair with before and after swapped, or with a long ticket. *Expected signal:* the judge label changes with presentation order or length. *Fix:* randomise and average over both orders, or fix the order in the rubric and lengthen no inputs.
```

- Proposed text:

```
- Krippendorff's α between the judge and your labels is at least 0.80 on that set, with a bootstrap interval, and the order-disagreement rate is reported beside α. A disagreeing pair is not averaged into one label, and an unparsed judge string stays in the α denominator as `error`. If α is not reached within the T14 budget, ADR-013 records the shortfall and the judge is advisory only; that is a written decision, not a silent one. The judge does not override a passed check run.
```

```
| P4-T24 | Break it: swap the order of before and after images, and pad the explanation | [ME] | test | 2 | P4-T13 | Judge verdict flips or drifts on swapped order; the order-disagreement rate is reported beside α; a disagreeing pair is not averaged into one label; written up with the mitigation |
```

```
1. **Order swap and padding (P4-T24).** *Induced failure:* present the same pair with before and after swapped, or with a long ticket. *Expected signal:* the judge label changes with presentation order or length. *Fix:* report the order-disagreement rate beside α and do not average a disagreeing pair into one label, or fix the order in the rubric and lengthen no inputs.
```

Delta: the order-disagreement rate is reported beside α, a disagreeing pair is not averaged into one label, and an unparsed judge string stays in the α denominator as `error`. The last sentence of the Done when line is PLAN-025. If both are accepted, use this Done when line.

### EDGE-001
- Severity: Med
- Section: P4-T23
- Owner: [CLAUDE]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P4-T23 | Add CI job for verify tests on recorded fixtures, no LLM calls | [CLAUDE] | deploy | 2 | P4-T06 | Workflow green; uses stored screenshots; no secrets |
```

- Proposed text:

```
| P4-T23 | Add CI job for verify tests on recorded fixtures, no LLM calls | [CLAUDE] | deploy | 2 | P4-T06 | Workflow green on a matching stored pair; exits non-zero on a committed pair over the named ratio or on a missing or unparsable verdict file; uses stored screenshots; no secrets |
```

Delta: P4-T23 only. The unsliced-log clause stays on the bench task.

### EDGE-002
- Severity: Med
- Section: P4-T26
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P4-T26 | Break it: introduce a screenshot that differs only by font loading | [ME] | test | 2 | P4-T02 | False positive reproduced; stabilisation or tolerance removes it; written up |
```

```
3. **Font-loading flake (P4-T26).** *Induced failure:* screenshot taken before the web font loads. *Expected signal:* intermittent pixel-diff false positive. *Fix:* wait for fonts and network idle, and keep fonts pinned in the test build.
```

- Proposed text:

```
| P4-T26 | Break it: introduce a screenshot that differs only by font loading | [ME] | test | 2 | P4-T02 | False positive reproduced; the font wait stays; a fringe under the named cap passes and a different font family still fails; written up |
```

```
3. **Font-loading flake (P4-T26).** *Induced failure:* screenshot taken before the web font loads. *Expected signal:* intermittent pixel-diff false positive. *Fix:* wait for fonts and network idle, and keep fonts pinned in the test build; a fringe under the named cap passes, and a different font family still fails.
```

### PLAN-009
- Severity: Med
- Section: P4-T02
- Owner: [PAIR]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
| P4-T02 | Build pixel-diff check against the golden screenshot with region masks | [PAIR] | build | 2 | P3-T14 | Passes on a clean tree, fails on a tree with a 4 px shift in a masked-out-of-scope area; threshold is a named constant |
```

- Proposed text:

```
| P4-T02 | Build pixel-diff check against the golden screenshot with region masks | [PAIR] | build | 2 | P3-T14 | Passes on a clean tree; passes when the only difference is inside the mask, and fails when a 4 px shift is outside the mask; the mask keeps layout; the constant is a changed-pixel ratio written next to its unit; a size change fails without scaling; the 4 px shift exceeds the fringe cap; a repeated fingerprint stays a hard failure |
```

Delta: the check passes when the only difference is inside the mask, and fails when a 4 px shift is outside the mask. The mask, ratio, size, fringe, and fingerprint clauses are DESIGN-008. If both are accepted, use this row.

### PLAN-025
- Severity: Med
- Section: Goal; P4-T19
- Owner: [ME]
- Hours delta: 0
- Replacement or cut: none
- Current text:

```
Decide whether a patch really fixed the bug and broke nothing else, using deterministic checks first and a calibrated cross-family vision judge second, then measure what best-of-k buys.
```

```
| P4-T19 | Build best-of-k sampler: k candidate patches, verifier and judge pick one | [ME] | build | 3 | P4-T06, P4-T14, P3-T18 | `best_of_k(k)` returns the selected patch and all candidates; selection reason is recorded; token use per candidate is in the ledger |
```

```
- Krippendorff's α between the judge and your labels is at least 0.80 on that set, with a bootstrap interval. If it is not reached within the T14 budget, ADR-013 records the shortfall and the judge is advisory only; that is a written decision, not a silent one.
```

- Proposed text:

```
Decide whether a patch really fixed the bug and broke nothing else, using deterministic checks first and a calibrated cross-family vision judge second. The judge does not override a passed check run. Best-of-k stays inside the P4-T19 selector, then the phase measures what best-of-k buys.
```

```
| P4-T19 | Build best-of-k sampler: k candidate patches, verifier and judge pick one | [ME] | build | 3 | P4-T06, P4-T14, P3-T18 | `best_of_k(k)` stays inside this selector; checks run first and the judge does not override a passed check run; it returns the selected patch and all candidates; selection reason is recorded; token use per candidate is in the ledger |
```

```
- Krippendorff's α between the judge and your labels is at least 0.80 on that set, with a bootstrap interval, and the order-disagreement rate is reported beside α. A disagreeing pair is not averaged into one label, and an unparsed judge string stays in the α denominator as `error`. If α is not reached within the T14 budget, ADR-013 records the shortfall and the judge is advisory only; that is a written decision, not a silent one. The judge does not override a passed check run.
```

Delta: checks run first, the judge does not override a passed check run, and best-of-k stays inside the P4-T19 selector. This file does not add a hard gate that rejects a clean check run. The disagreement-rate clauses in the Done when line are DESIGN-010. If both are accepted, use this Done when line.

Hours and tasks in this file: unchanged.
