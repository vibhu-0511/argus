# ADR-013: Judge selection

Status: accepted (P4-T18).

## Context

The judge is supposed to say whether a fix matches the ticket without collateral change. The bar is Krippendorff's α of at least 0.80 against human labels, with a bootstrap interval. The same-family judge is a Mistral vision model. The cross-family judge is Gemma. If α is not reached, the shortfall has to be written down and the judge must not become a hard gate.

## Decision

The judge that ships, when it is used at all, is local Ollama `gemma4:e4b`. The same-family runner uses `pixtral-12b-2409` and the same prompt. Hosted Gemma is not selected. A directory page lists Together AI `google/gemma-4-E4B-it` as fair-use and key-gated as of 2026-10-18. That quota was not measured. See `docs/notes/p4-runtime-judge.md`.

α was not computed. `packages/verify/fixtures/calibration/labels.json` has 100 null labels. Those labels have to be made by a person before any judge output. Ollama is not installed here, so the overnight CPU run did not happen. There is no same-family run and no cross-family run. Rows A and B of the ablation table are not filled. The iteration log has no rubric revision. Held-out α is null.

That is below 0.80. The judge is advisory only. `best_of_k` may use a judge label to prefer one check-passing patch over another. A judge label of `fail` does not reject a patch whose checks passed. A flagged injection and a judge error do not accept a patch. Deterministic checks remain the hard gate.

`pixtral-12b-2409` is the id in the runner. This pass did not re-read the Mistral model card, and the free tier still has no measured quota in `docs/quotas.md`.

## Alternatives

- Treat the synthetic `constructed_as` field as the human label and report an α. That field is how the pair was drawn, not a person's judgment, and it was written by the same process that would then score it.
- Call Together on an unmeasured fair-use key. The personal profile is $0, and an unmeasured quota is not a decision.
- Ship no judge object at all. The runner, the rubric, and the α function are what the calibration needs once labels exist. Deleting them would repeat this phase.

## Consequences

A later run fills rows A and B from saved judge labels and the human file, on the held-out split. If that held-out α is still below 0.80, this decision stays: advisory only. Crossing 0.80 is a revision of this ADR, not a silent promotion.

## Update 2026-10-31 (facts only; the decision is unchanged)

Ollama 0.40.13 and `gemma4:e4b` (6.6 GB on disk) are now installed and the runner works on CPU (about 72 to 109 s per pair). The calibration set was rebuilt as 100 real Canvas screenshots (20 tickets; see `docs/notes/p4-finish.md`). `labels.json` holds Claude's draft labels, adopted by the owner; they are not independently produced human labels, and every alpha below is agreement with them. Baseline (rubric v1, all 100 pairs): the judge answered `pass` for every pair, alpha -0.245 (95% -0.309 to -0.192), false-accept rate 1.0. One iteration (rubric v2 and a prompt that names the difference first), scored on the 50-pair dev split only: alpha -0.005 (95% -0.199 to 0.182), agreement 17 of 50. The budget for T14 is spent, so alpha did not reach 0.80. Final held-out result (run `p4-judge-gemma4e4b-v2-heldout`, rubric v2 and prompt v2 on the 50 held-out pairs, forward and reverse order both finished): alpha 0.116 (bootstrap 95% -0.118 to 0.343), agreement 24 of 50 with the adopted drafts, false-accept rate 0.57, no errors, and the forward and reverse orders disagree on 40% of pairs (20 of 50). That is far below 0.80 and the interval includes zero, so the judge is not shown to agree with the labels better than chance. Dev alpha was -0.005, so the held-out number is not evidence of a real gain from the rubric change. Record: `docs/notes/p4-iteration-log.json`. The same-family run has no endpoint (no Mistral key). The judge stays advisory, which is the policy above for alpha below 0.80.

Same-family control (P4-T17), added 2026-10-31. The plan's same-family judge was a Mistral vision model with no endpoint. The fixer in the runs is a Claude session, so the owner chose Claude as the same-family judge. Run `p4-judge-claude-v2-heldout`: the same rubric v2 and prompt v2, the 50 held-out pairs, forward order only, one fresh Claude subagent per pair that saw only the prompt and the two images. Result against the adopted drafts: alpha 0.671 (bootstrap 95% 0.469 to 0.836), agreement 40 of 50, false-accept rate 0.13, 0 errors. Gemma on the same pairs: alpha 0.116, false-accept 0.57. The planned hypothesis (a cross-family judge agrees better than a same-family one) is not supported here; the gap is the other way. It cannot be read as a self-preference result for two reasons: the labels are Claude's own drafts, so a Claude judge agrees with them partly by construction, and the two judges differ a lot in capability (a hosted Claude model against a 4B model on CPU). Alpha is below 0.80 and its interval reaches 0.47, so the policy above is unchanged: advisory only. No reverse-order run, so there is no order-disagreement figure for the Claude judge.
