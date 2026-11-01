# P4 judge design notes

Read on 2026-10-31.

- [LLM evaluators recognize and favor their own generations](https://arxiv.org/abs/2404.13076) (Panickssery, Bowman, Feng, 2024).
- [Computing Krippendorff's Alpha-Reliability](https://repository.upenn.edu/asc_papers/43/) (Krippendorff, 2011).
- [Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters](https://arxiv.org/abs/2408.03314) (Snell, Lee, Xu, Kumar, 2024).

## Self-preference

Panickssery et al. find that an LLM judge scores text from its own model family higher than text from another family, and that the judge can often tell which outputs are its own. The practical claim for this phase: a judge from the fixer's family (Mistral) will accept the fixer's bad patches more often than a judge from another family (Gemma).

The measurement is the same 100 pairs, the same rubric, two runners. Compare judge–human α and the false-accept rate on pairs a human did not label `pass`. A higher false-accept rate on the Mistral judge is the self-preference signal. The response is to ship the cross-family judge, and to keep deterministic checks as the hard gate so a biased judge cannot accept a broken screenshot.

## Alpha

Krippendorff's α is `1 - Do/De` for nominal labels. Coders are the columns, pairs are the rows. Each unit adds to a coincidence matrix: an agreement on label `c` adds 2 to the diagonal cell, a disagreement adds one off-diagonal each way. With two coders and n pairs, the value count is `2n`.

The published two-observer example (Ben `a a b b d c c c e d d a`, Gerry `b a b b b c c c e d d d`) is α = 0.692. `alpha_nominal` reproduces that to three decimals.

The interval is a percentile bootstrap over pairs, seeded. An unparsed judge string is the label `error` and stays in the denominator. It is not dropped. Two presentation orders are not averaged into one label. α uses the fixed order (before, then after). The fraction of pairs whose reverse-order label differs is reported beside α.

## Best-of-k

Snell et al. show that extra samples at test time raise quality only when something can pick the better sample. Best-of-k is that bet: draw k patches, score them, keep one. If the selector is no better than chance, k=3 and k=5 spend more tokens and do not raise the resolve rate.

The selector here is the deterministic checks, then the judge only as a ranker among patches the checks already passed. The judge does not override a passed check run. Cost is about k times the fixer tokens for that bug. The quota cap is the point where more samples stop, until a measured curve says otherwise. That curve is not in this phase: the 30-task runs were not made.
